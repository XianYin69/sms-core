#!/usr/bin/env python3
"""hud.py — 界面顶面 HUD：任务进行时才常显，置顶·点击穿透·不抢焦点·只读，居屏幕顶中；start [文本]（启用并拉起查看器）/ session <简述> [ttl秒=1800] / step <步骤> [ttl=120] / alert <告警> [ttl=1800] / hide / stop（隐藏并终止查看器）/ status；缺文本时回 usage（修复旧版 `:hud session` 空文本被当清除＝「没法启用」）；状态只存 <SMS_HOME>/hud/，查看进程由 hud_view.py 后台拉起（首次使用自动启动，长期空自动退出），绝不写入 skill 目录；开关＝settings hud.enabled＋hud.auto（TUI 对话自动常显）。"""
import os, sys, json, time, subprocess
S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, S)
import resolve_home
ROOT = os.path.dirname(S); sms = resolve_home.ensure()
def _st():
    p = os.path.realpath(os.path.join(sms, "hud", "state.json"))
    if p == ROOT or p.startswith(ROOT + os.sep): raise SystemExit("拒绝：HUD 状态不得位于 skill 目录")
    return p
def _load():
    try: return json.load(open(_st(), encoding="utf-8"))
    except Exception: return {}
def _save(**kv): d = _load(); d.update(kv); os.makedirs(os.path.dirname(_st()), exist_ok=True); json.dump(d, open(_st(), "w", encoding="utf-8"))
def _alive():
    try: pid = int(open(_st() + ".pid").read().strip())
    except Exception: return False
    if os.name != "nt":
        try: os.kill(pid, 0); return True
        except Exception: return False
    import ctypes; k = ctypes.windll.kernel32  # OpenProcess 只查询句柄，绝不可用 os.kill(pid,0)——Windows 下会误杀查看进程
    h = k.OpenProcess(0x1000, False, pid); c = ctypes.c_ulong(); r = bool(h) and k.GetExitCodeProcess(h, ctypes.byref(c)) and c.value == 259
    if h: k.CloseHandle(h)
    return r
def _spawn():
    kw = {"creationflags": 0x08000000 | 0x8, "close_fds": True} if os.name == "nt" else {"start_new_session": True}
    dn = open(os.devnull, "r+b")
    subprocess.Popen([sys.executable, "-B", os.path.join(S, "hud_view.py"), sms], stdin=dn, stdout=dn, stderr=dn, **kw)
def _set(key, text, ttl):
    _save(**{key: text, key + "_expires": (time.time() + ttl) if text else 0})
    if text and not _alive(): _spawn()
    return {"hud_" + key: text or "(cleared)", "viewer": "alive" if _alive() else "stopped"}
def _hide(): _save(session="", session_expires=0, step="", step_expires=0, alert="", alert_expires=0); return {"hud": "hidden"}
def _stop():
    try:
        pid = int(open(_st() + ".pid").read().strip()); subprocess.run(["taskkill", "/pid", str(pid), "/f"], capture_output=True) if os.name == "nt" else os.kill(pid, 15)
    except Exception: pass
    return _hide()
if __name__ == "__main__":
    try: __import__("session_reg").bind("bg", "hud", "HUD")
    except Exception: pass
    a = sys.argv[1:]; cmd = a[0] if a else "status"
    num = lambda i, d: float(a[i]) if len(a) > i and a[i].replace(".", "", 1).isdigit() else d
    if cmd in ("session", "step", "alert"): r = _set(cmd, a[1], num(2, 120 if cmd == "step" else 1800)) if len(a) > 1 else {"usage": "hud " + cmd + " <文本> [ttl秒]（清除用 :hud hide）"}
    elif cmd == "start": r = _set("session", " ".join(a[1:]) or "sms-shell 任务进行中", 1800)
    elif cmd == "hide": r = _hide()
    elif cmd == "stop": r = _stop()
    elif cmd == "status": r = dict(_load(), alive=_alive())
    else: r = {"usage": "start [文本] | session <文本> [ttl] | step <文本> [ttl] | alert <文本> [ttl] | hide | stop | status"}
    print(json.dumps(r, ensure_ascii=False, indent=2))
