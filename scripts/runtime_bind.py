#!/usr/bin/env python3
"""runtime_bind.py — 壳↔核唯一接缝（批27 分离治理·用户「检查 SMS 的 shell 和核心是否完全分离」）：
core 侧模块（net_util/planned_tasks/qq_inbound…）不得 import shell_*，凡需「把一句话语交壳执行」或
「跑壳的待办/生命周期」者一律经本模块注册的回调。set_runner/set_pending/bound/runner/run/pending——
注册方＝shell_core（handle）与 shell_lifecycle（run_pending）在自身 import 时登记；未登记＝按名惰性
import 兜底（同一进程内先 import 壳再调用则永不触发兜底），兜底也失败即回明确「未绑定壳」错误串，
调用方自决降级，绝不静默改行为。本模块是 sms-core 与 sms-shell 之间唯一的反向依赖点，
sep_audit.py 据此把它计为 SEAM 而非 core（审计口径：core→shell 边＝0）。用法：python -B runtime_bind.py。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_R = [None]; _P = [None]
def set_runner(fn): _R[0] = fn
def set_pending(fn): _P[0] = fn
def bound(): return bool(_R[0])
def runner():
    """取壳运行器：已注册即用；否则惰性 import shell_core 兜底并回填注册（失败回 None）。"""
    if _R[0]: return _R[0]
    try:
        import shell_core; _R[0] = shell_core.handle; return _R[0]
    except Exception: return None
def pending():
    """取壳待办执行器（shell_lifecycle.run_pending）：同上，未注册即惰性兜底，失败回 None。"""
    if _P[0]: return _P[0]
    try:
        import shell_lifecycle as lc; _P[0] = lc.run_pending; return _P[0]
    except Exception: return None
def run(text, on_line=None, st=None, ev=None):
    """把一句话语交壳（元指令＋数据流同 TUI/GUI）：回壳的返回值；未绑定壳＝回错误串（不抛，调用方按文本判）。"""
    f = runner()
    if not f: return "未绑定壳运行器（sms-shell 未安装/未 import——纯核链路请改调 agent_stream.ask 或 gateway.run）"
    try: return f(text, on_line or (lambda s: None), st or (lambda n: None), ev)
    except Exception as e: return "壳执行异常：" + repr(e)[:200]
def pending_run(**kw):
    """跑壳侧待办（计划任务/接续等）：未绑定＝回 None 静默跳过（与「无待办」同义）。"""
    f = pending(); return f(**kw) if f else None
if __name__ == "__main__":
    print("bound=%s runner=%s pending=%s" % (bound(), bool(runner()), bool(pending())))
