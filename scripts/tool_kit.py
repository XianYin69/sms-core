#!/usr/bin/env python3
"""tool_kit.py — 工具件精准高速内核（批27·用户「write/read/network_fetch 等工具使用更精准和高速的算法及命令执行步骤、更清晰准确的工具命令执行范式」）：
① read_window＝流式窗口读（islice 只取所需行，大文件不再整读进内存；带 offset/总行数/截断标记）；
② grep_walk＝剪枝目录＋二进制/超大文件跳过＋逐行流式＋命中即止（旧版整文件 read().splitlines() 且无体积闸）；
③ glob_fast＝生成器 islice 早停（旧版整树展开再截 200）；
④ fetch＝Accept-Encoding gzip/deflate＋响应头 charset＋字节上限＋retry_io 有限重试＋html_to_text 正文抽取（旧版整页原样吐 HTML 给模型，白烧 token）；
⑤ adapt＝命令执行范式适配（PowerShell 顶层 && → ;、cmd 内建重定向 2>nul → 2>$null、dir /b → Get-ChildItem -Name），改写即回说明行，杜绝「一条命令因分隔符语法报错再试一轮」。
本模块只做算法与文案，权限/门禁/信封仍归 agent_tools*。用法：python -B tool_kit.py selftest。"""
import os, re, sys, gzip, zlib, fnmatch, io as _io
from itertools import islice
PRUNE = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".pytest_cache", ".idea", ".kilocode_cache"}
BIN_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz", ".7z", ".exe", ".dll", ".pyc", ".mp4", ".mp3", ".woff", ".woff2", ".ttf", ".bak"}
MAXF = 8_000_000
BIG = 2_000_000

def read_window(path, max_lines=120, offset=0, chars=4000):
    """流式窗口读：只缓存 [offset, offset+max_lines) 行；>2MB 文件取满窗口即早停（总行数回 None）。"""
    n = int(max_lines or 120); n = n if n >= 1 else 1; off = max(0, int(offset or 0))
    size = os.path.getsize(path); buf = []; total = 0; early = False
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, ln in enumerate(f):
            if off <= i < off + n: buf.append(ln.rstrip("\n"))
            elif i >= off + n and size > BIG: early = True; break
            total = i + 1
    txt = "\n".join(buf); cut = len(txt) > chars
    if cut: txt = txt[:chars]
    return txt, (None if early else total), (cut or early or total > off + len(buf))
def _keep(ns):
    ns[:] = [x for x in ns if x not in PRUNE and (not x.startswith(".") or x in (".github", ".vscode"))]
def grep_walk(root, rx, include="*", max=60):
    """剪枝＋流式＋命中即止：跳二进制扩展名与 >8MB 文件，逐行扫不再整读。回 (命中行, 是否截断)。"""
    out = []; rx = rx if hasattr(rx, "search") else re.compile(str(rx)); lim = int(max or 60); lim = lim if lim >= 1 else 1
    for dp, ns, fs in os.walk(root):
        _keep(ns)
        for fn in fs:
            if include != "*" and not fnmatch.fnmatch(fn, str(include)): continue
            if os.path.splitext(fn)[1].lower() in BIN_EXT: continue
            p = os.path.join(dp, fn)
            try:
                if os.path.getsize(p) > MAXF: continue
                with open(p, encoding="utf-8", errors="replace") as f:
                    for i, ln in enumerate(f, 1):
                        if rx.search(ln):
                            out.append(os.path.relpath(p, root) + ":" + str(i) + ":" + ln.rstrip("\n").strip()[:200])
                            if len(out) >= lim: return out, True
            except Exception: continue
    return out, False

def glob_fast(pattern, root, limit=200):
    """生成器早停：取 limit+1 判是否还有更多（旧版 sorted 整树展开后再截断）。回 (匹配列表, 是否截断)。"""
    import glob as _g
    it = islice(_g.iglob(str(pattern), root_dir=root, recursive=True), int(limit) + 1)
    rows = sorted(list(it))
    return rows[:int(limit)], len(rows) > int(limit)
_TAG = re.compile(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>|<[^>]+>")
_SP = re.compile(r"[ \t]{2,}|(?:\r?\n){3,}")
def html_to_text(h):
    """正文抽取：去 script/style/标签＋实体还原＋空行折叠（省 token 的主因）。"""
    import html as H
    t = _TAG.sub(" ", str(h or "")); t = H.unescape(t).replace("\xa0", " ")
    return _SP.sub(lambda m: "\n" if "\n" in m.group(0) else " ", t).strip()
def decode(raw, hdr):
    enc = (hdr.get("Content-Encoding") or "").lower()
    if "gzip" in enc:
        try: raw = gzip.decompress(raw)
        except Exception: pass
    elif "deflate" in enc:
        try: raw = zlib.decompress(raw)
        except Exception:
            try: raw = zlib.decompressobj(-zlib.MAX_WBITS).decompress(raw)
            except Exception: pass
    cs = (hdr.get("Content-Type") or "").lower(); m = re.search(r"charset=([\w\-]+)", cs)
    for c in ([m.group(1)] if m else []) + ["utf-8"]:
        try: return raw.decode(c), cs
        except Exception: continue
    return raw.decode("utf-8", "replace"), cs

MAXB = 2_000_000
def fetch(url, chars=4000, as_text=True, call=None, retries=2):
    """精准取文：Accept-Encoding gzip/deflate＋字节上限 2MB＋charset 优先响应头＋HTML 抽正文＋瞬时错有限重试。
    call 由调用方注入（SMS 传 run_watch.net_call 走 T1 超时分级），缺省 urllib.urlopen。回 (正文, 说明)。"""
    import urllib.request
    req = urllib.request.Request(str(url), headers={"User-Agent": "sms-shell/1.0",
        "Accept-Encoding": "gzip, deflate", "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8"})
    def _once():
        r = call(req) if call else urllib.request.urlopen(req, timeout=30)
        with r: raw, hdr = r.read(MAXB + 1), r.headers
        txt, ct = decode(raw[:MAXB], hdr)
        big = len(raw) > MAXB
        if as_text and ("html" in ct or txt.lstrip()[:1] == "<"):
            t2 = html_to_text(txt); txt = t2 or txt
        note = "%s·%d 字节→%d 字%s" % (ct.split(";")[0] or "?", len(raw[:MAXB]), len(txt), "·已截 2MB" if big else "")
        return txt, note
    try:
        import retry_io as rio
        return rio.call(_once, max(0, int(retries)), base=1.0, cap=5.0)
    except Exception as e: return None, str(e)[:180]

def _amp(c):
    """引号感知的 && → ; 改写（引号内不动·反斜杠转义按 PS 规则只在双引号内处理）。回 (新命令, 改写处数)。"""
    out = []; q = ""; i = 0; n = 0
    while i < len(c):
        ch = c[i]
        if q:
            out.append(ch)
            if ch == "\\" and q == '"': out.append(c[i + 1:i + 2]); i += 2; continue
            if ch == q: q = ""
            i += 1; continue
        if ch in "\"'": q = ch; out.append(ch); i += 1; continue
        if c.startswith("&&", i): out.append(";"); i += 2; n += 1; continue
        out.append(ch); i += 1
    return "".join(out), n
PS = ("powershell", "pwsh")
def adapt(cmd, kind="powershell"):
    """命令执行范式适配：仅当目标壳为 PowerShell 且命令含已知不兼容语法时改写，回 (新命令, 说明行)。
    目的＝一次成功，杜绝「因分隔符语法报错再试一轮」。"""
    if str(kind) not in PS: return str(cmd), []
    c = str(cmd); notes = []
    if "&&" in c:
        c2, n = _amp(c)
        if n: c = c2; notes.append("PowerShell 5.1 不支持 && 作语句分隔·已按范式改写为 ;（%d 处）" % n)
    if re.search(r"(?i)2>nul\b", c):
        c = re.sub(r"(?i)2>nul\b", "2>$null", c); notes.append("cmd 重定向 2>nul 已改写为 PowerShell 2>$null")
    segs = c.split(";"); hit = False
    for i, s in enumerate(segs):
        if re.match(r"(?i)^\s*dir\s+/b\b", s): segs[i] = re.sub(r"(?i)^(\s*)dir\s+/b\s*", "\\1Get-ChildItem -Name ", s); hit = True
    if hit: c = ";".join(segs); notes.append("cmd 内建 dir /b 已改写为 PowerShell Get-ChildItem -Name")
    if "||" in c:
        _q, n2 = _amp(c.replace("||", "&&")); notes.append("⚠ || 在 Windows PowerShell 5.1 不是语句分隔（pwsh7 才支持）·建议拆步或 if ($LASTEXITCODE -eq 0)")
    return c, notes

if __name__ == "__main__":
    import tempfile, json as _j
    d = tempfile.mkdtemp(); f = os.path.join(d, "a.txt")
    _io.open(f, "w", encoding="utf-8").write("\n".join("line%d hit" % i if i == 900 else "x" * 40 for i in range(2000)))
    txt, tot, more = read_window(f, 5, 0, 4000)
    assert tot == 2000 and len(txt.splitlines()) == 5 and more, (tot, len(txt))
    txt2, tot2, m2 = read_window(f, 3, 1997, 4000); assert tot2 == 2000 and txt2.count("\n") == 2 and not m2, txt2
    hits, tr = grep_walk(d, re.compile("hit"), "*.txt", 3); assert len(hits) == 1 and not tr, hits
    os.makedirs(os.path.join(d, "node_modules", "x"), exist_ok=True)
    _io.open(os.path.join(d, "node_modules", "x", "b.txt"), "w").write("hit")
    assert not any("node_modules" in h for h in grep_walk(d, re.compile("hit"), "*", 9)[0])
    g, tr2 = glob_fast("**/*.txt", d, 200); assert g and not tr2, g
    assert html_to_text("<html><script>var a=1;</script><style>p{}</style><h1>Hi&nbsp;there</h1><p>x</p></html>") == "Hi there x", html_to_text("<b>x</b>")
    import gzip as _gz
    class _H(dict):
        get = dict.get
    raw = _gz.compress("你好".encode()); txt3, ct = decode(raw, _H({"Content-Encoding": "gzip", "Content-Type": "text/html; charset=utf-8"}))
    assert txt3 == "你好", (txt3, ct)
    c1, n1 = adapt("cd X && dir /b && echo done"); assert "&&" not in c1 and c1.count(";") == 2 and len(n1) == 2, (c1, n1)
    assert adapt("echo 'a && b'")[0] == "echo 'a && b'"
    assert "2>$null" in adapt("python x 2>nul")[0]
    assert adapt("ls -la", "bash")[1] == []
    print(_j.dumps({"selftest": "OK", "read_window": [tot, len(txt.splitlines())], "grep": len(hits), "adapt": c1}, ensure_ascii=False))
