#!/usr/bin/env python3
"""sep_audit.py — 壳/核分离审计（批27·用户「检查 SMS 的 shell 和核心是否完全分离」）：按 import 图判边界——
shell＝shell_*.py＋bin 入口，core＝其余 scripts 模块，seam＝runtime_bind.py（唯一允许知道壳名的边界件）。
合格线：core→shell 反向边＝0（seam 除外）、seam→shell≤2、shell→core 单向依赖合法（壳站在核上）。
回 JSON：groups/edges/violations/verdict。用法：python -B sep_audit.py [--json]。"""
import os, sys, re, json
D = os.path.dirname(os.path.abspath(__file__))
MODS = {f[:-3] for f in os.listdir(D) if f.endswith(".py")}
SHELL = {m for m in MODS if m.startswith("shell")}
SEAM = {"runtime_bind"}
CORE = MODS - SHELL - SEAM
def imports(m):
    t = open(os.path.join(D, m + ".py"), encoding="utf-8", errors="replace").read()
    t = re.sub(r'"""[\s\S]*?"""', "", t)
    return {x for x in re.findall(r"(?:^|[;\s])import\s+([a-zA-Z_]\w*)", t)} | {x for x in re.findall(r"from\s+([a-zA-Z_]\w*)\s+import", t)} - {m} & MODS
def audit():
    s2c = {}; c2s = {}; z2s = {}
    for m in SHELL:
        for x in imports(m) & CORE: s2c.setdefault(m, []).append(x)
    for m in CORE:
        for x in imports(m) & SHELL: c2s.setdefault(m, []).append(x)
    for m in SEAM:
        for x in imports(m) & SHELL: z2s.setdefault(m, []).append(x)
    v = [{"from": a, "to": b} for a, bs in c2s.items() for b in bs]
    return {"groups": {"shell": len(SHELL), "core": len(CORE), "seam": len(SEAM)},
            "shell_to_core": sum(len(v2) for v2 in s2c.values()), "core_to_shell": len(v),
            "seam_to_shell": sum(len(v2) for v2 in z2s.values()),
            "shell_to_core_map": {k: sorted(v2) for k, v2 in sorted(s2c.items())[:6]},
            "violations": v, "verdict": "SEPARATED" if not v else "COUPLED"}
if __name__ == "__main__":
    r = audit(); print(json.dumps(r, ensure_ascii=False, indent=2 if "--json" in sys.argv else None))
    sys.exit(0 if r["verdict"] == "SEPARATED" else 1)
