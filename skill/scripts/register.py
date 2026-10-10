#!/usr/bin/env python3
"""register.py — 扫描技能安装位置与所用工具，生成 registry/register.json。
默认扫描根读 skills_config（<SMS_HOME>/config/skills.json 的 scan_roots），--add-root <path>
登记本地目录/文件为扫描根；根自身含 SKILL.md（或 skill/SKILL.md）时该根即作为一个
技能登记（按路径加入单个 skill），父子根重复命中自动去重。深度 2：候选根下
<skill>/private/* 含 SKILL.md 者同样登记（附属技能必须可被 SMS 索引与派发），
条目附 visibility/parent/publish——publish=false 语义＝永不进 git/远端/GitHub，
注册≠发布。"""
import os, sys, time, glob, io

TOOLS = ["read", "write", "edit", "glob", "grep", "bash", "task", "skill", "websearch", "webfetch"]
HUB = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
DEFAULT_ROOTS = [os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sub_skills"), HUB]
ENTRY_RELS = ("SKILL.md", "skill/SKILL.md")
# 批39 剪枝：工具/版本控制/缓存目录不进扫描面（实测 .kilo\worktrees 下 4 个随机名技能被当独立技能登记，
# 吃扫描时间还污染 :skills 清单与路由打分面）；技能内子技能目录名＝中文（哲学法律\独立思考），
# 旧版只扫 private/* 扫不到（实测 106 个含 SKILL.md 目录只登记 75 个，缺 16＝9 子技能＋6 系统件＋1 误登）。
PRUNE_DIRS = (".git", ".kilo", ".claude", ".codex", ".vscode", ".idea", "__pycache__", "node_modules", ".pytest_cache")

def candidates(root):
    """深度 1 候选：root 自身 + root/*（剪 PRUNE_DIRS；root 本身不受剪，与原实现同集合）。"""
    out = [root]
    try:
        ents = sorted(os.listdir(root))
    except OSError:
        return out
    for n in ents:
        if n in PRUNE_DIRS or n.startswith("."):
            continue
        out.append(os.path.join(root, n))
    return out

def find_skills(roots):
    """深度 1 全扫后追加深度 2：候选目录下 `private/*` 含 SKILL.md 者也登记（parent＝所属技能名）。"""
    out = []; seen = set(); skill_dirs = []
    for root in roots:
        cands = candidates(root)
        for d in cands:
            for rel in ENTRY_RELS:
                if os.path.isfile(os.path.join(d, rel)) and d not in seen:
                    seen.add(d); skill_dirs.append(d)
                    out.append((os.path.basename(d), d, os.path.join(d, rel), rel, None)); break
        for d in skill_dirs:  # 深度 2：只对真技能目录扫 private/* ＋ 一级子目录（附属技能必属某技能）
            for p in _sub_dirs(d):
                for rel in ENTRY_RELS:
                    if os.path.isfile(os.path.join(p, rel)) and p not in seen:
                        seen.add(p)
                        out.append((os.path.basename(p), p,
                                    os.path.join(p, rel), rel,
                                    os.path.basename(d)))
                        break
    return out

def _sub_dirs(d):
    """附属候选目录＝private/*（显式附属）＋ d 下直接含 SKILL.md 的子目录（中文命名子技能）。
    只再下一层、剪 PRUNE_DIRS／点开头目录；sub_skills/* 已由独立根登记，不重复登记（防同 id 双条目）。"""
    cand = sorted(glob.glob(os.path.join(d, "private", "*")))
    try:
        for n in sorted(os.listdir(d)):
            if n in PRUNE_DIRS or n.startswith(".") or n == "sub_skills":
                continue
            cand.append(os.path.join(d, n))
    except OSError:
        pass
    return [p for p in cand if os.path.isdir(p)]

def name_of(sk):
    """frontmatter 顶层 `name:`＝技能真名（批39：目录名可能是运行时混合体——核内 skill/ 目录声明
    name: smsystem-suit，按目录名登记会多出一条 id=skill 的假技能并抢走派发路径）。"""
    try:
        rows = io.open(sk, encoding="utf-8-sig", errors="ignore").read().splitlines()
    except OSError:
        return ""
    if not rows or rows[0].strip() != "---":
        return ""
    for l in rows[1:]:
        if l.strip() == "---":
            break
        if l[:1].isspace():
            continue
        if l.strip().startswith("name:"):
            v = l.split(":", 1)[1].strip()
            return v.strip(CHRQ)
    return ""

CHRQ = chr(34) + chr(39)

def meta(sk):
    rows = open(sk, encoding="utf-8", errors="ignore").read().splitlines()
    low = "\n".join(rows).lower()
    i = next((i for i, l in enumerate(rows) if l.strip().startswith("description:")), -1)
    v = rows[i].split(":", 1)[1].strip() if i >= 0 else ""
    if v and v[0] not in ">&|":
        d = v.strip("\"'")
    elif i >= 0:  # 折叠/块标量：取缩进续行拼一句（实测 description: > 的 20+ 技能登记成空串描述）
        buf = []
        for l in rows[i + 1:]:
            if not l.strip() or (l[:1].isdigit() is False and not l[:1].isspace()):
                break
            if l[:1].isspace():
                buf.append(l.strip())
            elif l.strip() in (">", "|", ">-", "|-"):
                continue
            else:
                break
        d = " ".join(buf)
    else:
        d = ""
    if not d:  # frontmatter 无描述 → 取正文首段非标题行（注册描述不为空＝路由/清单可用）
        infm = rows and rows[0].strip() == "---"
        for l in (rows[2:] if infm else rows):
            t = l.strip()
            if infm and t == "---":
                break
            if t and not t.startswith(("#", "-", ">", "|", "!", "```")) and ":" not in t[:20]:
                d = t; break
    return [t for t in TOOLS if t in low], d[:220]  # 批39：100→220（旧值把「批量改名/爬虫」类关键动词截掉，路由无词可配）

def visibility_of(sk, attached):
    """读 SKILL.md frontmatter 顶层 `visibility:`；缺省：附属（private/ 下）＝PRIVATE，普通技能＝PUBLIC。"""
    default = "PRIVATE" if attached else "PUBLIC"
    try:
        rows = open(sk, encoding="utf-8-sig", errors="ignore").read().splitlines()
    except OSError:
        return default
    if not rows or rows[0].strip() != "---":
        return default
    for l in rows[1:]:
        if l.strip() == "---":
            break
        if l[:1].isspace():
            continue
        if l.strip().startswith("visibility:"):
            val = l.split(":", 1)[1].strip().strip("\"'")
            return val.upper() if val else default
    return default

def build(sms, roots):
    rows = []
    import trust
    seen_ids = set()
    for n, d, sk, rel, parent in find_skills(roots):
        tools, desc = meta(sk)
        vis = visibility_of(sk, parent is not None)
        sid = name_of(sk) or n  # 声明名优先；同 id 后到者（嵌套运行时混合体）不重复登记
        if sid in seen_ids:
            continue
        seen_ids.add(sid)
        rows.append({"id": sid, "name": sid, "install_path": d, "entry": rel,
                     "kind": "sub_skill" if "sub_skills" in d else "skill",
                     "tools": tools, "description": desc,
                     "status": "active", "updated_at": time.strftime("%Y-%m-%d"),
                     "trust": trust.label_of(sms, n),
                     "visibility": vis, "parent": parent, "publish": vis != "PRIVATE"})
    doc = {"schema": "skill_register", "version": "1.1.0",
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
