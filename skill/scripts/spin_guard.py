#!/usr/bin/env python3
"""spin_guard.py — 壳自身「空转卡死」哨兵（2026-10-03 用户「解决卡死问题」）。

现场：sess-20261003-133957 的 Textual 壳 pid 14052 单线程 95% CPU 连烧 76 分钟、零输出
零产物，任务总览 134231-131 余 3/5、135023-493 余 7/9 永不推进。机制＝自增强死循环：
某轮 worker 未收口 → busy 恒真 → ProgressBar(total=None) 常显 → Textual Bar.auto_refresh
=1/15 每帧整屏重绘 → RichLog 未设 max_lines、logbuf 无上限（该会话抽帧/OCR 海量输出）
→ 重绘代价爆炸 → UI 消息泵被自己饿死 → 收口消息再也处理不掉 → busy 永不清、条永不藏。
旧盲区：proc_guard/stall_class 只盯子进程且把 CPU 高一律判 computing（勿误杀），壳自身
空转在监控里隐形；全 scripts 无 faulthandler＝抓不到栈。

本模块补壳自身：① faulthandler 全程开（dump_traceback_later 独立线程，GIL 被死循环攥着
也能抓栈）；② 活性只认真进展（输出行/产物落盘/任务总览行 done），UI 定时器自转不算进展；
③ 判自旋即分级：抓栈→藏 #prog 停动画（立刻还核子）→stop_channel 停在轮→仍不止则
shell_lifecycle.restart 自愈。零焦点侵入：不动前台窗口/不动光标/不激活窗口。
批29 修（2026-10-03 22:49 取证）：旧 arm() 的 dump_traceback_later(repeat=True)
与「有无进展」无关，每个壳每 120s 无条件把全线程栈灌进 spin.log
（现场 3.8MB/5261 段空闲栈，真自旋被噪声淹没）。
现改进展驱动：_watch 判可疑才挂一次性转栈，beat() 真进展即撤销；
spin.log 另加体积封顶轮转（shell.spin_log_max_kb 默认 512KB 只留尾部）。
用法：python -B spin_guard.py status|probe <pid>|selftest"""
import os, sys, time, json, ctypes, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SMS = None
def _home():
    global SMS
    if not SMS:
        import resolve_home; SMS = resolve_home.ensure()
    return SMS
def _cfg(k, d):
    try:
        import settings; return float(settings.get("shell." + k, d))
    except Exception: return float(d)
ST = {"beat": time.time(), "bkind": "boot", "app": None, "cpu": 0.0, "silent": 0.0,
      "verdict": "ok", "hits": 0, "armed": False, "hide_req": False, "last_ext": 0.0, "tid": ""}
_FH = {"fh": None, "path": "", "armed": False, "until": 0.0, "fired": 0.0, "susp": False}
class _FT(ctypes.Structure):
    """FILETIME（lo/hi 两个 DWORD）——进程 CPU 时间戳载体。"""
    _fields_ = [("lo", ctypes.c_uint32), ("hi", ctypes.c_uint32)]
def _cpu_ms(pid=0):
    """本进程（pid=0）或指定 pid 的 kernel+user CPU 毫秒；取不到回 -1。纯 ctypes，零依赖。
    64 位实测坑：GetCurrentProcess 的伪句柄 (HANDLE)-1 取回是 18446744073709551615，不给
    GetProcessTimes 声明 argtypes 就按 C int 回传 → OverflowError → 自测恒 -1 → rate 恒 0
    → 壳自身空转永远检不出（正是本修复要治的盲区）；故 argtypes 必声明＋伪句柄兜底。"""
    try:
        k = ctypes.windll.kernel32
        import ctypes.wintypes as wt
        LP = ctypes.POINTER(_FT)
        k.GetCurrentProcess.restype = wt.HANDLE; k.OpenProcess.restype = wt.HANDLE
        k.GetProcessTimes.restype = wt.BOOL
        k.GetProcessTimes.argtypes = [wt.HANDLE, LP, LP, LP, LP]
        own = (not pid) or int(pid) == os.getpid()
        h = k.GetCurrentProcess() if own else k.OpenProcess(0x1000, False, int(pid))
        if not h and own:
            h = k.OpenProcess(0x1000, False, os.getpid())   # 伪句柄不可用时的兜底
        if not h: return -1.0
        c, e, kr, us = _FT(), _FT(), _FT(), _FT()
        ok = k.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(kr), ctypes.byref(us))
        if not own: k.CloseHandle(h)
        _v = lambda f: (f.hi << 32) | f.lo
        return (_v(kr) + _v(us)) / 10000.0 if ok else -1.0
    except Exception: return -1.0
def beat(kind="out", tid=""):
    """壳在「真进展」处调用：输出行 / 产物落盘 / 任务总览行 done。UI 定时器自转绝不可调本函数。"""
    ST["beat"] = time.time(); ST["bkind"] = str(kind)[:24]
    if tid: ST["tid"] = str(tid)
    _cancel_dump("progress")   # 进展驱动：真进展一到即撤销待落转栈（UI 定时器自转不走这里）
def _ext_new(since):
    """外部进展证据：工作区 tmp 最新 mtime、runtime/procs.json mtime、tasks/*.json 最新 mtime。
    取不到一律回 0（宁缺勿误杀）。"""
    best = 0.0
    try:
        h = _home()
        for pat, root in ((None, os.path.join(h, "runtime")), ("*.json", os.path.join(h, "tasks"))):
            if not os.path.isdir(root): continue
            if pat is None:
                p = os.path.join(root, "procs.json")
                if os.path.isfile(p): best = max(best, os.path.getmtime(p))
            else:
                import glob as G
                for p in G.glob(os.path.join(root, pat)):
                    try: best = max(best, os.path.getmtime(p))
                    except Exception: pass
    except Exception: pass
    try:
        ws = os.environ.get("SMS_TMP") or ""
        for root, dirs, files in (os.walk(ws, topdown=True) if ws else []):
            dirs[:] = dirs[:8]
            for f in files[:200]:
                try: best = max(best, os.path.getmtime(os.path.join(root, f)))
                except Exception: pass
            break
    except Exception: pass
    return best
def dump_stack(why=""):
    """把全线程栈写 logs/spin.log（faulthandler 独立线程，死循环攥着 GIL 也能抓）。"""
    try:
        import faulthandler
        p = os.path.join(_home(), "logs"); os.makedirs(p, exist_ok=True)
        with open(os.path.join(p, "spin.log"), "a", encoding="utf-8") as f:
            f.write("\n==== spin dump %s %s ====\n" % (time.strftime("%H:%M:%S"), why))
            f.flush(); faulthandler.dump_traceback(file=f, all_threads=True); f.write("\n")
        _cap_log()          # 写完即封顶：spin.log 不得无界增长
        return True
    except Exception: return False
def _log_path():
    """logs/spin.log 绝对路径（顺带建目录）。"""
    p = os.path.join(_home(), "logs"); os.makedirs(p, exist_ok=True)
    return os.path.join(p, "spin.log")
def _open_fh():
    """faulthandler 落盘句柄（懒开、轮转后重开）。"""
    fh = _FH["fh"]
    if fh is not None and not getattr(fh, "closed", True): return fh
    fh = open(_log_path(), "a", encoding="utf-8")
    _FH["fh"] = fh; _FH["path"] = fh.name
    return fh
def _cap_log():
    """spin.log 体积封顶：超 shell.spin_log_max_kb（默认 512KB）只留尾部半份。
    任何路径（faulthandler 自写／dump_stack 追加）都不得再造成无界增长。"""
    try:
        p = _FH["path"] or _log_path()
        lim = int(_cfg("spin_log_max_kb", 512) * 1024)
        if lim <= 0 or not os.path.isfile(p): return 0
        sz = os.path.getsize(p)
        if sz <= lim: return 0
        _cancel_dump("rotate")                      # 先撤定时器，防写进已关句柄
        with open(p, "rb") as f:
            f.seek(max(0, sz - lim // 2)); tail = f.read()
        with open(p, "wb") as f:
            tag = ("==== spin.log rotated, tail kept %s ====\n"
                   % time.strftime("%m-%d %H:%M:%S")).encode()
            f.write(tag)
            f.write(tail)
        if _FH["fh"] is not None:
            try: _FH["fh"].close()
            except Exception: pass
            _FH["fh"] = None
        return sz
    except Exception: return 0
def _arm_dump(secs, why=""):
    """进展驱动转栈：仅在 _watch 判可疑时挂一次性 dump_traceback_later（repeat=False）。
    到点仍无进展才落全线程栈——GIL 被死循环攥死时由 faulthandler 独立线程照样抓到。"""
    if _FH["armed"]: return False
    try:
        import faulthandler
        fh = _open_fh()
        faulthandler.enable(file=fh, all_threads=True)
        try: faulthandler.cancel_dump_traceback_later()
        except Exception: pass
        t = max(5.0, float(secs))
        faulthandler.dump_traceback_later(t, repeat=False, file=fh)
        _FH["armed"] = True; _FH["until"] = time.time() + t; _FH["fired"] = time.time()
        fh.write("==== arm dump %s %s (in %.0fs) ====\n"
                 % (time.strftime("%H:%M:%S"), why, t))
        fh.flush()
        return True
    except Exception: return False
def _cancel_dump(why=""):
    """进展恢复即撤销待落转栈——这是与旧版墙钟定时器的根本区别。"""
    if not _FH["armed"]: return False
    _FH["armed"] = False
    try:
        import faulthandler; faulthandler.cancel_dump_traceback_later()
        return True
    except Exception: return False
def arm(app=None, tick_s=None):
    """壳启动时调一次：开 faulthandler（含 dump_traceback_later——GIL 被 C 调用攥死也能抓栈）
    ＋起守护线程。app 可空（无 UI 时只观测不处置）。"""
    if ST["armed"]: return status()
    ST["armed"] = True
    if app is not None: ST["app"] = app
    try:
        import faulthandler
        faulthandler.enable(file=_open_fh(), all_threads=True)   # 致命错误才落栈（极小）
        _cap_log()   # 现场遗留的超大 spin.log 先截尾（旧版墙钟定时器灌出来的）
    except Exception: pass
    threading.Thread(target=_watch, args=(tick_s or _cfg("spin_tick_s", 5.0),), daemon=True, name="spin-guard").start()
    return status()
def _escalate(s):
    """分级处置：①抓栈＋记链＋通报 ②藏 #prog 停 15fps 动画 ③停在轮 ④重启自愈。"""
    n = int(s.get("hits") or 0)
    cpu = float(s.get("cpu_ms_per_s") or 0.0); sil = float(s.get("silent_s") or 0.0)
    bk = str(s.get("last_beat") or "")   # 键名以 status() 为准（旧代码 s["cpu"]/s["silent"]/s["bkind"] 必 KeyError）
    dump_stack("hit#%d cpu=%.0fms/s silent=%.0fs" % (n, cpu, sil))
    try:
        import chains; chains.record("event", "spin-detect hit=%d cpu_ms_s=%.0f silent=%.0fs beat=%s" % (n, cpu, sil, bk))
    except Exception: pass
    if n == 1:
        try:
            import qq_push; qq_push.push("⚠ 壳空转检出（CPU %.0f%%·%.0fs 无进展）：已停进度条动画回收核子，栈存 logs/spin.log" % (cpu / 10.0, sil))
        except Exception: pass
        ST["hide_req"] = True                       # UI tick 消费→藏 #prog（跨线程只置标志）
    if n >= 2:
        try:
            import stop_channel; stop_channel.request("spin-guard 空转自愈")
        except Exception: pass
    if n >= 3 and _cfg("spin_selfheal", 1) >= 1:
        try:
            import runtime_bind; runtime_bind.lifecycle_request("restart", "spin-selfheal cpu=%.0fms/s silent=%.0fs" % (cpu, sil))
        except Exception: pass
def _watch(tick_s):
    prev = _cpu_ms(); pts = time.time(); ext = 0.0
    while True:
        time.sleep(tick_s)
        now = time.time(); c = _cpu_ms()
        rate = (c - prev) / max(0.2, now - pts) if c >= 0 and prev >= 0 else 0.0   # ms CPU / s 墙钟
        prev, pts = c, now
        ext = max(ext, _ext_new(ext))
        silent = now - max(ST["beat"], ext or 0.0)
        ST["cpu"], ST["silent"] = rate, silent
        thr_c = _cfg("spin_cpu_ms_per_s", 600); thr_s = _cfg("spin_after_s", 60)
        _cap_log()   # 兜底封顶：faulthandler 自己写也受体积约束
        # 一次性定时器已落栈 → 释放标志，持续可疑时冷却期满可再挂
        if _FH["armed"] and now > _FH["until"]: _FH["armed"] = False
        susp = (rate >= thr_c) or (silent >= thr_s)   # 可疑＝高CPU 或 无进展超阈
        if susp and not _FH["armed"] and now - _FH["fired"] >= _cfg("spin_dump_s", 120):
            _arm_dump(_cfg("spin_dump_s", 120), "susp cpu=%.0f silent=%.0f" % (rate, silent))
        elif not susp and _FH["armed"]:
            _cancel_dump("recovered")
        if rate >= thr_c and silent >= thr_s:
            ST["hits"] += 1; ST["verdict"] = "spin"
            try:
                _escalate(status())      # 处置链任何异常都不得打死守护线程
            except Exception:
                dump_stack("escalate-error hit=%d" % ST["hits"])
        elif ST["verdict"] == "spin" and silent < thr_s:
            ST["verdict"] = "ok"; ST["hits"] = 0
        else:
            ST["verdict"] = "busy" if rate >= thr_c else "ok"
def tick(app=None):
    """UI 定时器调（1s）：消费 hide_req 藏掉不确定进度条——这是本次空转的放大器，
    藏下即停 15fps 整屏重绘，核子当场归还。绝不可在此调 beat()（自转不算进展）。"""
    a = app or ST["app"]
    if not ST["hide_req"] or a is None: return ST["verdict"]
    ST["hide_req"] = False
    try:
        from textual.widgets import ProgressBar
        a.query_one("#prog", ProgressBar).display = False
    except Exception: pass
    return ST["verdict"]
def stalled(): return ST["verdict"] == "spin"
def status():
    return {"pid": os.getpid(), "armed": ST["armed"], "verdict": ST["verdict"],
            "cpu_ms_per_s": round(ST["cpu"], 1), "silent_s": round(ST["silent"], 1),
            "hits": ST["hits"], "last_beat": ST["bkind"], "beat_age": round(time.time() - ST["beat"], 1),
            "thr": {"cpu_ms_per_s": _cfg("spin_cpu_ms_per_s", 600), "after_s": _cfg("spin_after_s", 60),
                    "selfheal": _cfg("spin_selfheal", 1)}}
def probe(pid):
    c = _cpu_ms(int(pid)); return {"pid": int(pid), "cpu_ms_total": c, "alive": c >= 0}
def selftest():
    """受控自测（隔离临时 cap.log·_escalate/_ext_new 打桩，不碰处置链/UI）：
    ①纯忙等 4s 判 spin 且 hits>=1 ②可疑才挂转栈、beat() 即解除
    ③忙等期间全线程栈确实落盘（原能力不丢）④空闲不周期灌栈 ⑤spin.log 封顶轮转
    ⑥外部产物 mtime 前进不得误杀。用法：python -B spin_guard.py selftest"""
    import tempfile
    res = []
    def chk(n, c, g=""): res.append((n, bool(c), g))
    cap = os.path.join(tempfile.mkdtemp(prefix="spin_st_"), "cap.log")
    cfg0, esc0, ext0 = _cfg, _escalate, _ext_new
    fh0, path0 = _FH["fh"], _FH["path"]
    try:
        def _c(k, d):
            return {"spin_cpu_ms_per_s": 100.0, "spin_after_s": 1.5,
                    "spin_dump_s": 5.0, "spin_log_max_kb": 64.0}.get(k, float(d))
        globals()["_cfg"] = _c
        globals()["_escalate"] = lambda s: None
        globals()["_ext_new"] = lambda since: 0.0
        _FH.update({"fh": open(cap, "a", encoding="utf-8"), "path": cap,
                    "armed": False, "until": 0.0, "fired": 0.0})
        ST.update({"beat": time.time(), "hits": 0, "verdict": "ok", "armed": False})
        arm(tick_s=0.3)
        t0 = time.time()
        while time.time() - t0 < 4.0: pass
        s = status()
        chk("busy_wait_judged_spin", s["verdict"] == "spin" and s["hits"] >= 1,
            "hits=%d cpu=%.0f" % (s["hits"], s["cpu_ms_per_s"]))
        chk("suspicious_arms_dump", _FH["armed"] is True)
        beat("out")
        chk("beat_cancels_dump", _FH["armed"] is False)
        t0 = time.time()
        while time.time() - t0 < 12.0: pass      # 冷却期满仍可疑 → 再挂并落栈
        beat("out"); time.sleep(0.8)
        txt = open(cap, encoding="utf-8", errors="replace").read()
        chk("stack_still_captured", "Thread 0x" in txt or "Current thread" in txt,
            "blocks=%d" % txt.count("Thread 0x"))
        chk("dump_only_when_suspicious", 1 <= txt.count("==== arm dump") <= 6,
            "arms=%d bytes=%d" % (txt.count("==== arm dump"), os.path.getsize(cap)))
        arms_now = txt.count("==== arm dump")   # 有进展窗口内不得再新增转栈
        globals()["_ext_new"] = lambda since: time.time()
        t0 = time.time()
        while time.time() - t0 < 4.0:
            beat("out"); time.sleep(0.2)
        txt2 = open(cap, encoding="utf-8", errors="replace").read()
        chk("progress_adds_no_dump", txt2.count("==== arm dump") == arms_now,
            "arms %d -> %d" % (arms_now, txt2.count("==== arm dump")))
        with open(cap, "a", encoding="utf-8") as f: f.write("NOISE\n" * 20000)
        big = os.path.getsize(cap); _cap_log()
        chk("log_capped_rotation", os.path.getsize(cap) <= 64 * 1024,
            "%d -> %d" % (big, os.path.getsize(cap)))
        globals()["_ext_new"] = lambda since: time.time()   # 外部产物在前进
        t0 = time.time()
        while time.time() - t0 < 3.0: time.sleep(0.2)
        s2 = status()
        chk("external_progress_not_killed", s2["verdict"] != "spin",
            "verdict=%s silent=%.1f" % (s2["verdict"], s2["silent_s"]))
        _cancel_dump("selftest-end")
    finally:
        globals()["_cfg"], globals()["_escalate"] = cfg0, esc0
        globals()["_ext_new"] = ext0
        try: _FH["fh"].close()
        except Exception: pass
        _FH.update({"fh": fh0, "path": path0, "armed": False, "until": 0.0, "fired": 0.0})
        ST.update({"hits": 0, "verdict": "ok", "beat": time.time()})
    bad = [r for r in res if not r[1]]
    for n, ok, g in res: print("  %s %s %s" % ("PASS" if ok else "FAIL", n, g))
    print("spin_guard selftest: " + ("OK" if not bad else "FAIL(%d)" % len(bad)))
    raise SystemExit(0 if not bad else 1)
if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "probe" and len(a) > 1: print(json.dumps(probe(a[1]), ensure_ascii=False))
    elif a and a[0] == "selftest": selftest()
    elif a and a[0] == "test":
        arm(); t0 = time.time()
        while time.time() - t0 < 200: pass
    else:
        print(json.dumps(status(), ensure_ascii=False))
