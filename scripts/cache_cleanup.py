#!/usr/bin/env python3
"""cache_cleanup.py — 按天缓存清理：删除 sessions/ 下早于 --keep-days（默认 7）的日目录。默认预览；--write 且已授予 write 才删除；memory.json 钉选日期保留。"""
import os, sys, json, shutil
from datetime import date

KEEP = 7

def _day_dirs(sms):
    root = os.path.join(sms, "sessions")
    out = []
    for n in os.listdir(root) if os.path.isdir(root) else []:
        try:
            date.fromisoformat(n)
        except ValueError:
            continue
        if os.path.isdir(os.path.join(root, n)):
            out.append(n)
    return sorted(out)

def _pins(sms):
    p = os.path.join(sms, "memory.json")
    pins = set()
    if not os.path.exists(p):
        return pins
    for e in json.load(open(p, encoding="utf-8")).get("entries", []):
        if e.get("date"):
            pins.add(e["date"])
        for tok in str(e.get("path", "")).replace("\\", "/").split("/"):
            if len(tok) == 10 and tok[4] == "-":
                pins.add(tok)
    return pins

def plan(sms, keep_days):
    today = date.today(); pins = _pins(sms)
    return [n for n in _day_dirs(sms) if n not in pins and n != today.isoformat()
            and (today - date.fromisoformat(n)).days > keep_days]

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home, permissions
    sms = resolve_home.ensure()
    keep = int(sys.argv[sys.argv.index("--keep-days") + 1]) if "--keep-days" in sys.argv else KEEP
    targets = plan(sms, keep)
    if "--write" not in sys.argv:
        print("would delete: " + (", ".join(targets) or "无")); sys.exit(0)
    try:  # 后台/非交互：SOLO 自审不入此路（无人应答·防阻塞与成本失控）
        import permissions; permissions.set_noninteractive(True)
    except Exception: pass
    if not permissions.allow(sms, "write"):
        print("DENIED: 会话未授予 write 权限（permissions.json），拒绝清理"); sys.exit(1)
    for n in targets:
        shutil.rmtree(os.path.join(sms, "sessions", n))
    print("OK deleted " + (", ".join(targets) or "无"))
