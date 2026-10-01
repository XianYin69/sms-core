#!/usr/bin/env python3
"""task.py — 任务的拆分·理解·整合（understand/decompose/integrate/merge）。"""
import os, sys, time


def understand(intent):
    return intent.strip()[:120] or "（未填写意图）"


def decompose(intent):
    out, word = [], ""
    for ch in intent:
        word += ch
        if ch in "，,。;；\n":
            part = word.strip("，,。;； \n")
            if part:
                out.append(part)
            word = ""
    if word.strip("，,。;； \n"):
        out.append(word.strip("，,。;； \n"))
    return [{"id": f"t{i + 1}", "goal": g, "status": "pending"} for i, g in enumerate(out)] or \
        [{"id": "t1", "goal": understand(intent), "status": "pending"}]


def integrate(subtasks, results):
    done = [t["goal"] for t in subtasks for r in results if r.get("task_id") == t["id"]]
    return "；".join(done) or "（无结果可整合）"


def merge(intent):
    sub = decompose(intent)
    return integrate(sub, [{"task_id": t["id"]} for t in sub])


def build(intent):
    return {"schema": "skill_task", "version": "1.0.0", "intent": intent,
            "understanding": understand(intent), "subtasks": decompose(intent),
            "merged": merge(intent)}


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try: __import__("session_reg").bind("bg", "task", "任务拆分")
    except Exception: pass
    import resolve_home, emit
    sms = resolve_home.ensure()
    intent = sys.argv[1] if len(sys.argv) > 1 else "（未填写意图）"
    p = os.path.join(sms, "sessions", time.strftime("%Y-%m-%d"), "task.json")
    print(emit.write_json(p, build(intent), sms, "--write" not in sys.argv))