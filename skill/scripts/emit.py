#!/usr/bin/env python3
"""emit.py — 统一写盘门控：默认预览；仅当 --write 且会话已授予 write 才落盘。"""
import os, json


def write_json(path, doc, sms, dry):
    if dry:
        return "（dry-run 预览·未写盘——加 --write 且已 grant write 才生效）\n" + json.dumps(doc, ensure_ascii=False, indent=2)
    import permissions
    if not permissions.allow(sms, "write"):
        return "DENIED: 会话未授予 write 权限（permissions.json），拒绝写盘"
    # 批39 缺陷D1 护栏：空清单绝不覆盖非空真源（实测 pack 在非规范目录 --write 把
    # registry/interfaces.json 从 79 条清成 skills:[]，全技能瞬时不可派发＝线上事故）。
    if isinstance(doc, dict) and isinstance(doc.get("skills"), list) and not doc["skills"]:
        try:
            prev = json.load(open(path, encoding="utf-8")).get("skills") or []
        except Exception:
            prev = []
        if prev:
            return "DENIED: 空技能清单拒绝覆盖非空真源（%d 条在册）——检查扫描根是否正确（skills_config.roots）" % len(prev)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if os.path.basename(os.path.dirname(os.path.dirname(path))) == "sessions":
        import auto_compress; auto_compress.maybe(sms)
        import dream; dream.maybe(sms)
    return "OK " + path