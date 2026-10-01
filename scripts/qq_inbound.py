#!/usr/bin/env python3
"""qq_inbound.py — QQ 入站消息的派发（2026-09-29 用户「我要发消息给你」；解析与准入在 qq_policy，回复通道在 qq_reply，长连接在 qq_session，本模块只做「一条消息 → 一次 SMS 对话 → 回到原会话」）：handle(m) 顺序＝parse → allowed（非白名单只记审计不外泄本机状态）→ seen（RESUME 补发去重）→ gate（安全元指令白名单）→ mark → deliver；准入全通过后 handle 先 qq_reply.set_reply(msg_id, openid, kind) 置被动上下文（自 deliver 上移）、再发极短即时回执「收到 ✓ <原文前16字>」tag=QQ·回执（qq_push.DEF.ack 开关·异常吞掉不影响派发），回执走 qq_chunk.send 直发主动端点（不经 qq_reply→不消耗该 msg_id 的被动窗，被动位留给正文），随后 set_reply 置上下文再 deliver；deliver 不再截头丢字（旧 [-1400:] 已废·全文交 qq_chunk 分段），并在调 agent_stream.ask 前置 qq_brief=1（简洁模式·结束/异常清掉）——① 以 : ／ ! 开头＝元指令：经 shell_core.handle 执行并把可见行合并成一条回发（tag QQ·指令）；② 普通话语＝交 agent_stream.ask 走完整数据流（开新 conv、压缩记忆注入、工具循环、收口时 qq_flow.close 自动把正文经被动回复发出），本模块不重复发以免双份。被动窗口 5 分钟，过期由 qq_push.send 自动回落主动推送。2026-09-29 接线：① 过闸后即时回执「收到·正在处理 HH:MM:SS」（qq.json ack=false 可关；此刻被动上下文为空，故走主动推送不占被动窗）② 调 agent_stream.ask 前置 qq_brief.on(True)、finally 清，令 prompt_builder 追加简洁指令、qq_flow 收口限长。任何异常吞掉→记 error 链并回一句错误摘要，监听器绝不因单条消息崩。用法：python -B qq_inbound.py handle '<事件JSON>'|test '<文本>'。"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qq_push as qp, qq_reply, qq_policy as Q, chain_error, qq_report, session_reg as _sreg
def _beat(stage=None):
    """阶段边界打活动戳（2026-10-01 error 链 2ab90541b9）：入站解析→网关请求前/后→技能派发→出站推送
    每跨一个边界就 beat()；长等待处（agent_stream.ask 内含网关 LLM 请求）拿不到逐行输出，就 set_stage()
    把该阶段声明成长等待档（qq.handle_stall_llm 宽阈值）——绝不允许「活着却被平铺 240s 误杀」。"""
    try:
        import run_watch as rw
        if stage: rw.set_stage(stage)
        rw.beat()
    except Exception: pass

def _col(L):
    def on_line(x):
        x = str(x).rstrip()
        if x: L.append(x)
        try:
            import run_watch as rw; rw.beat()  # 活动戳：有输出＝在推进，看门狗不杀（只杀静默卡死）
        except Exception: pass
    return on_line
def deliver(e, c=None):
    c = c or qp.conf(); txt = e.get("text") or ""; L = []
    try: _sreg.bind("remote", e.get("openid") or "", "QQ:" + str(e.get("user") or "")[:12])
    except Exception: pass
    try:
        if txt[:1] in (":", "：", "!"):
            _beat("exec"); import runtime_bind as rb; rb.run(txt, _col(L)); _beat()
            _beat("push"); s = qq_report.snapshot(); return qp.push(("\n".join(L) or "（无输出）") + ("\n" + s if s else ""), "QQ·指令", c)
        try: qp._wj(qp._f(c["sms"], "active.json"), {"conv": str(__import__("chains").ACTIVE.get("conv") or ""), "ts": time.time()})
        except Exception: pass
        import agent_stream, qq_brief; qq_brief.on(bool(c.get("brief")))
        _beat("llm")  # 网关请求前：声明长等待阶段（T2 走宽档）＋打活动戳
        try: agent_stream.ask(txt, _col(L))
        finally: qq_brief.on(False); _beat("skill")  # 网关请求后／技能对话边界
        try:
            import runtime_bind as rb; rb.pending_run(allow=True)
        except Exception: pass
        _beat("push"); return "数据流已跑·正文经 qq_flow 被动回复（行 %d）" % len(L)
    finally:
        qq_reply.clear()
        try:
            import run_watch as rw; rw.clear_stage()  # 阶段声明不留存：常驻线程带着上一次的宽/窄档进下一条消息＝阈值错档
        except Exception: pass
def ack(e, c):
    """即时回执（t1）：走 qq_chunk.send 直发**主动**端点——绝不消耗该 msg_id 的被动窗（被动位留给正文），也不经 push 的间隔/配额簿记（不占 min_gap）；≤20字；qq.json ack=false 可关；异常一律吞掉，绝不影响后续派发。"""
    if not c.get("ack"): return None
    try:
        import qq_chunk as KC
        return KC.send(c, "收到·正在处理 " + time.strftime("%H:%M:%S"), "QQ·回执", qp.API + "/v2/users/%s/messages" % c["openid"])
    except Exception: return None
def handle(m, c=None):
    try:
        _beat("inbound"); c = c or qp.conf(); e = Q.parse(m); _beat()  # 入站解析边界
        if not e or not e.get("text"): return None
        if not Q.allowed(e, c): Q.mark(e["msg_id"], e, c); return "拒·非白名单 " + e["openid"][:14]
        if Q.seen(e["msg_id"], c): return "重复忽略 " + e["msg_id"][:16]
        ok, why = Q.gate(e["text"], c, e.get("openid", "")); Q.mark(e["msg_id"], e, c)
        if not ok: return qp.push("⚠" + why, "QQ·准入", c)
        qq_reply.set_reply(e["msg_id"], e["openid"], e["kind"]); _beat("push"); ack(e, c)
        _beat("dispatch"); return deliver(e, c)  # 技能派发边界
    except Exception as ex:
        try: chain_error.hook("gate", "qq_inbound.handle", str(ex)[:200])
        except Exception: pass
        return qp.push("⚠入站处理异常：" + str(ex)[:120], "QQ·错误", c or qp.conf())
if __name__ == "__main__":
    a = sys.argv[1:] or ["help"]
    print(json.dumps(handle(json.loads(a[1])), ensure_ascii=False) if a[0] == "handle" and len(a) > 1
         else str(deliver({"kind": "user", "msg_id": "", "openid": (qp.conf().get("openid") or ""), "text": " ".join(a[1:])})) if a[0] == "test"
         else __doc__.strip()[:300])
