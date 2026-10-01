#!/usr/bin/env python3
"""dream_watch.py — 做梦「真在后台跑」校验＋顶栏徽标（2026-09-29 用户「检查是否真的在后台执行」「做梦时 SHELL 顶部栏有提示」）：dream_bg 锁文件只记 pid|ts，进程崩了锁还在＝假在跑，故三重判活——① 锁内 pid 经 Windows OpenProcess（非 os.kill，Win 下会误杀）真存在 ② 心跳 <SMS_HOME>/chains/dream.heartbeat（pid|ts|step）新鲜（<HB 秒）③ 锁龄 < dream_bg.STALE；beat(step) 每步写心跳，state() 回 running/pid/since/step/beat_age/lock_age/zombie，僵尸判真＝锁在但 pid 死或心跳超时（:dream status 据此报「后台未真执行」并落 error 链）；badge() 供顶栏：跑＝「◌做梦·<step>」、僵尸＝「⚠做梦中断」、空闲＝空串。用法：python -B dream_watch.py status|beat <步骤>|badge"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home
HB = 900.0  # 心跳窗口：合并近义单步可 >4min（全库两两比对），过短会把在跑的做梦误判为僵尸
def _sms(sms=None): return sms or resolve_home.ensure()
def _f(sms, n): return os.path.join(sms, "chains", n)
def _rd(sms, n):
    try: return open(_f(sms, n), encoding="utf-8").read().strip()
    except Exception: return ""
def _alive(pid):
    if not pid: return False
    if os.name != "nt":
        try: os.kill(pid, 0); return True
        except Exception: return False
    import ctypes; k = ctypes.windll.kernel32
    h = k.OpenProcess(0x1000, False, pid); c = ctypes.c_ulong()
    r = bool(h) and k.GetExitCodeProcess(h, ctypes.byref(c)) and c.value == 259
    if h: k.CloseHandle(h)
    return bool(r)
def beat(step, sms=None):
    sms = _sms(sms)
    try:
        open(_f(sms, "dream.heartbeat"), "w", encoding="utf-8").write("%d|%d|%s" % (os.getpid(), time.time(), str(step)[:24])); return True
    except Exception: return False
def state(sms=None):
    sms = _sms(sms); lk = _rd(sms, "dream.lock").split("|"); p = lk[0]
    pid = int(p) if p.isdigit() else 0; since = float(lk[1]) if len(lk) > 1 and lk[1].replace(".", "", 1).isdigit() else 0.0
    hb = _rd(sms, "dream.heartbeat").split("|"); hp = int(hb[0]) if hb and hb[0].isdigit() else 0
    ht = float(hb[1]) if len(hb) > 1 and hb[1].replace(".", "", 1).isdigit() else 0.0
    live = _alive(hp or pid); age = round(time.time() - ht, 1) if ht else None
    return {"running": bool(live and age is not None and age < HB), "pid": pid or hp, "since": time.strftime("%H:%M:%S", time.localtime(since)) if since else None,
            "step": hb[2] if len(hb) > 2 else "", "beat_age": age, "lock_age": round(time.time() - since, 1) if since else None,
            "zombie": bool(lk[0]) and (not live or (age is not None and age >= HB))}
def badge(sms=None):
    s = state(sms)
    return ("◌做梦·" + (s["step"] or "进行中")) if s["running"] else ("⚠做梦中断" if s["zombie"] else "")
if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]
    print(str(beat(" ".join(a[1:]) or "cli")) if a[0] == "beat" else badge() if a[0] == "badge" else __import__("json").dumps(state(), ensure_ascii=False))