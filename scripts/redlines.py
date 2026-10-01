#!/usr/bin/env python3
"""redlines.py — 约束持久化机械自检：check 断言 AGENTS.md、SKILL.md、resistance.md 关键约束句未因压缩·改写丢失，全仓 .md/.py/.ps1/.sh/.cmd 等脚本 ≤50 行（含根目录与 bin/ 部署包），悬空链接=0，SKILL.md 含 frontmatter；初始化第一步与每轮 git 提交前必跑，任一失败 exit 1 禁止继续；seal 把三份入口文档 sha256 基线冻结到 <SMS_HOME>/redlines/baseline.json，check 报告未 seal 的漂移（drift，不致失败）。"""
import os, sys, re, json, hashlib
SK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(SK)
MUST = {"AGENTS.md": ["调度器", "先询问", "委托 Skill_Generator", "仅复制 bin", "十一链记忆·对话隔离·做梦", "主流程守卫"],
        "SKILL.md": ["委托 Skill_Generator", "redlines.py", "仅复制 bin", "直接回答", "十一链"],
        os.path.join("resistance", "resistance.md"): ["grant danger", "部署＝", "先询问", "17. 记忆链·对话隔离·做梦"]}
def _scan():
    for root, ds, fs in os.walk(ROOT):
        ds[:] = [d for d in ds if d not in (".git", ".kilo", "__pycache__", "tmp", "SMS", "workspaces", "registry", "sessions", "node_modules")]
        for f in sorted(fs):
            if f.endswith((".md", ".py", ".ps1", ".sh", ".cmd")) or f in ("sms", "sms-shell"): yield os.path.join(root, f)
def _dangling(path):
    bad = []
    for t in re.findall(r"\]\(([^)\s]+)[^)]*\)", open(path, encoding="utf-8").read()):
        if t.startswith(("http:", "https:", "mailto:", "#")): continue
        if not os.path.exists(os.path.join(os.path.dirname(path), t.split("#")[0])): bad.append(t)
    return bad
def _fails():
    fails = []
    for rel, pats in MUST.items():
        p = os.path.join(SK, rel)
        if not os.path.isfile(p): fails.append("缺失入口文档 " + rel); continue
        txt = open(p, encoding="utf-8").read()
        fails += ["缺少关键约束句 %s: %s" % (rel, s) for s in pats if s not in txt]
    for p in _scan():
        n = sum(1 for _ in open(p, encoding="utf-8-sig"))
        if n > 50: fails.append("超 50 行(%d): %s" % (n, os.path.relpath(p, ROOT)))
        if p.endswith(".md"): fails += ["悬空链接 %s: %s" % (os.path.relpath(p, ROOT), t) for t in _dangling(p)]
    if not open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read(4).startswith("---"):
        fails.append("SKILL.md 缺 YAML frontmatter")
    return fails
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home
    sms = resolve_home.ensure(); cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    base = os.path.join(sms, "redlines", "baseline.json")
    sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
    if cmd == "seal":
        doc = {rel: sha(os.path.join(SK, rel)) for rel in MUST if os.path.isfile(os.path.join(SK, rel))}
        os.makedirs(os.path.dirname(base), exist_ok=True)
        json.dump(doc, open(base, "w", encoding="utf-8"), indent=1)
        print(json.dumps({"sealed": sorted(doc)}, ensure_ascii=False)); sys.exit(0)
    fails = _fails()
    prev = json.load(open(base, encoding="utf-8")) if os.path.isfile(base) else {}
    drift = sorted(r for r, h in prev.items() if os.path.isfile(os.path.join(SK, r)) and sha(os.path.join(SK, r)) != h)
    print(json.dumps({"ok": not fails, "fails": fails, "drift": drift}, ensure_ascii=False, indent=2))
    sys.exit(1 if fails else 0)
