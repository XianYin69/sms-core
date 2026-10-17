#!/usr/bin/env python3
"""skill_errors.py — 记录 skill 出错位置与日志：SMS/errors/skill_errors.json；同一(skill,where)合并计数；未解决≥TH 时 due 提示启用 Skill_Generator self_update 修复（list/due 同义）。

新增状态：caller_error（调用方参数缺失等，非技能缺陷）
"""
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

def record(sms, skill, where, msg, write, status=None):
    """登记错误；status 可选：open/resolved/not_defect/caller_error，默认 open"""
    doc = _doc(sms)
    # caller_error 和 open 分开统计
    e = next((x for x in doc["entries"] if x["skill"] == skill and x["where"] == where 
              and x["status"] in ("open", status or "open")), None)
    if e:
        e["count"] += 1
        e["last"] = DATE
        if status and status != e["status"]:
            e["status"] = status
    else:
        entry = {"skill": skill, "where": where, "msg": msg, "count": 1, 
                 "first": DATE, "last": DATE, "status": status or "open"}
        doc["entries"].append(entry)
    return _save(sms, doc, write)

def resolve(sms, skill, write):
    doc = _doc(sms); n = 0
    for x in doc["entries"]:
        if x["skill"] == skill and x["status"] == "open":
            x["status"] = "resolved"
            x["last"] = DATE
            n += 1
    if not n: return {"error": "无 %s 未解决记录" % skill}
    return _save(sms, doc, write)

def due(sms):
    agg = {}
    for x in _doc(sms)["entries"]:
        if x["status"] in ("open", "caller_error"):  # caller_error 也计未解决
            agg[x["skill"]] = agg.get(x["skill"], 0) + x["count"]
    hits = {k: v for k, v in agg.items() if v >= TH}
    return {"due": hits, "suggest": ["启用 Skill_Generator self_update 修复 %s（未解决错误 %d 处）" % (k, v) for k, v in hits.items()]}

def list_errors(sms, exclude_caller=False):
    """列出错误；exclude_caller=True 时排除 caller_error 看技能真问题"""
    entries = _doc(sms)["entries"]
    if exclude_caller:
        entries = [e for e in entries if e["status"] != "caller_error"]
    return {"entries": entries, "total": len(entries)}

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home
    sms = resolve_home.ensure()
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    w = "--write" in sys.argv
    opt = lambda k, d="": sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
    
    cmd = a[0] if a else "list"
    if cmd == "record":
        r = record(sms, a[1], opt("--where", "unknown"), opt("--msg", ""), w, opt("--status"))
    elif cmd == "resolve":
        r = resolve(sms, a[1], w)
    elif cmd == "list":
        exclude = "--exclude-caller" in sys.argv
        r = list_errors(sms, exclude_caller=exclude)
    elif cmd == "due":
        r = due(sms)
    else:
        r = {"error": f"未知命令: {cmd}"}
    print(json.dumps(r, ensure_ascii=False, indent=2))
