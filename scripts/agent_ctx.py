#!/usr/bin/env python3
"""agent_ctx.py — agent 工具线程上下文（批8·task 并行实例化根修复·批23 加 per-对话 conv）：旧版 agent_tools.CTX 全局单例，ThreadPool 并行 run_skill 互相覆写 on_line/depth/chain/streamed——skill1_1 的正文以 skill1_2 前缀上屏、深度闸假触「已达 2 层」。cur()：主线程恒返 MAIN；其他线程首次调用 fork(MAIN)（继承当轮已绑 on_line/ev/depth/chain/conv），此后只动本线程副本。adopt(parent)：池 worker 显式继承发起线程上下文；嵌套 gateway.run 内 ad.bind 只回写 worker 自身副本·互不串台。fork 后主线程再改 MAIN 不回传已 fork 线程——task 先 bind 后派发，顺序安全。conv 键＝批23 派发对话各持独立 conv（信封/链归属用本对话 id 非父 conv）。用法：import agent_ctx as ac; c = ac.cur()"""
import threading
MAIN = {"on_line": lambda s: None, "ev": False, "depth": 0, "streamed": False, "chain": [], "conv": ""}
_L = threading.local()
_MT = threading.current_thread()
def cur():
    if threading.current_thread() is _MT: return MAIN
    if getattr(_L, "c", None) is None: _L.c = dict(MAIN)
    return _L.c
def adopt(parent):
    if threading.current_thread() is not _MT: _L.c = dict(parent)
    return cur()
