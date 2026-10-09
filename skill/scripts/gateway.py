#!/usr/bin/env python3
"""gateway.py — SMS 原生大模型网关（OpenAI 兼容·TUI 默认直连）：config llm_gateway{enabled,base_url,api_key,api_key_env,model}；对话/工具/视觉不依赖 agent CLI——run() 工具循环经 agent_dispatch 执行 exec·read·write·skill·ask·task·task_detail·user_send·thinking_chain 并回填（子进程 UTF-8 中文·附图 base64（>800KB 经可选 Pillow 缩为 JPEG）），首条恒为 SYS 系统提示词（批16 起 LLM 主导治理：简单问答可直答、动手才用工具·执行类经 skill 对等对话真跑（批23：每次派发独立 conv 独立链归属·对话间无主次·互任监视者·指导者·训诫者）＋查证红线·批18 主流程守卫：话语带〔任务表〕且仍有未完成行时禁止收口，注入续推提示让模型继续派发/改表，depth==0 才生效（派发对话内由收口返回后续推）；批20 空口守卫 flow_guard：免表单步任务以「现在开始写/Let me check」类纯文本收口且本轮无 write/skill/task 调用时同样注入续推（共用 task.max_continue 熔断），finish=length 截断致工具参数不完整即不执行并回分段 append 指引，且写回历史前经 flow_guard.clean_tool_calls 净化（半截 arguments 补全或降级 "{}"、空 tool_call_id 补稳定 id——防非法参数常驻历史致后续每轮网关 400）；批21 token 预算：发送前经 fg.budget 估算消息 tokens、大于 max_tokens 即在首条用户消息追加〔Token 预算〕块——脚本只测量、超限拆分由模型自决，finish=length 截断正文亦注入续推让模型分段续写；批22 模型裁量：〔任务表·脚本未建〕时建不建表由模型判（task_plan op=plan 自建）、动手诉求无相近技能→SYS 令先派 Skill_Generator 创建再执行；批23 会话拓扑：chains.conversation 注入〔会话拓扑〕块供各对话查看他 session 未完成/冲突并负监视训诫之责；批24 处理协议：SYS 尾令内部英语处理·输出译回用户语言，配合 prompt_builder 引导增强分段与精简语境语句）；输出区治理（批7②）：只有末轮（无 tool_calls）正文经 on_line 上主输出，工具轮 content/reasoning 与非流式思考全走 ◌ reasoning 信封进 F9/detail.json——思考混进 content 的上游同样不漏进主屏；工具输出与进度经 msg_flow 信封（on_line 人读行＋ev 结构化回调供顶栏 task 进度）；每次调用记 tool_call 链（挂当前 conv/sess 边）。批28：同错计数改用 solo.err_count（模块级跨调用存活·solo.retry_ttl_sec 过期自动清·拿到有效响应即 reset 清零），run 内不再有局部 same 字典。用法：python -B gateway.py ask|models|doctor "<文本>" [图片路径…]。"""
import os, sys, json, base64, urllib.request, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import resolve_home, chains, settings, msg_flow, agent_dispatch as ad, agent_ctx as ac, task_table as tt, latency, stop_channel as stop, flow_guard as fg, runtime_rec as rr, solo
import retry_io as rio
import urllib.error
import dsm
def _b64img(p):
    if os.path.getsize(p) > 800_000:
        try: from PIL import Image; import io as _io; im = Image.open(p); im.thumbnail((1568, 1568)); buf = _io.BytesIO(); im.convert("RGB").save(buf, "JPEG", quality=82); return "image/jpeg", base64.b64encode(buf.getvalue()).decode()
        except Exception: pass
    return ({".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}).get(os.path.splitext(p)[1].lower(), "image/png"), base64.b64encode(open(p, "rb").read()).decode()
def image_message(text, paths): return {"role": "user", "content": [{"type": "text", "text": text}] + [{"type": "image_url", "image_url": {"url": "data:" + m + ";base64," + d}} for m, d in (_b64img(p) for p in paths)]}
def cfg():
    """网关配置快照。密钥口径（批34 根治）：env（api_key_env 命名）优先，但**空值不覆盖配置密钥**——
    旧写法 os.environ.get(k, 默认) 只挡「变量不存在」，挡不住「变量存在但为空」：任何父进程/壳把
    SCNet-Max 带成空串，密钥即变 "Bearer " → 网关 401 invalid api key，SOLO 自审与对话全线哑火
    （2026-10-07/10-08 event 链实证「SOLO故障分析不可用：HTTP Error 401」）。回 key_source 供 doctor 说明密钥来处。"""
    c = dict(resolve_home.conf(resolve_home.ensure()).get("llm_gateway") or {})
    k = c.get("api_key_env"); v = (os.environ.get(k) or "").strip() if k else ""
    c["api_key"] = v or (c.get("api_key") or "")
    c["key_source"] = "env" if v else ("config" if c.get("api_key") else "none")
    return c
def enabled(): return bool(cfg().get("enabled"))
def _http(req):
    with urllib.request.urlopen(req, timeout=int(cfg().get("timeout", 120))) as r: return json.loads(r.read().decode("utf-8", "replace"))
def _ctxlen():
    """真实上下文窗口（model_meta 缓存＝上游标注或越界实测；取不到＝None 走旧口径）。"""
    try:
        import model_meta; return model_meta.context()
    except Exception: return None
def _send(req):
    """提供商（大模型网关）访问失败＝有限次重试：次数＝settings llm_gateway.retries（默认 3·指数退避 1.2s 起封顶 10s·HTTP 4xx 不重试·stop 即时中断），每次记 tool 链。耗尽回 (None, err)，err 带「重试耗尽(N次)」标记——run 见标记不再整轮重发（防重试次数相乘）。"""
    n = max(0, int(settings.get("llm_gateway.retries", 3)))
    def _t(e):
        """predicate 只在**真要重试**时留痕：旧写法每失败一次先记「提供商访问失败重试」再判瞬时性，
        401/404/405 这类不可重试错也被记成重试风暴，事后查链一律误判（批34 实测：401 被记 3 次）。"""
        ok = rio.transient(e)
        ok and chains.log("tool", "提供商访问失败重试（瞬时）：" + str(e)[:100]); return ok
    bx = {"i": 0}
    def _ot(i, k, e, d): bx["i"] = i; rr.rec("llm", attempt=i, retries=max(0, k - i), err=e)
    rr.rec("llm", attempt=0, retries=n)
    try:
        r = rio.call(_http, n, base=1.2, cap=10.0, retry_on=_t, on_try=_ot, args=(req,))
        rr.rec("llm", attempt=bx["i"], retries=max(0, n - bx["i"]), err=""); return r, ""
    except Exception as e:
        rr.rec("llm", attempt=max(1, bx["i"]), retries=0, err=e)
        try: d = e.read().decode("utf-8", "replace")[:300]
        except Exception: d = str(e)[:150]
        return None, str(e)[:150] + " " + d
def _req(path, body=None):
    c = cfg(); h = {"Authorization": "Bearer " + str(c.get("api_key", ""))}; d = None if body is None else json.dumps(body).encode("utf-8"); d is not None and h.update({"Content-Type": "application/json"}); return _send(urllib.request.Request(dsm.api_url(path, str(c.get("base_url", ""))), data=d, headers=h))
def _dsm_warn(text, on_line=None):
    """DSM 降级/异常一律留痕（契约：绝不静默）——tool 链一条＋主输出 notice 一行。"""
    chains.log("tool", "DSM warning: " + str(text)[:160])
    try:
        if callable(on_line): on_line(msg_flow.brief(msg_flow.make("notice", "DSM：" + str(text))))
    except Exception: pass


def _dsm_url(path, base=None):
    """DSM/legacy 端点 URL 的**唯一拼接口**＝dsm.api_url（尾巴2 的结构性根治）。

    旧写法只在 base 以 /v1 **结尾**时剥前缀；代理前缀形如 /api/v1 或 base 不含 /v1
    时仍会拼出 /v1/v1/…（服务端 404 → 客户端锁死降级 legacy，DSM 永远用不上）。
    dsm.api_url 改为守不变量「最终 URL 里 /v1 只出现一次」，两种 base 形都正确。"""
    return dsm.api_url(path, base if base is not None else str(cfg().get("base_url", "")))


def _dsm_post(path, body, accept=None, on_frame=None):
    """DSM 专用 POST（Content-Type/Accept＝application/dsm+json·契约 §1 内容协商）。
    与 _send 分开：需要保留 HTTP 状态码判 404/415 降级，_send 会把状态码压成字符串。

    `on_frame`＝ndjson 逐帧回调（out=delta 专用）：**逐行读、到一帧回调一帧**，
    不再 r.read() 整包缓冲。尾巴3 的另一半就在这里——整包读时首字延迟＝整轮延迟，
    增量协议在客户端被缓冲成了整包，于是「DSM 路不出逐字流」。"""
    c = cfg(); ct = dsm.CTYPE
    h = {"Authorization": "Bearer " + str(c.get("api_key", "")), "Content-Type": ct, "Accept": accept or ct}
    req = urllib.request.Request(_dsm_url(path, str(c.get("base_url", ""))),
                                 data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers=h)
    try:
        with urllib.request.urlopen(req, timeout=int(c.get("timeout", 120))) as r:
            ct = str(r.headers.get("content-type") or "")
            if dsm.CTYPE_STREAM in ct and on_frame is not None:
                # 真增量：迭代响应对象（urllib 的 response 本身是行迭代器）＝边到边解析
                rows = []
                for raw in r:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    rows.append(obj)
                    try:
                        on_frame(obj)
                    except Exception:
                        pass
                return (rows or None), "", 200, ct
            raw = r.read().decode("utf-8", "replace")
            if dsm.CTYPE_STREAM in ct:                       # out=delta：一 seq 一行的 ndjson
                rows = [json.loads(x) for x in raw.splitlines() if x.strip()]
                return (rows or None), "", 200, ct
            try:
                return json.loads(raw), "", 200, ct
            except Exception:                                # 服务端未按头声明也照 ndjson 收
                rows = [json.loads(x) for x in raw.splitlines() if x.strip()]
                return (rows or None), "", 200, ct
    except urllib.error.HTTPError as e:
        d = ""
        try: d = e.read().decode("utf-8", "replace")[:200]
        except Exception: pass
        return None, "HTTP %d %s" % (e.code, d), e.code, ""
    except Exception as e:
        return None, str(e)[:150], 0, ""


def _dsm_register(env, on_line=None):
    """sch 首帧登记（POST /v1/dsm/schema·幂等）：404/415＝服务端无 DSM 路由 → 需降级。"""
    data, err, code, _ct = _dsm_post(dsm.ENDPOINT_SCHEMA, dsm.schema_frame(env), dsm.CTYPE)
    if code in (404, 415): return "downgrade", err, code
    if code != 200:
        _dsm_warn("schema 登记未成功(%s)——继续按引用发送（服务端 require_registered_schema=false 时可正常 chat）：%s"
                  % (code, str(err)[:80]), on_line)
    else:
        dsm.mark_registered(env["sch"])
    return "ok", "", code


def _dsm_chat(msgs, on_line=None):
    """dsm.enabled=true 的信封路径：build_env → 首帧登记 → POST /v1/dsm/chat → decode_to_openai_shape。
    回 (message, note, kind)，kind∈ok|legacy|err——legacy 即调用方落回今天完全相同的路径。"""
    c = dsm.cfg()
    if dsm.broken():
        # 冷却期内不再试信封：直接走与今天逐字节相同的 legacy 路
        return None, "DSM 暂不可用（%s）→legacy" % dsm.broken_info()[1], "legacy"
    mem = None
    if c.get("mem_ref"):
        q = " ".join(str(m.get("content") or "") for m in msgs[-2:] if m.get("role") in ("user", "tool"))[:600]
        mem = dsm.mem_ids(q) or None
    try:
        env = dsm.build_env(msgs, tools=ad.tools_schema(), model=cfg().get("model") or "auto", dsm_cfg=c, mem=mem)
    except Exception as e:
        _dsm_warn("信封构造失败（语义装不下）→legacy：" + str(e)[:120], on_line); return None, str(e)[:150], "legacy"
    if c.get("schema_ref") and dsm.needs_register(env["sch"]):
        st, err, code = _dsm_register(env, on_line)
        if st == "downgrade":
            if c.get("fallback"):
                _dsm_warn("服务端 DSM schema 路由缺失(%d)→降级 legacy（dsm.fallback=true）" % code, on_line); dsm.mark_broken("schema route %d" % code); return None, err, "legacy"
            _dsm_warn("服务端 DSM schema 路由缺失(%d)且 dsm.fallback=false→报错不降级" % code, on_line); return None, err, "err"
    accept = dsm.CTYPE_STREAM if c.get("out") == "delta" else dsm.CTYPE
    data, err, code, _ct = _dsm_post(dsm.ENDPOINT, env, accept)
    if code in (404, 415):
        if c.get("fallback"):
            _dsm_warn("服务端未提供 DSM(%d)→降级 legacy（dsm.fallback=true）" % code, on_line); dsm.mark_broken("dsm chat %d" % code); return None, err, "legacy"
        _dsm_warn("服务端未提供 DSM(%d)且 dsm.fallback=false→报错不降级" % code, on_line); return None, err, "err"
    if code == 409:
        # 水位不符（服务端会话态与本侧对不上）：绝不带着同一个水位重试——那会 409 到底。
        # 丢掉本 conv 的水位、整段历史重发一次（resync），DSM 路就此恢复；再失败才降级。
        _dsm_warn("服务端 DSM 水位不符(409)→重置 delta 并全量重发一次", on_line)
        dsm.reset_delta((env.get("x") or {}).get("sms.delta_key") or "")
        try:
            env = dsm.build_env(msgs, tools=ad.tools_schema(), model=cfg().get("model") or "auto",
                                dsm_cfg=c, mem=mem, resync=True)
        except Exception as e:
            if c.get("fallback"):
                _dsm_warn("重同步信封构造失败→legacy：" + str(e)[:120], on_line); dsm.mark_broken("resync build_env"); return None, str(e)[:150], "legacy"
            return None, str(e)[:150], "err"
        if c.get("schema_ref") and dsm.needs_register(env["sch"]):
            _dsm_register(env, on_line)
        data, err, code, _ct = _dsm_post(dsm.ENDPOINT, env, accept)
        if code in (404, 415) and c.get("fallback"):
            _dsm_warn("服务端未提供 DSM(%d)→降级 legacy" % code, on_line); dsm.mark_broken("resync route %d" % code); return None, err, "legacy"
    if data is None:
        if code == 409 and c.get("fallback"):
            _dsm_warn("DSM 重同步仍失败(409)→降级 legacy 并冷却", on_line); dsm.mark_broken("409 resync failed"); return None, err, "legacy"
        return None, err, "err"
    o = dsm.decode_to_openai_shape(data)
    m = o["choices"][0]["message"]
    if not (m.get("tool_calls") or []) and not ((m.get("content") or "") + (m.get("reasoning_content") or "")).strip():
        # DSM 回 200 但信封是空的（上游只吐 reasoning 就被截断 / 服务端收口帧 answer=""）。
        # 绝不把空信封交给上层——那就是用户看到的「空响应」（2026-10-06 报障）。
        # 也不推进水位：空轮次写进 delta ⇒ 后续每轮都少一段历史。
        if c.get("fallback"):
            _dsm_warn("DSM 空信封（200 无正文/无工具调用）→legacy 全量重发一次", on_line)
            return None, "dsm empty envelope → legacy", "legacy"
        _dsm_warn("DSM 空信封且 dsm.fallback=false→报错不降级", on_line)
        return None, "DSM 空信封（200 无正文·fallback=false）", "err"
    dsm.clear_broken()
    dsm.commit_from_env(env, msgs)
    m["content"] = (m.get("content") or "").replace("\x00", "").replace("\r", "\n")
    m["reasoning_content"] = (m.get("reasoning_content") or "").replace("\x00", "")
    chains.log("tool", "gateway:dsm/" + str(o.get("model")))
    return m, "finish=" + str(o["choices"][0].get("finish_reason")), "ok"


def chat(msgs, on_line=None):
    if on_line is not None and settings.get("llm_gateway.stream", True): import gateway_sse as sse; return sse.stream(msgs, on_line)
    if dsm.enabled():
        m, note, kind = _dsm_chat(msgs, on_line)
        if kind == "ok": return m, note
        if kind == "err": return None, note
    if rf := dsm.legacy_refused(): return None, rf   # openai_compat=false → 拒绝构造 legacy body（loud）
    data, err = _req("/chat/completions", {"model": cfg().get("model") or "auto", "messages": msgs, "max_tokens": int(cfg().get("max_tokens", 1024)), "tools": ad.tools_schema(), **{k: cfg()[k] for k in ("temperature", "top_p", "reasoning_effort") if cfg().get(k) is not None}})
    if data: m = data["choices"][0]["message"]; m["content"] = (m.get("content") or "").replace("\x00", "").replace("\r", "\n"); m["reasoning_content"] = (m.get("reasoning_content") or "").replace("\x00", "")
    return (None, err) if not data else ((chains.log("tool", "gateway:" + str(data.get("model"))) and data)["choices"][0]["message"], "finish=" + str(data["choices"][0].get("finish_reason")))
SYS = "你是 smsystem-suit（SMS）数据流中的主导决策者：由你自主判断如何完成用户请求——纯知识问答/闲聊/解释可直接作答（简短·用户语言），不必先派子技能；需要本机事实（文件/配置/日志/网络）时用 read/grep/glob/ls/exec/webfetch 查证后再答，禁止编造；需要动手执行（写盘/派技能/调脚本）才用工具——执行类诉求经 skill 工具派发独立对等对话真执行（批23·对话无主次·互任监视者/指导者/训诫者·输出停止只是形式停止非实质完成；按注入的 SKILL.md 与脚本清单），禁止空口声称已执行、也不得越权直接写 skill 目录；动手诉求在技能表内无相近匹配且属新领域/需长期复用→先 skill 工具派 Skill_Generator 创建适配技能再派发执行，不得因「没找到技能」空手拒绝或临时拼凑代替；宣告动手必须在同一轮直接调用 write/exec/skill 落地，禁止只说一句「现在开始写/Let me check」就结束回合；单次 write 内容较长时分多段 append=true（每段≤600字）防 max_tokens 截断；话语带〔Token 预算〕块＝脚本估算输入已超单轮 max_tokens，凡预计单轮输出会超限的自行分段/拆多轮（拆分方案由你定），预计不超则忽略该块。可用工具：exec/read/write/skill/ask/ask_user/task/task_detail/task_plan/user_send/thinking_chain/chain/debate/glob/grep/ls/webfetch（webfetch 需 :grant network）。链＝省 token 的记忆介质（批17·相信大模型）：涉既往经验/历史决定先用 chain recall 查证再答，禁止只凭猜测；得出值得留存的结论、偏好、修法即用 chain append 写入 memory/knowledge/logic 链（收口链收口时自动落盘）；决策岔路先用 debate 铺正反双链自辩修正路径——人多在回路旁、机制自动修正，只有高危节点（:grant danger/云端下载/对外端口）才回人在回路征求确认。[SMS 路由] 注入只是打分参考提示，命中与否由你结合话语与索引自行决定派发或直答；多技能约束冲突时先派 constraint_arbiter 仲裁。话语带〔任务表〕时按表推进（批18·行数无上限）：脚本给的是粗分种子，首轮据实改表（task_plan add/remove/skill）到真实步数，每步完成必调 task_plan status <表id> <行id> done；批22·复杂由你判——话语带〔任务表·脚本未建〕或你自行判定请求是多步动手任务（≥2 执行步）时，别等用户列步骤或输「制表」，直接 task_plan op=plan value=你拆的各步骤（逗号分隔）建表再按表推进；纯问答/单步直接办、勿为表而表；子任务并发前提＝资源互斥（task_res.py）：行目标里声明 files=/dir=/reads=/port=/device=/skill=（未声明则按 goal 自动抽路径与端口），task_plan op=conflict 取「哪几行可并发、哪几行必须串行」（value=all 连其他在途表一起判＝多任务之间的子步骤并行），op=run 一次把互不冲突的行组成并发批次执行（批内≤task.batch_parallel·每行独立超时 task.row_timeout·失败隔离只标该行并写 error 链），或 task 工具（parallel=true）并发派发，有依赖则 parallel=false 或依序逐 skill 派发；同轮并行硬令：互不依赖的工具调用必须在同一条回复里一次性并行发起（exec/read/grep/glob/chain/task_plan 皆可并列），严禁「调一个→等结果→再调下一个」的串行浪费；多条本机检查合并为一次 exec（PowerShell 用 ; 串联），一次 exec 冷启约 0.8s——能合并就别拆；只有后一步真依赖前一步的输出时才另起一轮。找文件用 glob/ls、查内容用 grep，禁止 dir/find 反复试探。skill 工具返回若带「已实时显示·禁止复述」包装头，正文用户已看过、你只见首尾片段，最终回复严禁复述/引用/改写/摘要原文；派发对话收口＝形式停止而非实质完成，控制权回到你的对话继续调度：主任务＝整张任务表全部行 done，未完成前不得结束本对话——先查〔任务表〕未完成行并继续推进（续派 skill/task 或自办工具），全部完成后才以一句 ≤40 字收尾回报，禁止把单个派发完成当作整段任务结束、禁止反复宣告完成而不推进；SMS 主流程守卫会在任务表仍有未完成行时阻止收口并注入续推提示；需要技能结果里的数据继续干活时用 read/exec 读其产物文件；话语带〔会话拓扑〕＝其他 session 有未完成表或同技能跨会话冲突——你负监视/训诫之责：向用户说明冲突与先后（创建顺序），提示 :session use <id> 接续或 task_plan 收口，未经用户确认不越会话代改他人表。用户话语含问题/故障/报错/检查/为什么＝诊断请求：用工具实际排查（日志、doctor、链）后给结论，禁止回「输入 help/查配置表」式敷衍，也禁止拿压缩记忆里的旧用法文本充当答案；仅问 sms-shell 用法/配置入口时可指路 :help/:config/:cmds。问到 SMS 设置时用 exec 跑一次 `python -B " + os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.py") + " show`（或 status/get <dot路径>）读真实配置再作答；配置存 <SMS_HOME>\\config\\config.json，命令汇总 `commands.py help`。生成文件一律入工作区 tmp\\（env SMS_TMP）；目标为工作区文件的产物经用户审核后用 ws_release.py diff 预览、release --yes 收编（用户当轮确认＋:grant danger）。向用户的重要结论用 user_send；缺关键信息必须用户拍板才能继续时用 ask_user（阻塞等待用户屏幕应答，一次一问、问题简短，超时按合理假设继续）。〔SOLO 重试策略·批27〕SOLO 模式下重试次数无限但有硬条件：任何阻塞或错误发生后，你必须先做根因分析（错误签名、已试次数、是否同类重复），分析之后才决定是「修复」（换参数/换路径/换技能/拆步/降级）还是「重试」（同做法再来）；禁止未分析就原样重试或直接收口——同类错误重复出现即视为需要修复而非继续重试；无进展时系统按 solo.max_same_error 强制中止转人工。〔工具执行范式·批27〕read＝流式窗口读（先 grep 定位再按 offset 续读，禁止整读大文件，>2MB 取满窗口即早停）；grep/glob＝剪枝 .git/__pycache__/node_modules＋跳二进制＋命中即止/早停，禁止 dir/find 反复试探；exec＝sys_shells 统一入口，PowerShell 下 &&/2>nul/dir /b 由 tool_kit.adapt 自动改写并回说明，命令一次到位；webfetch＝gzip/charset 自适应＋HTML 抽正文（默认 as_text=true），拿原文才传 as_text=false。〔处理协议·批24〕内部处理（思考·工具参数·链写入·任务表步骤·草稿）一律用英语、语句精简；给用户的最终输出先以英语处理完成、再译回用户话语所用语言（跟随用户输入语言），简短直给。〔壳生命周期·批33〕用户说「关闭/重启 SMS」或任务确实需要重启＝exec 跑 `python -B shell_lifecycle.py request restart|shutdown 原因`（只登记一条请求），本对话收口时由壳自己执行：重启会拉起一个可见可输入的新终端窗口并回收旧实例与全部后台服务，关闭会把 HUD/网页壳/计划任务/监听器一并收干净。禁止自行乱杀进程、禁止把「关闭 SMS」理解成只关窗口而把后台留成常驻。"
def _sys():
    """系统提示词＝SYS＋SOLO 权限指令段（solo.enabled=false 时逐字等于 SYS·零回归）。"""
    try:
        import solo; n = solo.prompt_note()
    except Exception:
        n = ""
    return SYS + n
def run(text, on_line=lambda ln: None, images=None, ev=None, max_rounds=None):
    ad.bind(on_line=on_line, ev=ev if ev is not None else False); cap = int(settings.get("caps.gateway_rounds", 0) if max_rounds is None else max_rounds); n = 0; last = ""; idle = 0; acted = False; R = max(0, int(settings.get("llm_gateway.retries", 3))); left = R; msgs = [{"role": "system", "content": _sys()}, image_message(text, images) if images else {"role": "user", "content": text}]; msgs[-1] = fg.add_note(msgs[-1], fg.budget(msgs, int(cfg().get("max_tokens", 4096)), _ctxlen()))
    while True:
        stop.check(); n += 1
        if cap and n > cap: on_line("⚠ 工具循环达 %d 轮上限——强制收口返回（caps.gateway_rounds＝0 即无限·F4 图形配置可调）" % cap); return last or "（达轮次上限·无正文输出）"
        m, err = latency.wrap("llm", cfg().get("model") or "auto", chat, msgs, on_line); m, err = ((None, "空响应（上游 200 无正文·多为并发过载）") if m and not (m.get("tool_calls") or []) and not ((m.get("content") or "") + (m.get("reasoning_content") or "")).strip() else (m, err))
        if not m:
            cnt = solo.err_count(err); dec, d = solo.on_error(err, cnt)
            if dec == "legacy":
                if left > 0 and "重试耗尽" not in str(err): left -= 1; time.sleep(1.2 * (R - left)); on_line(msg_flow.brief(msg_flow.make("reasoning", "网关瞬时错误（" + str(err)[:80] + "）自动重试 " + str(R - left) + "/" + str(R) + "·stop 可中断"))); continue
                on_line("网关错误：" + str(err)[:150] + "（重试仍失败——本轮收口·未尽事项由接续注入下轮续跑）"); return last or None
            if dec == "abort": on_line("⚠ SOLO 分析判定中止（同错第 " + str(cnt) + " 次）：" + str((d or {}).get("reason"))[:120] + "（未尽事项由接续注入下轮续跑）"); return last or None
            left = R; time.sleep(min(solo.retry_cfg()["cap"], 1.2 * (2 ** min(cnt, 4))))
            if dec == "retry": on_line(msg_flow.brief(msg_flow.make("reasoning", "SOLO 分析→重试（第 " + str(cnt) + " 次·无限但有条件）：" + str(d.get("reason"))[:80]))); continue
            msgs.append({"role": "user", "content": "[SOLO 故障分析→修复] 根因：" + str(d.get("reason")) + chr(10) + "修复指令：" + (str(d.get("action")) or "换做法再试") + chr(10) + "按此调整做法后继续原任务——禁止原样重复同一调用、禁止就此收口。"}); on_line(msg_flow.brief(msg_flow.make("reasoning", "SOLO 分析→修复：" + str(d.get("reason"))[:80]))); continue
        solo.err_count(reset=True)
        if not (tcs := m.get("tool_calls") or []):
            r = m.get("reasoning_content") or ""; p = not m.get("printed"); p and r and on_line(msg_flow.brief(msg_flow.make("reasoning", r))); txt = m.get("content") or (r if p else ""); go = ac.cur()["depth"] == 0 and settings.get("task.auto_continue", True); pend = go and tt.pending(chains.ACTIVE.get("conv") or ""); prom = go and not pend and not acted and fg.promises(txt); cut = go and not pend and not prom and bool(txt) and "finish=length" == str(err).strip(); kind = "pend" if pend else "prom" if prom else "cut" if cut else ""
            if kind:
                (p and txt) and on_line(msg_flow.brief(msg_flow.make("reasoning", "（续推·主任务未完成）" + txt[:200]))); msgs.append(fg.clean_tool_calls(m)); idle += 1; mc = int(settings.get("task.max_continue", 5)); on_line(msg_flow.brief(msg_flow.make("notice", fg.notice(kind, idle))))
                if mc and idle > mc:
                    go2, d2 = solo.continue_gate(kind, idle, str(pend or ""))
                    if not go2: on_line(msg_flow.brief(msg_flow.make("notice", "⚠ 主流程续推达上限 task.max_continue·任务未收口·请用户介入或用 :task status 收口" + (("（SOLO 分析：" + str((d2 or {}).get("reason"))[:60] + "）") if d2 else "")))); return last or txt or None
                    if d2.get("decision") == "fix" and d2.get("action"): msgs.append({"role": "user", "content": "[SOLO 续推分析→修复] " + str(d2.get("reason")) + " → " + str(d2.get("action"))})
                    on_line(msg_flow.brief(msg_flow.make("notice", "SOLO 分析后继续推进（第 " + str(idle) + " 次·无限但有条件）")))
                msgs.append({"role": "user", "content": fg.inject(kind, pend)}); last = txt or last; continue
            txt and on_line(txt); return txt
        r = m.get("reasoning_content") or ""; c = "" if m.get("printed") else (m.get("content") or ""); (x := (r + (("过程·" + c) if c else ""))[:2000]) and on_line(msg_flow.brief(msg_flow.make("reasoning", x))); bad = fg.bad_args(tcs); msgs.append(fg.clean_tool_calls(m)); last = m.get("content") or last; idle = 0
        for k, tc in enumerate(tcs):
            f = tc.get("function") or {}; nm = str(f.get("name") or ""); raw = str(f.get("arguments") or "{}"); acted = acted or nm in ("write", "skill", "task"); res = fg.TRUNC if bad[k] else latency.wrap("tool", nm, ad.execute, nm, raw); stop.check(); msgs.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": str(res)[:4000] or "(无输出)"})
if __name__ == "__main__":
    a = sys.argv[1:] or ["doctor"]; cmd, arg, c = a[0], " ".join(a[1:]), cfg()
    if cmd == "doctor": print(json.dumps({"enabled": bool(c.get("enabled")), "base_url": c.get("base_url"), "model": c.get("model"), "key": "set" if c.get("api_key") else "missing", "key_source": cfg().get("key_source"), "env_var": c.get("api_key_env"), "env_empty": bool(c.get("api_key_env") and not (os.environ.get(c.get("api_key_env") or "") or "").strip())}, ensure_ascii=False))
    elif cmd == "models": data, err = _req("/models"); print("\n".join(x["id"] for x in (data or {}).get("data", [])) or "ERR " + err)
    else: run(arg or "你好", print, images=[p for p in a[1:] if os.path.isfile(p) and not p.startswith("-")] or None) if not cmd.startswith("-") else (print(__doc__.strip()), sys.exit(1))
