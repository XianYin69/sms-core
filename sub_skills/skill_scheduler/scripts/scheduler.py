#!/usr/bin/env python3
"""scheduler.py — 任务字段并发：五 lane 并行（理解/拆分/注册/权限/整合），写 scheduler.json。"""
import os, sys, time
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts"))]
from concurrent.futures import ThreadPoolExecutor

LANES = ("understand", "decompose", "register", "permit", "integrate")


def _work(lane, sms, intent, dry):
    if lane == "understand":
        import task
        return {"lane": lane, "out": task.understand(intent)}
    if lane == "decompose":
        import task
        return {"lane": lane, "subtasks": task.decompose(intent)}
    if lane == "register":
        import process
        return {"lane": lane, **process.act(sms, "spawn", "scheduler", ["integrate"], dry)}
    if lane == "permit":
        import permissions
        return {"lane": lane, **permissions.apply(sms, "check", "write", True)}
    import task
    return {"lane": lane, "merged": task.merge(intent)}


def schedule(sms, intent, slots, dry):
    with ThreadPoolExecutor(max_workers=slots or len(LANES)) as ex:
        results = list(ex.map(lambda l: _work(l, sms, intent, dry), LANES))
    doc = {"schema": "skill_scheduler", "version": "1.0.0",
           "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "slots": slots or len(LANES), "lanes": results}
    import emit
    return emit.write_json(os.path.join(sms, "registry", "scheduler.json"), doc, sms, dry)


if __name__ == "__main__":
    import resolve_home
    sms = resolve_home.ensure()
    intent = sys.argv[1] if len(sys.argv) > 1 else "（未填写意图）"
    slots = None
    if "--slots" in sys.argv:
        try:
            slots = max(1, int(sys.argv[sys.argv.index("--slots") + 1]))
        except (IndexError, ValueError):
            slots = None
    print(schedule(sms, intent, slots, "--write" not in sys.argv))