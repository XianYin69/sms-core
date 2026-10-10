#!/usr/bin/env python3
"""pack.py — 读取 register.json，描述每个技能的用途与接口，生成 interfaces.json。"""
import os, sys, time, re


def headings(sk):
    try:
        txt = open(sk, encoding="utf-8").read()
    except Exception:
        return []
    return re.findall(r"^#{1,3}\s+(.*)$", txt, re.M)


def pack(sms, reg):
    rows = []
    for s in reg.get("skills", []):
        heads = headings(os.path.join(s["install_path"], s.get("entry", "SKILL.md")))
        caps = [h for h in heads if h.lower() != s["id"]][:8]
        rows.append({
            "skill_id": s["id"], "purpose": s.get("description", ""),
            "capabilities": caps,
            "interfaces": [{"name": h, "description": s.get("description", "")} for h in caps],
            "context_in": [], "context_out": ["result"],
            "dependencies": [],
        })
    doc = {"schema": "skill_packer", "version": "1.0.0",
           "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"), "skills": rows}
    return os.path.join(sms, "registry", "interfaces.json"), doc


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home, register, skills_config
    sms = resolve_home.ensure()
    # 批39 缺陷D1：旧版扫描根由 register.DEFAULT_ROOTS（=__file__ 派生）取，同一 pack.py
    # 在不同 cwd/挂载形态下条数 79→11→0；`pack --write` 命中非规范目录即把线上 interfaces.json 清成空表。
    # 现与 register.py __main__ 同口径：位置参数 → skills_config.roots(sms) → DEFAULT_ROOTS 三级找回。
    roots = [a for a in sys.argv[1:] if not a.startswith("--")] or skills_config.roots(sms) or register.DEFAULT_ROOTS
    _, reg = register.build(sms, roots)
    out, doc = pack(sms, reg)
    import emit
    print(emit.write_json(out, doc, sms, "--write" not in sys.argv))