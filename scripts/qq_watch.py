#!/usr/bin/env python3
"""qq_watch.py — QQ 入站监听器「真在后台跑」判活＋顶栏徽标（2026-09-29·与做梦 dream_watch 同范式）：pid 文件 <SMS_HOME>/qq/listen.pid（pid|ts）＋心跳文件 qq/listen.heartbeat（pid|ts|state）双证——① OpenProcess 真 pid（绝不用 os.kill(pid,0)，Windows 下会误杀）② 心跳新鲜（窗口 HB=180s·重连退避最长 60s 不误判僵尸）；status() 回 running/pid/beat_age/state/zombie/ready，僵尸＝记了 pid 但进程已死或心跳超时（:qq lstatus 据此报「后台未真执行」）；badge() 供顶栏：在听＝「◌QQ入站·<state>」、僵尸＝「⚠QQ监听中断」、未启＝空串；log() 追加 qq/listen.log 业务流水，tail() 取末 n 行。用法：python -B qq_watch.py status|badge|beat <状态>|tail [n]。"""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, qq_push as qp
HB = 180.0
def _d(sms=None): return os.path.join(sms or resolve_home.ensure(), "qq")
def _f(n, sms=None): return os.path.join(_d(sms), n)
def _rd(n, sms=None):
    try: return open(_f(n, sms), encoding="utf-8").read().strip()
    except Exception: return ""
def _pid(sms=None):
    try: return int(_rd("listen.pid", sms).split("|")[0])
    except Exception: return 0
def alive(sms=None):
    p = _pid(sms)
    if not p: return False
    if os.name != "nt":
        try: os.kill(p, 0); return True
        except Exception: return False
    import ctypes; k = ctypes.windll.kernel32; h = k.OpenProcess(0x1000, False, p); c = ctypes.c_ulong()
    r = bool(h) and k.GetExitCodeProcess(h, ctypes.byref(c)) and c.value == 259
    if h: k.CloseHandle(h)
    return bool(r)
def beat(state, sms=None):
    try: open(_f("listen.heartbeat", sms), "w", encoding="utf-8").write("%d|%d|%s" % (os.getpid(), time.time(), str(state)[:60])); return True
    except Exception: return False
def _hb(sms=None):
    try: p = _rd("listen.heartbeat", sms).split("|"); return time.time() - float(p[1]), (p[2] if len(p) > 2 else "")
    except Exception: return 1e9, ""
def status(sms=None):
    r = alive(sms); age, st = _hb(sms); pid = _pid(sms); fresh = age < HB
    return {"running": r, "pid": pid, "beat_age": None if age > 1e8 else round(age, 1), "state": st, "fresh": fresh,
            "zombie": bool(pid) and (not r or not fresh), "ready": qp.ready()}
def badge(sms=None):
    d = status(sms)
    if d["zombie"]: return "⚠QQ监听中断"
    return ("◌QQ入站·" + (d["state"] or "?")) if d["running"] and d["fresh"] else ""
def log(txt, sms=None):
    try: os.makedirs(_d(sms), exist_ok=True); open(_f("listen.log", sms), "a", encoding="utf-8").write(time.strftime("%m-%d %H:%M:%S ") + str(txt) + "\n")
    except Exception: pass
def tail(n=12, sms=None):
    try: return "\n".join(open(_f("listen.log", sms), encoding="utf-8", errors="replace").read().splitlines()[-int(n):]) or "（日志空）"
    except Exception: return "（无日志）"
if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]
    print(json.dumps(status(), ensure_ascii=False, indent=1) if a[0] == "status" else badge() if a[0] == "badge"
          else str(beat(" ".join(a[1:]) or "manual")) if a[0] == "beat" else tail(a[1] if len(a) > 1 else 12) if a[0] == "tail" else __doc__.strip()[:260])
