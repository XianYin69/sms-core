#!/usr/bin/env python3
"""solo.py — SOLO 模式唯一真源（权限免用户确认·缺权限时由大模型自审决定是否授予）：cfg/enabled/auto_pending/never/set/banner_lines/status/review/allow/gate/granted_today/notice；auto_pending＝SOLO 开且 solo.auto_pending（默认 true）时对「做梦修复待批」视同用户已同意，空闲自动续跑（dream_pending.auto_solo）；自审 danger 授予范围＝用户明确要求的 skill 目录改动，或用户明确要求的 git 写操作（commit/merge/push/branch 删除等·非强推非改写已推送历史）；review 经 gateway._req 非流式、不带 tools 的单次判定（批34：review 与 analyze 共用 gw_fail_cooldown_sec 冷却窗）（批34 加固：回复截断经 _salvage 抢救判定位、缺判定位仍保守拒绝；网关连续失败进 solo.gw_fail_cooldown_sec 冷却窗，窗内直接保守拒绝不再烧一次必然失败的请求）（prompt 含〔键/工具/目标/意图/本轮用户话语摘要/风险摘要〕，只回一行 JSON {"grant","ttl_min","reason"}），网关未启用/调用失败/不可解析/异常一律保守拒绝（绝不因审核失败放行）；allow 顺序＝已授予即真→SOLO 关即假→solo.never 键永不自审→danger 未开 solo.allow_danger 不自审→自审通过才 permissions.apply(grant, ttl 钳 max_ttl_min) 并落 audit（solo 标记）＋event 链；gate 回 (bool, note) 供工具层拼拒绝文案。红线：SOLO 只改「权限准入」，不绕 stop_channel/任务总览/审计，自审授予可 :grant revoke <键> 即时收回（注意 :grant <键> 0＝永久授予、非收回）；后台与非交互路径（auto_compress/cache_cleanup/dep_fetch/dream_*/deploy 等）不经本模块，防做梦链路阻塞与成本失控；SOLO 关闭＝行为与今天逐字一致。批28：err_sig＝分类前缀＋全串归一哈希签名（不截断头部，同错必同签、异错必不同签），err_count＝模块级跨调用同错计数（solo.retry_ttl_sec 默认 300s 过期自动清、成功一轮 reset 清零），修「同错熔断形同虚设＋跨轮计数清零」；批35（SOLO 失灵根治·四处）：① _ask 共用请求体——自审/分析带 chat_template_kwargs.enable_thinking=false 闭思考（solo.fast_think·默认 true；实测推理型上游开思考单次 13-25s 且无视 max_tokens，自审串在每次受门禁工具调用前＝卡顿主源），上游不认该参数（400）自动回退旧体一次＝绝不再被参数兼容问题打死；② _pos 正整数钳制——review_max_tokens/analyze_max_tokens 被写成 0/负不再触发上游 400（旧式 int() 无下限＝自审全灭一路保守拒绝），ttl 0 值回落 solo.ttl_min（旧写法 min(0,…)=0＝授予即过期、白烧一次审核）；③ _extra 口径——〔本轮话语〕为空/截断/带〔非本轮〕不再等同「用户没要求」（SMS 自身代码修复类 danger/git 写曾被反复误拒），分析器根因必须逐字来自错误详情、禁止编造详情里没有的参数名；④ _conv_tail_user——取不到 ACTIVE[conv] 时回落 shell/last_conv.json 最近 user 轮次。status 增 fast_think/review_max_tokens/analyze_max_tokens，check 钉死并回 review_latency_s。自检 python -B solo.py check。用法：python -B solo.py status|on|off|banner|review <key> [ctx]"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, settings, permissions, chains
SMS = resolve_home.ensure()
CORE_DIR = os.path.dirname(os.path.abspath(__file__))
NEVER = ("remote",)
RISK = ("无人确认：缺权限时不再询问用户，由大模型自审判定即执行",
        "自审可放行 skill 目录写入——仅 solo.allow_danger=true 时（红线16·默认 false 仍须当轮 :grant danger）",
        "solo.never 列内键（默认 remote）永不自审",
        "误判不可逆：授予即生效并可能被后续工具立即使用",
        "全部自审授予落 permissions.json audit（solo 标记）＋event 链，可追溯可收回",
        "随时关闭：:solo off 或 F4 改 solo.enabled=false；单项收回：:grant revoke <键>（:grant <键> 0＝永久授予非收回）")
def cfg(): return settings.get("solo") or {}
def enabled(): return bool(cfg().get("enabled"))
def auto_pending():
    """SOLO 下「自动同意修复待批」（配置 solo.auto_pending·默认 true）：开关开且 SOLO 开才为真。
    供 dream_repair.blocked 视同用户已同意、dream_pending.auto_solo 空闲时逐条续跑；SOLO 关＝恒假零回归。"""
    try: return bool(cfg().get("auto_pending", True) and enabled())
    except Exception: return False
def never(): return tuple(cfg().get("never") or NEVER)
def banner_lines(): return "\n".join("· " + x for x in RISK)
def prompt_note():
    """SOLO 权限指令段（批28·提示词唯一真源）：SOLO 开＝返回「权限免用户确认」硬指令；
    关＝空串（系统提示词与旧版逐字一致·零回归）。修「机制已通但提示词写死回人确认」——
    模型照提示词办事才反复找用户要 :grant／用 ask_user 要权限。"""
    if not enabled(): return ""
    c = cfg()
    return ("\n〔SOLO 权限自审·批28〕SOLO 已开启：权限准入由 solo.gate 自动自审并按 TTL 落账，"
            "**你不得再向用户要权限**——不得为权限调用 ask_user、不得让用户输入 :grant、"
            "不得在回复里征求授权；按用户诉求直接发起工具调用，缺权限时自审当场判定并放行/拒绝。"
            "被拒（自审拒绝或 never 键）＝换低风险做法或如实说明受阻，仍不得回头问用户要授权。"
            "禁止「先讨要 danger、用完 :grant revoke 收回」——收回令下次自审重来＝变相骚扰用户。"
            "唯一例外：solo.never 列内键（当前=" + "、".join(never()) + "）永不自审须用户当轮授予；"
            "skill 目录写与 git 写受 allow_danger=" + str(bool(c.get("allow_danger"))) + " 约束。"
            "ask_user 只用于任务内容本身缺关键信息（目标/偏好/取舍），绝不用于权限。")

def _pos(v, default):
    """正整数钳制（批35）：0/负/脏值回落默认，合法值原样。实测上游对 max_tokens<=0 直接回 400
    （{"error":{"message":"One or more request parameters are invalid","type":"upstream_error"}}），
    旧式 int(cfg 值) 无下限保护——solo.review_max_tokens 被写成 0 即自审全灭，每次受门禁的工具调用
    都保守拒绝＝用户看到的「SOLO 失灵」。ttl 同口径：0 值＝授予即过期，白烧一次审核。"""
    try: n = int(v)
    except Exception: return int(default)
    return n if n > 0 else int(default)


def _nothink():
    """自审/分析是否闭思考（solo.fast_think·默认 true）：实测推理型上游 SCNet-Max 开思考时
    usage.reasoning_tokens 400±、单次 13-25s 且无视 max_tokens 上限；带
    chat_template_kwargs.enable_thinking=false 后同题 1.2-3.8s、一行 JSON 判定不变。"""
    try: return bool(cfg().get("fast_think", True))
    except Exception: return True


def _ask(gc, sysp, usr, mt):
    """review/analyze 共用非流式单次请求：快体（闭思考）若被上游以 400 拒（不认该参数），回退旧体
    重发一次＝绝不再因参数兼容问题把自审/分析打死成「网关调用失败」（回退即旧行为逐字一致）。"""
    import gateway
    def body(fast):
        b = {"model": gc.get("model") or "auto",
             "messages": [{"role": "system", "content": sysp}, {"role": "user", "content": usr}],
             "max_tokens": int(mt), "temperature": 0}
        fast and b.update({"chat_template_kwargs": {"enable_thinking": False}})
        return b
    if _nothink():
        data, err = gateway._req("/chat/completions", body(True))
        if data or "400" not in str(err): return data, err
        try: chains.log("tool", "SOLO 闭思考体被上游拒（400）·回退旧体重发一次")
        except Exception: pass
    return gateway._req("/chat/completions", body(False))


def _extra(kind):
    """追加口径（批35·修两类高频误判，证据见 event 链「SOLO自审拒绝 key=danger」与两次互斥归因）。"""
    if kind == "analyze":
        return ("\n〔补充口径〕根因必须逐字来自〔错误/阻塞详情〕里出现的字段（HTTP 状态码＋error.message/type＋参数名），"
                "详情里没有的参数名一律不得写进 reason——禁止「temperature 已弃用」「max_tokens 非正数」这类猜测式归因；"
                "详情不足以定因时 decision=fix、action 只写「按详情原字段核对调用参数」。"
                "本机上游已知真因：400＝max_tokens<=0 或参数名不被接受；401＝api_key 为空串（env 空值已不遮蔽内联密钥）。")
    return ("\n〔补充口径〕〔本轮用户话语摘要〕为空、被截断或带〔非本轮〕前缀只说明上下文不完整，不等于用户没提要求："
            "判定以〔意图〕〔目标〕为准。若〔目标〕落在 SMS 自身代码/配置（solo、gateway、permissions、dream、链、壳层脚本等）"
            "且〔意图〕是修复/验证/回归该组件，即视为用户已明确要求该 skill 目录改动与相应本地 git 提交——按最小 TTL 授予，"
            "不得以「用户未明确要求改 skill 目录」「目标截断」为由拒绝；此口径不外延到与 SMS 修复无关的用户业务目录。")


def _conv_tail_user():
    """本轮话语兜底（批35）：chains.ACTIVE["conv"] 在独立子进程/新进程里为空 → dialogue 链按 conv 取不到
    本轮 → 旧版直落 user 链尾（仅偏好落盘时写）＝拿到数日前陈旧文本，据此判「本轮未明确要求」误拒。
    现回落 <SMS_HOME>/shell/last_conv.json（壳层每轮收口写·同 session 累积）最近一条 user 轮次——
    只读数据文件不引壳层件，保 core→shell 反向边＝0（sep_audit 口径：注释/文案也不得出现壳层模块名）。"""
    try:
        # 壳核分离红线：core 侧不得 import 壳层件，故直读壳层落的同一份接续缓存文件
        # （<SMS_HOME>/shell/last_conv.json·字段 conv/sess/ts/turns 与壳层写入端一致）
        import atomic_io
        d = atomic_io.rjson(os.path.join(SMS, "shell", "last_conv.json"), encoding="utf-8") or {}
        if not d or str(d.get("sess") or "") != str(chains.cur_sess() or ""): return ""
        for role, txt in reversed(list(d.get("turns") or [])):
            if role == "user" and str(txt or "").strip():
                return "〔本轮话语·壳接续缓存〕" + str(txt).strip()[:300]
        return ""
    except Exception: return ""


def set(on):
    """开关（写 config solo.enabled）：开启即回风险提示文案（供主输出窗口/菜单打印）。"""
    on = bool(on); settings.set("solo.enabled", on)
    return ("── SOLO 模式已开启 ──\n权限不再向用户确认，缺权限时由大模型自审决定是否授予。风险须知：\n" + banner_lines()) if on \
        else "SOLO 模式已关闭——权限准入回到用户确认（:grant），与未启用 SOLO 时逐字一致"
def _utter():
    """本轮用户话语摘要（批29 P1-03）：user 链只在偏好落盘时写、非逐轮写，旧版只取该链尾碎片——
    本轮话语未落链时拿到数日前陈旧文本，用户明确要求的操作被判「本轮未明确要求」而误拒 danger/git 写。
    现优先级＝① 当前 conv 在 dialogue 链的 user@ 记录（agent_stream 轮次开始即写全文）② user 链尾碎片
    （超 48h 标〔非本轮·链内旧文本〕供审核器折价）③ 全取不到＝空串，绝不因缺上下文阻断审核。"""
    try:
        c = chains.ACTIVE.get("conv") or ""
        if c:
            pre = "user@" + c; best = ""; bts = ""
            for f in chains.store().all_frags("dialogue"):
                t = str((f or {}).get("text") or "")
                if not t.startswith(pre): continue
                ts = str((f or {}).get("ts") or "")
                if ts >= bts: bts, best = ts, t[len(pre):].strip()
            if best: return best[:300]
        if not best:
            t = _conv_tail_user()
            if t: return t
        fs = [f for f in chains.store().all_frags("user") if (f or {}).get("text")]
        if not fs: return ""
        f = sorted(fs, key=lambda x: x.get("ts", ""))[-1]; txt = str(f.get("text") or "")[:300]
        try:
            stale = (time.time() - time.mktime(time.strptime(str(f.get("ts"))[:19], "%Y-%m-%dT%H:%M:%S"))) > 172800
        except Exception:
            stale = False
        return ("〔非本轮·链内旧文本〕" if stale else "") + txt
    except Exception: return ""
def _balanced(s, i):
    """自 s[i]=='{' 起按字符串态扫描配对花括号，回完整对象子串；未闭合回 None。"""
    d = 0; q = False; esc = False
    for j in range(i, len(s)):
        ch = s[j]
        if q:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': q = False
            continue
        if ch == '"': q = True
        elif ch == "{": d += 1
        elif ch == "}":
            d -= 1
            if d == 0: return s[i:j + 1]
    return None


def _salvage(s):
    """截断回复抢救（批34）：审核器/分析器偶发把 JSON 吐到一半（length 截断/多写解释）——
    旧实现整串 json.loads 失败即保守拒绝，用户看到的是「自审回复不可解析」而非真判定。
    只抢救**必填判定位**（grant 为布尔 / decision 为 retry|fix|abort），缺位仍回 None＝保守拒绝，
    绝不因抢救而放行。"""
    i = s.find("{"); t = s[i:] if i >= 0 else s
    g = _re.search(r'"grant"\s*:\s*(true|false)', t, _re.I)
    d = _re.search(r'"decision"\s*:\s*"?(retry|fix|abort)"?', t, _re.I)
    if not (g or d): return None
    out = {}
    if g: out["grant"] = (g.group(1).lower() == "true")
    if d: out["decision"] = d.group(1).lower()
    m = _re.search(r'"ttl_min"\s*:\s*(\d+)', t)
    m and out.update({"ttl_min": int(m.group(1))})
    for k in ("reason", "action"):
        m = _re.search('"' + k + '"' + r"\s*:\s*" + '"([^"]*)', t)
        m and out.update({k: m.group(1)})
    return out


def _jsonline(txt):
    """从回复里取第一个 JSON 对象（模型多话也容得下）：优先配对截取→整串兜底→截断抢救；
    三者都拿不到判定位＝None，上层保守拒绝（审核失败绝不放行）。"""
    s = str(txt or ""); i = s.find("{")
    if i < 0: return None
    seg = _balanced(s, i) or s[i:s.rfind("}") + 1]
    try: return json.loads(seg)
    except Exception: return _salvage(s)
_GW_FAIL = {}


def _cool(key="gw"):
    """网关失败冷却窗（秒·solo.gw_fail_cooldown_sec 默认 60）：同窗内不再重复发必然失败的自审请求。"""
    try: return float(cfg().get("gw_fail_cooldown_sec", 60) or 0)
    except Exception: return 60.0


def gw_cooling():
    """是否处于失败冷却中；到期自动放行（下一次真尝试）。"""
    t = _GW_FAIL.get("ts"); ok = bool(t) and (time.time() - t) < _cool()
    if not ok: _GW_FAIL.clear()
    return ok


def gw_fail_reset():
    _GW_FAIL.clear()


def gw_fail_note():
    return _GW_FAIL.get("err") or ""


def review(key, ctx=None):
    """LLM 自审：回 (grant, reason, ttl_min)。网关未启用/调用失败/不可解析/异常一律 (False, 原因, 0)——审核失败绝不放行。"""
    c = cfg(); ctx = ctx or {}
    try:
        import gateway
        if not gateway.enabled(): return False, "网关未启用（llm_gateway.enabled=false），无法自审", 0
        gc = gateway.cfg()
        sysp = ('你是 SMS SOLO 权限自审器：判断本次工具调用是否应授予权限键。只回一行 JSON：'
                '{"grant":true|false,"ttl_min":整数,"reason":"≤40字中文理由"}。原则：与本轮用户诉求直接相关且最小必要才授予；'
                '破坏性/不可逆/越权/与诉求无关/意图不明＝拒绝；danger 仅限用户明确要求的 skill 目录改动，'
                '〔工具〕为 dream_repair 且 SOLO 开（auto_pending）时，修复待批续跑＝用户已预先同意该 skill/脚本修复性改动，属可授予范围（给最小 TTL）；'
                '或用户明确要求的 git 写操作（commit/merge/push/branch 删除等·非强推、非改写已推送历史）；never 列内键不得授予。'
                'never 列内是 SMS 权限键名（remote＝远程会话越权执行元指令的键），'
                '与 git remote、网络推送、GitHub 无关；用户明确要求的 git commit/merge/push '
                '不得以 remote 键为由拒绝。' + _extra("review"))
        usr = "\n".join(["〔键〕" + str(key), "〔工具〕" + str(ctx.get("tool") or "-"),
                         "〔目标〕" + str(ctx.get("path") or ctx.get("url") or ctx.get("target") or "-"),
                         "〔意图〕" + str(ctx.get("intent") or "-"),
                         "〔本轮用户话语摘要〕" + (_utter() or "-"),
                         "〔风险摘要〕" + banner_lines().replace("\n", "；"),
                         "〔永不自审权限键（非 git remote）〕" + "、".join(never()),
                         "〔allow_danger〕" + str(bool(c.get("allow_danger"))), "〔已授予键〕" + "、".join(sorted(k for k in permissions.KEYS if permissions.allow_base(SMS, k)))])
        if gw_cooling():   # 网关刚失败过＝不重复烧一次必然 401/5xx 的请求，直接保守拒绝并给出来处
            return False, "网关不可用冷却中（上次失败：" + str(gw_fail_note())[:60] + "）", 0
        data, err = _ask(gc, sysp, usr, _pos(c.get("review_max_tokens", 200), 200))
        if not data:
            _GW_FAIL.update({"ts": time.time(), "err": str(err)[:160], "sig": err_sig(err)})
            chains.record("event", "SOLO自审网关失败：%s" % str(err)[:90])
            return False, "自审网关调用失败：" + str(err)[:80], 0
        gw_fail_reset()
        txt = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        j = _jsonline(txt)
        if not isinstance(j, dict) or not isinstance(j.get("grant"), bool):
            return False, "自审回复不可解析（须 JSON·grant 为布尔）：" + str(txt)[:60], 0
        return bool(j["grant"]), str(j.get("reason") or "（未给理由）")[:120], int(j.get("ttl_min") or 0)
    except Exception as e: return False, "自审异常：" + str(e)[:100], 0
def _mark(sms, key, reason):
    """给本次自审授予的 audit 末条打 solo 标记与理由（审计可追溯·失败不影响授予结果）。"""
    try:
        import atomic_io
        p = permissions._path(sms); d = permissions._doc(p, sms)
        for a in reversed(d.get("audit") or []):
            if a.get("action") == "grant" and a.get("key") == key: a["solo"] = True; a["reason"] = reason; break
        atomic_io.wjson(p, d); return True
    except Exception: return False
def notice(text):
    """主输出窗口通报一行（SOLO 自审放行/拒绝上屏）：solo.notify=false 即静默；惰性 import agent_ctx/msg_flow
    防循环依赖，信封机制同 agent_tools.emit（kind=notice＝msg_flow CLASS body，主输出可见）；全程 try/except，
    异常只回 False——绝不影响权限判定与工具执行。"""
    if not cfg().get("notify", True): return False
    try:
        import agent_ctx, msg_flow
        c = agent_ctx.cur()
        e = msg_flow.make("notice", str(text), conv=c.get("conv") or chains.ACTIVE["conv"],
                          sess=chains.cur_sess(), tool="solo", ok=True)
        if callable(c.get("ev")): c["ev"](e)
        ln = c.get("on_line")
        if ln: ln(msg_flow.brief(e))
        return True
    except Exception: return False
def _decide(sms, key, ctx=None):
    """自审决策核心（allow/gate 共用·一次判定一次落账）：回 (grant, reason)。never 键与未开 allow_danger 的 danger 不送审；
    审核通过即 permissions.apply(grant, ttl 钳 max_ttl_min)＋audit 打 solo 标记＋event 链，可 :grant revoke <键> 收回。"""
    if str(key) in never(): return False, "键 %s 在 solo.never 列内永不自审" % key
    if str(key) == "danger" and not cfg().get("allow_danger"): return False, "danger 不随自审（须 solo.allow_danger=true 或当轮 :grant danger）"
    g, why, ttl = review(key, ctx)
    if not g:
        chains.record("event", "SOLO自审拒绝 key=%s 理由=%s" % (key, why)); notice("SOLO 自审拒绝 %s：%s" % (key, why)); return False, why
    c = cfg(); t2 = min(_pos(ttl, _pos(c.get("ttl_min", 30), 30)), _pos(c.get("max_ttl_min", 120), 120))
    permissions.apply(sms, "grant", str(key), False, t2); _mark(sms, str(key), why)
    chains.record("event", "SOLO自审授予 key=%s ttl=%d分钟 理由=%s" % (key, t2, why)); notice("SOLO 自审放行 %s（ttl=%d分钟）：%s" % (key, t2, why)); return True, why
def allow(sms, key, id=None, ctx=None):
    """准入判定（布尔版）：已授予即真；SOLO 关即假；否则走自审（通过即落授予）。"""
    if permissions.allow_base(sms, key, id): return True
    if not enabled(): return False
    return _decide(sms, key, ctx)[0]
def gate(sms, key, ctx=None):
    """(是否放行, 说明)：SOLO 关＝(False,「需 :grant <key>」) 与今天逐字一致；SOLO 开＝拒绝原因给到用户可见。"""
    if permissions.allow_base(sms, key, (ctx or {}).get("id")): return True, ""
    if not enabled(): return False, "需 :grant " + str(key)
    g, why = _decide(sms, key, ctx); return (True, "") if g else (False, "SOLO 自审判定不予授予：" + why)
def tail(note):
    """拒绝文案尾部拼接：SOLO 关（note＝原文案「需 :grant ..」）＝空串保零回归；SOLO 开＝拼「（SOLO 自审：..）」，
    理由自带全角括号时改用〔〕包裹，避免括号套括号影响可读性。"""
    if not note or note.startswith("需 :grant"): return ""
    o, c = ("〔", "〕") if "（" in note else ("（", "）")
    return o + note + c
def granted_today(sms=None):
    """今日 SOLO 自审授予条数（permissions.json audit 中带 solo 标记者）。"""
    try:
        d = permissions._doc(permissions._path(sms or SMS), sms or SMS)
        return sum(1 for a in (d.get("audit") or []) if a.get("action") == "grant" and a.get("solo"))
    except Exception: return 0

def _gw_ok():
    try:
        import gateway; return bool(gateway.enabled())
    except Exception: return False


def _key_source():
    """密钥来处（env/config/none）——SOLO 自审依赖网关鉴权，401 时先让 doctor 看得见是哪一头空。"""
    try:
        import gateway; return gateway.cfg().get("key_source") or "?"
    except Exception: return "?"


def _env_empty():
    """配了 api_key_env 但环境变量为空/缺失＝401 高危信号（配置密钥仍会兜底，但来处已偏离预期）。"""
    try:
        import gateway
        c = gateway.cfg(); k = c.get("api_key_env")
        return bool(k) and not (os.environ.get(k) or "").strip()
    except Exception: return False
# ---- 批27 SOLO 故障分析（用户：SOLO 下重试无限但有条件——阻塞/错误后大模型必须先分析，分析后才决定修复还是重试）
import re as _re, hashlib as _hashlib
def analyze_on():
    """分析闸：SOLO 开＋solo.analyze_retry＋非后台非交互（做梦/压缩等无人应答链路不入此路）。"""
    try: return bool(enabled() and cfg().get("analyze_retry", True) and not permissions._NONINTERACTIVE[0])
    except Exception: return False
def retry_cfg():
    c = cfg(); return {"max_same": int(c.get("max_same_error", 5)), "cap": float(c.get("retry_backoff_cap", 30.0))}
_VOL_UUID = _re.compile(r"\b[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b")
_VOL_HEX = _re.compile(r"\b[0-9a-fA-F]{8,}\b")
_VOL_Q = _re.compile(r'(["\'])(.{40,}?)\1', _re.S)
_CLS = _re.compile(r"\b([A-Za-z0-9_]*(?:Error|Exception|Timeout|Failure))\b")
_CODE = (_re.compile(r"HTTP Error (\d{3})"), _re.compile(r"Error code:?\s*(\d{3})"),
         _re.compile(r'"(?:code|status)"\s*:\s*"?(\d{3})'))
_ETYPE = _re.compile(r'"(?:type|error_code)"\s*:\s*"?([A-Za-z][A-Za-z0-9_.\-]{2,})')


def _norm_err(s):
    """全串易变归一（不截断头部）：uuid/长十六进制→H、引号内长文本只留前 40 字、数字→N、空白折叠。"""
    s = _VOL_UUID.sub("H", s)
    s = _VOL_HEX.sub("H", s)
    s = _VOL_Q.sub(lambda m: m.group(1) + m.group(2)[:40] + m.group(1), s)
    s = _re.sub(r"\d+", "N", s)
    return _re.sub(r"\s+", " ", s).strip()


def _classify(s):
    """分类前缀＝异常类名 + 状态码（HTTP Error NNN / Error code: NNN / JSON "code"），
    抽不到码退 JSON error.type 字符串；前缀只增辨识度，判同仍靠全串哈希。"""
    m = _CLS.search(s)
    cls = m.group(1) if m else ""
    code = ""
    for rx in _CODE:
        mm = rx.search(s)
        if mm:
            code = mm.group(1)
            break
    if not code:
        mm = _ETYPE.search(s)
        code = mm.group(1) if mm else ""
    return cls, code


def err_sig(err):
    """批28 签名＝分类前缀 + 完整串归一哈希（sha1[:12]）。旧实现先归一数字再截断 160 字符：长错误
    （gateway._send 回 str(e)[:150]+" "+body[:300]）尾部差异被截掉致异错塌缩同签，易变量落在保留区
    又致同错签名漂移——same 恒为 1 令 solo.max_same_error 熔断形同虚设。现不截断，同错必同签。"""
    s = str(err or "")
    cls, code = _classify(s)
    # 大小写不参与身份（同一错误的措辞大小写漂移＝异签＝同错熔断永不触发）
    h = _hashlib.sha1(_norm_err(s).lower().encode("utf-8", "replace")).hexdigest()[:12]
    return ":".join([x for x in (cls, code) if x] + [h])


_SIG_COUNT = {}


def _ttl():
    """同错计数存活秒数（solo.retry_ttl_sec·默认 300）：超时自动过期，防陈旧计数误熔断。"""
    try:
        return float(cfg().get("retry_ttl_sec", 300) or 300)
    except Exception:
        return 300.0


def err_count(err=None, reset=False):
    """跨调用同错计数（批28·模块级存活）：gateway.run 旧版局部 same 每次调用即清零，400 投毒每轮
    只计到 1＝无限烧 token。reset=True（拿到有效响应/成功一轮）＝全清；err=None 且非 reset＝回快照；
    否则按 err_sig 累计并回本次次数（超 TTL 则从 1 重计）。solo.on_error 入参语义不变。"""
    now = time.time()
    if reset:
        _SIG_COUNT.clear()
        return 0
    if err is None:
        return dict((k, v[0]) for k, v in _SIG_COUNT.items())
    sg = err_sig(err)
    prev = _SIG_COUNT.get(sg)
    n = (prev[0] if prev and now - prev[1] <= _ttl() else 0) + 1
    _SIG_COUNT[sg] = (n, now)
    return n


def reset_sig():
    """清空同错计数（成功一轮的显式入口·等价 err_count(reset=True)）。"""
    return err_count(reset=True)
def _ajson(txt):
    """故障分析回复解析＝与 review 同一容错口径（配对截取＋截断抢救）。"""
    return _jsonline(txt)

def analyze(kind, detail, ctx=None):
    """故障分析器（非流式单次·不带 tools）：回 {"decision":"retry|fix|abort","reason","action"}；
    网关未启用/调用失败/不可解析/异常＝None——上层据此回退旧的有限重试，绝不因分析失败而盲目放行或死循环。"""
    c = cfg(); ctx = ctx or {}
    try:
        import gateway
        if not gateway.enabled(): return None
        gc = gateway.cfg()
        sysp = ("你是 SMS SOLO 故障分析器：对刚发生的阻塞/错误先做根因分析，再决定下一步。只回一行 JSON："
                '{"decision":"retry|fix|abort","reason":"≤40字根因","action":"≤80字给主模型的修复指令（retry 时可空）"}。'
                "原则：必须先分析后决定，禁止未分析就原样重试。瞬时性（网络抖动/超时/429/5xx/空响应）且首次出现＝retry；"
                "同类错误重复出现＝不得原样重试，必须 fix（换参数/换路径/换技能/拆步/降级）；权限缺失＝fix（先申请或改走不需该权限的路）；"
                "不可恢复（认证失败/内容安全/目标不存在且无法创建/诉求本身矛盾）＝abort。" + _extra("analyze"))
        usr = "\n".join(["〔类别〕" + str(kind), "〔错误/阻塞详情〕" + str(detail)[:600],
                         "〔同签名连续次数〕" + str(ctx.get("same", 1)), "〔连续续推次数〕" + str(ctx.get("idle", 0)),
                         "〔任务总览未完成〕" + str(ctx.get("pend") or "-")[:600],
                         "〔本轮用户话语摘要〕" + (_utter() or "-")])
        if gw_cooling():   # 网关不可用冷却中＝不再发必然失败的分析请求（旧行为每错一轮白烧一次）
            chains.record("event", "SOLO故障分析跳过（网关冷却中）：" + str(gw_fail_note())[:60]); return None
        data, err = _ask(gc, sysp, usr, _pos(c.get("analyze_max_tokens", 300), 300))
        if not data:
            _GW_FAIL.update({"ts": time.time(), "err": str(err)[:160], "sig": err_sig(err)})
            chains.record("event", "SOLO故障分析不可用：" + str(err)[:80]); return None
        gw_fail_reset()
        j = _ajson(((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
        if not isinstance(j, dict) or str(j.get("decision")) not in ("retry", "fix", "abort"):
            chains.record("event", "SOLO故障分析回复不可解析：" + str(j)[:60]); return None
        out = {"decision": str(j["decision"]), "reason": str(j.get("reason") or "")[:160],
               "action": str(j.get("action") or "")[:300]}
        chains.record("event", "SOLO故障分析 %s→%s：%s" % (kind, out["decision"], out["reason"]))
        notice("SOLO 分析（%s）→ %s：%s" % (kind, out["decision"], out["reason"]))
        return out
    except Exception as e:
        chains.record("event", "SOLO故障分析异常：" + str(e)[:100]); return None

def on_error(err, same, kind="llm"):
    """run() 错误口决策（批27）：分析闸未开＝("legacy", None) 与旧行为逐字一致；开＝先分析后决定
    ("retry",d)/("fix",d)/("abort",d)。硬条件：同签名连续超 solo.max_same_error 直接 abort——
    「无限重试」的边界是「有进展」，无进展即停，防死循环烧钱。"""
    try:
        if not analyze_on(): return "legacy", None
        if same > retry_cfg()["max_same"]:
            return "abort", {"decision": "abort", "reason": "同类错误已连续第 %d 次（solo.max_same_error=%d）·分析后仍无进展" % (same, retry_cfg()["max_same"]), "action": ""}
        d = analyze(kind, err, {"same": same})
        if not d: return "legacy", None
        return (d["decision"], d)
    except Exception: return "legacy", None
def continue_gate(kind, idle, pend=""):
    """主流程守卫熔断的 SOLO 分支：闸未开＝(False,None) 上层按旧 task.max_continue 收口；
    开＝分析后决定继续（retry/fix 带修复指令注入）或中止。回 (是否继续, d)。"""
    try:
        if not analyze_on(): return False, None
        d = analyze("stall", "主流程守卫连续续推第 %d 次（kind=%s）仍未收口" % (idle, kind), {"idle": idle, "same": idle, "pend": pend})
        if not d or d["decision"] == "abort": return False, d
        return True, d
    except Exception: return False, None
def status(sms=None):
    sms = sms or SMS; c = cfg()
    return {"enabled": bool(c.get("enabled")), "allow_danger": bool(c.get("allow_danger")),
            "auto_pending": auto_pending(), "never": list(never()),
            "ttl_min": int(c.get("ttl_min", 30)), "max_ttl_min": int(c.get("max_ttl_min", 120)),
            "notify": bool(c.get("notify", True)), "gateway_ok": _gw_ok(), "granted_today": granted_today(sms),
            "review_cooling": gw_cooling(), "review_cool_err": str(gw_fail_note())[:90],
            "gw_fail_cooldown_sec": _cool(), "key_source": _key_source(), "env_empty": _env_empty(),
            "fast_think": _nothink(), "review_max_tokens": _pos(c.get("review_max_tokens", 200), 200),
            "analyze_max_tokens": _pos(c.get("analyze_max_tokens", 300), 300)}
if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]; k = a[0]
    if k == "on": print(set(True))
    elif k == "off": print(set(False))
    elif k == "banner": print(banner_lines())
    elif k == "review":
        g, why, ttl = review(a[1] if len(a) > 1 else "write", {"tool": "cli", "target": " ".join(a[2:]) or "-"})
        print(json.dumps({"grant": g, "reason": why, "ttl_min": ttl}, ensure_ascii=False))
    elif k == "check":
        e4 = ('HTTP Error 400: Bad Request {"error": {"message": "This model maximum context length '
              'is 8192 tokens, however you requested 9000 tokens (index=17, offset=4201)", "type": '
              '"invalid_request_error"}, "id": "chatcmpl-1a2b3c4d5e6f7a8b9c0d"}')
        mx = retry_cfg()["max_same"]; reps = max(6, mx + 1)
        sigs = [err_sig(e4) for _ in range(reps)]
        uniq = list(dict.fromkeys(sigs))
        assert len(uniq) == 1, "同错签名漂移：%s" % uniq
        ns = [err_count(e4) for _ in range(reps)]
        assert ns == list(range(1, reps + 1)), "计数未递增：%s" % ns
        assert ns[-1] > mx, "未达熔断阈值：%s>%s" % (ns[-1], mx)
        assert _pos(0, 200) == 200 and _pos(-5, 200) == 200 and _pos("x", 200) == 200 and _pos(500, 200) == 500, "预算下限钳制失效"
        assert _pos(0, 30) == 30, "ttl 0 值未回落（授予即过期）"
        _k = "SMS_SOLO_PROBE_KEY_" + str(os.getpid())
        try:
            os.environ[_k] = ""
            assert (os.environ.get(_k) or "inline-secret") == "inline-secret", "空 env 遮蔽内联密钥（401 根因）"
            os.environ[_k] = " env-secret "
            assert (os.environ.get(_k) or "").strip() == "env-secret", "env 密钥口径失效"
        finally: os.environ.pop(_k, None)
        import gateway as _gw; _gcf = _gw.cfg()
        assert _gcf.get("key_source") in ("env", "config", "none"), "doctor 缺 key_source 口径"
        assert not ((_gcf.get("api_key") or "") and _gcf.get("key_source") == "none"), "有内联密钥却报 none"
        assert "SMS 自身代码" in _extra("review"), "审核补充口径丢失"
        assert "猜测式归因" in _extra("analyze"), "分析补充口径丢失"
        _lat = None
        if enabled() and _gw_ok():
            _t0 = time.time()
            review("write", {"tool": "check", "target": os.path.join(CORE_DIR, "solo.py"), "intent": "SOLO 自检探针·非真实改动"})
            _lat = round(time.time() - _t0, 1); gw_fail_reset()
        s401 = err_sig(e4.replace("400", "401"))
        soth = err_sig(e4.replace("maximum context", "content policy"))
        assert s401 != sigs[0], "400/401 塌缩同签"
        assert soth != sigs[0], "同码异文塌缩同签"
        assert err_count(reset=True) == 0 and err_count(e4) == 1, "reset 未清零"
        _SIG_COUNT[sigs[0]] = (9, time.time() - _ttl() - 1)
        assert err_count(e4) == 1, "TTL 未过期"
        err_count(reset=True)
        # 批34：截断回复必须抢救出判定位；缺判定位仍保守拒绝；网关失败冷却窗只发一次请求
        j1 = _jsonline('{"grant": true, "ttl_min": 3, "reason": "用户明确要求修 SOLO，最小')
        assert isinstance(j1, dict) and j1.get("grant") is True and j1.get("ttl_min") == 3, "截断抢救失灵：%s" % j1
        assert _jsonline('抱歉，我需要更多信息') is None, "无判定位却解析成功＝危险放行路径"
        assert err_sig("HTTP Error 401: Unauthorized invalid api key") == \
            err_sig("HTTP Error 401: UNAUTHORIZED Invalid API Key"), "401 大小写漂移致异签（熔断失真）"
        _g = {"n": 0}
        def _fail(path, body=None):
            _g["n"] += 1; return None, "HTTP Error 401: Unauthorized invalid api key"
        import gateway as _gw; _real = _gw._req; _gw._req = _fail
        try:
            gw_fail_reset(); review("danger", {"tool": "write", "path": "x"}); review("danger", {"tool": "write", "path": "x"})
            assert _g["n"] == 1 and gw_cooling(), "网关失败冷却窗未生效（白烧 %d 次）" % _g["n"]
            _GW_FAIL["ts"] -= _cool() + 1; review("danger", {"tool": "write", "path": "x"})
            assert _g["n"] == 2, "冷却过期未恢复尝试"
        finally:
            _gw._req = _real; gw_fail_reset()
        print(json.dumps({"check": "pass", "sig": sigs[0], "counts": ns, "max_same": mx,
                          "review_latency_s": _lat, "fast_think": _nothink(),
                          "ttl_sec": _ttl(), "sig_401": s401, "sig_other": soth},
                         ensure_ascii=False, indent=2))
    elif k == "allow":
        print(json.dumps({"allow": allow(SMS, a[1] if len(a) > 1 else "write", ctx={"tool": "cli", "target": " ".join(a[2:]) or "-"}), "status": status()}, ensure_ascii=False))
    else: print(json.dumps(status(), ensure_ascii=False, indent=2))
