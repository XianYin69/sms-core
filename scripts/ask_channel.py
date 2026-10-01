#!/usr/bin/env python3
"""ask_channel.py — 数据流「问用户」通道（模型→用户阻塞问答·2026-09-26 用户报障「无法回答大模型向我提出的问题」）：网关工具循环在 worker 线程调 ask()——有 TUI 在线（arm() 置位）则把问题投递并阻塞等应答（默认 1800s 超时后指导模型按最佳判断继续）；无交互通道（ps1 原生壳·CLI 单发·未 arm）立即返回说明文本，模型改走 user_send＋假设，不死等。TUI 侧 Flow 每 0.4s poll 展示问题并置 awaiting，用户下一条输入经 reply() 直达等待中的工具线程——任务进行中可应答、不中断执行。
批27（用户「多个用户输入无需排队等待·全部并行处理」）＝通道由进程内单队列改为**按任务分队**：bind(tid) 把 worker 线程绑到某任务，ask()/reply()/poll_any() 各认自己的队列与在等账本 _OUT——并行多任务时 A 任务的提问不会把 B 任务的输入吃掉（reply 无 tid 时按 _OUT 最早一条自动路由，poll_any 只读不消费故路由账本不被破坏）；tid 为空＝沿用全局队列 ASK_Q/ANS_Q（web_shell/QQ 等老调用点零改动）。队列进程内共享，无需落盘。用法：python -B ask_channel.py status"""
import queue, time, threading
ASK_Q, ANS_Q = queue.Queue(), queue.Queue()
UI = {"armed": False, "asked": 0, "answered": 0}
_TL = threading.local()
_Q = {}
_OUT = {}
def bind(tid=""):
    _TL.t = str(tid or ""); return _TL.t
def tid(): return getattr(_TL, "t", "") or ""
def _pair(k=""):
    k = str(k or "")
    if not k: return ASK_Q, ANS_Q
    if k not in _Q: _Q[k] = (queue.Queue(), queue.Queue())
    return _Q[k]
def say(q):
    """批26 提问也要 TTS（用户「模型提问问题的输出的问题也要有TTS」）：TTS 开则朗读问题原文，失败静默不影响问答。"""
    try:
        import tts
        if tts.on(): tts.speak(str(q)[:400])
    except Exception: pass
def arm(): UI["armed"] = True
def disarm(): UI["armed"] = False
def ask(question, timeout=1800, t=None):
    k = t if t is not None else tid()
    aq, bq = _pair(k)
    if not UI["armed"]: return "无交互应答通道（原生壳/单发 CLI 不阻塞等用户）：请用 user_send 告知你的假设并继续，不要把问题悬置"
    UI["asked"] += 1; aq.put(str(question)[:2000]); _OUT[str(k or "")] = str(question)[:2000]
    __import__("qq_flow").fire("ask", question); say(question)
    try:
        ans = bq.get(timeout=timeout); UI["answered"] += 1; _OUT.pop(str(k or ""), None); return "用户答复：" + str(ans)
    except queue.Empty:
        _OUT.pop(str(k or ""), None); return "用户未在时限内答复——请按最佳判断继续执行，并在结果中说明所用假设"
def poll(t=None):
    """旧口径：取一条待显示问题（消费队列·留路由账本）；无 tid 时先取全局再兜各任务队列（web/QQ 老调用点照旧能拿到）。"""
    k = t if t is not None else tid()
    aq, _ = _pair(k)
    try: return aq.get_nowait()
    except queue.Empty: pass
    if str(k or ""): return None
    for kk in list(_Q.keys()):
        try: return _Q[kk][0].get_nowait()
        except queue.Empty: continue
    return None
def poll_any():
    """并行口径：返回 (任务id, 问题) 或 None——TUI 据此把问题与所属任务一起显示，应答才回得对线程。"""
    for kk in list(_Q.keys()):
        try: return kk, _Q[kk][0].get_nowait()
        except queue.Empty: continue
    try: return "", ASK_Q.get_nowait()
    except queue.Empty: return None
def pending():
    """在等问题账本 {任务id: 问题}（状态栏/底栏用）。"""
    return dict(_OUT)
def reply(text, t=None):
    """t 省略＝按 _OUT 最早一条自动路由（并行时用户直接输入即答他正在等的那个问题）。"""
    k = str(t or "")
    if not k:
        for kk in list(_OUT.keys()):
            k = kk; break
    _, bq = _pair(k)
    bq.put(str(text))
    return "已应答→任务继续" + ("（" + k + "）" if k else "")
def flush(t=None):
    k = str(t if t is not None else tid())
    for q in _pair(k):
        while not q.empty(): q.get_nowait()
    _OUT.pop(k, None)
def flush_all():
    flush("")
    for k in list(_Q.keys()): flush(k)
if __name__ == "__main__":
    print("ask_channel armed=%s asked=%d answered=%d 全局待问=%d · 各任务在等：%s（%s）" % (UI["armed"], UI["asked"], UI["answered"], ASK_Q.qsize(), pending() or "无", time.strftime("%H:%M:%S")))
