#!/usr/bin/env python3
"""chains_git.py — 十一链数据 git 管理（2026-09-25 用户红线：所有链必须使用 git 管理）：首次触链自动 git init <SMS_HOME>/chains 并把既有全部链导入提交；此后任何链写入防抖 5 秒自动 commit、进程退出兜底 flush；git 缺失或 init 失败即静默降级不阻断记录；ensure 只认 toplevel＝链目录自身（2026-09-26 修复：旧 rev-parse --git-dir 向上穿透命中祖先仓库，测试/临时 SMS_HOME 落他人工作树内时 add -A 混吞外层改动＝「混吞批」事故根因）；手动：python chains_git.py status|log [n]。"""
import os, sys, subprocess, threading, atexit
from time import strftime
S = {"root": None, "timer": None, "ok": False}
def _git(*a):
    if not S["root"]: return None
    try: return subprocess.run(("git", "-C", S["root"]) + a, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError: return None
def ensure(root):
    if S["root"] == root: return S["ok"]
    S["root"] = root; os.makedirs(root, exist_ok=True)
    top = _git("rev-parse", "--show-toplevel")  # 只认 toplevel＝链目录本身；祖先仓库（如 SMS_HOME 落在他人 git 工作树内）一律视为未建库——修复 add -A 混吞外层仓库改动事故
    if top is None: S["root"] = None; return False
    fresh = top.returncode != 0 or os.path.realpath(top.stdout.strip()) != os.path.realpath(root)
    if fresh:
        i = _git("init")
        if i.returncode != 0: S["root"] = None; return False
        _git("config", "user.name", "SMS"); _git("config", "user.email", "sms@chains.local")
    atexit.register(commit, "进程退出"); S["ok"] = True
    commit("建链仓库·导入既有链" if fresh else "补齐上次未归档链"); return True
def touch():
    if not S["ok"]: return
    if S["timer"]: S["timer"].cancel()
    t = threading.Timer(5.0, commit, args=("链写入",)); t.daemon = True; S["timer"] = t; t.start()
def commit(why):
    st = _git("status", "--porcelain")
    if st is None or not st.stdout.strip(): return False
    _git("add", "-A")
    r = _git("commit", "-m", "chore(chains): %s归档%d项 %s" % (why, len(st.stdout.splitlines()), strftime("%Y-%m-%dT%H:%M:%S")))
    return bool(r) and r.returncode == 0
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if not ensure(os.path.join(resolve_home.ensure(), "chains")):
        print("ERR git 不可用或链仓库初始化失败"); sys.exit(1)
    if commit(cmd): print("链变更已提交")
    if cmd == "log":
        r = _git("log", "--oneline", "-n", sys.argv[2] if len(sys.argv) > 2 else "20")
        print((r.stdout or "").strip() or "（无提交）")
    elif cmd == "status":
        st, fs, hd = _git("status", "--porcelain"), _git("ls-files"), _git("rev-parse", "--short", "HEAD")
        print("链仓库 %s｜HEAD=%s｜跟踪%d文件｜未提交%d行" % (S["root"], (hd.stdout or "").strip() or "（空）",
              len((fs.stdout or "").splitlines()), len((st.stdout or "").splitlines())))
    else: print("用法：chains_git.py status|log [n]")
