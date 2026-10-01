#!/usr/bin/env python3
"""ask_channel.py — 数据流「问用户」通道（模型→用户阻塞问答·2026-09-26 用户报障「无法回答大模型向我提出的问题」）：网关工具循环在 worker 线程调 ask()——有 TUI 在线（arm() 置位）则把问题投 ASK_Q 并阻塞等 ANS_Q 应答（默认 1800s 超时后指导模型按最佳判断继续）；无交互通道（ps1 原生壳·CLI 单发·未 arm）立即返回说明文本，模型改走 user_send＋假设，不死等。TUI 侧 Flow.drain 每 0.4s poll() 展示问题并置 awaiting，用户下一条输入经 reply() 直达等待中的工具线程——任务进行中可应答、不中断执行。队列进程内共享，无需落盘。用法：python -B ask_channel.py status"""
import queue, time
ASK_Q, ANS_Q = queue.Queue(), queue.Queue()
UI = {"armed": False, "asked": 0, "answered": 0}
def say(q):
    """批26 提问也要 TTS（用户「模型提问问题的输出的问题也要有TTS」）：TTS 开则朗读问题原文，失败静默不影响问答。"""
    try:
        import tts
        if tts.on(): tts.speak(str(q)[:400])
    except Exception: pass
def arm(): UI["armed"] = True
def disarm(): UI["armed"] = False
def ask(question, timeout=1800):
    if not UI["armed"]: return "无交互应答通道（原生壳/单发 CLI 不阻塞等用户）：请用 user_send 告知你的假设并继续，不要把问题悬置"
    UI["asked"] += 1; ASK_Q.put(str(question)[:2000]); __import__("qq_flow").fire("ask", question)
    say(question)
    try: ans = ANS_Q.get(timeout=timeout); UI["answered"] += 1; return "用户答复：" + str(ans)
    except queue.Empty: return "用户未在时限内答复——请按最佳判断继续执行，并在结果中说明所用假设"
def poll():
    try: return ASK_Q.get_nowait()
    except queue.Empty: return None
def reply(text): ANS_Q.put(str(text)); return "已应答→任务继续"
def flush():
    while not ASK_Q.empty(): ASK_Q.get_nowait()
    while not ANS_Q.empty(): ANS_Q.get_nowait()
if __name__ == "__main__":
    print("ask_channel armed=%s asked=%d answered=%d 待问=%d 待答=%d（%s）" % (UI["armed"], UI["asked"], UI["answered"], ASK_Q.qsize(), ANS_Q.qsize(), time.strftime("%H:%M:%S")))
