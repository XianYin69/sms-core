#!/usr/bin/env python3
"""dep_fetch.py — 依赖原始链接的校验与取回（批26 用户「依赖需要附上原始链接（github/gitlab…）可以网页检索和下载到相关 skill 的链接」）：
读技能目录 dependence/deps.json（Skill_Generator 新规则产物，每条 {name,source_url,license,version,install,checked_at}）——
①check：列出缺 source_url / 链接不可达的条目（缺链接＝不合格）；②fetch：按 source_url 把上游取回技能目录 dependence/vendor/<name>/（有 git 用 git clone --depth 1，否则 GitHub/GitLab 归档 zip 下载解压）；③list：打印依赖清单与链接。
高危提示：fetch 会联网下载外部代码，须 :grant network（＋落链记录），默认只列不取。
用法：python -B dep_fetch.py list <技能id或目录> | check [技能id…] | fetch <技能id> <依赖name>"""
import os, sys, json, subprocess, urllib.request, zipfile, io as _io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, permissions
SKILLS = [os.path.expanduser("~/.kilocode/skills"), os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sub_skills")]
DEPDIR = "dependence"; VEND = "vendor"

def skill_dir(sid):
    for r in SKILLS:
        if not os.path.isdir(r): continue
        for cand in (os.path.join(r, sid), os.path.join(r, "skill", "sub_skills", sid)):
            if os.path.isdir(cand): return cand
        for d in os.listdir(r):
            p = os.path.join(r, d)
            if os.path.isdir(p) and os.path.isdir(os.path.join(p, "skill", "sub_skills", sid)):
                return os.path.join(p, "skill", "sub_skills", sid)
    return None

def deps_of(sid):
    d = skill_dir(sid)
    if not d: return None, []
    p = os.path.join(d, DEPDIR, "deps.json")
    if not os.path.isfile(p): return d, []
    try: doc = json.load(open(p, encoding="utf-8"))
    except Exception as ex: return d, []
    items = doc if isinstance(doc, list) else (doc.get("dependencies") or doc.get("deps") or [])
    return d, items

def list_(sid):
    d, items = deps_of(sid)
    if not d: return "无此技能目录：" + str(sid)
    if not items: return "技能 %s 无 dependence/deps.json（旧技能可经 Skill_Generator 迭代补依赖记录）" % sid
    out = ["%s（%d 条依赖）" % (d, len(items))]
    for x in items:
        out.append("  %-22s %-10s %s" % (str(x.get("name"))[:22], str(x.get("version") or "-")[:10], str(x.get("source_url") or "〔缺原始链接＝不合格〕")))
    return "\n".join(out)

def check(sids=None):
    rows = []
    cand = sids or []
    dirs = []
    for r in SKILLS:
        if os.path.isdir(r): dirs += [os.path.join(r, x) for x in os.listdir(r) if os.path.isdir(os.path.join(r, x))]
    bad = 0
    for d in dirs:
        p = os.path.join(d, DEPDIR, "deps.json")
        if not os.path.isfile(p): continue
        sid = os.path.basename(d)
        if cand and sid not in cand: continue
        _, items = deps_of(sid)
        for x in items:
            u = str(x.get("source_url") or "").strip()
            if not u: rows.append("缺链接 %s｜%s" % (sid, x.get("name"))); bad += 1
            elif u.startswith("local://"): pass
            elif not (u.startswith("http://") or u.startswith("https://")): rows.append("链接非 URL %s｜%s→%s" % (sid, x.get("name"), u[:60])); bad += 1
    return "依赖链接校验：%d 条不合格\n%s" % (bad, "\n".join(rows[:40])) if bad else "依赖链接校验：全部合格（每条依赖均有原始链接）"

def _head(u):
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "sms-dep_fetch"})
        with urllib.request.urlopen(req, timeout=20) as r: return "可达 HTTP %s" % r.status
    except Exception as ex: return "不可达 " + str(ex)[:80]

def probe(sid, name=""):
    _, items = deps_of(sid)
    out = []
    for x in items:
        u = str(x.get("source_url") or "")
        if name and str(x.get("name")) != name: continue
        if not u.startswith("http"): out.append("%s：%s（本地依赖免验）" % (x.get("name"), u or "缺链接")); continue
        out.append("%s：%s → %s" % (x.get("name"), u, _head(u)))
    return "\n".join(out) or "无匹配依赖"

def fetch(sid, name, sms=None):
    """按 deps.json 的原始链接把上游取回 dependence/vendor/<name>/（须 :grant network）。"""
    sms = sms or resolve_home.ensure()
    try:  # 后台/非交互：SOLO 自审不入此路（无人应答·防阻塞与成本失控）
        import permissions; permissions.set_noninteractive(True)
    except Exception: pass
    if not permissions.allow(sms, "network"):
        return "拒绝：下载依赖需 :grant network（外部代码入库须授权·默认拒绝）"
    d, items = deps_of(sid)
    if not d: return "无此技能目录：" + str(sid)
    x = next((i for i in items if str(i.get("name")) == str(name)), None)
    if not x: return "无此依赖：" + str(name) + "（dep_fetch.py list %s 看清单）" % sid
    u = str(x.get("source_url") or "").strip()
    if not u.startswith("http"): return "%s 的链接非可下载 URL（%s）——本地依赖无需取回" % (name, u or "空")
    dst = os.path.join(d, DEPDIR, VEND, str(name)); os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.isdir(dst): return "已存在，跳过（删目录可重取）：" + dst
    if os.system("git --version >NUL 2>&1") == 0:
        r = subprocess.run(["git", "clone", "--depth", "1", u, dst], capture_output=True, text=True, errors="replace", timeout=300)
        if r.returncode == 0:
            __import__("chains").record("tool", "dep_fetch %s｜%s ← %s" % (sid, name, u))
            return "已 git clone 到 " + dst
    z = u.rstrip("/") + "/repository/archive.tar.gz" if "gitlab" in u else (u.rstrip("/") + "/archive/HEAD.zip" if "github.com" in u else "")
    if not z: return "git 不可用且无归档地址，请手动取回：" + u
    try:
        with urllib.request.urlopen(urllib.request.Request(z, headers={"User-Agent": "sms-dep_fetch"}), timeout=60) as resp:
            raw = resp.read()
        if z.endswith(".zip"):
            with zipfile.ZipFile(_io.BytesIO(raw)) as zf: zf.extractall(dst)
        else:
            import tarfile
            with tarfile.open(fileobj=_io.BytesIO(raw)) as tf: tf.extractall(dst)
        __import__("chains").record("tool", "dep_fetch archive %s｜%s ← %s" % (sid, name, z))
        return "已下载归档到 " + dst + "（%d 字节）" % len(raw)
    except Exception as ex:
        return "下载失败：" + repr(ex)[:200]

if __name__ == "__main__":
    a = sys.argv[1:] or ["check"]
    if a[0] == "list" and len(a) > 1: print(list_(a[1]))
    elif a[0] == "check": print(check(a[1:]))
    elif a[0] == "probe" and len(a) > 1: print(probe(a[1], a[2] if len(a) > 2 else ""))
    elif a[0] == "fetch" and len(a) > 2: print(fetch(a[1], a[2]))
    else: print(__doc__.strip().splitlines()[-1])
