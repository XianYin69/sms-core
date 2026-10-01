#!/usr/bin/env python3
"""init_registry.py — 初始设置：register → pack → connect → deps 一次跑通。"""
import os, sys, json


def run(sms, roots, dry):
    import register, pack, connect, deps, emit
    _, reg = register.build(sms, roots)
    _, itf = pack.pack(sms, reg)
    _, con = connect.build(sms, reg, itf)
    _, dp = deps.build(sms, reg)
    files = ((os.path.join(sms, "registry", "register.json"), reg),
             (os.path.join(sms, "registry", "interfaces.json"), itf),
             (os.path.join(sms, "registry", "connections.json"), con),
             (os.path.join(sms, "registry", "deps.json"), dp))
    if dry:
        return {os.path.basename(o): d for o, d in files}
    return {os.path.basename(o): emit.write_json(o, d, sms, False) for o, d in files}


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home, register
    sms = resolve_home.ensure()
    roots = [a for a in sys.argv[1:] if not a.startswith("--")] or register.DEFAULT_ROOTS
    res = run(sms, roots, "--write" not in sys.argv)
    print(json.dumps(res, ensure_ascii=False, indent=2))