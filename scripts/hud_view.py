#!/usr/bin/env python3
"""hud_view.py — HUD 查看进程（由 hud.py 后台以脚本方式拉起，禁止 import——旧版模块级建窗进 mainloop，任何 import 都会挂死调用方，现全部收进 main()，仅 __main__ 执行）：tkinter 置顶·点击穿透·不抢焦点，居屏幕顶中不打扰用户；轮询 <SMS_HOME>/hud/state.json 三行渲染 alert(红)/session/step，全空即隐藏，空闲 120s 自退。"""
import os, sys, json, time
sms = sys.argv[1] if len(sys.argv) > 1 else ""
st = os.path.join(sms, "hud", "state.json")
def load():
    try: return json.load(open(st, encoding="utf-8"))
    except Exception: return {}
def gui():
    import tkinter as tk
    if os.name == "nt":
        import ctypes
        try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception: pass
    r = tk.Tk(); r.overrideredirect(True); r.configure(bg="#1e1e2e")
    r.attributes("-topmost", True); r.attributes("-alpha", 0.85)
    lbl = tk.Label(r, font=("Segoe UI", 10), bg="#1e1e2e", fg="#89b4fa", padx=14, pady=6, justify="left"); lbl.pack()
    hit = [False]; idle = [0]
    try: open(st + ".pid", "w").write(str(os.getpid()))
    except Exception: pass
    def tick():
        d = load(); now = time.time(); lines = []; red = False
        for k, pre in (("alert", "⚠ "), ("session", "◆ SMS "), ("step", "   ")):
            if d.get(k) and now < d.get(k + "_expires", 0):
                lines.append(pre + d[k]); red = red or k == "alert"
        t = "\n".join(lines)
        if t:
            idle[0] = 0; lbl.config(text=t, fg="#f38ba8" if red else "#89b4fa")
            if not r.winfo_viewable(): r.deiconify()
        elif r.winfo_viewable():
            r.withdraw(); idle[0] += 1
            if idle[0] > 400: r.destroy(); return
        if not hit[0] and r.winfo_viewable() and os.name == "nt":
            import ctypes
            u = ctypes.windll.user32; h = u.GetParent(r.winfo_id()) or r.winfo_id()
            u.SetWindowLongW(h, -20, u.GetWindowLongW(h, -20) | 0x20 | 0x8000000)
            hit[0] = True
        r.attributes("-topmost", True); r.update_idletasks()
        if r.winfo_viewable():
            w, hg = lbl.winfo_reqwidth(), lbl.winfo_reqheight()
            r.geometry(f"{w}x{hg}+{(r.winfo_screenwidth() - w) // 2}+24")
        r.after(300, tick)
    tick(); r.mainloop()
if __name__ == "__main__": gui()
