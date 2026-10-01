#!/usr/bin/env python3
"""stall_class.py — 「卡住」原因分类器（2026-09-29 用户诉求「卡住看门狗分清原因＋不误杀＋带重试计数」第2步）：classify(doc, age, cfg) -> (kind, detail)，kind∈network|model|process|busy|unknown。判据①busy（不误杀）＝runtime.phase∈{exec,llm,llm_stream} 且 runtime.ts 距今 < 宽限窗（窗读实际配置 shell.exec_timeout / llm_gateway.timeout×(剩余重试+1)）且该 pid 真活，或该表派发仍在跑（qq_dispatch 队列非空/worker 刚动）→ 交上层静默、不告警、不消耗重试、不重发；②process＝runtime.pid 已死（ctypes OpenProcess 判活·不依赖 psutil）或监听器僵尸（qq_watch）或壳心跳 shell/alive.json 过期；③network＝err_kind/last_err 指向 URLError/超时/断连/5xx/429 或曾 gaveup；④model＝4xx 不可重试或网关空返回；⑤其余 unknown。detail 带证据（phase/age/窗/err 摘要/重试计数）。用法：python -B stall_class.py [态]。"""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, runtime_rec as rr, settings
ACTIVE = ("exec", "llm", "llm_stream", "qq_ws", "qq_push")
BUSY = ("exec", "llm", "llm_stream")
NET_KW = ("urlerror", "timeout", "timed out", "connection", "reset", "broken pipe", "getaddrinfo",
          "unreachable", "429", "500", "502", "503", "504", "eof", "网络", "断连", "重连失败", "gaveup", "重试耗尽")
MOD_KW = ("400", "401", "403", "404", "422", "空返回", "no choices", "empty response", "content_policy", "内容安全")
def _i(v, d=0):
    try: return int(v)
    except Exception: return d
def window(phase, rt):
    """宽限窗（秒）：exec＝shell.exec_timeout；llm/llm_stream＝llm_gateway.timeout×(还剩重试+1)；其余＝60。"""
    try:
        if phase == "exec": return max(60.0, float(settings.get("shell.exec_timeout", 600)))
        if phase in ("llm", "llm_stream"):
            return max(30.0, float(settings.get("llm_gateway.timeout", 120))) * (max(0, _i(rt.get("retries"))) + 1)
    except Exception: pass
    return 60.0

def _sig(rt, doc):
    """err_kind＋last_err＋表内 paused/note 合并成可判文本。"""
    return "%s %s %s" % (str(rt.get("err_kind") or ""), str(rt.get("last_err") or "")[:200],
                         str(doc.get("paused") or "") + " " + str(doc.get("note") or ""))
def _busy_run(c):
    """该表派发仍在跑＝QQ 派发队列非空或 worker 刚有动作。"""
    try:
        import qq_dispatch as qd; st = qd.stats()
        return int(st.get("depth") or 0) > 0 or time.time() - float(st.get("last") or 0) < float(c.get("busy_grace", 120))
    except Exception: return False
def _listener_zombie(c):
    """监听器僵尸＝qq_watch 判 pid 死或心跳过期（无 pid 文件不判，宁缺勿误杀）。"""
    try:
        import qq_watch as qw; s = qw.status(c.get("sms"))
        return bool(s.get("zombie")) and bool(s.get("pid"))
    except Exception: return False
def _shell_dead(c):
    """壳心跳 shell/alive.json 过期（无该文件＝不判，宁缺勿误杀）。"""
    try:
        p = os.path.join(c.get("sms") or resolve_home.ensure(), "shell", "alive.json")
        if not os.path.isfile(p): return False
        return time.time() - float(os.path.getmtime(p)) > float(c.get("shell_alive_ttl", 180))
    except Exception: return False
def _proc_hung(c):
    """在途子进程真阻塞＝proc_guard 点名：静默超自身阈且 CPU≈0／等交互输入／刷屏死循环。"""
    try:
        import proc_guard as pg
        h = pg.hung(c.get("sms"))
        if h:
            e = h[0]
            return "%s（命令「%s」·已跑 %.0fs·状态 %s）" % (e.get("detail"), str(e.get("name"))[:60],
                                                     time.time() - float(e.get("started") or time.time()),
                                                     e.get("kind"))
    except Exception:
        pass
    return ""


def classify(doc, age, cfg=None, rt=None):
    """主入口：回 (kind, detail)。busy/unknown 交上层静默；network/model/process 才告警。"""
    c = dict(cfg or {}); doc = doc or {}; rt = rt if rt is not None else rr.read(c.get("sms"))
    ph = str(rt.get("phase") or ""); ts = float(rt.get("ts") or 0) or 0.0
    pid = _i(rt.get("pid")); att = _i(rt.get("attempt")); ret = _i(rt.get("retries"))
    low = _sig(rt, doc).lower(); age = int(age or 0)
    hg = _proc_hung(c)
    if hg:
        return "process", hg
    inwin = ph in BUSY and bool(pid) and rr.alive(pid) and (time.time() - ts) < window(ph, rt)
    ek = str(rt.get("err_kind") or "")
    if inwin and (not ek or (ek == "network" and ret > 0)):
        return "busy", "phase=%s 在宽限窗内（%ds·pid=%d 活）" % (ph, int(window(ph, rt)), pid)
    if str(doc.get("id") or "") and ph in BUSY and _busy_run(c):
        return "busy", "该表派发仍在跑（qq_dispatch 队列/worker 活跃）"
    if ph in ACTIVE and pid and _fresh(rt, c) and not rr.alive(pid):
        return "process", "runtime.pid=%d 已死（phase=%s·ts 距今 %ds）" % (pid, ph, int(time.time() - ts))
    if _listener_zombie(c): return "process", "QQ 监听进程僵尸（pid 死或心跳过期）"
    if _shell_dead(c): return "process", "壳心跳 shell/alive.json 过期"
    if str(rt.get("err_kind") or "") == "network" or any(k in low for k in NET_KW):
        return "network", str(rt.get("last_err") or "网络类异常")[:80]
    if str(rt.get("err_kind") or "") == "model" or any(k in low for k in MOD_KW):
        return "model", "网关/模型侧不可重试（4xx 或空返回）：" + str(rt.get("last_err") or "")[:80]
    return "unknown", "phase=%s·age=%ds·无网络/模型/进程证据（静默不告警）" % (ph or "-", age)
def _fresh(rt, c):
    """runtime.ts 距今在可信窗内才拿它下结论（陈旧记录只作旁证，防误杀）。"""
    try: return (time.time() - float(rt.get("ts") or 0)) < float(c.get("rt_trust", 3600))
    except Exception: return False
if __name__ == "__main__":
    sms = resolve_home.ensure(); c = {"sms": sms}
    cases = {"network": {"phase": "llm", "pid": os.getpid(), "ts": time.time(), "attempt": 3, "retries": 0,
                         "err_kind": "network", "last_err": "<urlopen error timed out>"},
             "net_retrying": {"phase": "llm", "pid": os.getpid(), "ts": time.time(), "attempt": 1, "retries": 2,
                              "err_kind": "network", "last_err": "<urlopen error 10054>"},
             "model": {"phase": "llm", "pid": os.getpid(), "ts": time.time(), "attempt": 1, "retries": 0,
                       "err_kind": "model", "last_err": "HTTP Error 401"},
             "process": {"phase": "exec", "pid": 999999, "ts": time.time(), "attempt": 0, "retries": 0, "err_kind": "", "last_err": ""},
             "busy": {"phase": "exec", "pid": os.getpid(), "ts": time.time(), "attempt": 0, "retries": 3, "err_kind": "", "last_err": ""},
             "unknown": {"phase": "idle", "pid": os.getpid(), "ts": time.time() - 99999, "attempt": 0, "retries": 0, "err_kind": "", "last_err": ""}}
    doc = {"id": "conv-selftest-0001", "subtasks": [{"id": "t1", "status": "pending"}]}
    for k, rt in cases.items():
        got = classify(doc, 400, c, rt); print("%-8s -> %-8s %s" % (k, got[0], got[1]))
