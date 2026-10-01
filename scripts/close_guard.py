#!/usr/bin/env python3
"""close_guard.py — 关闭/重启的二次确认＋远端通报（2026-09-30 用户「用户关闭主窗口 或 键入 ctrl+c 时需要二次确认，然后向远端推送 SMS关闭中；如果 SMS 需要重启，大模型可以依据任务要求重启，重启后继续执行任务；用户手动重启也需要二次确认」）。
拦截三条真会「啪一下就没了」的路径：
① 控制台窗口 X／CTRL_CLOSE_EVENT／CTRL_LOGOFF／CTRL_SHUTDOWN——Windows 给进程几秒就硬杀，本模块首枪一律否决（SetConsoleCtrlHandler 回 True）并提示「再关一次才真退」，第二枪（15s 内）才放行；
② 终端 Ctrl+C／Ctrl+Break——同上（Textual 里 ctrl+c 被壳接管，走 TUI 的 confirm 动作；readline 兜底壳走 KeyboardInterrupt 捕获）；
③ 大模型侧：agent 用 exec 跑 shell_lifecycle restart 时，请求写进 shell/lifecycle.json，由壳进程在本轮收口时自己执行（spawn 新实例＋杀旧＋os._exit），保证「只保留重启之后的」那一个进程。
通报＝qq_push 尽力推一句「SMS 关闭中／重启中（原因·时间）」，任何异常吞掉，绝不因通报挡住退出。
用法：python -B close_guard.py status|test"""
import os, sys, time, json, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, chains
S = {"first": 0.0, "n": 0, "note": "", "app": None, "armed": False}
WINDOW = 15.0
CTRL_C, CTRL_BREAK, CTRL_CLOSE, CTRL_LOGOFF, CTRL_SHUTDOWN = 0, 1, 2, 5, 6

def _f(sms=None): return os.path.join(sms or resolve_home.ensure(), "shell", "lifecycle.json")
def push(text):
    """远端通报（QQ）——尽力而为，失败静默。"""
    try:
        import qq_push as qp
        if qp.ready(): return qp.push(text, "SMS·关闭")
    except Exception: pass
    return None
def enabled():
    """二次确认总开关（settings close_guard.enabled·默认开）：关＝首枪即放行（调用方仍走 _bye 通报远端）。"""
    try:
        import settings
        return bool(settings.get("close_guard.enabled", True))
    except Exception: return True
def ask(why="窗口关闭"):
    """二次确认计数：首枪＝否决＋提示；15s 内第二枪＝放行。回 (放行?, 该显示的文案)。close_guard.enabled=false＝首枪即放行（仍通报远端）。"""
    now = time.time()
    if not enabled():
        S.update(n=0, first=0.0)
        return True, "关闭二次确认已关（close_guard.enabled=false）——直接放行，远端已通报"
    if S["n"] and now - S["first"] < WINDOW:
        S.update(n=0, first=0.0)
        return True, "已确认退出（%s）——SMS 关闭中，远端已通报" % why
    S.update(n=1, first=now)
    return False, "⚠ 检测到%s：这是第一次，已拦下（任务还在跑就退出会丢进度）。再关一次／再按一次（15 秒内）才真的退出；要停任务先按 F11 停止。" % why
def pending(sms=None):
    """大模型侧的关闭/重启请求（读后即清）。"""
    try:
        d = json.load(open(_f(sms), encoding="utf-8"))
        os.remove(_f(sms))
        return d
    except Exception: return None
def request(action, why="", sms=None):
    """agent 请求壳在收口时执行 restart|shutdown（写文件＝跨进程可见）。"""
    try:
        os.makedirs(os.path.dirname(_f(sms)), exist_ok=True)
        json.dump({"action": action, "why": str(why)[:120], "at": time.strftime("%Y-%m-%d %H:%M:%S"), "by": os.getpid()}, open(_f(sms), "w", encoding="utf-8"))
        return "已登记 %s 请求（本轮收口后由壳自己执行·只保留新实例）" % action
    except Exception as e: return "登记失败：" + str(e)[:80]

def _msgbox(text, title="SMS 关闭确认"):
    """原生弹窗（控制台 X 关闭只有几秒宽限，TUI 里来不及打字，故用系统对话框问一次）。
    回 True＝用户点「是（关闭）」／False＝点「否」或弹窗不可用。"""
    try:
        import ctypes
        MB_YESNO, MB_ICONWARNING, IDYES = 4, 48, 6
        return ctypes.windll.user32.MessageBoxW(None, text, title, MB_YESNO | MB_ICONWARNING) == IDYES
    except Exception: return None
def _bye(why):
    """放行退出前的收尾：链落盘＋远端通报（顺序很重要——先通报再 flush，硬杀也至少发出去了）。"""
    push("SMS 关闭中（%s）· %s" % (why, time.strftime("%H:%M:%S")))
    try:
        import chain_timing; chain_timing.flush()
    except Exception: pass
    try:
        import chains as ch; ch.record("event", "shell-close " + why)
    except Exception: pass
def _handler(sig):
    """控制台控制事件回调（CTRL_C=0/BREAK=1/CLOSE=2/LOGOFF=5/SHUTDOWN=6）。"""
    name = {0: "Ctrl+C", 1: "Ctrl+Break", 2: "关闭主窗口", 5: "注销", 6: "系统关机"}.get(sig, "控制事件" + str(sig))
    if sig not in (CTRL_C, CTRL_BREAK, CTRL_CLOSE, CTRL_LOGOFF, CTRL_SHUTDOWN): return False
    ok, txt = ask(name)
    if ok:
        _bye(name)
        return False
    if sig == CTRL_CLOSE:
        # 窗口 X 没有第二次机会：弹窗当场问，答「是」才放行
        got = _msgbox(txt + "\n\n（点「是」立即关闭并通报远端；点「否」继续运行）")
        if got:
            _bye(name)
            return False
        push("SMS 关闭被拦下（用户选否·%s）" % time.strftime("%H:%M:%S"))
    try:
        app = S["app"]
        app and app.call_from_thread(app.log_line, __import__("rich.text", fromlist=["Text"]).Text(txt, style="bold yellow"))
    except Exception: pass
    return True
def arm(app=None):
    """注册控制台控制事件处理器（Windows 专用·非 nt 或失败一律静默，绝不挡启动）。"""
    S["app"] = app
    if S["armed"] or os.name != "nt": return "不适用（非 Windows 或已注册）"
    try:
        import ctypes
        global _CB
        _CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)(_handler)
        if not ctypes.windll.kernel32.SetConsoleCtrlHandler(_CB, True): return "注册失败（GetLastError=%s）" % ctypes.windll.kernel32.GetLastError()
        S["armed"] = True; return "已注册控制台关闭拦截（窗口 X／Ctrl+C 首枪拦下＋二次确认）"
    except Exception as e:
        return "注册异常已忽略：" + str(e)[:80]
def peek(sms=None):
    """看不消耗（诊断/status 用）。"""
    try: return json.load(open(_f(sms), encoding="utf-8"))
    except Exception: return None
def status():
    return json.dumps({"armed": S["armed"], "window_s": WINDOW, "first_at": time.strftime("%H:%M:%S", time.localtime(S["first"])) if S["n"] else "", "pending": peek()}, ensure_ascii=False)
if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]
    if a[0] == "test":
        print(ask("测试关闭")); print(ask("测试关闭")); print(ask("测试关闭"))
    elif a[0] == "arm": print(arm())
    else: print(status())
