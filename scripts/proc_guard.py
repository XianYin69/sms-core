#!/usr/bin/env python3
"""proc_guard.py — 子进程「阻塞画像」探针＋在途登记（2026-10-01 用户诉求「增强 sms 在子进程阻塞下的检测与应对」）。
补旧版三盲区：①静默看门狗只数「有没有新输出行」——把「闷头算不打印」的合法长任务误杀，又把「CPU=0 且无输出」的真死锁白拖满静默窗；②子进程 pid 从不进活性记录（runtime_rec 记的是 SMS 自身 pid，永远活着）→ stall_class 只能判 busy，看门狗/顶栏/QQ 都不知道「到底哪条命令卡住、卡了几秒」；③kill_tree 之后原读循环 readline 仍可能被「已脱离本树的后代」攥着的管道写端永久挂住＝最恶劣的子进程阻塞（壳再也拿不回控制权）。
能力：cpu_ms/children/descendants（纯 stdlib ctypes·不依赖 psutil）＋在途登记表 <SMS_HOME>/runtime/procs.json（register/beat/unregister/snapshot）＋classify 阻塞归因（waiting_input|computing|deadlock|flood|orphan_pipe|exited|running）＋drain（杀树后有界排空管道，超时即点名残留后代）。
用法：python -B proc_guard.py status | probe <pid> | classify <pid>"""
import os, sys, json, time, threading, ctypes as C
import ctypes.wintypes  # noqa: F401（C.wintypes 显式可用）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, atomic_io as ai

K32 = C.windll.kernel32 if os.name == "nt" else None
if K32:  # 64 位下句柄必须按 HANDLE 返回，截断成 int 会让 OpenProcess 假失败
    K32.OpenProcess.restype = C.wintypes.HANDLE
    K32.CreateToolhelp32Snapshot.restype = C.wintypes.HANDLE
    K32.CloseHandle.argtypes = [C.wintypes.HANDLE]
PROMPT_KW = ("y/n", "[y/n]", "password", "passphrase", "token", "secret", "login",
             "press enter", "input(", "确认", "密码", "输入", "是否", "按任意键", "continue?")
CPU_BUSY_MS = 300
FLOOD_LPS = 400
PROMPT_GRACE = 8.0
STALE = 900

def cpu_ms(pid):
    """进程累计 CPU 毫秒（kernel+user）；取不到回 -1。"""
    try:
        pid = int(pid)
    except Exception:
        return -1
    if pid <= 0:
        return -1
    if K32:
        h = K32.OpenProcess(0x1000, False, pid)
        if not h:
            return -1
        try:
            ft = [C.wintypes.FILETIME() for _ in range(4)]
            if not K32.GetProcessTimes(h, *[C.byref(x) for x in ft]):
                return -1
            ms = lambda f: ((f.dwHighDateTime << 32 | f.dwLowDateTime) // 10000)
            return ms(ft[2]) + ms(ft[3])
        except Exception:
            return -1
        finally:
            K32.CloseHandle(h)
    try:
        f = open("/proc/%d/stat" % pid).read().split()
        return (int(f[13]) + int(f[14])) * 1000 // os.sysconf("SC_CLK_TCK")
    except Exception:
        return -1


class _PE(C.Structure):
    _fields_ = [("dwSize", C.wintypes.DWORD), ("cntUsage", C.wintypes.DWORD),
                ("th32ProcessID", C.wintypes.DWORD), ("th32DefaultHeapID", C.c_size_t),
                ("th32ModuleID", C.wintypes.DWORD), ("cntThreads", C.wintypes.DWORD),
                ("th32ParentID", C.wintypes.DWORD), ("pcPriClassBase", C.c_long),
                ("dwFlags", C.wintypes.DWORD), ("szExeFile", C.c_wchar * 260)]


def children(pid):
    """直接子进程 pid 列表（Toolhelp32Snapshot / /proc）；取不到回 []（宁缺勿误判）。"""
    out = []
    try:
        pid = int(pid)
    except Exception:
        return out
    if K32:
        h = K32.CreateToolhelp32Snapshot(2, 0)
        if not h or int(h) == -1 or int(h) == 0:
            return out
        e = _PE(); e.dwSize = C.sizeof(_PE)
        try:
            ok = K32.Process32FirstW(h, C.byref(e))
            while ok:
                if e.th32ParentID == pid:
                    out.append(int(e.th32ProcessID))
                ok = K32.Process32NextW(h, C.byref(e))
        except Exception:
            pass
        finally:
            K32.CloseHandle(h)
        return out
    try:
        for d in os.listdir("/proc"):
            if d.isdigit():
                st = open("/proc/%s/stat" % d).read().split()
                if len(st) > 3 and int(st[3]) == pid:
                    out.append(int(d))
    except Exception:
        pass
    return out


def descendants(pid, cap=64):
    """整棵后代 pid（BFS·限量防失控）。"""
    seen, q = set(), [int(pid)]
    while q and len(seen) < cap:
        for c in children(q.pop(0)):
            if c not in seen:
                seen.add(c); q.append(c)
    return sorted(seen)


def alive(pid):
    try:
        import runtime_rec as rr
        return rr.alive(pid)
    except Exception:
        return False


def looks_like_prompt(line):
    s = str(line or "").strip().lower()
    if not s:
        return False
    return s.endswith("?") or any(k in s for k in PROMPT_KW)


_MEM = {}
_lock = threading.Lock()
_last_flush = [0.0]


def _rf(sms=None):
    return os.path.join(sms or resolve_home.ensure(), "runtime", "procs.json")


def _save(d, sms=None):
    try:
        p = _rf(sms)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        ai.wjson(p, d)
        return True
    except Exception:
        return False


def _flush(force=False, sms=None):
    """内存态落盘（≥1s 或强制才写·绝不为记账把业务拖慢）。"""
    now = time.time()
    if not force and now - _last_flush[0] < 1.0:
        return False
    _last_flush[0] = now
    with _lock:
        d = dict(_MEM)
    live = {k: v for k, v in d.items() if now - float(v.get("started") or 0) < STALE}
    return _save(live, sms)


def register(pid, name="", budget=0, stall=0, stage="exec", sms=None):
    """子进程起跑即登记（在途表＝看门狗/顶栏/QQ 的「谁卡住了」真源）。"""
    now = time.time()
    e = {"pid": int(pid), "name": str(name)[:160], "state": "running", "stage": str(stage),
         "started": now, "last_out": now, "lines": 0, "tail": "", "prompt": False,
         "budget": int(budget or 0), "stall": int(stall or 0), "cpu0": cpu_ms(pid), "cpu": -1, "why": ""}
    with _lock:
        _MEM[str(e["pid"])] = e
    _flush(force=True, sms=sms)
    return e


def beat(pid, lines=None, tail="", sms=None):
    """每出一行调一次（只改内存·不写盘）。"""
    with _lock:
        e = _MEM.get(str(int(pid)))
        if not e:
            return None
        e["last_out"] = time.time()
        if lines is not None:
            e["lines"] = int(lines)
        if tail != "":
            e["tail"] = str(tail)[-160:]
            e["prompt"] = looks_like_prompt(tail)
    _flush(sms=sms)
    return e


def unregister(pid, state="done", why="", rc=None, sms=None):
    with _lock:
        e = _MEM.pop(str(int(pid)), None)
    if e is None:
        return None
    e.update({"state": state, "why": str(why)[:200], "ended": time.time()})
    if rc is not None:
        e["rc"] = rc
    d = ai.rjson(_rf(sms), default={}) or {}
    d[str(int(pid))] = dict(e, state=state)
    _save({k: v for k, v in d.items() if time.time() - float(v.get("started") or 0) < STALE}, sms)
    return e


def sample(pid):
    """CPU 采样（看门狗每巡检一次调）：回本窗 CPU 毫秒增量与窗长。"""
    k = str(int(pid))
    with _lock:
        e = _MEM.get(k)
    if not e:
        return -1, 0.0
    now = time.time(); c = cpu_ms(pid)
    prev = e.get("cpu_prev") if e.get("cpu_prev") is not None else e.get("cpu0", -1)
    pts = float(e.get("cpu_ts") or e.get("started") or now)
    dt = max(0.25, now - pts)
    d = (c - int(prev)) if (c >= 0 and int(prev or -1) >= 0) else -1
    with _lock:
        if k in _MEM:
            _MEM[k].update({"cpu_prev": c, "cpu_ts": now, "cpu": c})
    return d, dt


def snapshot(sms=None, prune=True):
    """跨进程读在途表（清 STALE 残留）。"""
    d = ai.rjson(_rf(sms), default={}) or {}
    now = time.time()
    out = [v for v in d.values() if isinstance(v, dict) and now - float(v.get("started") or 0) < STALE]
    if prune and len(out) != len(d):
        _save({str(v["pid"]): v for v in out}, sms)
    return sorted(out, key=lambda x: -float(x.get("started") or 0))


def line_rate(pid, lines):
    """本窗行速率（增量行/增量秒）：旧版用「累计行/累计秒」＋age>2 门槛，
    1~2 秒内刷屏几万行会在门槛前就跑完（自测 flood 用例漏判）——改按窗算。"""
    k = str(int(pid))
    with _lock:
        e = _MEM.get(k)
        if not e:
            return -1.0, 0.0
        now = time.time()
        pl = int(e.get("lines_prev") if e.get("lines_prev") is not None else e.get("lines") or 0)
        pts = float(e.get("lines_ts") or e.get("started") or now)
        dt = now - pts
        d = max(0, int(lines) - pl)
        e["lines_prev"] = int(lines)
        e["lines_ts"] = now
    return (d / dt if dt > 0 else -1.0), dt


def classify(pid=None, entry=None, sms=None):
    """阻塞归因：回 (kind, detail)。kind∈exited|waiting_input|flood|computing|deadlock|running。"""
    e = entry or {}
    if not e and pid:
        e = next((x for x in snapshot(sms) if int(x.get("pid") or 0) == int(pid)), {})
    if not e:
        return "unknown", "不在途表（未登记或已清）"
    p = int(e.get("pid") or 0); now = time.time()
    sil = now - float(e.get("last_out") or e.get("started") or now)
    age = now - float(e.get("started") or now)
    lines = int(e.get("lines") or 0)
    if not alive(p):
        return "exited", "pid=%d 已退出（跑 %.0fs·输出 %d 行）" % (p, age, lines)
    d, dt = sample(p)
    rate = (d / dt) if d >= 0 else -1
    sl = float(e.get("stall") or 0)
    grace = min(PROMPT_GRACE, sl) if sl else PROMPT_GRACE
    if e.get("prompt") and sil >= grace:
        return "waiting_input", "pid=%d 末行像交互提示（「%s」）静默 %.0fs＝在等输入，非交互壳等不到" % (p, (e.get("tail") or "")[-60:], sil)
    rl, wdt = line_rate(p, lines)
    if rl >= FLOOD_LPS and wdt >= 0.3:
        return "flood", "pid=%d 本窗输出 %.0f 行/秒（共 %d 行·窗 %.1fs）＝疑似死循环刷屏" % (p, rl, lines, wdt)
    if rate >= CPU_BUSY_MS:
        return "computing", "pid=%d 静默 %.0fs 但 CPU 活跃（%.0f ms/s）＝闷头算不打印，勿误杀" % (p, sil, rate)
    if sl and sil >= sl:
        return "deadlock", "pid=%d 静默 %.0fs 且 CPU≈0＝判死锁/等外部资源" % (p, sil)
    return "running", "pid=%d 活着（静默 %.0fs·CPU %.0f ms/s）" % (p, sil, rate)


def hung(sms=None):
    """供 stall_class/顶栏/QQ 查：在途且已超自身静默阈的子进程（带归因）。"""
    out = []
    for e in snapshot(sms):
        if str(e.get("state")) != "running":
            continue
        k, det = classify(entry=dict(e), sms=sms)
        sl = float(e.get("stall") or 0)
        sil = time.time() - float(e.get("last_out") or e.get("started") or time.time())
        if k in ("deadlock", "waiting_input", "flood") or (sl and sil >= sl and k != "computing"):
            out.append(dict(e, kind=k, detail=det))
    return out


def drain(p, buf, deadline=5.0, name="命令", on_line=None, prefix=""):
    """杀树后有界排空管道：正常＝EOF 秒回；超时＝管道被残留后代攥着（旧版在此永久挂住＝真阻塞）。
    回 (ok, why)；ok=False 时调用方必须收口返回，绝不再 readline。"""
    import threading
    box = {"closed": False}

    def rd():
        try:
            for ln in iter(p.stdout.readline, ""):
                if ln and ln.strip():
                    buf.append(ln.rstrip())
                    if on_line:
                        try:
                            on_line(prefix + ln.rstrip())
                        except Exception:
                            pass
        except Exception:
            pass
        finally:
            box["closed"] = True
    try:
        if p.stdout is None:
            return True, ""
    except Exception:
        return True, ""
    t = threading.Thread(target=rd, name="pg-drain", daemon=True)
    t.start(); t.join(max(1.0, float(deadline)))
    if box["closed"]:
        return True, ""
    threading.Thread(target=lambda: (p.stdout.close() if p.stdout else None),
                     name="pg-drain-close", daemon=True).start()
    kids = [k for k in descendants(int(getattr(p, "pid", 0) or 0)) if alive(k)]
    return False, ("「%s」杀树后管道仍被持有（残留后代 pid=%s）——已强制收口，输出截至 %d 行；"
                   "该命令会脱离本壳继续跑，产物可能不完整") % (name, ",".join(map(str, kids)) or "已脱离本树/未知", len(buf))


def status(sms=None):
    import json
    return json.dumps({"procs": snapshot(sms), "hung": hung(sms),
                       "thresholds": {"cpu_busy_ms_per_s": CPU_BUSY_MS, "flood_lines_per_s": FLOOD_LPS,
                                      "prompt_grace_s": PROMPT_GRACE}}, ensure_ascii=False)


if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]
    if a[0] == "probe":
        p = int(a[1]); print(json.dumps({"pid": p, "alive": alive(p), "cpu_ms": cpu_ms(p),
                                         "children": children(p), "descendants": descendants(p)}, ensure_ascii=False))
    elif a[0] == "classify":
        k, d = classify(int(a[1])); print(json.dumps({"kind": k, "detail": d}, ensure_ascii=False))
    else:
        print(status())
