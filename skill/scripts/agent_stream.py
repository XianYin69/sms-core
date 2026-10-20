#!/usr/bin/env python3
"""agent_stream.py — sms-shell 数据流引擎（批16 LLM 主导）：默认直达系统原生网关（config llm_gateway.enabled→gateway），网关未启用才回退已装 agent CLI；每次输入＝开新对话（红线 17），会话层 chains.set_active(conv/sess)＋session/dialogue 碎片打 member→sess 边；工作区＝gateway exec 与 agent CLI 的 cwd；技能路由不再脚本裁决——skill_route 打分命中仅作〔参考〕注入（记 skill_call 链供审计），直答还是派发由模型在 gateway 工具循环内自主决定（批15 前「命中即自动开子会话扇出」已废除）；未命中→chains.conversation 压缩记忆＋对话规则（批23 对等对话·互任监视/指导/训诫）＋〔会话拓扑〕（他 session 未完成/冲突监视提示）＋SKILL.md 索引＋治理注入送网关；话语/工具/技能/任务输出全程 msg_flow 信封（on_line 人读行＋ev 回调供 TUI 顶栏进度）；各阶段步骤名经 st 回调上报；尾行 [图:<路径>] 为网关视觉附图；状态存 <SMS_HOME>/shell/；皆无执行器则拒绝并引导配置（未检出执行器时不得空口作答）。"""
import no_window  # 静默子进程：前台运行任务不弹命令行窗口
import os, sys, shutil, subprocess, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, chains, dream, qq_flow, qq_boot, gateway, model_meta, tts, skill_route, prompt_builder, prompt_pack, workspace as ws, agent_tools as at, shell_resume as sr, stop_channel as stop, agent_task as atk, task_table as tt, chain_timing as ct, shell_lifecycle as lc, run_watch as rw, ctx_compress
SMS = resolve_home.ensure(); STATE = os.path.join(SMS, "shell")
ADAPTERS = {"claude": {"bin": "claude", "args": ["-p"]}, "codex": {"bin": "codex", "args": ["exec"]}, "cursor": {"bin": "cursor-agent", "args": []}, "kilocode": {"bin": "kilocode", "args": ["run"]}, "kilo": {"bin": "kilo", "args": ["run"]}, "aider": {"bin": "aider", "args": ["--message"]}}
def adapters():
    extra = {k: v for k, v in (resolve_home.conf(SMS).get("agent_cli") or {}).items() if not k.startswith("_") and isinstance(v, dict)}
    return dict(ADAPTERS, **extra, **({"gateway": {"native": True}} if gateway.enabled() else {}))
def detected(): return {k: v for k, v in sorted(adapters().items()) if v.get("native") or shutil.which(v.get("bin", k))}
def _state(n, d=""):
    try: return open(os.path.join(STATE, n), encoding="utf-8").read().strip()
    except Exception: return d
def _put(n, v): os.makedirs(STATE, exist_ok=True); open(os.path.join(STATE, n), "w", encoding="utf-8").write(v)
def current():
    det = detected(); cur = _state("current_agent")
    return next((k for k, v in det.items() if v.get("native")), cur if cur in det else next(iter(det), None))
def prefix_on(): return _state("skill_prefix", "on") != "off"
def use(name): _put("current_agent", name); return "切到 agent：" + name + ("" if name in detected() else "（未检出其 CLI——配置 agent_cli {bin,args} 并确保在 PATH）")
def skill(on): _put("skill_prefix", "on" if on else "off"); return "smsystem-suit 前缀：" + _state("skill_prefix", "on")
def _extract_operation_keywords(resp):
    """从第一阶段理解回复中提取操作关键词（技能/工具/记忆）。"""
    if not resp: return ""
    kws = set()
    for m in re.finditer(r"(?:关键词|关键字|技能|工具|记忆|需要|涉及|操作)[：:]\s*([^。；\n]+)", str(resp)):
        seg = m.group(1)
        for w in re.split(r"[，,、/、\s+]", seg):
            w = w.strip()
            if len(w) >= 2: kws.add(w)
    if not kws:
        for w in re.findall(r"[a-zA-Z][a-zA-Z0-9_\-]{2,}|\u4e00-\u9fff{2,}", str(resp)):
            if len(w) >= 2: kws.add(w)
    return " ".join(sorted(kws))[:300]
def _inject_skill_summaries(keywords, sms):
    """基于关键词注入相关技能摘要（不注入全表，仅命中项）。"""
    if not keywords: return ""
    try:
        ranked, thr = skill_route._rank(keywords, sms)
        hs = [s for sc, s in ranked if sc >= thr][:3]
        if not hs: return ""
        lines = []
        for s in hs:
            sid = str(s.get("id", ""))
            desc = re.sub(r"\s+", "", str(s.get("description", "")))[:80]
            ip = str(s.get("install_path", "")); en = str(s.get("entry", "SKILL.md"))
            lines.append("%s：%s（%s）" % (sid, desc, os.path.join(ip, en)))
        return "\n".join(lines)
    except Exception:
        return ""
def compose(text, sms=None): return prompt_builder.build(text, sms or SMS) + "\n\n" + prompt_builder.init(sms or SMS)
def _edge(conv): return [[conv, "ref", 1], [chains.cur_sess(), "member", 1]]
def _consume(on_line):
    """批32 R1/R3/R5：本轮收口处消费大模型经 exec 登记的 restart/shutdown——壳内硬退（os._exit）前
    必须先出一行提示（on_line 交回 shell_lifecycle），异常绝不静默吞：记 error 链＋一行用户提示，
    请求文件由 shell_lifecycle 保留不删。"""
    try:
        r = lc.run_pending(sms=SMS, on_line=on_line)
        if isinstance(r, str) and "待壳执行" in r:
            on_line(r)  # R2：非壳宿主无执行者——明确串送会话输出（绝不与「无待办」混同·文件保留）
        return r
    except Exception as e:
        try:
            import chain_error
            chain_error.record("shell", "agent_stream.run_pending", str(e)[:160])
        except Exception as e2:
            on_line("!lifecycle▸ 消费登记请求异常且 error 链写入失败：" + repr(e2)[:100])
        on_line("!lifecycle▸ 收口消费 restart/shutdown 登记异常（请求文件保留·已记 error 链）：" + str(e)[:120])
        return None
def ask(text, on_line, st=lambda n: None, ev=None):
    on_line = qq_flow.wrap(tts.hook(on_line)); tts.preempt(); stop.clear(); dream.maybe(SMS); qq_boot.autostart(SMS); __import__("smsocket_boot").autostart(SMS); model_meta.maybe(); ag = current(); st("检测执行器：" + (ag or "无"))
    if not ag:
        on_line("拒绝：未检出 agent CLI 且原生网关未启用（config llm_gateway.enabled=true）"
                "——sms-shell 只经数据流执行，请先 :config 启用网关或装 agent CLI")
        _consume(on_line)  # 批32 R1：无执行器早退路径也消费登记的 restart/shutdown
        return None
    spec = adapters()[ag]; ct.flush(); conv = chains.session_id(); chains.set_active(conv); __import__("session_reg").attach(conv, chains.cur_sess()); chains.record("session", "open:" + conv, _edge(conv)); qq_flow._wb([]); st("开新对话：" + conv)
    wsp, virt = ws.begin(conv); st("工作区：" + wsp + ("〔虚拟·收口即删〕" if virt else "")); at.bind(on_line=on_line, ev=ev if ev is not None else False)
    want = _state("current_agent"); want and want != ag and not spec.get("native") and on_line("注意：所选 agent " + want + " 未检出，本次经 " + ag + " 执行（:agents 查看）")
    chains.record("dialogue", "user@" + conv + " " + text[:200], _edge(conv)); rc = 0; st("话语送数据流")
    try:
        if spec.get("native"):
            st("提示词构建·任务总览（脚本粗分种子＋批22 复杂判定交模型）·压缩记忆组装·网关流式执行（直答/派工具/建表/建技能由模型在 Phase1 理解＋Phase2 关键词技能摘要中自主定）")
            # 2026-10-15：st 先于 chains.conversation——旧版把记忆组装放在状态上报之前，
            # 用户侧看到的是「提示词构建」卡住 450ms 才跳到网关流式执行；现在状态先行，
            # 压缩记忆组装（冷启 all_frags ~400ms / warm ~50ms）在用户已看到提示后台进行。
            # 并行：实时上下文压缩（无损合并＋有损丢弃无用，基于搜索引用集，不阻塞前台）
            cc_th = ctx_compress.maybe(SMS, text, on_line=on_line)
            # Phase 1：任务理解——不注入技能列表，只携带记忆+规则+用户输入
            body1 = sr.prefix() + tt.attach(text) + (text if not prefix_on() else chains.conversation(text, raw=text))
            resp1 = gateway.run(body1, on_line, ev=ev)
            # 提取操作关键词（技能/工具/记忆）
            keywords = _extract_operation_keywords(resp1 or "")
            # Phase 2：基于关键词注入技能摘要 + 泛洪记忆召回（不再全量注入 SKILL.md 索引）
            skill_summaries = _inject_skill_summaries(keywords, SMS)
            flood_memory = prompt_pack.pack(text, 1200, sms=SMS, sess=cur_sess(), keywords=keywords)
            pre_parts = []
            if skill_summaries: pre_parts.append("[技能摘要注入]\n" + skill_summaries)
            if flood_memory and flood_memory != "（暂无压缩记忆）": pre_parts.append("[压缩记忆·泛洪召回]\n" + flood_memory)
            pre = "\n\n".join(pre_parts) if pre_parts else ""
            body2 = sr.prefix() + tt.attach(text) + chains.conversation(text, raw=text, pre=pre)
            if resp1: body2 += "\n\n[第一阶段·任务理解]\n" + str(resp1)[:1500]
            bl2 = body2.split("\n"); imgs2 = None
            if bl2[-1].startswith("[图:") and bl2[-1].endswith("]"): p2 = bl2[-1][3:-1].strip(); body2 = "\n".join(bl2[:-1]); imgs2 = [p2] if os.path.isfile(p2) else None
            resp2 = gateway.run(body2, on_line, images=imgs2, ev=ev)
            sr.flag() and sr.append(text, str(resp2 or "（本轮网关中断·任务未必完成——下轮据接续与任务总览继续推进）"))
        else:
            st("agent CLI 执行：" + ag); args = list(spec.get("args", []))
            # 批32 R4：显式钉死 SMS_HOME——exec 子进程 request 与壳 run_pending 写读同一 lifecycle.json
            env = dict(os.environ, PYTHONIOENCODING="utf-8", SMS_WORKSPACE=wsp,
                       SMS_TMP=resolve_home.wtmp(), SMS_HOME=SMS); env.update(spec.get("env") or {})
            stdin = subprocess.PIPE if spec.get("prompt_stdin") else subprocess.DEVNULL
            p = no_window.Popen([spec.get("bin", ag)] + args + ([] if stdin else [text if not prefix_on() else text]), stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", env=env, cwd=wsp)
            if spec.get("prompt_stdin"):
                try:
                    p.stdin.write(text); p.stdin.close()
                except Exception as e:
                    on_line("!agent▸ 提示词写入异常（继续按已启动的 CLI 收口）：" + str(e)[:120])
            # 2026-10-01 t4（表 001-161413-507）：agent CLI 子进程挂看门狗＋有界读管道。
            # 旧版裸 readline 循环＝最恶劣的子进程阻塞：CLI 等交互输入／死循环刷屏／后代攥住管道写端时，
            # 本壳永久拿不回控制权（任务总览无人续推、QQ 侧再无回复）。现由 run_watch.watchdog 在途登记＋分级判定，
            # 命中即 kill_tree 整棵树；pump 把读取交独立线程、主循环只盯退出，进程已退而管道未 EOF 时至多再等 5s 强制收口并点名残留 pid。
            _nm = "agent:" + str(ag); _t0 = time.time(); _buf = []
            _done = rw.watchdog(p, _buf, rw.budget("agent"), rw.stall("agent"), _nm,
                                on_warn=lambda n, m: on_line("!watch▸ ⚠ " + m))
            _ok, _dwhy = rw.pump(p, _buf, on_line, "", _nm)
            stop.check()  # 用户 stop：pump 内吞异常不再抛，这里补检查点（旧版靠 kill_if 在行检查点抛）
            try:
                rc = p.wait(timeout=10)
            except Exception:
                rw.kill_tree(p); rc = -1
            _why = _done() or ("" if _ok else _dwhy)
            if _why:
                # 降级收口：不丢整轮——末段输出照常喂给大模型，并把「未完成」写进接续登记，下轮对照任务总览续跑
                on_line(rw.feedback(_nm, _why, time.time() - _t0, rw.budget("agent"), _buf))
                sr.flag() and sr.append(text, "（本轮 agent CLI 被阻塞应对收口：" + str(_why)[:120] + "·已收 %d 行·对照任务总览未完成行继续）" % len(_buf))
    except stop.Stopped as e: rc = 130; stop.clear(); on_line("⛔ 任务已停止（" + str(e)[:80] + "）——在途输出中断·会话照常收口·停止旗标已复位")
    except Exception as e: rc = 1; __import__("debug").enabled() and __import__("debug").log("EXC " + __import__("debug").tb()[-800:]); __import__("skill_errors").record(SMS, str(ag), "ask", __import__("skill_errors").describe(e), True); on_line("数据流异常（会话照常收口·任务总览保留·下轮按接续与任务总览续跑）：" + str(e)[:160]); sr.flag() and sr.append(text, "（本轮异常中断：" + str(e)[:100] + "·对照任务总览未完成行继续）")
    finally:
        # 批32 R1/R5：正常／异常／用户 stop 每条退出路径都在此收口——先落盘（任务总览对账·会话关闭链·工作区释放），
        # 再消费登记的 restart/shutdown（旧版包在 try/except pass 里＝异常静默吞，且无执行器早退路径不经过）。
        try: tt.reconcile(conv)  # 批30 P1 收口对账：有 result 或写资源已落盘的未完行补置 done
        except Exception as e:
            try:
                import chain_error
                chain_error.record("shell", "agent_stream.reconcile", str(e)[:160])
            except Exception as e2:
                on_line("!收口▸ 对账异常且 error 链写入失败：" + repr(e2)[:100])
            on_line("!收口▸ 任务总览对账异常（不挡收口·已记 error 链）：" + str(e)[:120])
        chains.record("session", "close:" + conv, _edge(conv))
        chains.record("time", "对话 " + conv + " 收口 rc=" + str(rc), _edge(conv))
        nf = ct.flush(); st("对话收口 rc=" + str(rc) + ("·收口链补写%d" % nf if nf else ""))
        m_ = ws.end(wsp, virt); m_ and on_line(m_)
        chains.ACTIVE["conv"] = ""; qq_flow.close(); _consume(on_line)  # R1：落盘之后再消费登记请求
    return {"agent": ag, "rc": rc, "conv": conv}