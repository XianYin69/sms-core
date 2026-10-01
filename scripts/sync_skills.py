#!/usr/bin/env python3
"""sync_skills.py — 多 agent 客户端 skills 管理与同步：SMS/skills 为 hub，pull/push/status 与各客户端 skills 目录同步；sha1(SKILL.md) 比对、冲突取新，pending_review/quarantine 不推送。客户端默认已知目录，env SMS_CLIENTS="name=path;..." 可增改。"""
import os, sys, json, glob, shutil, hashlib

KNOWN = {"kilocode": "~/.kilocode/skills", "claude": "~/.claude/skills", "codex": "~/.codex/skills", "agents": "~/.agents/skills", "cursor": "~/.cursor/skills"}

def clients():
    out = {k: os.path.expanduser(v) for k, v in KNOWN.items() if os.path.isdir(os.path.dirname(os.path.expanduser(v)))}
    for pair in (os.environ.get("SMS_CLIENTS") or "").split(";"):
        if "=" in pair:
            k, v = pair.split("=", 1); out[k.strip()] = os.path.expandvars(os.path.expanduser(v.strip()))
    return out

def _hash(p):
    f = os.path.join(p, "SKILL.md")
    return hashlib.sha1(open(f, "rb").read()).hexdigest()[:10] if os.path.isfile(f) else ""

def scan(root):
    return {os.path.basename(d): d for d in sorted(glob.glob(os.path.join(root, "*"))) if os.path.isfile(os.path.join(d, "SKILL.md"))}

def _copy(src, dst):
    shutil.rmtree(dst, ignore_errors=True); shutil.copytree(src, dst, dirs_exist_ok=True)

def sync(sms, mode, write):
    hubd = os.path.join(sms, "skills"); os.makedirs(hubd, exist_ok=True); hub = scan(hubd); cls = clients()
    rep = {"pull": [], "push": [], "blocked": []}; import trust
    if mode in ("pull", "status"):
        for c, root in sorted(cls.items()):
            for n, p in sorted(scan(root).items()):
                hp = hub.get(n)
                if (not hp) or (_hash(p) != _hash(hp) and os.path.getmtime(os.path.join(p, "SKILL.md")) > os.path.getmtime(os.path.join(hp, "SKILL.md"))):
                    rep["pull"].append(("add " if not hp else "upd ") + c + "/" + n)
                    if write and mode == "pull": _copy(p, hp or os.path.join(hubd, n)); hub = scan(hubd)
    if mode in ("push", "status"):
        for n, p in sorted(scan(hubd).items()):
            lb = trust.label_of(sms, n)
            if lb in ("quarantine", "pending_review"): rep["blocked"].append(n + ":" + lb); continue
            for c, root in sorted(cls.items()):
                dst = os.path.join(root, n)
                if not os.path.isdir(dst) or _hash(dst) != _hash(p):
                    rep["push"].append(("add " if not os.path.isdir(dst) else "upd ") + c + "/" + n)
                    if write and mode == "push": _copy(p, dst)
    return rep

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home, permissions
    sms = resolve_home.ensure(); write = "--write" in sys.argv; mode = next((x for x in sys.argv[1:] if not x.startswith("--")), "status")
    if write and not permissions.allow(sms, "write"): print("DENIED: 会话未授予 write 权限（permissions.json），拒绝同步"); sys.exit(1)
    print(json.dumps(sync(sms, mode, write), ensure_ascii=False, indent=2))
