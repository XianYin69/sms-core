#!/usr/bin/env python3
"""ff_lite.py — firefox lite 内核（联网搜索·取页·下载服务，resistance #19）：动作须 grant network（默认拒绝）；search＝Bing/DDG lite 结果 JSON（engine 可配、失败自动改投另一引擎）；fetch＝页面正文（优先 playwright 随包无头 Firefox 渲染，缺则回退 urllib，绝不自动装依赖）；download＝只落 <SMS_HOME>/downloads/·限尺寸（重名拒绝，覆盖须 --force 且 grant danger）；动作记 tool_call 链。用法见 scripts.md。"""
import os, sys, re, json, html, importlib.util as U, urllib.request as ur, urllib.parse as up
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, settings, permissions, chains
SMS = resolve_home.ensure(); UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"
def cfg(): return settings.get("ff_lite") or {}
def _gate(v):
    if not permissions.allow(SMS, "network"): return "DENIED：firefox lite 内核需 network 权限（壳内 :grant net），拒绝 " + v
    chains.log("tool", "ff_lite:" + v)
def _get(url): return ur.urlopen(ur.Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.8,en;q=0.5"}), timeout=int(cfg().get("timeout_s", 30))).read()
def _strip(h): return re.sub(r"[ \t]+", " ", html.unescape(re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>|<[^>]+>", " ", h))).strip()
def _ff(url):
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p, p.firefox.launch(headless=bool(cfg().get("headless", True))) as b:
            pg = b.new_page(user_agent=UA); pg.goto(url, timeout=int(cfg().get("timeout_s", 30)) * 2000); return pg.evaluate("document.body.innerText")
    except Exception: return None
def search(q, n=5):
    ENGS = {"bing": ("https://www.bing.com/search?q=", r'<h2[^>]*><a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', ""), "duckduckgo": ("https://html.duckduckgo.com/html/?q=", r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', "uddg")}
    pref = str(cfg().get("engine", "bing")); order = [pref] + [k for k in ENGS if k != pref]
    for name in order:
        try: base, rx, pk = ENGS.get(name, ENGS["bing"]); h = _get(base + up.quote(str(q))).decode("utf-8", "replace")
        except Exception: continue
        out = []
        for u, t in list(re.findall(rx, h))[:n]:
            if pk: u = up.parse_qs(up.urlparse("https:" + u if u.startswith("//") else u).query).get(pk, [u])[0]
            out.append({"title": re.sub(r"<[^>]+>", "", html.unescape(t)).strip()[:120], "url": u[:300]})
        if out: return json.dumps(out, ensure_ascii=False, indent=1)
    return "ERR lite内核搜索失败（Bing/DDG 均无结果或不可达）"
def fetch(url):
    cap = int(cfg().get("max_page_chars", 8000)); t = _ff(url)
    try: t = t if t is not None else _strip(_get(url).decode("utf-8", "replace"))
    except Exception as e: return "ERR 取页失败：%s" % str(e)[:150]
    return t[:cap] + ("\n…[截断]" if len(t) > cap else "")
def download(url, name="", force=False):
    if force and not permissions.allow(SMS, "danger"): return "DENIED：覆盖下载须用户当轮确认并 grant danger（红线16）"
    d = os.path.join(SMS, str(cfg().get("download_dir", "downloads"))); os.makedirs(d, exist_ok=True)
    fn = re.sub(r'[\\/:*?"<>|]+', "_", name or up.unquote(os.path.basename(up.urlparse(url).path)) or "file.bin"); p = os.path.join(d, fn)
    if os.path.exists(p) and not force: return "EXISTS：" + p + "（覆盖须 --force 且 grant danger）"
    try: raw = _get(url)
    except Exception as e: return "ERR 下载失败：%s" % str(e)[:150]
    if len(raw) > int(cfg().get("max_download_mb", 200)) * 1048576: return "REFUSED：超出尺寸上限"
    open(p, "wb").write(raw); return "OK %s（%d bytes，firefox lite 内核下载）" % (p, len(raw))
def status(): ff = bool(U.find_spec("playwright")); return {"network_granted": permissions.allow(SMS, "network"), "engine": str(cfg().get("engine", "bing")), "firefox_lite_kernel": ff, "render": "无头Firefox·缺则urllib回退（绝不自动装）" if ff else "urllib回退（内核缺失·不装依赖）", "download_dir": "<SMS_HOME>/downloads", "max_download_mb": int(cfg().get("max_download_mb", 200))}
if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]; cmd = a[0]
    if cmd in ("status", "doctor"): print(json.dumps(status(), ensure_ascii=False, indent=1))
    else: g = _gate(cmd); print(g or (search(a[1], int(a[2]) if len(a) > 2 and a[2].isdigit() else 5) if cmd == "search" and len(a) > 1 else fetch(a[1]) if cmd == "fetch" and len(a) > 1 else download(a[1], a[2] if len(a) > 2 and not a[2].startswith("--") else "", "--force" in a) if cmd == "download" and len(a) > 1 else "用法：search \"关键词\" [n] | fetch <url> | download <url> [文件名] [--force] | doctor|status"))
