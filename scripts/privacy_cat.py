#!/usr/bin/env python3
"""privacy_cat.py — 隐私类别策略：类别注册表/默认留存天数/超期清理/开账统计，作用于 privacy.py 的 records.json。"""
import json, os, sys
from datetime import date, datetime
CATS = {"identity": ("证件/姓名/地址", 30), "credential": ("账号口令/令牌", 1), "behavior": ("操作轨迹/屏幕内容", 14),
        "content": ("聊天/文档片段", 7), "biometric": ("人脸/指纹/声纹", 7), "contact": ("邮箱/电话", 30),
        "location": ("行踪坐标", 14)}
def _io(d, save=False, doc=None):
    rp = os.path.join(d, "records.json")
    if save:
        json.dump(doc, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=2); return doc
    return json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else {"records": [], "audit": []}
def _age_days(ts):
    try: return (date.today() - datetime.strptime(str(ts)[:10], "%Y-%m-%d").date()).days
    except ValueError: return 10 ** 6
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home, permissions, privacy
    sms = resolve_home.ensure(); d = os.path.join(sms, "privacy"); os.makedirs(d, exist_ok=True)
    doc = _io(d)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        print(json.dumps({k: {"desc": v[0], "retention_days": v[1]} for k, v in CATS.items()}, ensure_ascii=False, indent=2))
    elif cmd == "report":
        cnt = {}
        for r in doc["records"]:
            cnt[r.get("category", "?")] = cnt.get(r.get("category", "?"), 0) + 1
        print(json.dumps({"records_by_category": cnt, "total": len(doc["records"]),
                          "decrypt_opens": sum(1 for a in doc.get("audit", []) if a.get("action") == "open"),
                          "unknown_categories": sorted(c for c in cnt if c not in CATS)}, ensure_ascii=False, indent=2))
    elif cmd == "purge":
        kept = [r for r in doc["records"] if _age_days(r.get("ts")) <= CATS.get(r.get("category"), ("?", 30))[1]]
        removed = len(doc["records"]) - len(kept)
        if "--write" not in sys.argv:
            print(json.dumps({"preview_removed": removed, "hint": "--write 执行（需 grant write）"}, ensure_ascii=False))
        elif not permissions.allow(sms, "write"):
            sys.exit("DENIED: purge 写盘需 grant write")
        else:
            doc["records"] = kept; _io(d, True, doc); privacy.notice(d, doc)
            print("PURGED %d 条超期记录，NOTICE.md 已更新" % removed)
    else:
        print("用法: list | report | purge [--write]")
