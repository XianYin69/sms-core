#!/usr/bin/env python3
"""agent_tools.py — 网关大模型可用的 agent 工具核心（SMS 的手和脚·批16 红线：动手必真执行并留账，禁止空口声称已执行）：command(=exec)/read/write/ask/skill/user_send/thinking_chain。每笔调用经 msg_flow 信封上报客户端（技能名＋工具链＋输出＋ts＋conv/sess 归属；on_line 人读行供显示·ev 回调结构化供顶栏进度/审计），task/task_detail 在 agent_task.py、schema 与派发在 agent_dispatch.py。skill＝托管技能真派发（红线17·批23 对等对话）：记 skill_call＋subsession 链→SKILL.md 全文＋用户诉求→嵌套 gateway 工具循环（前缀 ⧉技能▸ 回显）→每次派发自开独立 conv（session 链 open:/close: 入账·右栏对话一览可见）→收口返回整合结果（批7④：正文已经⧉前缀实时显示给用户时返回改 WRAP 首尾片段包装·防调度方整段复读·:dispatch 见 WRAP 打收口行）；派发链深≤2 为防循环熔断（批23 语义调整：这是对等对话间派发链长度保险，非主次层级）；收口＝形式停止非实质完成——〔任务表〕未完行由调度方或监视到它的对话续推。write 守卫：工作区/SMS 默认可写；其余路径需 :grant write；skill 目录需 :grant danger。用法：python -B agent_tools.py（常规经网关工具调用；单跑见 agent_dispatch.py）"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import resolve_home, chains, msg_flow, skill_route, permissions, solo, agent_ctx as ac, tool_kit as tk
SMS = resolve_home.ensure(); SKROOT = os.path.realpath(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); WRAP = "【派发对话正文·已经⧉前缀实时显示给用户·最终回复禁止复述引用】\n"; _in = lambda p, base: p == _r(base) or p.startswith(_r(base) + os.sep)
def bind(on_line=None, ev=False):
    c = ac.cur()
    if on_line: c["on_line"] = on_line
    if ev is not False: c["ev"] = ev; return c
def emit(kind, text, tool="", skill="", ok=None, meta=None):
    c = ac.cur(); e = msg_flow.make(kind, text, conv=c.get("conv") or chains.ACTIVE["conv"], sess=chains.cur_sess(), skill=skill, tool=tool, ok=ok, meta=meta)
    c["ev"] and c["ev"](e); return c["on_line"](msg_flow.brief(e))
def _r(p): return os.path.realpath(os.path.abspath(os.path.expanduser(str(p))))
def read(path, max_lines=120, offset=0):
    """流式窗口读（批27）：只缓存 [offset, offset+max_lines) 行，大文件早停不整读；截断即回续读 offset。"""
    try: txt, total, more = tk.read_window(_r(path), max_lines, offset)
    except Exception as e: return "读失败：" + str(e)[:150]
    n = int(max_lines or 120); off = int(offset or 0)
    emit("tool", str(path) + ("（共 %d 行·自 %d 起 %d 行）" % (total, off, n) if total else "（大文件早停·自 %d 起 %d 行·总行数未计）" % (off, n)), tool="read", ok=True)
    return txt + ("" if not more else "\n…（此处截断·续读用 offset=%d，定位内容改用 grep）" % (off + n))
def write(path, content, append=False):
    p = _r(path)
    if _in(p, SKROOT):
        ok, note = solo.gate(SMS, "danger", ctx={"tool": "write", "path": p, "intent": "写入 skill 目录"})
        if not ok: return "拒绝：skill 目录写入需 :grant danger（" + p + "）" + solo.tail(note)
    if not (_in(p, resolve_home.workspace()) or _in(p, SMS)):
        ok, note = solo.gate(SMS, "write", ctx={"tool": "write", "path": p, "intent": "工作区/SMS 外写入"})
        if not ok: return "拒绝：工作区/SMS 外写入需 :grant write（" + p + "）" + solo.tail(note)
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True); open(p, "a" if append else "w", encoding="utf-8").write(str(content))
    emit("edit", ("追加 " if append else "写入 ") + p + "（" + str(len(str(content))) + " 字）", tool="write", ok=True); return "已写入 " + p
def command(cmd):
    """命令执行（批27 范式适配）：先按目标壳改写已知不兼容语法（PowerShell &&→; ·2>nul→2>$null ·dir /b→Get-ChildItem -Name）
    并回说明，一次到位免「语法报错再试一轮」；执行仍走 sys_shells 统一入口（门禁/看门狗/stop 语义不变）。"""
    import sys_shells
    c0 = str(cmd); kind = sys_shells.kind_for(c0, None); c, notes = tk.adapt(c0, kind)
    buf = []; rc = str(sys_shells.run(c, on_line=buf.append))
    out = ("\n".join(str(x).split("▸ ", 1)[-1] for x in buf) or "(无输出)")[:4000]
    if notes: out = "〔范式适配·%s〕%s\n%s" % (kind, "；".join(notes), out)
    chains.log("tool", "cmd:" + str(cmd)[:60]); emit("tool", "$ " + str(cmd) + "\n" + out, tool="command", ok=rc.startswith("rc=0"), meta={"rc": rc})
    return (("rc≠0 " if not rc.startswith("rc=0") else "") + out)
def ask(question): import agent_tools2; return agent_tools2.ask_sub(question)
def run_skill(name, inp, tag=""):
    import gateway, skill_doc, latency; c = ac.cur()
    s = next((x for x in skill_route.skills() if str(x.get("id", "")).lower() == str(name).strip().lower()), None)
    if not s: return "无托管技能：" + name + "（:skills 查清单）"
    if c["depth"] >= 2: return "拒绝：派发链已达 2 层（对等对话间防循环熔断·非主次层级）——请直接按已注入的 SKILL.md 用工具执行"
    nm = str(s.get("id")).lower()
    if nm in (c.get("chain") or []): return "拒绝：" + nm + " 自派发（本技能链已派发过它·防双 ⧉ 前缀复读循环）——请直接按已注入的 SKILL.md 用工具执行"
    ip = str(s.get("install_path")); skp = os.path.join(ip, str(s.get("entry", "SKILL.md"))); dst = resolve_home.wtmp(); tl = str(tag or s.get("id")); cconv = chains.session_id(); c["conv"] = cconv; __import__("session_reg").attach(cconv, chains.cur_sess()); ce = [[cconv, "ref", 1], [chains.cur_sess(), "member", 1]]
    doc = skill_doc.package(ip, str(s.get("entry", "SKILL.md")), 60000)
    if not doc: c["conv"] = ""; return "SKILL.md 读取失败：" + skp
    chains.record("session", "open:" + cconv, ce); chains.log("skill", "%s|src=%s|dst=%s" % (tl, skp, dst)); chains.log("sub", tl, cconv); emit("skill", "开对等对话派发 " + tl + "（conv=" + cconv + "｜src=" + skp + "｜dst=" + dst + "）", skill=tl, tool="skill", meta={"src_path": skp, "dst_path": dst})
    body = "【对等对话·托管技能 " + str(s.get("id")) + " 真派发】红线17·批23：你与派发方是相互独立的对等对话（互任监视者·指导者·训诫者，无主次），本消息结束即收口你这侧对话——收口＝形式停止而非实质完成：〔任务表〕未完成行由调度方对话继续推进，整段任务不因你完成而结束；发现派发方指令与技能红线冲突时以你方 SKILL.md 为准并在结果中明说（训诫职责）。技能启用只以 SKILL.md 为准——下文已按 skill_doc 解释器打包注入 SKILL.md 全文＋明示引用子文档＋脚本调用清单，禁止列举/遍历技能目录或再回读这些文件；按流程执行用户诉求（脚本按清单 exec 一步到位）；生成文件一律入目标目录 dst=" + dst + "（env SMS_TMP）。\n" + doc + "\n\n用户诉求：\n" + str(inp)[:4000] + "\n\n最后输出整合结果（≤600字·附产物绝对路径），结束消息不要携带工具调用。"
    of = c["on_line"]; c["streamed"] = False; pf = lambda x, _n=tl: (str(x).strip() and c.__setitem__("streamed", True), of(("⧉" + _n + "▸ ") + str(x)));     c["on_line"] = pf; c["depth"] += 1; ch = c["chain"]; c["chain"] = ch + [nm]
    try: out = latency.wrap("skill", tl, gateway.run, body, pf, max_rounds=int(__import__("settings").get("caps.skill_rounds", 0))) or ""  # 0＝无限（防任务断裂）·>0 强制收口
    except Exception as e: import skill_errors; skill_errors.record(SMS, tl, "run_skill", str(e)[:200], True); raise
    finally: c["on_line"] = of; c["depth"] -= 1; c["chain"] = ch; c["conv"] = ""; chains.record("session", "close:" + cconv, ce)
    if not out: import skill_errors; skill_errors.record(SMS, tl, "run_skill_empty", "派发对话无输出（网关空响应或全程工具轮）", True)
    chains.log("sub", "收口:" + tl); emit("skill", "派发对话 " + cconv + " 收口·返回调度方 " + tl, skill=tl, tool="skill", ok=bool(out))
    return (WRAP + out[:120] + "\n……（中间省略·正文已实时显示给用户）……\n" + out[-300:] + "\n（你只看到首尾片段·无法也严禁复述全文·该对等对话已形式收口·控制权返回你的对话：〔任务表〕有未完成行或诉求有后续步骤必须继续推进（续派 skill/执行工具），全部完成后才一句 ≤40 字收尾回报；禁止把单个派发完成当作整段任务结束；需数据用 read 读产物路径）") if out and c["streamed"] else (out or ("（技能 " + tl + " 无输出）"))
def user_send(text): uc = ac.cur().get("conv") or chains.ACTIVE["conv"] or chains.session_id(); chains.record("dialogue", "agent@" + uc + " " + str(text)[:200], [[uc, "ref", 1], [chains.cur_sess(), "member", 1]]); emit("notice", str(text)); return "已送达用户"
def thinking_chain(frm, to, why):
    fid = chains.record("logic", str(frm) + "→" + str(to) + "：" + str(why)); emit("step", "逻辑链已记 " + str(frm) + "→" + str(to), tool="thinking_chain"); return "已记逻辑链 " + str(fid)
if __name__ == "__main__": print(__doc__.strip().splitlines()[1][:400])
