#!/usr/bin/env python3
"""shell_lifecycle.py — SMS 壳生命周期（2026-09-29 用户「菜单里加入 重启SMS 和 关闭SMS」；2026-09-30 三条升级：① 手动 :restart/:shutdown 与关窗口/Ctrl+C 一律二次确认；② 关闭/重启前向远端推送「SMS关闭中」；③ 大模型可依任务要求重启，重启后继续执行任务，且重启完只保留新实例——旧进程必须死）。
批30 关闭/重启语义根治：① _spawn 改 CREATE_NEW_CONSOLE(0x10) 且绕开 no_window（它强制
CREATE_NO_WINDOW|SW_HIDE＝重启后子进程 GetConsoleWindow()==0 隐形，用户看不到新窗口）；
② kill_others 去 PowerShell 依赖——主路径＝shells.json 壳登记表 + proc_guard 后代，CIM 仅作
带 TTL 缓存的兜底，命令行取不到一律不杀（严禁误杀非 SMS python）；③ 回收面从「只杀壳」扩到
「壳 ∪ 命令行含 smsystem-suit 的 core 后台（web_shell/planned/hud/qq_listen/dream_bg/tts）」。
restart＝通报→写旗标→落链→分离式拉起 bin/sms-shell-gui.py（图形入口·新窗；缺则 sms-shell-tui.py）→reclaim 清旧壳与 core 后台
（含本进程，os._exit 硬退，杜绝新旧并存）；
shutdown＝通报＋reclaim（收 HUD/TTS＋清所有壳与 core 后台）＋落链；
request(action,why)＝大模型侧入口（exec 跑 `python -B shell_lifecycle.py request restart 原因`）：只写 <SMS_HOME>/shell/lifecycle.json，由壳在本轮数据流收口时经 run_pending() 自己执行——当前对话先把话说完、任务总览先落盘，再重启；
cmd(m,sms,on_line)＝手动入口（F1 菜单与 readline 兜底壳同径）：15 秒内连点两次才真做；
resume(sms)＝重启后「继续执行任务」单一入口（回 (提示文案, 续跑话语或 None)·旗标一次性消费并留档；resume_hint/auto_resume 为委托它的兼容壳，不再二次消费旗标；开关 settings shell.auto_resume 默认开）。
用法：python -B shell_lifecycle.py restart|shutdown|status|request <action> [原因]"""
import no_window  # 静默子进程：前台运行任务不弹命令行窗口（_spawn 例外，见 A1 注释）
import os, sys, json, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, chains, chain_timing, atomic_io, close_guard as cg
S = os.path.dirname(os.path.abspath(__file__))
# 批34：启动器可经 env SMS_LAUNCHER 覆盖（部署态 bin 与脚本不同根时用之）
# 批37 双入口：默认按当前进程是哪个入口起（SMS_LAUNCHER_NAME）选重启后拉起的入口，缺省＝图形入口 sms-shell-gui.py，
#   该入口不存在时回退终端入口 sms-shell-tui.py（旧名 sms-shell.py 一并兼容＝仍在 PATTERNS 里识别老进程）
_B = os.path.join(os.path.dirname(os.path.dirname(S)), "bin")
_GUIISH = ("sms-shell-gui.py", "sms-shell-tui.py", "sms-shell.py")
_TUIISH = ("sms-shell-tui.py", "sms-shell-gui.py", "sms-shell.py")
def _default_launcher():
    """批37：重启保持用户当前前端——GUI 进程（bin/sms-shell-gui 置 SMS_GUI_ENTRY/SMS_FRONT）→拉图形入口，
    否则拉终端入口（_spawn 用 CREATE_NEW_CONSOLE＝要一个可输入控制台，TUI 用户绝不落到隐形 GUI）；
    两者皆缺再认旧名 bin/sms-shell.py；都没有则回 GUI 路径让 _spawn 报「启动器缺失」而非静默。"""
    gui = bool(os.environ.get("SMS_GUI_ENTRY")) or (os.environ.get("SMS_FRONT") or "").lower() == "gui"
    for n in (_GUIISH if gui else _TUIISH):
        if os.path.isfile(os.path.join(_B, n)): return os.path.join(_B, n)
    return os.path.join(_B, _GUIISH[0] if gui else _TUIISH[0])
BIN = os.environ.get("SMS_LAUNCHER") or _default_launcher()
PATTERNS = ("shell_tui_textual.py", "shell_tui.py", "shell_console.py", "shell_gui.py", "shell_qt.py",
            "sms-shell-gui.py", "sms-shell-tui.py", "sms-shell.py")
SMS_MARK = ("smsystem-suit", "skill_manage_system", "SMS-core", "SMS-shell")  # 批34 移动 Developin：命令行特征串三认
def _sms_hit(cl): return any(m in (cl or "") for m in SMS_MARK)
CONF = {"m": "", "at": 0.0}
# A1 重启必须出现可用新窗口：CREATE_NEW_CONSOLE(0x10)；绝不含 CREATE_NO_WINDOW(0x08000000)
NEW_CONSOLE = 0x00000010
CREATE_NO_WINDOW = 0x08000000
SPAWN_FLAGS = NEW_CONSOLE  # _spawn 在 nt 上用的 creationflags（提为常量便于 selftest 断言）
# A3 CIM 兜底缓存（模块级·TTL 秒）：主路径零 PowerShell，只有登记表+后代都没命中才跑一次
CIM_TTL = 60.0
CIM_TIMEOUT = 2.5
_CIM_CACHE = {"at": 0.0, "rows": [], "ok": False}
def _p(sms): return os.path.join(sms, "shell", "restart.json")
def _flag(sms, on):
    os.makedirs(os.path.dirname(_p(sms)), exist_ok=True)
    json.dump({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "relaunched": bool(on)}, open(_p(sms), "w", encoding="utf-8"))
def pending(sms=None):
    """读并清重启旗标（新实例 startup 用）。"""
    sms = sms or resolve_home.ensure()
    try: d = json.load(open(_p(sms), encoding="utf-8"))
    except Exception: return None
    try: os.remove(_p(sms))
    except Exception: pass
    return d if d.get("relaunched") else None

# ── A2 壳进程登记表（多值表 <SMS_HOME>/shell/shells.json·atomic_io 原子读写）──────────
def _sf(sms=None): return os.path.join(sms or resolve_home.ensure(), "shell", "shells.json")
def _cl_summary():
    """本进程命令行摘要（≤80 字·登记表判据留痕）。"""
    try:
        return (" ".join([os.path.basename(sys.executable)] + sys.argv))[:80]
    except Exception:
        return "python"
def _rows(sms=None):
    """登记表行 [{pid,at,cl}]：缺文件/坏数据＝空表，绝不抛（关闭路径不许被读表挡住）。"""
    try:
        d = atomic_io.rjson(_sf(sms), default={})
    except Exception:
        return []
    raw = d.get("pids") if isinstance(d, dict) else d
    out = []
    for r in raw or []:
        try:
            out.append({"pid": int(r["pid"]), "at": float(r.get("at") or 0),
                        "cl": str(r.get("cl") or "")[:80]})
        except Exception:
            continue
    return out
def _save_rows(rows, sms=None):
    try:
        atomic_io.wjson(_sf(sms), {"pids": rows})
    except Exception as e:
        try:
            import chain_error
            chain_error.record("shell", "shell_lifecycle._save_rows", str(e)[:120])
        except Exception:
            pass
# ── A2 登记表判据（批31 补修：只收壳＋读表自愈＋pid 复用防线）───────────────────
def _cl_is_shell(cl):
    """命令行摘要里有没有壳特征（PATTERNS 任一）——非壳进程（CLI 自检/工具）一律不入表。"""
    return any(pt in (cl or "") for pt in PATTERNS)
def _proc_start(pid):
    """kernel32 GetProcessTimes 取进程创建时间（FILETIME→epoch 秒·与 time.time() 同基准）；
    取不到回 None（判不了＝不动，宁漏不误杀）。零 PowerShell、不新增 import 方向。"""
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1004, False, int(pid))
        if not h:
            return None
        try:
            ct = ctypes.c_ulonglong(); et = ctypes.c_ulonglong()
            kt = ctypes.c_ulonglong(); ut = ctypes.c_ulonglong()
            ok = k.GetProcessTimes(h, ctypes.byref(ct), ctypes.byref(et),
                                   ctypes.byref(kt), ctypes.byref(ut))
        finally:
            k.CloseHandle(h)
        if not ok or not ct.value:
            return None
        return ct.value / 1e7 - 11644473600.0
    except Exception:
        return None
def _row_trust(r, tol=2.0):
    """表行可信三重判据：① 进程活 ② 行内 cl 命中 PATTERNS（污染行＝非壳混入，剔除）
    ③ pid 未被复用——`at` 是登记时刻，进程创建必不晚于它；创建时间晚于 at+tol 即该 pid
    已被后来的进程占用（陈旧/复用），绝不回收。取不到创建时间＝判不了，按 ①② 结论保留。"""
    if not _alive(r["pid"]) or not _cl_is_shell(r.get("cl")):
        return False
    born = _proc_start(r["pid"])
    return not (born is not None and r.get("at") and born > r["at"] + tol)
def register_shell(sms=None, pid=None, cl=None):
    """登记壳 pid（批31 校验：cl 或本进程命令行摘要必须命中 PATTERNS 才写表——非壳回 None
    不写不抛，死/可复用 pid 混进回收面正是误杀无关进程的根因）。幂等：已在表＝只刷 at；
    顺手剔除死 pid。写失败回 None。"""
    try:
        sms = sms or resolve_home.ensure()
        cl = (cl or _cl_summary())[:80]
        if not _cl_is_shell(cl):
            return None
        pid = int(pid or os.getpid())
        rows = [r for r in _rows(sms) if r["pid"] != pid and _alive(r["pid"])]
        rows.append({"pid": pid, "at": time.time(), "cl": cl})
        _save_rows(rows, sms)
        return pid
    except Exception:
        return None
def unregister_shell(pid=None, sms=None):
    """注销 pid（本壳退出前必调，防登记表残留死 pid 让下次 reclaim 空转）。"""
    sms = sms or resolve_home.ensure()
    pid = int(pid or os.getpid())
    rows = _rows(sms); left = [r for r in rows if r["pid"] != pid]
    if len(left) != len(rows):
        _save_rows(left, sms)
    return pid
def shell_pids_table(sms=None):
    """表内可信 pid（死 pid／污染行／pid 复用行一律剔除并回写文件＝自愈，回收面只含壳）。"""
    sms = sms or resolve_home.ensure()
    rows = _rows(sms); live = [r for r in rows if _row_trust(r)]
    if len(live) != len(rows):
        _save_rows(live, sms)
    return [r["pid"] for r in live]

# ── A3 零 PowerShell 主路径取 pid（登记表 → 后代 → CIM 兜底带 TTL 缓存）──────────────
def _gscan(sms=None, global_ok=None):
    """批33：全机枚举（CIM 扫描）的安全闸。
    global_ok 显式传入＝按传入值（selftest 用假 CIM 缓存自测回收面时传 True）；
    未传＝看 sms 是不是真实 <SMS_HOME>——镜像/临时根一律 False，绝不拿真机器进程开刀
    （实测旧版镜像 selftest 经 CIM 兜底误杀 4 个在跑的后台服务）。"""
    if global_ok is not None:
        return bool(global_ok)
    try:
        return os.path.realpath(sms or resolve_home.ensure()) == os.path.realpath(resolve_home.ensure())
    except Exception:
        return True
def _cim_rows(force=False):
    """CIM 兜底：回 [[pid, 命令行], ...]；TTL 内用缓存，失败回旧缓存（绝不回空覆盖好数据）。
    本函数＝全模块唯一的 PowerShell 调用点（timeout≤2.5s、TTL 缓存、异常回旧值）。"""
    now = time.time()
    if _CIM_CACHE["rows"] and not force and now - _CIM_CACHE["at"] < CIM_TTL:
        return _CIM_CACHE["rows"]
    q = ("Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | "
         "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }")
    try:
        out = no_window.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", q],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=CIM_TIMEOUT).stdout
    except Exception:
        return _CIM_CACHE["rows"]
    rows = []
    for ln in out.splitlines():
        pid, _, cl = ln.partition("\t")
        if pid.strip().isdigit() and cl.strip():
            rows.append([int(pid.strip()), cl[:400]])
    if rows:
        _CIM_CACHE.update(at=now, rows=rows, ok=True)
    return rows
def _cmdline(pid):
    """取命令行：登记表自带 → CIM 缓存 → 空串（空串＝判不了，一律不杀）。"""
    for p, cl in _CIM_CACHE["rows"]:
        if p == pid:
            return cl
    return ""
def _shell_pids(exclude=(), force=False, sms=None, cim=True, global_ok=None):
    """按命令行特征列出其它 SMS 壳进程（排除自己与 exclude 里的新实例）。
    三源合并去重：① shells.json 登记表 ② proc_guard 后代 ③ CIM 兜底（仅 ①② 皆空或 force）。"""
    keep = set([os.getpid()] + [int(x) for x in exclude if x])
    table = shell_pids_table(sms)
    try:
        import proc_guard as pg
        kin = [d for d in pg.descendants(os.getpid()) if d not in keep]
    except Exception:
        kin = []
    hits = [p for p in table if p not in keep]
    for p in kin:
        if p not in hits and any(pt in _cmdline(p) for pt in PATTERNS):
            hits.append(p)
    if cim and _gscan(sms, global_ok) and (force or (not table and not kin)):
        for p, cl in _cim_rows(force=force):
            if p in keep or p in hits:
                continue
            if any(pt in cl for pt in PATTERNS):
                hits.append(p)
    return hits
def _sms_pids(exclude=(), force=False, sms=None, cim=True, global_ok=None):
    """A4 回收面＝壳 ∪ 命令行含 smsystem-suit 的 python ∪ SVC pid 文件。
    铁律：候选必须 活 + 不在 keep + 命令行命中 PATTERNS 或含 smsystem-suit；
    命令行取不到一律不杀——两个例外＝SVC pid 文件与 shells.json 登记表（登记表行已由
    _row_trust 按 cl＋创建时间双重校验，故不依赖 CIM 也能回收；CIM 来源必须命令行命中才进表）。"""
    sms = sms or resolve_home.ensure()
    keep = set([os.getpid()] + [int(x) for x in exclude if x])
    out = []
    def add(pid):
        if pid not in keep and pid not in out and _alive(pid):
            out.append(pid)
    for pid in _shell_pids(exclude=exclude, force=force, sms=sms, cim=cim):
        add(pid)
    if cim and _gscan(sms, global_ok):
        for p, cl in _cim_rows(force=force):
            if int(p) not in keep and _sms_hit(cl):
                add(int(p))
    for _name, rel in SVC:
        try:
            p = os.path.join(sms, *rel)
            if not os.path.exists(p):
                continue
            svc = int((open(p, encoding="utf-8").read() or "0").split("|")[0].strip() or 0)
            if svc:
                add(svc)
        except Exception:
            continue
    return out

# ── A5/A6/A7 回收 ──────────────────────────────────────────────────────────────
SVC = (("web_shell", ("shell", "web_shell.pid")), ("planned", ("planned", "serve.pid")),
       ("hud", ("hud", "state.json.pid")), ("qq_listen", ("qq", "listen.pid")),
       ("smsocket", ("shell", "smsocket.pid")))
def _kill(pid, tree=False):
    """taskkill 单点：tree=True 仅对登记表来源（我们自己拉起、连带合理）；
    CIM 来源不带 /T——防连带杀掉用户无关子进程。"""
    cmd = ["taskkill", "/PID", str(pid), "/F"] + (["/T"] if tree else [])
    try:
        no_window.run(cmd, capture_output=True, timeout=15)
        return True
    except Exception:
        return False
def kill_others(exclude=(), why="", force=False, sms=None, cim=True, global_ok=None):
    """清掉旧壳＋含 smsystem-suit 的 core 后台——重启后只保留新实例，关闭后无残留。
    A5：回收面由 _shell_pids 扩到 _sms_pids（旧版只杀壳＝漏收 dream_bg/tts/ff_lite 等后台）。"""
    sms = sms or resolve_home.ensure()
    keep = set([os.getpid()] + [int(x) for x in exclude if x])
    table = set(shell_pids_table(sms))
    gone = []
    for pid in _sms_pids(exclude=exclude, force=force, sms=sms, cim=cim, global_ok=global_ok):
        if _kill(pid, tree=pid in table):
            gone.append(pid)
    gone and chains.record("event", "shell-kill-others %s（%s）" % (",".join(map(str, gone)), why or "restart"))
    return gone
def _alive(pid):
    """ctypes 真判活（GetExitCodeProcess==259·绝不用 os.kill 防误杀）。"""
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1004, False, int(pid))
        if not h: return False
        c = ctypes.c_ulong(); ok = k.GetExitCodeProcess(h, ctypes.byref(c)); k.CloseHandle(h)
        return bool(ok) and c.value == 259
    except Exception: return True
def kill_services(exclude=(), sms=None, budget=1.5, why=None, global_ok=None):
    """回收壳自己拉起的一切后台进程——DETACHED 子进程不随 os._exit 而亡，正是「点了确认关闭程序还在」的真根因。
    三路取 pid：① SVC pid 文件表（不活只清文件绝不误杀）② 本进程全部后代（proc_guard Toolhelp32·零 PowerShell）
    ③ A3 缓存 CIM 兜底（预算内才跑·命令行不含 smsystem-suit 一律不杀）。
    taskkill /T /F 逐个杀，总预算 budget 秒，异常一律静默。
    why＝调用场景（close_guard._bye 按规格传「窗口/控制事件」·缺省按 close 记链）。"""
    t0 = time.time(); sms = sms or resolve_home.ensure()
    keep = set([os.getpid()] + [int(x) for x in exclude if x]); pids = []
    for _name, rel in SVC:
        try:
            p = os.path.join(sms, *rel)
            if not os.path.exists(p): continue
            pid = int((open(p, encoding="utf-8").read() or "0").split("|")[0].strip() or 0)
            if pid and pid not in keep and _alive(pid): pids.append(pid)
            else:
                try: os.remove(p)
                except Exception: pass
        except Exception: pass
    try:
        import proc_guard as pg
        for d in pg.descendants(os.getpid()):
            if d not in keep and d not in pids and _alive(d): pids.append(d)
    except Exception: pass
    if time.time() - t0 < budget and _gscan(sms, global_ok):  # ③ 兜底只在预算内跑·走 TTL 缓存·镜像根不扫全机
        for pid, cl in _cim_rows():
            if pid in keep or pid in pids: continue
            if _sms_hit(cl) or any(pt in cl for pt in PATTERNS):
                if _alive(pid): pids.append(pid)
    for pid in pids:
        if time.time() - t0 > budget: break
        try: no_window.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=3)
        except Exception: pass
    pids and chains.record("event", "shell-kill-services %s（%s）" % (",".join(map(str, pids)), why or "close"))
    return pids

def _push_async(text, wait=1.2):
    """远端通报挪到 daemon 线程（旧版同步 urlopen timeout=8s＝确认关闭后干等 8 秒＝「没关」错觉）。"""
    import threading
    try:
        t = threading.Thread(target=cg.push, args=(text,), daemon=True); t.start(); t.join(wait)
    except Exception: pass
def _bye(sms, tag):
    chains.record("event", tag + " " + time.strftime("%Y-%m-%dT%H:%M:%S"))
    try: chain_timing.flush()
    except Exception: pass
def _spawn(sms):
    """拉起新实例——A1：这里绝不经 no_window.Popen。
    no_window.flags() 会强制 f |= CREATE_NO_WINDOW 并塞 startupinfo(SW_HIDE)，实测子进程
    GetConsoleWindow()==0＝隐形进程，用户看不到「重启后的新窗口」。重启的语义就是要一个
    可用新控制台，故 nt 上直接用 CREATE_NEW_CONSOLE(0x10) 调 subprocess.Popen。"""
    if not os.path.isfile(BIN): return ("启动器缺失：" + BIN + "（可用 env SMS_LAUNCHER 指向真实 bin/sms-shell-gui.py / sms-shell-tui.py）", None)
    # A1b：nt 上不重定向任何标准流——传 stdin=DEVNULL 会让新控制台立刻读到 EOF
    # （键盘输入失效＝重启后那个窗口打字没反应）；不传则 CreateProcess 把子进程
    # 三个句柄绑到新控制台本身，才是「可用新窗口」。posix 无控制台概念，保持 DEVNULL。
    kw = {"creationflags": SPAWN_FLAGS} if os.name == "nt" else {"start_new_session": True, "stdin": subprocess.DEVNULL}
    try:
        # sms-visible：重启必须给用户一个可见可输入的终端窗口
        pr = subprocess.Popen([sys.executable, "-B", BIN], cwd=os.path.dirname(BIN),
                              env=dict(os.environ, SMS_SESSION=chains.cur_sess()), **kw)
    except Exception as e:
        import chain_error; chain_error.record("shell", "shell_lifecycle._spawn", str(e))
        return ("拉起失败：" + str(e)[:120], None)
    try:  # A2：新壳一拉起就登记，后续 reclaim 不再依赖 PowerShell 找它
        register_shell(sms, pr.pid, cl=os.path.basename(BIN) + "（新实例·_spawn 登记）")
    except Exception: pass
    return ("已拉起新实例 pid=%s（%s）" % (pr.pid, BIN), pr.pid)
def reclaim(exclude=(), why="", sms=None, global_ok=None):
    """A7 关闭/重启的统一回收口：先收用户看得见的服务（HUD/网页壳/planned/qq），
    再清旧壳与含 smsystem-suit 的 core 后台。回 (服务 pids, 其它 pids)。"""
    svc = kill_services(exclude=exclude, sms=sms, why=why, global_ok=global_ok)
    others = kill_others(exclude=exclude, why=why, sms=sms, global_ok=global_ok)
    return svc, others
def restart(sms=None, why="", hard=True, allow=False):
    """重启：通报远端→写旗标→拉起新实例（新控制台窗口）→reclaim 清旧壳与 core 后台（含本进程）。
    非壳进程调用＝只登记请求交壳收口执行；allow=True 的常驻宿主（QQ 监听器这类）自己执行——
    拉起新实例＋清旧壳，但 hard=False 不让它 os._exit，通道不断（批33：旧版把 allow 宿主也退回
    request()，请求被壳消费后又重登记＝永远不重启，正是「子代理请求重启没反应」的真根因）。"""
    sms = sms or resolve_home.ensure()
    if not (_is_shell() or allow): return request("restart", why, sms)
    cg.push("SMS 重启中（%s）· %s" % (why or "restart", time.strftime("%H:%M:%S")))
    _flag(sms, True); _bye(sms, "shell-restart")
    r, newpid = _spawn(sms)
    if not newpid: return r
    time.sleep(1.0)
    # 先收可见服务，再清旧壳＋core 后台（零 PowerShell 主路径＝不再让用户干等）；新实例 on_mount 重拉服务
    reclaim(exclude=[newpid], why="restart", sms=sms)
    try: unregister_shell(sms=sms)
    except Exception: pass
    if hard:
        try: chain_timing.flush()
        except Exception: pass
        os._exit(0)   # 本进程必死——旧实例不留（用户「只保留重启之后的」）
    return r
def shutdown(sms=None, why="", hard=True, allow=False):
    """关闭：通报远端→收 HUD/TTS→reclaim 清所有壳与 core 后台（批30：关了就真没了，不许残留）。
    allow=True 的常驻宿主同样真回收，但 hard=False＝宿主自己不死、远程通道不断。"""
    sms = sms or resolve_home.ensure()
    if not (_is_shell() or allow): return request("shutdown", why, sms)
    _push_async("SMS 关闭中（%s）· %s" % (why or "shutdown", time.strftime("%H:%M:%S")))
    _flag(sms, False)
    try:
        import hud; hud._stop()
    except Exception: pass
    try:
        import tts; hasattr(tts, "stop") and tts.stop()
    except Exception: pass
    reclaim(why="shutdown", sms=sms)  # 关壳必清后台＝批29 真根因（DETACHED 不随 os._exit 而亡）
    try: unregister_shell(sms=sms)
    except Exception: pass
    _bye(sms, "shell-shutdown")
    if hard:
        try: kill_services(budget=0.4, why="shutdown-hard", sms=sms)
        except Exception: pass
        try: chain_timing.flush()
        except Exception: pass
        os._exit(0)
    return "已关闭SMS：HUD/后台已收，本壳退出"

def _is_shell():
    """本进程是不是壳：argv 命中 PATTERNS 即真（旧版跑 PowerShell 查自身命令行＝实测 2.24s 白等，
    点「确认关闭」后数秒无反馈正是「看起来没关」的成因之一）。取不到一律按壳处理＝宁硬退不误登记。"""
    try:
        cl = " ".join([os.path.basename(sys.executable)] + sys.argv)
    except Exception:
        return True
    return any(pt in cl for pt in PATTERNS)
def request(action, why="", sms=None):
    """大模型侧入口：登记 restart/shutdown，本轮数据流收口处由壳自己执行（先说完话、先落任务总览）。
    批32 R4：回串带 lifecycle.json 绝对路径——写读同一 <SMS_HOME>/shell/lifecycle.json 可核对。"""
    sms = sms or resolve_home.ensure()
    r = cg.request(action, why, sms)
    return r if str(r).startswith("登记失败") else "%s·文件=%s" % (r, cg._f(sms))
DEFER = set()
def _note(e, src):
    """批32 R5：异常一律进 error 链，禁静默吞（非裸 except）。"""
    try:
        import chain_error
        chain_error.record("shell", src, str(e)[:160])
    except Exception as e2:
        try:
            import chain_error
            chain_error.record("shell", src + ".recordfail", repr(e2)[:120])
        except Exception as e3:
            sys.stderr.write("lifecycle note fail: %r\n" % (e3,))
def _deferred(d, sms):
    """批32 R2：非壳宿主取不到执行者——请求文件保留不删，记一条可见链，回明确串（不与「无待办」混同）。"""
    a = str(d.get("action") or "?"); why = str(d.get("why") or ""); by = d.get("by"); f = cg._f(sms)
    try:
        key = (a, str(d.get("at")), str(by))
        if key not in DEFER:
            DEFER.add(key)
            chains.record("event", "lifecycle-defer 请求 %s 待壳执行·文件=%s·by=%s·原因=%s" % (a, f, by, why))
    except Exception as e:
        _note(e, "run_pending.defer")
    return ("⏳ lifecycle 请求 %s（原因：%s·登记 pid=%s）待壳执行——本进程非壳且未获 allow，"
            "请求文件保留未删：%s" % (a, why, by, f))
def run_pending(sms=None, allow=False, on_line=None, hard=None):
    """每轮数据流收口处的唯一消费口（批32 规格 R1–R5）：
    ① 无登记＝回 None（真「无待办」）；② 非壳且未 allow＝文件保留＋记链＋回明确串（R2，绝不静默回 None）；
    ③ 壳／allow 宿主＝消费并执行，执行前先把一行提示交出去（R3：restart 硬分支 os._exit 前不打印就永远看不到）；
    ④ hard=None 取 _is_shell()（壳硬退只留新实例；常驻宿主软执行不死），selftest 可显式传 False。"""
    sms = sms or resolve_home.ensure()
    d = cg.peek(sms)
    if not d: return None
    if not (_is_shell() or allow):
        return _deferred(d, sms)
    a = str(d.get("action") or "")
    if a not in ("restart", "shutdown"):
        _note(ValueError("unknown lifecycle action: " + a), "run_pending.action")
        return "lifecycle 请求动作无法识别（%s）·文件保留：%s" % (a or "空", cg._f(sms))
    why = str(d.get("why") or "")
    h = _is_shell() if hard is None else bool(hard)
    if not cg.pending(sms):
        return "lifecycle 请求 %s 消费失败（文件保留待下次）：%s" % (a, cg._f(sms))
    tip = "⟳ 已按大模型请求执行 %s（原因：%s）·%s" % (
        a, why, "新实例已拉起·旧实例退出" if a == "restart" else "HUD/后台已回收·本实例退出")
    if on_line:
        on_line(tip)
    else:
        sys.stdout.write(tip + "\n"); sys.stdout.flush()
    chains.record("event", "lifecycle-consume %s by=%s hard=%s" % (a, os.getpid(), h))
    r = (restart if a == "restart" else shutdown)(sms, "大模型请求·" + why, hard=h, allow=bool(allow))
    if isinstance(r, str) and ("失败" in r or "缺失" in r):
        # 软执行没做成＝不许丢请求：退回登记，下次收口再消费（硬分支已 os._exit，到不了这里）
        cg.request(a, why, sms)
        _note(RuntimeError(str(r)[:160]), "run_pending." + a)
        return "%s·执行未成，请求已退回登记（下次收口重试）：%s" % (tip, r)
    return r
def cmd(m, sms=None, on_line=None, force=False):
    """手动入口（F1 菜单 :restart/:shutdown·readline 兜底壳同径）：15 秒内连点两次才真做＝二次确认（settings close_guard.enabled=false 时首枪即真做，restart/shutdown 内部仍向远端通报）。"""
    now = time.time()
    if not force and cg.enabled() and not (CONF["m"] == m and now - CONF["at"] < 15):
        CONF.update(m=m, at=now)
        msg = ("⚠ 二次确认：%s 已收到第一次——再执行一次 :%s（15 秒内）才真%s；任务进行中建议先 F11 停止。" % ("重启SMS" if m == "restart" else "关闭SMS", m, "重启" if m == "restart" else "关闭"))
        on_line and on_line(msg)
        return msg
    CONF.update(m="", at=0.0)
    on_line and on_line(("已拉起新实例并清掉旧壳＝重启SMS 完成" if m == "restart" else "已关闭SMS：HUD/后台已收·远端已通报"))
    _fold(m, sms, on_line)  # R1：真做之前收口大模型登记的请求（同动作即消费清文件，异动作即一行告知）
    return restart(sms, "用户手动 :restart") if m == "restart" else shutdown(sms, "用户手动 :shutdown")
def _fold(m, sms=None, on_line=None):
    """批32 R1：:restart/:shutdown 真做前消费 lifecycle.json——登记的正是同一动作就合并原因并清文件
    （否则新实例会在下一轮再重启一次）；登记的是另一动作则保留文件并一行告知，交新实例收口消费。"""
    sms = sms or resolve_home.ensure()
    d = cg.peek(sms)
    if not d: return None
    a = str(d.get("action") or ""); why = str(d.get("why") or "")
    if a == m:
        cg.pending(sms)
        msg = "⟳ 一并执行大模型登记的 %s 请求（原因：%s）·文件已清：%s" % (a, why, cg._f(sms))
        on_line and on_line(msg)
        chains.record("event", "lifecycle-fold %s by=%s" % (a, os.getpid()))
        return msg
    on_line and on_line("⏳ 另有登记请求 %s（原因：%s）与本次 :%s 不同·文件保留：%s·新实例收口时执行" % (a, why, m, cg._f(sms)))
    return None

_LAST = None
def resume(sms=None):
    """重启后唯一入口：一次性算出（提示文案, 自动续跑话语或 None）——旗标只消费一次，结果留档 _LAST 供 resume_hint/auto_resume 兼容壳复用。"""
    global _LAST
    if not pending(sms):
        _LAST = ("", None); return _LAST
    try:
        import task_table as tt, settings
        un = tt.unfinished(); auto = bool(settings.get("shell.auto_resume", True))
    except Exception:
        _LAST = ("已重启（上一实例退出）。", None); return _LAST
    if not un:
        _LAST = ("已重启（上一实例退出·无未完成任务总览）。", None); return _LAST
    top = "；".join("%s（%d/%d）" % (t[-14:], d, n) for t, d, n in un[:3])
    hint = "⟳ 重启完成：检测到未完成任务总览 %d 张（%s）——%s" % (
        len(un), top, "本轮自动续跑（:config set shell.auto_resume false 可关）" if auto else "按 F12／输「继续任务」续跑")
    _LAST = (hint, "继续任务（重启后自动续跑·见〔任务总览〕未完成行）" if auto else None)
    return _LAST
def resume_hint(sms=None):
    """兼容壳（旧入口·新代码请直接用 resume）：文案取 resume()，旗标已被 resume 消费过则复用留档，绝不二次消费。"""
    return (resume(sms) if _LAST is None else _LAST)[0]
def auto_resume(sms=None):
    """兼容壳（旧入口·新代码请直接用 resume）：续跑话语取 resume()[1]（同上·不二次消费旗标）。"""
    return (resume(sms) if _LAST is None else _LAST)[1]
def _fake_rows(pr, ps):
    """selftest 用假 CIM 行：pr＝命令行不含 SMS 特征（必须被排除），ps＝含 smsystem-suit。"""
    return [[pr.pid, "python.exe -B -c import time"],
            [ps.pid, "python.exe -B -c time # smsystem-suit"]]
def _selftest():
    """批29 回归：① _is_shell 零 PowerShell ② kill_services 真收 DETACHED 后代 ③ 死 pid 只清文件不误杀。
    批30 追加（A9）：④ _spawn 用 CREATE_NEW_CONSOLE 且不含 CREATE_NO_WINDOW ⑤ 主路径零 PowerShell
    （no_window.run 被 monkeypatch 抛异常后 _sms_pids 仍靠登记表给出结果）⑥ 命令行不含
    smsystem-suit/PATTERNS 的假 pid 必须被 _sms_pids 排除（防误杀）⑦ register/unregister 幂等
    ＋死 pid 自动剔除。回收只在 tmp 镜像根里跑＝真服务进程不受扰；真实 pid 文件先备份后还原。"""
    import shutil, tempfile
    SHELL_CL = "python.exe -B sms-shell-gui.py（selftest 壳行·GUI 入口）"
    JUNK_CL = "python.exe close_guard.py arm"
    assert _sms_hit("python -B x.py # skill_manage_system") and _sms_hit("python -B x.py # smsystem-suit"), "兼容红线：旧名/新名命令行都必须命中回收面"
    t = time.time(); assert not _is_shell(), "直跑本文件应判非壳（argv 不含 PATTERNS）"
    dt = time.time() - t
    assert dt < 0.2, "_is_shell 耗时 %.3fs＝仍在跑 PowerShell（旧版实测 2.24s）" % dt
    assert SPAWN_FLAGS & NEW_CONSOLE and not SPAWN_FLAGS & CREATE_NO_WINDOW, \
        "A9④ _spawn flags 必须 CREATE_NEW_CONSOLE(0x10) 且不含 CREATE_NO_WINDOW(0x08000000)"
    sms = resolve_home.ensure(); bak = {}
    for _n, rel in SVC:  # 真实 pid 文件先备份（测试全程不写它们＝兜底防污染）
        p = os.path.join(sms, *rel)
        bak[p] = open(p, "rb").read() if os.path.exists(p) else None
    root = tempfile.mkdtemp(prefix="lc_selftest_"); pr = ps = None
    cache0 = dict(at=_CIM_CACHE["at"], rows=list(_CIM_CACHE["rows"]))
    try:
        pr = no_window.Popen([sys.executable, "-B", "-c", "import time;time.sleep(60)"],
                             creationflags=0x08000000 | 0x8)
        ps = no_window.Popen([sys.executable, "-B", "-c",
                              "import time;time.sleep(60)  # smsystem-suit bg"],
                             creationflags=0x08000000 | 0x8)
        time.sleep(0.6)
        import proc_guard as pg
        kin = pg.descendants(os.getpid())
        assert pr.pid in kin, "Toolhelp32 后代枚举未命中测试孙进程 %s" % pr.pid
        assert ps.pid in kin, "后代枚举未命中模拟 core 后台 %s" % ps.pid
        _CIM_CACHE.update(at=time.time(), rows=_fake_rows(pr, ps))
        got = _sms_pids(sms=root, global_ok=True)
        assert ps.pid in got, "A9⑥ 命令行含 smsystem-suit 的 core 后台未被回收＝漏收真根因"
        assert pr.pid not in got, "A9⑥ 命令行不含 SMS 特征的进程进了回收表＝会误杀非 SMS python"
        assert os.getpid() not in got, "自己进了回收表"
        pid = register_shell(sms=root, pid=pr.pid, cl=SHELL_CL)
        assert pid == pr.pid and pr.pid in shell_pids_table(root), "register_shell 未登记"
        register_shell(sms=root, pid=pr.pid, cl=SHELL_CL)
        assert len([r for r in _rows(root) if r["pid"] == pr.pid]) == 1, "register_shell 非幂等"
        assert pr.pid in _sms_pids(sms=root), "登记表来源（按构造即 SMS 自有）未被回收"
        dead = os.getpid() + 10 ** 6
        register_shell(sms=root, pid=dead, cl=SHELL_CL)
        assert dead not in shell_pids_table(root), "A9⑦ 死 pid 未被自动剔除"
        unregister_shell(sms=root, pid=pr.pid)
        assert pr.pid not in shell_pids_table(root), "unregister_shell 未清自己"
        _CIM_CACHE.update(at=0.0, rows=[])  # A9⑤ 缓存冷＋PowerShell 全挂
        orig_run = no_window.run
        no_window.run = lambda *x, **k: (_ for _ in ()).throw(RuntimeError("PS-BLOCKED"))
        try:
            register_shell(sms=root, pid=ps.pid, cl=SHELL_CL)
            assert ps.pid in _sms_pids(sms=root), "A9⑤ 主路径仍依赖 PowerShell（登记表应独立给出结果）"
            unregister_shell(sms=root, pid=ps.pid)
        finally:
            no_window.run = orig_run
        # 批31 补修断言：登记表只收壳、读表二次校验自愈、pid 复用行不回收
        assert register_shell(sms=root, pid=ps.pid, cl=JUNK_CL) is None, \
            "非壳命令行被登记＝死/可复用 pid 混进回收面（会误杀非 SMS python）"
        assert not [r for r in _rows(root) if r.get("cl") == JUNK_CL], "非壳条目仍落表"
        _save_rows(_rows(root) + [{"pid": pr.pid, "at": time.time(), "cl": JUNK_CL}], root)
        assert pr.pid not in shell_pids_table(root), "shell_pids_table 未剔除污染行"
        assert not [r for r in _rows(root) if r.get("cl") == JUNK_CL], "剔除后未回写文件（自愈失效）"
        _save_rows(_rows(root) + [{"pid": pr.pid, "at": time.time() - 1000.0,
                                   "cl": SHELL_CL}], root)
        assert pr.pid not in shell_pids_table(root), "pid 复用行（创建晚于登记）未剔除＝会误杀"
        assert register_shell(sms=root, pid=pr.pid, cl=SHELL_CL) == pr.pid, "壳行登记失效"
        assert pr.pid in shell_pids_table(root), "壳行未回表"
        _CIM_CACHE.update(at=time.time(), rows=_fake_rows(pr, ps))
        got = kill_services(sms=root, budget=2.0, global_ok=True)
        assert pr.pid in got, "kill_services 未收到后代（got=%s）" % got
        time.sleep(1.2)
        assert not _alive(pr.pid), "DETACHED 孙进程仍活着＝真根因未修"
        dead = os.getpid() + 10 ** 6
        pf = os.path.join(root, "planned", "serve.pid")
        os.makedirs(os.path.dirname(pf), exist_ok=True)
        open(pf, "w", encoding="utf-8").write("%d|%d" % (dead, time.time()))
        got2 = kill_services(sms=root, budget=1.0, global_ok=True)
        assert dead not in got2, "死 pid 进了回收表＝pid 复用会误杀（got=%s）" % got2
        assert not os.path.exists(pf), "死 pid 文件未被清（残留＝下次误判在跑）"
        assert not _alive(dead), "死 pid 竟判活"
    finally:
        _CIM_CACHE.update(at=cache0["at"], rows=cache0["rows"])
        for p in (pr, ps):
            try:
                p and p.kill()
            except Exception: pass
        shutil.rmtree(root, ignore_errors=True)
        for p, data in bak.items():  # 还原真实 pid 文件
            try:
                if data is None:
                    os.path.exists(p) and os.remove(p)
                else:
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                    open(p, "wb").write(data)
            except Exception: pass
    tip = _lc_roundtrip()
    print("selftest OK（_is_shell %.3fs·零 PowerShell·登记表只收壳/污染自愈/pid 复用防线/"
          "防误杀/新窗口 flags 全过·lifecycle 往返=%s）" % (dt, tip))
def _lc_roundtrip():
    """批32 R6 子测试（tmp 镜像根·绝不真重启真杀）：非壳登记→非壳消费被拒（文件保留＋记链＋明确串）
    →壳侧 hard=False 消费成功（先出一行提示再执行·文件清除）→无待办回 None。"""
    import shutil as _sh, tempfile as _tf
    root = _tf.mkdtemp(prefix="lc_roundtrip_"); sms = os.path.join(root, "shell")
    f = cg._f(sms)
    assert not _is_shell(), "selftest 直跑必须判非壳"
    r = request("restart", "selftest 需重启", sms=sms)
    assert "已登记" in r and f in r, "R4 request 回串缺绝对路径：%s" % r
    assert os.path.isfile(f), "request 未落 lifecycle.json"
    out = run_pending(sms=sms)
    assert out and "待壳执行" in out, "R2 非壳消费未回明确串：%s" % out
    assert os.path.isfile(f) and cg.peek(sms), "R2 非壳消费把请求文件删了"
    keep = (_is_shell, _spawn, reclaim, _bye, cg.push)
    globals()["_is_shell"] = lambda: True
    globals()["_spawn"] = lambda s: ("已拉起新实例 pid=FAKE(1)（selftest）", 1)
    globals()["reclaim"] = lambda *x, **k: ([], [])
    globals()["_bye"] = lambda s, t: None
    cg.push = lambda t: None
    L = []
    try:
        res = run_pending(sms=sms, on_line=L.append, hard=False)
        assert L and "已按大模型请求执行 restart" in L[0], "R3 硬退前未出一行提示：%s" % L
        assert "selftest 需重启" in L[0], "R3 提示缺登记原因：%s" % L
        assert not os.path.isfile(f), "R1 消费后 lifecycle.json 未清除"
        assert isinstance(res, str) and "FAKE" in res, "软消费未回结果串：%s" % res
        assert run_pending(sms=sms) is None, "无待办必须回 None（不得与被拒串混同）"
    finally:
        for _k, _v in (("_is_shell", keep[0]), ("_spawn", keep[1]), ("reclaim", keep[2])):
            globals()[_k] = _v
        globals()["_bye"] = keep[3]
        cg.push = keep[4]
        _sh.rmtree(root, ignore_errors=True)
    return L[0][:36]

if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]
    if a[0] in ("restart", "shutdown"):
        print(restart(why="CLI " + a[0]) if _is_shell() else request(a[0], "CLI " + a[0]))
    elif a[0] == "request":
        print(request(a[1] if len(a) > 1 else "restart", " ".join(a[2:]) or "大模型请求"))
    elif a[0] == "force":
        print(restart(why="CLI force") if a[1] != "shutdown" else shutdown(why="CLI force"))
    elif a[0] == "pending":
        print(run_pending(allow=len(a) > 1 and a[1] == "allow") or "无待执行请求（%s）" % cg._f())
    elif a[0] == "selftest":
        _selftest()
    else:
        print(json.dumps({"launcher": BIN, "exists": os.path.isfile(BIN), "is_shell": _is_shell(),
                          "lifecycle_file": cg._f(), "pending_restart": cg.peek(),
                          "others": _shell_pids(cim=False), "table": shell_pids_table(),
                          "sms_pids": _sms_pids(cim=False)}, ensure_ascii=False))

import runtime_bind as _rb; _rb.set_pending(run_pending)  # 批27 接缝登记
