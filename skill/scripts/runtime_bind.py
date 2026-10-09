#!/usr/bin/env python3
"""runtime_bind.py — 壳↔核唯一接缝（批27 分离治理·用户「检查 SMS 的 shell 和核心是否完全分离」）：
core 侧模块（net_util/planned_tasks/qq_inbound…）不得 import shell_*，凡需「把一句话语交壳执行」或
「跑壳的待办/生命周期」者一律经本模块注册的回调。set_runner/set_pending/bound/runner/run/pending——
注册方＝shell_core（handle）与 shell_lifecycle（run_pending）在自身 import 时登记；未登记＝按名惰性
import 兜底（同一进程内先 import 壳再调用则永不触发兜底），兜底也失败即回明确「未绑定壳」错误串，
调用方自决降级，绝不静默改行为。生命周期同径：lifecycle_request(action, why) 登记 restart/shutdown、lifecycle_kill_services(why) 回收壳拉起的后台服务——二者＝SEAM→shell 的契约边，core 侧模块（spin_guard/close_guard）因此自身绝不出现 shell_* import。本模块是 sms-core 与 sms-shell 之间唯一的反向依赖点，
sep_audit.py 据此把它计为 SEAM 而非 core（审计口径：core→shell 边＝0）。用法：python -B runtime_bind.py。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_R = [None]; _P = [None]; _LC = [None]
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
def _lifecycle():
    """取壳生命周期件（shell_lifecycle）：缓存后复用；不可用回 None（调用方按未绑定自决降级）。"""
    if _LC[0]: return _LC[0]
    try:
        import shell_lifecycle as lc; _LC[0] = lc; return lc
    except Exception: return None
def run(text, on_line=None, st=None, ev=None):
    """把一句话语交壳（元指令＋数据流同 TUI/GUI）：回壳的返回值；未绑定壳＝回错误串（不抛，调用方按文本判）。"""
    f = runner()
    if not f: return "未绑定壳运行器（sms-shell 未安装/未 import——纯核链路请改调 agent_stream.ask 或 gateway.run）"
    try: return f(text, on_line or (lambda s: None), st or (lambda n: None), ev)
    except Exception as e: return "壳执行异常：" + repr(e)[:200]
def pending_run(**kw):
    """跑壳侧待办（计划任务/接续/lifecycle 请求）：未绑定＝回明确错误串（批32 R2——不再与「无待办」
    混同，调用方按文本自决降级；lifecycle 请求文件由 shell_lifecycle 保留不删）。"""
    f = pending()
    return f(**kw) if f else "未绑定壳待办执行器（shell_lifecycle 不可用）：待办未消费·请求文件保留"
def lifecycle_request(action, why=""):
    """向壳登记生命周期请求（restart/shutdown·本轮收口由壳自己执行）：回壳的登记结果串；
    未绑定壳/异常＝回明确错误串（不抛不静默，调用方按文本自决·语义同直接调用）。"""
    lc = _lifecycle()
    if not lc: return "未绑定壳生命周期器（shell_lifecycle 不可用）：请求未登记"
    try: return lc.request(action, why)
    except Exception as e: return "壳生命周期请求异常：" + repr(e)[:200]
def lifecycle_kill_services(why="", exclude=(), budget=1.5, others=False):
    """回收壳拉起的后台服务（DETACHED 子进程不随本进程死）：回被回收 pid 列表；
    未绑定壳/异常＝回 None（＝无服务可回收，与调用方原 try-except 吞异常同义，不改行为）。
    批30 others=True＝再回收「其它壳＋命令行含 smsystem-suit 的 core 后台」（lc.kill_others），
    回 (服务 pids, 其它 pids)——关闭/重启必须把整台 SMS 收干净，close_guard._bye 用此参数。"""
    lc = _lifecycle()
    if not lc: return None
    try:
        svc = lc.kill_services(exclude=exclude, budget=budget, why=why)
    except Exception:
        svc = None
    if not others: return svc
    try:
        return svc, lc.kill_others(exclude=exclude, why=why)
    except Exception:
        return svc, None
def lifecycle_register_shell(pid=None):
    """批30：把本壳 pid 登记进壳侧登记表（shells.json）——reclaim 的零 PowerShell 主路径。
    未绑定壳/异常＝回 None（只降级不抛，绝不挡壳启动）。"""
    lc = _lifecycle()
    if not lc: return None
    try:
        return lc.register_shell(pid=pid)
    except Exception:
        return None
def lifecycle_unregister_shell(pid=None):
    """批30：退出时注销本壳 pid（防登记表残留死 pid）。未绑定/异常＝回 None。"""
    lc = _lifecycle()
    if not lc: return None
    try:
        return lc.unregister_shell(pid=pid)
    except Exception:
        return None
if __name__ == "__main__":
    print("bound=%s runner=%s pending=%s lifecycle=%s" % (
        bound(), bool(runner()), bool(pending()), bool(_lifecycle())))
