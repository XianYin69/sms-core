#!/usr/bin/env python3
"""user_index.py — 用户「/」索引层：文件或文件夹经壳内文件选择菜单或 `:index <路径>` 登记为索引项，存 <SMS_HOME>/config/skills.json 的 index_items（{name,path,kind}，name＝末段、重名自动加短哈希）；技能令牌 /<id> 不落盘、实时取自 registry 活跃技能。TUI 菜单以「/名称」插入输入行；提交时 expand() 把令牌就地展开为 文件/目录/SKILL.md 引用（左界定符＋仅匹配已登记名，绝不误伤 C:/ 等路径）。用法：python -B user_index.py list|add <path>|rm <name>。"""
import os, sys, re, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import skills_config
KEY = "index_items"
def load(sms=None): return [x for x in (skills_config.get(KEY, [], sms) or []) if isinstance(x, dict) and x.get("name") and x.get("path")]
def save(items, sms=None): skills_config.set(KEY, items, sms); return items
def add(p, sms=None):
    p = os.path.abspath(os.path.expanduser(p)); name = os.path.basename(os.path.normpath(p)) or p
    items = load(sms)
    if any(x["path"] == p for x in items): return "已在索引：" + p
    if any(x["name"] == name for x in items): name += "#" + hashlib.md5(p.encode()).hexdigest()[:4]
    save(items + [{"name": name, "path": p, "kind": "dir" if os.path.isdir(p) else "file"}], sms)
    return "已加入索引 /" + name + " → " + p
def rm(name, sms=None):
    items = load(sms); out = [x for x in items if x["name"] != name]; save(out, sms)
    return "已移出索引 /" + name if len(out) < len(items) else "无索引项：" + name
def skills_map(sms=None):
    try:
        import skill_route
        return {str(s.get("id")): os.path.join(str(s.get("install_path", "")), str(s.get("entry", "SKILL.md"))) for s in skill_route.skills(sms) if s.get("id")}
    except Exception: return {}
def refs(sms=None):
    m = {x["name"]: x for x in load(sms)}
    for k, v in skills_map(sms).items(): m.setdefault(k, {"name": k, "path": v, "kind": "skill"})
    return m
def expand(text, sms=None):
    rep = []
    for name, x in refs(sms).items():
        r = ("托管技能 " + name + "（按其 SKILL.md 派发对等对话执行：" + x["path"] + "）") if x["kind"] == "skill" else (("目录：" if x["kind"] == "dir" else "文件：") + x["path"])
        text, n = re.subn(r"(?:(?<=^)|(?<=[\s,，;；（(]))/" + re.escape(name) + r"(?=$|[\s,，;；。！？?!）)])", lambda _m, _r=r: _r, text)
        if n: rep.append("/" + name)
    return text + (("\n[索引展开] " + "、".join(rep)) if rep else "")
def fill(ta, name):
    ta.text = (ta.text.rstrip() + "  " if ta.text.strip() else "") + "/" + name + " "
    try:
        ls = (ta.text or "").splitlines() or [""]; ta.cursor_location = (len(ls) - 1, len(ls[-1]))
    except Exception: pass
    return ta
if __name__ == "__main__":
    a = sys.argv[1:] or ["list"]; cmd = a[0]
    if cmd == "list": print(json.dumps(load(), ensure_ascii=False, indent=2))
    elif cmd == "add" and len(a) > 1: print(add(" ".join(a[1:])))
    elif cmd == "rm" and len(a) > 1: print(rm(a[1]))
    else: print(__doc__.strip().splitlines()[-1])
