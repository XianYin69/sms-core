#!/usr/bin/env python3
"""session.py — 在 SMS/sessions/<日期>/ 建立五元组（对话/用户链/逻辑链/技能/权限），并把会话日/意图同步登记到全局十一链（time/event/user）。"""
import os, sys, json, time

DATE = time.strftime("%Y-%m-%d")

def _files(intent):
    import permissions
    return {
        "dialogue.md": f"# 对话 · {DATE}\n\n## 意图\n{intent}\n\n## 记录\n",
        "user_chain.json": {"date": DATE, "intent": intent, "user": None, "context": []},
        "logic_chain.json": {"nodes": [{"id": "n1", "type": "intent", "label": intent}], "edges": []},
        "skills.json": {"used": []},
        "permissions.json": {"date": DATE, "audit": [], "grants": dict(permissions.DEFAULT_GRANTS)},
    }

def create(sms, intent, persist):
    d = os.path.join(sms, "sessions", DATE)
    files = _files(intent)
    if not persist:
        return d, files
    import chains
    os.makedirs(d, exist_ok=True)
    for c, txt in (("time", "会话日 " + DATE + " 建立"), ("event", "intent:" + intent), ("user", intent)):
        chains.record(c, txt)
    for name, data in files.items():
        p = os.path.join(d, name)
        if os.path.exists(p):
            continue
        if name.endswith(".json"):
            json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        else:
            open(p, "w", encoding="utf-8").write(data)
    return d, files

def touch(d, skill_id):
    p = os.path.join(d, "skills.json")
    data = json.load(open(p, encoding="utf-8"))
    if skill_id not in data["used"]:
        data["used"].append(skill_id)
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home
    sms = resolve_home.ensure()
    intent = sys.argv[1] if len(sys.argv) > 1 else "（未填写意图）"
    d, files = create(sms, intent, "--write" in sys.argv)
    print("OK " + d if "--write" in sys.argv else "would create: " + d + " -> " + ", ".join(files))
