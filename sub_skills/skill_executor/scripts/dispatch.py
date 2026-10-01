#!/usr/bin/env python3
"""dispatch.py — 依据 task.json + register.json 规划子任务→技能→工具→权限。"""
import os, sys, json, time
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts"))]
PERMS = {
    "read": "read", "glob": "read", "grep": "read", "semantic_search": "read",
    "skill": "read", "question": "read", "list_mcp_resources": "read", "read_mcp_resource": "read",
    "write": "write", "edit": "write", "memory_create_entities": "write", "memory_add_observations": "write",
    "bash": "execute", "task": "execute", "agent_manager": "execute", "background_process": "execute",
    "websearch": "network", "webfetch": "network", "generate_image": "network",
}
SKILL_REQ = {"login-vault": "vault", "captcha-assist": "verify"}
DATE = time.strftime("%Y-%m-%d")

def _load(sms, rel):
    p = os.path.join(sms, rel)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}

def _match(goal, skills):
    g = goal.lower()
    for sid, s in skills.items():
        toks = [t for t in sid.lower().split("_") if len(t) >= 4] + [str(s.get("name", "")).lower()]
        if sid.lower() in g or any(t and t in g for t in toks):
            return sid, s
    return None, None

def plan(sms):
    task = _load(sms, f"sessions/{DATE}/task.json")
    skills = {s["id"]: s for s in _load(sms, "registry/register.json").get("skills", [])}
    out = []
    for st in task.get("subtasks", []):
        sid, s = _match(st.get("goal", ""), skills)
        lb = (s or {}).get("trust") or "unlabeled"
        blocked = lb in ("quarantine", "pending_review")
        tools = [] if blocked else ((s.get("tools") or []) if s else [])
        req = {PERMS.get(t, "execute") for t in tools} | ({SKILL_REQ[sid]} if sid in SKILL_REQ else set())
        out.append({"subtask_id": st.get("id"), "goal": st.get("goal"), "skill_id": sid, "trust": lb,
                    "tools": tools, "requires": sorted(req),
                    "needs_new": s is None, "return_to": "sms"})
    return {"schema": "skill_executor", "version": "1.0.0",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "intent": task.get("intent", ""), "dispatches": out}

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home, emit
    sms = resolve_home.ensure()
    print(emit.write_json(os.path.join(sms, "registry", "dispatch.json"),
                          plan(sms), sms, "--write" not in sys.argv))