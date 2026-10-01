#!/usr/bin/env python3
"""runtime_rec.py — SMS 本体「活性记录」（2026-09-29 用户诉求「改 SMS 本体 scripts：卡住看门狗分清原因＋不误杀＋带重试计数」第1步）：<SMS_HOME>/runtime.json 单文件记 {ts,pid,sess,conv,phase,attempt,retries,last_err,err_kind}——phase∈llm|llm_stream|qq_ws|qq_push|exec|idle、err_kind∈network|model|http4xx|""、attempt＝已重试几次、retries＝还剩几次；写点＝gateway/gateway_sse 每次尝试（含 on_try）、qq_session 连上/重连/gaveup、qq_push 发送、agent_dispatch exec 长任务起止；一律 atomic_io.wjson 原子写、任何异常静默（绝不因记活性把业务拖崩）。用法：rec("llm", attempt=1, retries=2, err=e)／read()／alive(pid)（ctypes OpenProcess·不用 os.kill 防误杀）／kind_of(e)／idle()。"""
import os, sys, time, json, ctypes
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, atomic_io as ai
NET = ("urlerror", "timeout", "timed out", "connection", "reset by peer", "broken pipe", "getaddrinfo",
       "unreachable", "10054", "10060", "10053", "ssl", "网络", "断连", "eof occurred")
MODEL = ("重试耗尽", "空返回", "no choices", "empty response", "finish=length", "content_policy", "内容安全")


def path(sms=None): return os.path.join(sms or resolve_home.ensure(), "runtime.json")
def read(sms=None):
    """读活性记录（无文件/坏档一律回 {}，调用方按空处理）。"""
    try: return ai.rjson(path(sms), default={}) or {}
    except Exception: return {}
def alive(pid):
    """ctypes OpenProcess 真判活（Windows 下 os.kill(pid,0) 会误杀·同 qq_watch 范式）；非 nt 退 os.kill。"""
    try:
        pid = int(pid or 0)
        if pid <= 0: return False
        if os.name != "nt":
            os.kill(pid, 0); return True
        k = ctypes.windll.kernel32; h = k.OpenProcess(0x1000, False, pid); c = ctypes.c_ulong()
        r = bool(h) and k.GetExitCodeProcess(h, ctypes.byref(c)) and c.value == 259
        if h: k.CloseHandle(h)
        return bool(r)
    except Exception: return False
def kind_of(e):
    """异常→错误类别：HTTP 4xx（408/425/429 除外）＝model 不可重试；5xx/429/超时/断连＝network；其余按文本判，判不出回 ""。"""
    try:
        import urllib.error
        if isinstance(e, urllib.error.HTTPError):
            return "model" if (e.code < 500 and e.code not in (408, 425, 429)) else "network"
        if isinstance(e, (urllib.error.URLError, TimeoutError, ConnectionError, OSError)): return "network"
    except Exception: pass
    s = str(e).lower()
    if any(x in s for x in NET): return "network"
    if any(x in s for x in MODEL): return "model"
    return ""


def _ctx():
    """sess/conv 尽力取（agent_ctx 线程上下文＋chains），取不到留空，不抛。"""
    conv = ""; sess = ""
    try: import agent_ctx as ac; conv = str((ac.cur() or {}).get("conv") or "")
    except Exception: pass
    try:
        import chains as ch; sess = str(ch.cur_sess() or "")
    except Exception: pass
    return sess, conv
def rec(phase, attempt=None, retries=None, err=None, sms=None, keep=True):
    """写一条活性记录（异常静默）：phase 必填；err 给异常对象时自动算 err_kind/last_err；keep＝保留上一轮 last_err（成功尝试不清空，供看门狗回溯原因）。"""
    try:
        p = path(sms); old = read(os.path.dirname(p)) if keep else {}
        sess, conv = _ctx(); ek = ""; le = ""
        if err is not None:
            if str(err) == "": ek = ""; le = ""
            else: ek = kind_of(err); le = (str(err)[:200] or type(err).__name__)
        elif keep: ek = str(old.get("err_kind") or ""); le = str(old.get("last_err") or "")
        d = {"ts": time.time(), "pid": os.getpid(), "sess": sess, "conv": conv or str(old.get("conv") or ""),
             "phase": phase, "attempt": int(attempt) if attempt is not None else int(old.get("attempt") or 0),
             "retries": int(retries) if retries is not None else int(old.get("retries") or 0),
             "last_err": le, "err_kind": ek}
        ai.wjson(p, d); return d
    except Exception: return {}
def idle(sms=None):
    """长任务收尾：phase=idle、清 err（异常静默）。"""
    return rec("idle", err="", sms=sms, keep=False)
if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]
    if a[0] == "rec": print(json.dumps(rec(a[1], *(int(x) if x.isdigit() else None for x in a[2:4])), ensure_ascii=False))
    elif a[0] == "idle": print(idle())
    elif a[0] == "alive": print(alive(a[1]))
    else:
        d = read(); d["self_alive"] = alive(d.get("pid")); d["path"] = path()
        print(json.dumps(d, ensure_ascii=False, indent=1))
