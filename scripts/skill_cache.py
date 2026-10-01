#!/usr/bin/env python3
"""skill_cache.py — 扫描并清理 skill 目录中的缓存/运行时残留（红线#2 自净工具）：__pycache__/*.pyc 直接删除；tmp/、SMS/、误落 skill 内的 config/config.json 迁入 <SMS_HOME>/tmp/skill_legacy/<ts>/。默认预览；--write 且已授予 write 才执行。"""
import os, sys, shutil, time

SKIP = (".git", ".kilo", ".vscode", ".idea")
DROP_DIRS = ("__pycache__",)
MOVE_DIRS = ("tmp", "SMS")


def scan(root):
    dels, moves = [], []
    for r, dirs, fs in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for d in list(dirs):
            if d in DROP_DIRS or d in MOVE_DIRS:
                (dels if d in DROP_DIRS else moves).append(os.path.join(r, d))
                dirs.remove(d)
        for f in fs:
            p = os.path.join(r, f)
            if f.endswith(".pyc"): dels.append(p)
            elif os.path.basename(r) == "config" and f == "config.json": moves.append(p)
    return dels, moves


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home, permissions
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if "--path" in sys.argv: root = os.path.abspath(sys.argv[sys.argv.index("--path") + 1])
    sms = resolve_home.ensure()
    dels, moves = scan(root)
    legacy = os.path.join(sms, "tmp", "skill_legacy", time.strftime("%Y%m%d-%H%M%S"))
    if "--write" not in sys.argv:
        print("扫描根:", root)
        print("将删除(%d):" % len(dels), ", ".join(os.path.relpath(p, root) for p in dels) or "无")
        print("将迁移(%d) → %s:" % (len(moves), legacy), ", ".join(os.path.relpath(p, root) for p in moves) or "无")
        return
    if not permissions.allow(sms, "write"):
        print("DENIED: 会话未授予 write 权限（permissions.json），拒绝清理"); sys.exit(1)
    for p in dels:
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    for p in moves:
        dst = os.path.join(legacy, os.path.relpath(p, root))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(p, dst)
    print("OK 删除 %d 项；迁移 %d 项%s" % (len(dels), len(moves), " → " + legacy if moves else ""))


if __name__ == "__main__":
    main()
