#!/usr/bin/env python3
"""agent_stream.py — sms-shell 数据流引擎（批16 LLM 主导）：默认直达系统原生网关（config llm_gateway.enabled→gateway），网关未启用才回退已装 agent CLI；每次输入＝开新对话（红线 17），会话层 chains.set_active(conv/sess)＋session/dialogue 碎片打 member→sess 边；工作区＝gateway exec 与 agent CLI 的 cwd；技能路由不再脚本裁决——skill_route 打分命中仅作〔参考〕注入（记 skill_call 链供审计），直答还是派发由模型在 gateway 工具循环内自主决定（批15 前「命中即自动开子会话扇出」已废除）；未命中→chains.conversation 压缩记忆＋对话规则（批23 对等对话·互任监视/指导/训诫）＋〔会话拓扑〕（他 session 未完成/冲突监视提示）＋SKILL.md 索引＋治理注入送网关；话语/工具/技能/任务输出全程 msg_flow 信封（on_line 人读行＋ev 回调供 TUI 顶栏进度）；各阶段步骤名经 st 回调上报；尾行 [图:<路径>] 为网关视觉附图；状态存 <SMS_HOME>/shell/；皆无执行器则拒绝并引导配置（未检出执行器时不得空口作答）。"""
import no_window  # 静默子进程：前台运行任务不弹命令行窗口
import os, sys, shutil, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, chains, dream, qq_flow, qq_boot, gateway, model_meta, tts, skill_route, prompt_builder, workspace as ws, agent_tools as at, shell_resume as sr, stop_channel as stop, agent_task as atk, task_table as tt, chain_timing as ct, shell_lifecycle as lc, run_watch as rw
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
def compose(text, sms=None): return prompt_builder.init(sms or SMS) + "\n\n" + prompt_builder.build(text, sms or SMS)
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
    sid2, inj = skill_route.route(text, SMS); st("路由参考：" + (sid2 and ("打分命中 " + sid2 + "·已记 skill_call 链（〔参考〕注入模型·非脚本裁决）") or "未命中·注入技能全表"))
    chains.record("dialogue", "user@" + conv + " " + text[:200], _edge(conv)); rc = 0; st("话语送数据流")
    try:
        if spec.get("native"):
            body = sr.prefix() + tt.attach(text) + (text if not prefix_on() else chains.conversation(compose(text, SMS) + "\n\n" + inj))
            st("提示词构建·任务表（脚本粗分种子＋批22 复杂判定交模型）·压缩记忆组装·网关流式执行（路由命中仅作〔参考〕，直答/派工具/建表/建技能由模型自主定）")
            bl = body.split("\n"); imgs = None
            if bl[-1].startswith("[图:") and bl[-1].endswith("]"): p = bl[-1][3:-1].strip(); body = "\n".join(bl[:-1]); imgs = [p] if os.path.isfile(p) else None
            resp = gateway.run(body, on_line, images=imgs, ev=ev); sr.flag() and sr.append(text, str(resp or "（本轮网关中断·任务未必完成——下轮据接续与任务表继续推进）"))
        else:
            st("agent CLI 执行：" + ag); args = list(spec.get("args", []))
            # 批32 R4：显式钉死 SMS_HOME——exec 子进程 request 与壳 run_pending 写读同一 lifecycle.json
            env = dict(os.environ, PYTHONIOENCODING="utf-8", SMS_WORKSPACE=wsp,
                       SMS_TMP=resolve_home.wtmp(), SMS_HOME=SMS); env.update(spec.get("env") or {})
            stdin = subprocess.PIPE if spec.get("prompt_stdin") else subprocess.DEVNULL
            p = no_window.Popen([spec.get("bin", ag)] + args + ([] if stdin else [text if not prefix_on() else text + "\n\n" + inj]), stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", env=env, cwd=wsp)
            if spec.get("prompt_stdin"):
                try:
                    p.stdin.write(text + "\n\n" + inj); p.stdin.close()
                except Exception as e:
                    on_line("!agent▸ 提示词写入异常（继续按已启动的 CLI 收口）：" + str(e)[:120])
            # 2026-10-01 t4（表 001-161413-507）：agent CLI 子进程挂看门狗＋有界读管道。
            # 旧版裸 readline 循环＝最恶劣的子进程阻塞：CLI 等交互输入／死循环刷屏／后代攥住管道写端时，
            # 本壳永久拿不回控制权（任务表无人续推、QQ 侧再无回复）。现由 run_watch.watchdog 在途登记＋分级判定，
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
                # 降级收口：不丢整轮——末段输出照常喂给大模型，并把「未完成」写进接续登记，下轮对照任务表续跑
                on_line(rw.feedback(_nm, _why, time.time() - _t0, rw.budget("agent"), _buf))
                sr.flag() and sr.append(text, "（本轮 agent CLI 被阻塞应对收口：" + str(_why)[:120] + "·已收 %d 行·对照任务表未完成行继续）" % len(_buf))
    except stop.Stopped as e: rc = 130; stop.clear(); on_line("⛔ 任务已停止（" + str(e)[:80] + "）——在途输出中断·会话照常收口·停止旗标已复位")
    except Exception as e: rc = 1; __import__("debug").enabled() and __import__("debug").log("EXC " + __import__("debug").tb()[-800:]); __import__("skill_errors").record(SMS, str(ag), "ask", str(e)[:200], True); on_line("数据流异常（会话照常收口·任务表保留·下轮按接续与任务表续跑）：" + str(e)[:160]); sr.flag() and sr.append(text, "（本轮异常中断：" + str(e)[:100] + "·对照任务表未完成行继续）")
    finally:
        # 批32 R1/R5：正常／异常／用户 stop 每条退出路径都在此收口——先落盘（任务表对账·会话关闭链·工作区释放），
        # 再消费登记的 restart/shutdown（旧版包在 try/except pass 里＝异常静默吞，且无执行器早退路径不经过）。
        try: tt.reconcile(conv)  # 批30 P1 收口对账：有 result 或写资源已落盘的未完行补置 done
        except Exception as e:
            try:
                import chain_error
                chain_error.record("shell", "agent_stream.reconcile", str(e)[:160])
            except Exception as e2:
                on_line("!收口▸ 对账异常且 error 链写入失败：" + repr(e2)[:100])
            on_line("!收口▸ 任务表对账异常（不挡收口·已记 error 链）：" + str(e)[:120])
        chains.record("session", "close:" + conv, _edge(conv))
        chains.record("time", "对话 " + conv + " 收口 rc=" + str(rc), _edge(conv))
        nf = ct.flush(); st("对话收口 rc=" + str(rc) + ("·收口链补写%d" % nf if nf else ""))
        m_ = ws.end(wsp, virt); m_ and on_line(m_)
        chains.ACTIVE["conv"] = ""; qq_flow.close(); _consume(on_line)  # R1：落盘之后再消费登记请求
    return {"agent": ag, "rc": rc, "conv": conv}