#!/usr/bin/env python3
"""deps.py — 依赖库：关联 skill（.md 互相提及判定 depends/independent/related）+ 关联 python（deps_scan 扫描）→ registry/deps.json。"""
import glob, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deps_scan

KINDS = (("independent", r"独立于|不依赖|无关|互不"), ("depends", r"委托|依赖|需要|调用|导入|拉取|转交"))


def sk_deps(txt, me, ids):
    rows = []
    for other in ids:
        if other == me:
            continue
        m = re.search(re.escape(other), txt, re.I)
        if not m:
            continue
        w = " ".join(txt[max(0, m.start() - 30):m.end() + 30].split())
        kind = next((k for k, pat in KINDS if re.search(pat, w)), "related")
        rows.append({"to": other, "kind": kind, "evidence": w[:80]})
    return rows


def build(sms, reg):
    ids = [s["id"] for s in reg.get("skills", [])]
    rows = []
    for s in reg.get("skills", []):
        txt = "\n".join(open(f, encoding="utf-8", errors="ignore").read()
                        for f in glob.glob(os.path.join(s["install_path"], "**", "*.md"), recursive=True))
        rows.append({"skill_id": s["id"], "related_skills": sk_deps(txt, s["id"], ids),
                     "related_python": deps_scan.py_deps(s["install_path"])})
    doc = {"schema": "skill_deps", "version": "1.0.0", "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"), "skills": rows}
    return os.path.join(sms, "registry", "deps.json"), doc


if __name__ == "__main__":
    import resolve_home, register, emit
    sms = resolve_home.ensure()
    roots = [a for a in sys.argv[1:] if not a.startswith("--")] or register.DEFAULT_ROOTS
    _, reg = register.build(sms, roots)
    out, doc = build(sms, reg)
    print(emit.write_json(out, doc, sms, "--write" not in sys.argv))
