#!/usr/bin/env python3
"""stop_channel.py — 任务中途停止通道（协作式收口·2026-09-27 用户「支持中途输入stop等指令 停止任务」）：request() 置停止旗标（TUI/GUI 主线程拦到 stop 词时调用），worker 线程在流式块/工具轮/子进程输出行处检查——check() 抛 Stopped 收口当前任务，kill_if(p) 先杀子进程再抛；is_stop_word() 为确定性词表（仅任务进行中把裸词当指令·普通排队话语不受影响）；clear() 复位（新任务开始自动调用·空闲 :stop 元指令亦清残留）；ask_user 阻塞提问时经应答收尾后即命中下一轮检查。进程内共享内存态·不落盘。用法：python -B stop_channel.py status"""
import time
S = {"req": False, "why": "", "at": ""}
WORDS = frozenset(("stop", "stops", "halt", "abort", "cancel", ":stop", "stop task", "abort task", "cancel task", "停止", "中止", "停止任务", "中止任务", "取消任务"))
class Stopped(Exception): pass
STOP_NOTE = "⛔ 已停止（stop）——在途输出中断·停止旗标已复位"
def norm(t): return str(t).strip().lower().rstrip("。.！!，,、")
def is_stop_word(t): return norm(t) in WORDS
def request(why="用户请求"): S.update(req=True, why=str(why), at=time.strftime("%H:%M:%S"))
def stopped(): return bool(S["req"])
def clear(): S.update(req=False, why="", at="")
def check():
    if stopped(): raise Stopped(S["why"] or "用户请求")
def kill_if(p):
    if stopped():
        try: p.kill()
        except Exception: pass
        raise Stopped(S["why"] or "用户请求")
def guard(fn, fallback=STOP_NOTE):
    try: return fn()
    except Stopped: clear(); return fallback
def status(): return "已请求停止（%s·%s）——待下一检查点收口" % (S["why"], S["at"]) if stopped() else "无停止请求"
if __name__ == "__main__":
    print("stop_channel:", status(), "· 词表：", "、".join(sorted(WORDS)))
