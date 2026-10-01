#!/usr/bin/env python3
"""register.py — 扫描技能安装位置与所用工具，生成 registry/register.json；默认扫描根读 skills_config（<SMS_HOME>/config/skills.json 的 scan_roots），--add-root <path> 登记本地目录/文件为扫描根；根自身含 SKILL.md（或 skill/SKILL.md）时该根即作为一个技能登记（按路径加入单个 skill），父子根重复命中自动去重。"""
import os, sys, time, glob

TOOLS = ["read", "write", "edit", "glob", "grep", "bash", "task", "skill", "websearch", "webfetch"]
DEFAULT_ROOTS = [os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sub_skills"), os.path.expanduser("~/.kilocode/skills")]

def find_skills(roots):
    out = []; seen = set()
    for root in roots:
        for d in [root] + sorted(glob.glob(os.path.join(root, "*"))):  # root 自身含 SKILL.md 也登记（按路径加入 skill 可直接指技能夹）
            for rel in ("SKILL.md", "skill/SKILL.md"):
                if os.path.isfile(os.path.join(d, rel)) and d not in seen:
                    seen.add(d); out.append((os.path.basename(d), d, os.path.join(d, rel), rel)); break
    return out

def meta(sk):
    rows = open(sk, encoding="utf-8", errors="ignore").read().splitlines()
    low = "\n".join(rows).lower()
    i = next((i for i, l in enumerate(rows) if l.strip().startswith("description:")), -1)
    v = rows[i].split(":", 1)[1].strip() if i >= 0 else ""
    d = v.strip("\"'") if v and v[0] not in ">|" else (rows[i + 1].strip() if 0 <= i < len(rows) - 1 else "")
    return [t for t in TOOLS if t in low], d[:100]

def build(sms, roots):
    rows = []
    import trust
    for n, d, sk, rel in find_skills(roots):
        tools, desc = meta(sk)
        rows.append({"id": n, "name": n, "install_path": d, "entry": rel,
                     "kind": "sub_skill" if "sub_skills" in d else "skill",
                     "tools": tools, "description": desc,
                     "status": "active", "updated_at": time.strftime("%Y-%m-%d"),
                     "trust": trust.label_of(sms, n)})
    doc = {"schema": "skill_register", "version": "1.0.0",
           "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "scan_roots": roots, "skills": rows}
    return os.path.join(sms, "registry", "register.json"), doc

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home, skills_config
    sms = resolve_home.ensure(); args = sys.argv[1:]
    if "--add-root" in args: v = args[args.index("--add-root") + 1]; print(skills_config.add_root(v, sms)); args = [a for a in args if not a.startswith("--") and a != v]
    roots = [a for a in args if not a.startswith("--")] or skills_config.roots(sms) or DEFAULT_ROOTS  # 批4修复：--write 等旗标曾被当扫描根致注册表刷空
    out, doc = build(sms, roots)
    import emit
    print(emit.write_json(out, doc, sms, "--write" not in sys.argv))