#!/usr/bin/env python3
"""stop_channel.py — 任务中途停止通道（协作式收口·2026-09-27 用户「支持中途输入stop等指令·停止任务」）：request() 置停止旗标（TUI/GUI 主线程拦到 stop 词时调用），worker 线程在流式块/工具轮/子进程输出行处检查——check() 抛 Stopped 收口当前任务，kill_if(p) 先杀子进程再抛；is_stop_word() 为确定性词表；clear() 复位（新任务开始自动调用·空闲 :stop 元指令亦清残留）。
批27（用户「多个用户输入无需排队等待·全部并行处理」）＝旗标由进程内单例改为**按任务隔离**：bind(tid) 把当前线程绑到某任务，request(why, t)/stopped(t)/clear(t)/check() 只作用该任务——并行跑三个任务时停其中一个不牵连其余；t 省略且线程未绑＝退回**广播**语义（旧行为·裸 stop 词/F11 停全部·run_watch/GUI 等老调用点零改动）。旗标仍进程内内存态·不落盘。用法：python -B stop_channel.py status"""
import time, threading
S = {"req": False, "why": "", "at": ""}
_TASK = {}
_TL = threading.local()
WORDS = frozenset(("stop", "stops", "halt", "abort", "cancel", ":stop", "stop task", "abort task", "cancel task", "停止", "中止", "停止任务", "中止任务", "取消任务"))
class Stopped(Exception): pass
STOP_NOTE = "⛔ 已停止（stop）——在途输出中断·停止旗标已复位"
def bind(tid=""):
    """当前线程绑到某任务 id（并行 worker 起跑时调一次·此后 check/clear 默认只作用本任务）。"""
    _TL.t = str(tid or ""); return _TL.t
def tid(): return getattr(_TL, "t", "") or ""
def _key(t=None): return str(t) if t else tid()
def norm(t): return str(t).strip().lower().rstrip("。，！？.!?、")
def is_stop_word(t): return norm(t) in WORDS
def request(why="用户请求", t=None):
    k = _key(t); at = time.strftime("%H:%M:%S")
    if not k: S.update(req=True, why=str(why), at=at); return "已请求停止（广播·全部任务）"
    _TASK[k] = {"req": True, "why": str(why), "at": at}
    return "已请求停止任务 " + k
def stopped(t=None):
    k = _key(t)
    return bool(S["req"] or (k and (_TASK.get(k) or {}).get("req")))
def clear(t=None):
    """复位：已绑任务＝只清本任务旗标（并行时新任务起跑不牵连他人）；未绑（旧单任务前端）＝清广播，同旧行为。"""
    k = _key(t)
    if k: _TASK.pop(k, None); return
    S.update(req=False, why="", at="")
def clear_all():
    S.update(req=False, why="", at=""); _TASK.clear()
def why(t=None):
    k = _key(t)
    return ((_TASK.get(k) or {}).get("why") or S["why"] or "用户请求") if stopped(k) else ""
def check(t=None):
    if stopped(t): raise Stopped(why(t))
def kill_if(p, t=None):
    if stopped(t):
        try: p.kill()
        except Exception: pass
        raise Stopped(why(t))
def guard(fn, fallback=STOP_NOTE):
    try: return fn()
    except Stopped: clear(); return fallback
def status():
    n = len(_TASK)
    return ("广播：已请求停止（%s·%s）" % (S["why"], S["at"]) if S["req"] else "广播：无停止请求") + (" · 按任务旗标 %d 个：%s" % (n, "、".join(sorted(_TASK))) if n else "")
if __name__ == "__main__":
    print("stop_channel:", status(), "· 词表：", "、".join(sorted(WORDS)))
