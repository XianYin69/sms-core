#!/usr/bin/env python3
"""trust.py — 信任链：为每个 skill 维护 SMS/trust.json 标签（pending_review/trusted_local/trusted_cloud/quarantine/unlabeled）；云端必审（review），本地按日随机 audit。"""
import os, sys, json, time, random

DATE = time.strftime("%Y-%m-%d")
LABELS = ("pending_review", "trusted_local", "trusted_cloud", "quarantine", "unlabeled")


def _p(sms): return os.path.join(sms, "trust.json")

def _doc(sms):
    return json.load(open(_p(sms), encoding="utf-8")) if os.path.exists(_p(sms)) else {}

def label_of(sms, skill):
    return _doc(sms).get(skill, {}).get("label", "unlabeled")

def blocked(sms, skill):
    return label_of(sms, skill) in ("quarantine", "pending_review")

def mark(sms, skill, label, source="local", by="cli", write=True):
    if label not in LABELS: return {"error": "标签需为 " + "/".join(LABELS)}
    doc = _doc(sms); e = doc.setdefault(skill, {"source": source, "chain": []})
    e["label"] = label; e["source"] = source; e["updated"] = DATE
    e["chain"].append({"ts": time.strftime("%F %T"), "action": "mark:" + label, "by": by})
    if not write: return {"preview": True, skill: label}
    json.dump(doc, open(_p(sms), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": _p(sms), skill: label}

def audit_due(sms):
    pool = sorted(k for k, v in _doc(sms).items() if v.get("label") == "trusted_local")
    random.seed(DATE)
    return {"today": random.choice(pool) if pool else None}

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home
    sms = resolve_home.ensure(); a = [x for x in sys.argv[1:] if x != "--write"]; w = "--write" in sys.argv
    cmd = a[0] if a else "list"
    if cmd == "list": r = _doc(sms)
    elif cmd == "label": r = {a[1]: label_of(sms, a[1])}
    elif cmd == "mark": r = mark(sms, a[1], a[2], write=w)
    elif cmd == "review": r = mark(sms, a[1], "trusted_cloud" if a[2] == "pass" else "quarantine", "cloud", "review", w)
    elif cmd == "audit": r = audit_due(sms) if len(a) < 2 else mark(sms, a[1], "trusted_local" if a[2] == "pass" else "quarantine", by="audit", write=w)
    else: r = {"error": "用法: list | label s | mark s <label> | review s pass|fail | audit [s pass|fail] --write"}
    print(json.dumps(r, ensure_ascii=False, indent=2))
