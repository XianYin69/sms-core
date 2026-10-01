#!/usr/bin/env python3
"""resolve_home.py — SMS 固定路径解析：SMS_HOME（数据根·恒指一开始创建的 SMS 目录——配置/记忆十一链/注册表/内建虚拟工作区都在其中）解析顺序 env SMS_HOME → bootstrap 用户配置 sms_home → 缓存目录 → 根目录；用户配置固定存 <SMS_HOME>/config/config.json。SMS_WORKSPACE（智能体操作文件的真实工作区·与数据根分离）＝ env SMS_WORKSPACE → 配置 sms_workspace（存在目录）→ 回落 <SMS_HOME>/workspaces/_virtual（虚拟工作区·每对话由 workspace.py begin 创建·end 删除）；真实与虚拟工作区一律自动建 tmp/ 子目录（wtmp()·生成文件只落此处），大模型/技能配置恒直读 <SMS_HOME>/config 文件、不进工作区。"""
import os, sys, json, platform, atomic_io
NAME = "SMS"
def _cache():
    s = platform.system()
    if s == "Windows": return os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    if s == "Darwin": return os.path.expanduser("~/Library/Caches")
    return os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
def _bootfile(): return os.path.join(os.path.join(_cache() or os.path.expanduser("~"), NAME), "config", "config.json")
def resolve():
    if os.environ.get("SMS_HOME"): return os.environ["SMS_HOME"]
    p = _bootfile()
    if not os.path.exists(p): return os.path.dirname(os.path.dirname(p))
    try: return atomic_io.rjson(p).get("sms_home") or os.path.dirname(os.path.dirname(p))
    except Exception: return os.path.dirname(os.path.dirname(p))
_CF = {}
def conf(sms=None):
    p = os.path.join(sms or resolve(), "config", "config.json")
    seed = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "config.example.json")
    if not os.path.exists(p) and os.path.exists(seed):
        os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w", encoding="utf-8").write(open(seed, encoding="utf-8").read())
    try: k = (os.path.getmtime(p), os.path.getsize(p))  # mtime+size 缓存：TUI 0.15–0.5s 轮询不再反复读盘解析（整壳缓慢根因之一）
    except Exception: return {}
    if (e := _CF.get(p)) and e[0] == k: return dict(e[1])
    doc = atomic_io.rjson(p); _CF[p] = (k, doc); return dict(doc)
def workspace(sms=None):
    w = os.environ.get("SMS_WORKSPACE") or conf(sms).get("sms_workspace")
    if w and os.path.isdir(w): return os.path.abspath(os.path.expanduser(w))
    return os.path.join(sms or resolve(), "workspaces", "_virtual")
def wtmp(sms=None): p = os.path.join(workspace(sms), "tmp"); os.makedirs(p, exist_ok=True); return p
def ensure():
    p = resolve()
    for name in ("registry", "sessions", "tmp", "config"):
        os.makedirs(os.path.join(p, name), exist_ok=True)
    return p
def temp(p, rel="", mkdir=False):
    base = os.path.realpath(os.path.join(p, "tmp"))
    d = os.path.realpath(os.path.join(base, *(rel or "").split(os.sep)))
    if d != base and not d.startswith(base + os.sep): raise SystemExit("拒绝：子 skill 新建目录必须位于 SMS/tmp 下")
    if mkdir:
        os.makedirs(d, exist_ok=True)
    return d
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "temp": print(temp(ensure(), sys.argv[2] if len(sys.argv) > 2 else "", "--mkdir" in sys.argv))
    elif cmd == "workspace": print(workspace())
    elif cmd == "wtmp": print(wtmp())
    else: print(ensure() if "--ensure" in cmd or cmd == "ensure" else resolve())
