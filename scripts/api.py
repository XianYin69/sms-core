#!/usr/bin/env python3
"""api.py — 格式 API（并入 sms-shell 统一入口）：`sms-shell api formats|detect|show|validate|export ...`（原 sms-api 命令面不变）或壳内 `:api ...`；亦可直跑本脚本。命令：formats（格式族）· detect（本机客户端技能目录）· show <skill>（解析 frontmatter）· validate <skill>（claude 规范断言）· export <skill> --out <dir> [--format claude|claude-code|openai|all]（默认预览，--write 落盘）。<skill>＝SKILL.md 路径或 <SMS_HOME>/registry/register.json 登记的技能 id。"""
import os, sys, re, json
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try: import sms_formats as F
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "bin")); import sms_formats as F
def sms_home():
    h = os.environ.get("SMS_HOME")
    if h: return h
    home = os.path.expanduser("~")
    c = os.environ.get("LOCALAPPDATA") or (os.path.join(home, "Library", "Caches") if sys.platform == "darwin" else os.path.join(home, ".cache"))
    for cand in (os.path.join(c, "SMS"), os.path.join(home, "SMS")):
        if os.path.isfile(os.path.join(cand, "config", "config.json")): return cand
    return os.path.join(c, "SMS")
def resolve_skill(arg):
    if os.path.isfile(arg): return os.path.abspath(arg)
    reg = os.path.join(sms_home(), "registry", "register.json")
    doc = json.load(open(reg, encoding="utf-8-sig")) if os.path.isfile(reg) else {}
    for s in doc.get("skills", []):
        if arg in (s.get("id"), s.get("name")): return os.path.join(s["install_path"], s.get("entry") or "SKILL.md")
    sys.exit("未找到 skill：%s（给 SKILL.md 路径或 register.json 中的 id）" % arg)
def in_fmt(path, fmt):
    rel = path.replace(os.sep, "/"); group = "openai" if "/openai/" in rel else ("claude" if rel.endswith("SKILL.md") else "claude-code")
    return fmt == "all" or fmt == group
def main(a):
    cmd = a[0] if a else "formats"
    if cmd in ("formats", "detect"):
        if cmd == "formats": print(json.dumps(F.FORMATS, ensure_ascii=False, indent=2)); return
        home = os.path.expanduser("~"); p = lambda x: x if os.path.isdir(os.path.join(home, x)) else None
        print(json.dumps({"claude": p(".claude/skills"), "codex": p(".codex/skills"), "kilocode": p(".kilocode/skills"), "cursor": p(".cursor/skills")}, ensure_ascii=False, indent=2)); return
    if len(a) < 2: sys.exit("用法: sms-shell api formats|detect|show|validate|export <skill> [--out D] [--format F] [--write]")
    skill = resolve_skill(a[1]); meta, _ = F.load(skill)
    if cmd == "show": print(json.dumps({"path": skill, "meta": meta}, ensure_ascii=False, indent=2)); return
    if cmd == "validate":
        bad = [x for x in ("缺 frontmatter/name/description" if not (meta.get("name") and meta.get("description")) else "",
              "name 不符 OpenAI ^[a-z0-9_]{1,64}$" if not re.fullmatch(r"[a-z0-9_]{1,64}", F.openai_name(meta, skill)) else "") if x]
        print(json.dumps({"skill": skill, "ok": not bad, "problems": bad}, ensure_ascii=False, indent=2)); return
    if cmd == "export":
        if "--out" not in a: sys.exit("export 需 --out <dir>")
        out = a[a.index("--out") + 1]; fmt = a[a.index("--format") + 1] if "--format" in a else "all"; w = "--write" in a
        for path, text in F.convert(skill, out)["files"]:
            if not in_fmt(path, fmt): continue
            print(("write " if w else "preview ") + path)
            if w: os.makedirs(os.path.dirname(path), exist_ok=True); open(path, "w", encoding="utf-8").write(text)
        return
    sys.exit("未知命令：%s（formats/detect/show/validate/export）" % cmd)
if __name__ == "__main__": main(sys.argv[1:])
