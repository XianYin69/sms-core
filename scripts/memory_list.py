#!/usr/bin/env python3
"""memory_list.py — 重要记忆列表：管理 SMS/memory.json（add/list/remove）。默认预览；--write 且已授予 write 才落盘。"""
import os, sys, json, time

DATE = time.strftime("%Y-%m-%d")

def _path(sms):
    return os.path.join(sms, "memory.json")

def _doc(sms):
    p = _path(sms)
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    return {"updated": DATE, "entries": []}

def apply(sms, argv, dry):
    doc = _doc(sms); entries = doc["entries"]
    cmd = argv[0] if argv else "list"
    if cmd == "list":
        return {"entries": entries}
    if cmd == "add":
        note = argv[1] if len(argv) > 1 else "（未命名）"
        path = argv[argv.index("--path") + 1] if "--path" in argv else "sessions/" + DATE
        nid = max([e["id"] for e in entries], default=0) + 1
        entries.append({"id": nid, "date": DATE, "path": path, "note": note})
    elif cmd == "remove":
        try:
            nid = int(argv[1])
        except Exception:
            return {"error": "remove 需整数 id"}
        doc["entries"] = [e for e in entries if e["id"] != nid]
        if len(doc["entries"]) == len(entries):
            return {"error": "无 id=%d 的记忆" % nid}
    else:
        return {"error": "用法: add <note> [--path p] | list | remove <id>"}
    doc["updated"] = DATE
    if dry:
        return {"dry_run": True, "entries": doc["entries"]}
    import permissions
    if not permissions.allow(sms, "write"):
        return {"denied": "会话未授予 write 权限（permissions.json），拒绝写盘"}
    json.dump(doc, open(_path(sms), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": _path(sms), "entries": doc["entries"]}

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home
    print(json.dumps(apply(resolve_home.ensure(), sys.argv[1:], "--write" not in sys.argv), ensure_ascii=False, indent=2))
