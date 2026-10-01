#!/usr/bin/env python3
"""dream_bg.py — 做梦后台拉起器（批17：做梦跑在后台分离子进程，不占对话前台）：maybe 到期→分离 spawn `python -B dream.py run`（stdout/stderr→<SMS_HOME>/logs/dream.log·DETACHED 不随壳退出而亡）；chains/dream.lock（pid|ts）防重复拉起，超 45 分钟视为陈旧可再拉（崩溃自收），run 起首/漫游前后 stamp 续锁、收口 unlock。用法：python -B dream_bg.py spawn|running|unlock"""
import os, sys, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, settings
STALE = 45 * 60
def _lk(sms): return os.path.join(sms, "chains", "dream.lock")
def stamp(sms):
    try: os.makedirs(os.path.dirname(_lk(sms)), exist_ok=True); open(_lk(sms), "w").write("%d|%d" % (os.getpid(), time.time())); return True
    except Exception as e:
        import chain_error; chain_error.hook("dream", "dream_bg.spawn", str(e)); return False
def running(sms):
    try: return time.time() - float(open(_lk(sms)).read().split("|")[1]) < STALE
    except Exception: return False
def spawn(sms):
    if not settings.get("dream.enabled", True, sms=sms) or running(sms): return False
    try:
        os.makedirs(os.path.join(sms, "logs"), exist_ok=True); f = open(os.path.join(sms, "logs", "dream.log"), "ab")
        stamp(sms)
        subprocess.Popen([sys.executable, "-B", os.path.join(os.path.dirname(os.path.abspath(__file__)), "dream.py"), "run"],
                         stdin=subprocess.DEVNULL, stdout=f, stderr=f, cwd=os.path.dirname(os.path.abspath(__file__)),
                         env=dict(os.environ, SMS_BG="1"),
                         creationflags=(0x00000008 | 0x00000200) if os.name == "nt" else 0)
    except Exception: return False
    return True
def unlock(sms):
    try: os.remove(_lk(sms))
    except Exception: pass
if __name__ == "__main__":
    sms = resolve_home.ensure(); c = sys.argv[1] if len(sys.argv) > 1 else "spawn"
    print(str(spawn(sms)) if c == "spawn" else str(running(sms)) if c == "running" else (unlock(sms), "unlocked")[1] if c == "unlock" else "用法：spawn|running|unlock")
