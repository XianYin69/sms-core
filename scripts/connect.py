#!/usr/bin/env python3
"""connect.py — 依据 register/interfaces 生成技能间上下文连接，写 connections.json。"""
import os, sys, time

PIPELINE = [
    ("skill_register", "skill_packer", ["install_path", "tools"]),
    ("skill_packer", "skill_connector", ["interfaces"]),
]


def build(sms, reg, itf):
    ids = {s["id"] for s in reg.get("skills", [])}
    chains = []
    for a, b, c in PIPELINE:
        if a in ids and b in ids:
            chains.append({"id": f"c{len(chains) + 1}", "from": a, "to": b,
                           "context": c, "handoff": f"{a} 输出 → {b} 输入"})
    for s in itf.get("skills", []):
        for dep in s.get("dependencies", []):
            if dep in ids:
                chains.append({"id": f"c{len(chains) + 1}", "from": dep,
                               "to": s["skill_id"], "context": s["context_in"],
                               "handoff": "依赖注入"})
    doc = {"schema": "skill_connector", "version": "1.0.0",
           "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"), "chains": chains}
    return os.path.join(sms, "registry", "connections.json"), doc


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home, register, pack
    sms = resolve_home.ensure()
    roots = [a for a in sys.argv[1:] if not a.startswith("--")] or register.DEFAULT_ROOTS
    _, reg = register.build(sms, roots)
    _, itf = pack.pack(sms, reg)
    out, doc = build(sms, reg, itf)
    import emit
    print(emit.write_json(out, doc, sms, "--write" not in sys.argv))