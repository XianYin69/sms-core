#!/usr/bin/env python3
"""emit.py — 统一写盘门控：默认预览；仅当 --write 且会话已授予 write 才落盘。"""
import os, json


def write_json(path, doc, sms, dry):
    if dry:
        return "（dry-run 预览·未写盘——加 --write 且已 grant write 才生效）\n" + json.dumps(doc, ensure_ascii=False, indent=2)
    import permissions
    if not permissions.allow(sms, "write"):
        return "DENIED: 会话未授予 write 权限（permissions.json），拒绝写盘"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if os.path.basename(os.path.dirname(os.path.dirname(path))) == "sessions":
        import auto_compress; auto_compress.maybe(sms)
        import dream; dream.maybe(sms)
    return "OK " + path