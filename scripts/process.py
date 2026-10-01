#!/usr/bin/env python3
"""process.py — 进程式注册：spawn/run/suspend/resume/kill，写 registry/processes.json。"""
import os, sys, json, time

STATES = ("spawn", "run", "suspend", "resume", "kill")


def _load(sms):
    p = os.path.join(sms, "registry", "processes.json")
    doc = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {
        "schema": "skill_process", "version": "1.0.0", "procs": []}
    return p, doc


def _next(doc):
    ids = [int(x["pid"][1:]) for x in doc["procs"] if x.get("pid", "p")[1:].isdigit()]
    return f"p{(max(ids, default=0) + 1)}"


def act(sms, op, skill, slots, dry):
    if op not in STATES:
        return {"error": f"unknown op {op}"}
    p, doc = _load(sms)
    if op == "spawn":
        pid = _next(doc)
        doc["procs"].append({"pid": pid, "skill_id": skill or "unknown", "state": "spawn",
                             "slots": slots, "granted": ["read"],
                             "spawned_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")})
        res = {"pid": pid, "state": "spawn"}
    else:
        hit = [x for x in doc["procs"] if (not skill or x["skill_id"] == skill) and x["state"] != "kill"]
        for x in hit:
            x["state"] = op
        res = {"changed": [x["pid"] for x in hit]}
    if dry:
        return dict(res, dry_run=True)
    import emit
    return dict(res, persisted=emit.write_json(p, doc, sms, False))


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home
    sms = resolve_home.ensure()
    op = sys.argv[1] if len(sys.argv) > 1 else "spawn"
    skill = sys.argv[2] if len(sys.argv) > 2 else None
    slots = ([a for a in sys.argv[3:] if not a.startswith("--")] or None)
    print(json.dumps(act(sms, op, skill, slots, "--write" not in sys.argv), ensure_ascii=False))