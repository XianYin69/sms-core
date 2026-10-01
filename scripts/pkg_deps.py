#!/usr/bin/env python3
"""pkg_deps.py — 技能包 dependence/ 检查与净化（install.py 安装时调用·与技能包同口径）：子包（含 SKILL.md）按来源标 trust（cloud→pending_review、local→trusted_local）；manifest 行 `名称 | 类型 | 来源`（skill/software/repo）标 dep:<名> pending_review；其余条目（软件/仓库地址/杂项）同标 pending_review 留人工 review；绝不自动下载或执行，URL 抽出留档；命中 quarantine 拒整包。"""
import os, re
URL_RE = re.compile(r"(?:gh:|https?://)[\w./:@~+%#\-]+")
TEXT = (".md", ".txt", ".json", ".yaml", ".yml", ".list", ".csv")
TYPES = ("skill", "software", "repo")
def _kind(p): return "pkg" if os.path.isdir(p) and os.path.isfile(os.path.join(p, "SKILL.md")) else "item"
def _read(p):
    try: return open(p, encoding="utf-8", errors="ignore").read(20000)
    except OSError: return ""
def _urls(p): return [] if os.path.isdir(p) or not p.endswith(TEXT) else URL_RE.findall(_read(p))[:8]
def _decls(p):
    if not p.endswith(TEXT): return []
    out = []; code = False
    for ln in _read(p).splitlines():
        if ln.strip().startswith("```"): code = not code
        q = [x.strip(" `") for x in ln.split("|")]
        if not code and len(q) == 3 and q[0] and q[1] in TYPES: out.append({"name": q[0], "type": q[1], "source": q[2]})
    return out

def check(sms, src, source, write):
    dep = os.path.join(src, "dependence")
    if not os.path.isdir(dep): return None
    import trust
    rep = {"checked": 0, "entries": [], "rejected": []}
    for n in sorted(os.listdir(dep)):
        p = os.path.join(dep, n); k = _kind(p); rep["checked"] += 1
        if trust.label_of(sms, "dep:" + n) == "quarantine" or (k == "pkg" and trust.label_of(sms, n) == "quarantine"):
            rep["rejected"].append(n + ":quarantine"); continue
        if k == "pkg":
            lb = "pending_review" if source == "cloud" else "trusted_local"
            trust.mark(sms, n, lb, source, "install:dep", write)
            rep["entries"].append({"name": n, "kind": k, "label": lb})
        else:
            trust.mark(sms, "dep:" + n, "pending_review", source, "install:dep", write); decls = _decls(p)
            for d in decls:
                dn = "dep:" + d["name"]
                if trust.label_of(sms, dn) == "quarantine": rep["rejected"].append(d["name"] + ":quarantine"); continue
                trust.mark(sms, dn, "pending_review", source, "install:decl", write)
            rep["entries"].append({"name": n, "kind": k, "label": "pending_review", "urls": _urls(p), "declared": decls,
                                   "note": "软件/仓库地址先 trust review 再单独安装，不自动下载执行"})
    return rep

if __name__ == "__main__":
    import sys, json
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import resolve_home
    a = sys.argv[1:]; src = a[0] if a else "."
    d = os.path.abspath(src)
    print(json.dumps(check(resolve_home.ensure(), os.path.dirname(d) if os.path.isfile(src) else d,
                           "cloud" if "--cloud" in a else "local", "--write" in a), ensure_ascii=False, indent=2))
