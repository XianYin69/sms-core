#!/usr/bin/env python3
"""remove.py — 删除 skill：从目标客户端 skills 目录/hub 移除指定技能；默认预览，--write 且已授予 write 才删，需 --yes 确认 + grant danger（高危键，红线 16），拒删受保护本体。"""
import os, sys, json, shutil

PROTECT = {"skill_manage_system", "Skill_Generator", "skill_executor", "skill_register",
           "skill_packer", "skill_connector", "skill_scheduler"}


def locate(name, roots):
    return [d for d in (os.path.join(r, name) for r in roots)
            if os.path.isdir(d) and os.path.isfile(os.path.join(d, "SKILL.md"))]


def remove(sms, name, write, yes):
    if name in PROTECT or name in (".", "..", "") or "/" in name or "\\" in name:
        return {"error": "拒绝删除受保护或非法技能名: " + str(name)}
    from sync_skills import clients
    roots = sorted(set(list(clients().values()) + [os.path.join(sms, "skills")]))
    hits = locate(name, roots)
    if not hits:
        return {"error": "未找到技能: " + name}
    if not yes:
        return {"confirm_required": True, "would_remove": hits, "hint": "加 --yes 确认删除；--write 落盘"}
    acts = []
    for d in hits:
        if not write:
            acts.append("would remove " + d); continue
        shutil.rmtree(d, ignore_errors=True); acts.append("removed " + d)
    if write:
        import trust; trust.mark(sms, name, "unlabeled", "local", "remove", write=write)
    return {"skill": name, "actions": acts}


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home, permissions
    sms = resolve_home.ensure(); argv = sys.argv[1:]; w = "--write" in argv
    pos = [x for x in argv if not x.startswith("--")]
    if not pos: print("用法: remove.py <skill_name> --yes --write"); sys.exit(1)
    if w and not permissions.allow(sms, "write"): print("DENIED: 会话未授予 write 权限（permissions.json）"); sys.exit(1)
    if w and "--yes" in argv and not permissions.allow(sms, "danger"): print("DENIED: 递归删除属高危，须用户当轮确认后 grant danger（红线 16）"); sys.exit(1)
    print(json.dumps(remove(sms, pos[0], w, "--yes" in argv), ensure_ascii=False, indent=2))
