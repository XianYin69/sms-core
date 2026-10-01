#!/usr/bin/env python3
"""skill_errors.py — 记录 skill 出错位置与日志：SMS/errors/skill_errors.json；同一(skill,where)合并计数；每笔直调 debug.py error 通道落 debug.log（做梦自修取错误现场）；未解决≥TH 时 due 提示启用 Skill_Generator self_update 修复（list/due 同义）。"""
import os, sys, json, time
TH = 3; DATE = time.strftime("%Y-%m-%d")
def _p(sms): return os.path.join(sms, "errors", "skill_errors.json")

def _doc(sms):
    return json.load(open(_p(sms), encoding="utf-8")) if os.path.exists(_p(sms)) else {"updated": DATE, "entries": []}

def _save(sms, doc, write):
    doc["updated"] = DATE
    if not write: return {"preview": True, "entries": doc["entries"]}
    import permissions
    if not permissions.allow(sms, "write"): return {"denied": "会话未授予 write 权限（permissions.json），拒绝写盘"}
    os.makedirs(os.path.dirname(_p(sms)), exist_ok=True)
    json.dump(doc, open(_p(sms), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": _p(sms)}

def record(sms, skill, where, msg, write):
    doc = _doc(sms)
    e = next((x for x in doc["entries"] if x["skill"] == skill and x["where"] == where and x["status"] == "open"), None)
    if e: e["count"] += 1; e["last"] = DATE
    else: doc["entries"].append({"skill": skill, "where": where, "msg": msg, "count": 1, "first": DATE, "last": DATE, "status": "open"})
    import chain_error; chain_error.hook("skill", skill + "@" + where, msg)
    import debug; debug.error("skill_error %s@%s ×%d %s" % (skill, where, (e or doc["entries"][-1])["count"], msg), sms)
    return _save(sms, doc, write)

def resolve(sms, skill, write):
    doc = _doc(sms); n = 0
    for x in doc["entries"]:
        if x["skill"] == skill and x["status"] == "open": x["status"] = "resolved"; x["last"] = DATE; n += 1
    if not n: return {"error": "无 %s 未解决记录" % skill}
    return _save(sms, doc, write)

def due(sms):
    agg = {}
    for x in _doc(sms)["entries"]:
        if x["status"] == "open": agg[x["skill"]] = agg.get(x["skill"], 0) + x["count"]
    hits = {k: v for k, v in agg.items() if v >= TH}
    return {"due": hits, "suggest": ["启用 Skill_Generator self_update 修复 %s（未解决错误 %d 处）" % (k, v) for k, v in hits.items()]}

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home
    sms = resolve_home.ensure(); a = [x for x in sys.argv[1:] if not x.startswith("--")]; w = "--write" in sys.argv
    opt = lambda k, d="": sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
    cmd = a[0] if a else "list"
    r = record(sms, a[1], opt("--where", "unknown"), opt("--msg", ""), w) if cmd == "record" else resolve(sms, a[1], w) if cmd == "resolve" else due(sms)
    print(json.dumps(r, ensure_ascii=False, indent=2))
