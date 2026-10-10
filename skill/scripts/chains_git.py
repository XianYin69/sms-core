#!/usr/bin/env python3
"""chains_git.py — 十一链数据 git 管理（2026-09-25 用户红线：所有链必须使用 git 管理）：首次触链自动 git init <SMS_HOME>/chains 并把既有全部链导入提交；此后任何链写入防抖 5 秒自动 commit、进程退出兜底 flush；git 缺失或 init 失败即静默降级不阻断记录；ensure 只认 toplevel＝链目录自身（2026-09-26 修复：旧 rev-parse --git-dir 向上穿透命中祖先仓库，测试/临时 SMS_HOME 落他人工作树内时 add -A 混吞外层改动＝「混吞批」事故根因）；手动：python chains_git.py status|log [n]。"""
import os, sys, time, threading, atexit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import no_window  # 静默子进程：链防抖 commit 不再闪黑框
from time import strftime
S = {"root": None, "timer": None, "ok": False}
def _git(*a):
    if not S["root"]: return None
    try: return no_window.run(("git", "-C", S["root"]) + a, capture_output=True, text=True, encoding="utf-8", errors="replace")
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
    # 批39 速度：ensure() 不再同步跑 commit——实测链目录 1.2 万文件时 git status 单发 178ms、
    # 未提交 1 万行时 add -A 秒级，而 ensure 由 Store.__init__ 触发＝每次链写入/每次路由都付这笔钱
    # （新进程首次 route 503ms 里约 500ms 是它）。红线「所有链进 git」不变：首建（fresh）当场导入提交；
    # 非首建只排一次防抖后台提交（5s 合并·daemon 线程·进程退出 atexit 兜底），不再挡用户首字。
    if fresh:
        commit("建链仓库·导入既有链")
    else:
        touch()
    return True
def touch():
    if not S["ok"]: return
    if S["timer"]: S["timer"].cancel()
    t = threading.Timer(5.0, commit, args=("链写入",)); t.daemon = True; S["timer"] = t; t.start()
LOCKFAIL = ("index.lock", "cannot lock ref", "lock exists")
STREAK = {"n": 0}
def _lock_cleanup():
    """崩溃/强杀遗留的陈旧锁自愈：index.lock 存在且 mtime＞5min 且无 git 进程在跑 → 删除重试一次
    （实测 10-04 遗留的 0 字节锁让 6 天内每次 add/commit rc=128 被静默吞掉＝红线破了无人知）。"""
    try:
        lk = os.path.join(S["root"], ".git", "index.lock")
        if not os.path.isfile(lk) or time.time() - os.path.getmtime(lk) < 300: return False
        r = no_window.run(("tasklist", "/FI", "IMAGENAME eq git.exe", "/NH"), capture_output=True, text=True, timeout=8)
        if r is None or "git.exe" in (r.stdout or ""): return False  # 探不到就当在跑（保守不删锁）
        os.remove(lk); return True
    except Exception:
        return False
def _alarm(msg):
    """归档失败可见化：event 链＋error 链（chain_error 按签名去重），不再静默吞 rc。"""
    try:
        import chains; chains.log("tool", "链 git 归档失败：" + msg[:160])
    except Exception: pass
    try:
        import chain_error; chain_error.hook("shell", "chains_git.commit", msg[:200])
    except Exception: pass
def commit(why):
    st = _git("status", "--porcelain")
    if st is None or not st.stdout.strip(): return False
    _git("add", "-A")
    r = _git("commit", "-m", "chore(chains): %s归档%d项 %s" % (why, len(st.stdout.splitlines()), strftime("%Y-%m-%dT%H:%M:%S")))
    if r is not None and r.returncode != 0:
        err = ((r.stderr or "") + (r.stdout or ""))[:200]
        if any(k in err for k in LOCKFAIL) and _lock_cleanup():
            r2 = _git("commit", "-m", "chore(chains): %s归档%d项 %s" % (why, len(st.stdout.splitlines()), strftime("%Y-%m-%dT%H:%M:%S")))
            if r2 is not None and r2.returncode == 0:
                STREAK["n"] = 0; _alarm("陈旧锁已自愈后归档成功（" + why + "）"); return True
        STREAK["n"] += 1
        if STREAK["n"] in (1, 5) or STREAK["n"] % 20 == 0: _alarm("连续%d次失败 rc=%s %s" % (STREAK["n"], r.returncode, err))
        return False
    STREAK["n"] = 0
    return True
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
