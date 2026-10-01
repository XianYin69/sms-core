#!/usr/bin/env python3
"""debate.py — 正反双辩论逻辑链：对一个论断生成 pro/con 两条链与裁决，写 sessions/<日期>/debate.json。"""
import os, sys, time

DATE = time.strftime("%Y-%m-%d")


def _chain(side, claim, reasons):
    nodes = [{"id": side + "0", "type": "claim", "label": ("正方: " if side == "pro" else "反方: ") + claim}]
    edges = []
    for i, r in enumerate(reasons):
        nid = f"{side}{i + 1}"
        nodes.append({"id": nid, "type": "argument", "label": str(r)})
        edges.append({"from": nodes[i]["id"], "to": nid})
    return {"nodes": nodes, "edges": edges}


def debate(claim, pro, con):
    pc, cc = _chain("pro", claim, pro), _chain("con", claim, con)
    verdict = "pro" if len(pro) > len(con) else ("con" if len(con) > len(pro) else "tie")
    return {"schema": "skill_debate", "version": "1.0.0", "claim": claim,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "pro": pc, "con": cc, "verdict": verdict, "rounds": max(len(pro), len(con))}


def _many(argv, flag):
    return [argv[i + 1] for i, x in enumerate(argv) if x == flag]


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home, emit
    sms = resolve_home.ensure()
    argv = sys.argv[1:]
    doc = debate((_many(argv, "--claim") or ["（未填写论断）"])[0],
                 _many(argv, "--pro") or ["（无正方论据）"], _many(argv, "--con") or ["（无反方论据）"])
    print(emit.write_json(os.path.join(sms, "sessions", DATE, "debate.json"), doc, sms, "--write" not in argv))
