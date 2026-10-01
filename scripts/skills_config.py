#!/usr/bin/env python3
"""skills_config.py — 技能列表配置独立存储 <SMS_HOME>/config/skills.json（与模型输入参数 config.json 分离）：持 scan_roots（扫描安装根）·skill_generator·sync_clients·Source_Remote·permissions_default 等 skill 管理键；首访经 migrate() 从旧 config.json 幂等搬迁这些键（搬出后原键删除·记 event 链）。get/set dot-path·roots() 展开扫描根·add_root/del_root 维护。用法：python -B skills_config.py show|get <dot>|set <dot> <json>|roots|add-root <path>|remove-root <path>|migrate。"""
import os, sys, json
from functools import reduce
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, chains
SKILL_KEYS = ("scan_roots", "skill_generator", "sync_clients", "Source_Remote", "permissions_default")
DEFAULT = {"scan_roots": [], "permissions_default": {"read": True, "write": False, "execute": False, "network": False, "privacy": False, "vault": False, "verify": False, "comment": "默认权限底（permissions.py：生效＝此默认→今日 :grant 覆盖；danger 恒不随默认，须当轮单独授予）"}, "comment": "技能列表配置（与模型参数 config.json 分离）：scan_roots 扫描安装根·skill_generator 无匹配时创建源·sync_clients 客户端↔hub 同步·Source_Remote 远程源·permissions_default 默认权限；register.py 读 scan_roots。"}
def path(sms=None): return os.path.join(sms or resolve_home.ensure(), "config", "skills.json")
def _read(p, seed):
    try: return json.load(open(p, encoding="utf-8-sig")) if os.path.exists(p) else json.loads(json.dumps(seed))
    except Exception: return json.loads(json.dumps(seed))
def _write(p, doc):
    os.makedirs(os.path.dirname(p), exist_ok=True); import atomic_io; atomic_io.wjson(p, doc)
def migrate(sms=None):
    sms = sms or resolve_home.ensure(); cp = os.path.join(sms, "config", "config.json")
    if not os.path.exists(cp): return []
    cfg = _read(cp, {}); moved = {k: cfg[k] for k in SKILL_KEYS if k in cfg}
    if not moved: return []
    sk = _read(path(sms), {**DEFAULT, **moved})
    for k in moved: sk.setdefault(k, moved[k]); del cfg[k]
    _write(cp, cfg); _write(path(sms), sk); chains.record("event", "skills_config migrate 搬出 " + "、".join(moved)); return list(moved)
def load(sms=None):
    sms = sms or resolve_home.ensure(); migrate(sms); doc = _read(path(sms), DEFAULT)
    return {**DEFAULT, **{k: v for k, v in doc.items() if v not in (None, "", [], {})}}
def _walk(d, p): return reduce(lambda a, k: a.get(k) if isinstance(a, dict) else None, p.split("."), d)
def get(dot, default=None, sms=None):
    v = _walk(load(sms), dot); return default if v is None else v
def set(dot, value, sms=None):
    sms = sms or resolve_home.ensure(); migrate(sms); doc = _read(path(sms), DEFAULT); ks = dot.split(".")
    cur = reduce(lambda a, k: a.setdefault(k, {}), ks[:-1], doc)
    cur.update({ks[-1]: value}) if value is not None else cur.pop(ks[-1], None)
    _write(path(sms), doc); chains.record("event", "skills set " + dot + "=" + json.dumps(value, ensure_ascii=False)[:80]); return get(dot, sms=sms)
def roots(sms=None): return [os.path.expanduser(x) for x in (get("scan_roots", [], sms) or [])]
def add_root(p, sms=None):
    rs = get("scan_roots", [], sms) or []; return "已存在扫描根：" + p if p in rs else (set("scan_roots", rs + [p], sms), "已加入 scan_roots：" + p)[1]
def del_root(p, sms=None):
    rs = get("scan_roots", [], sms) or []; return "无此扫描根：" + p if p not in rs else (set("scan_roots", [x for x in rs if x != p], sms), "已移除 scan_roots：" + p)[1]
if __name__ == "__main__":
    a = sys.argv[1:] or ["show"]; cmd = a[0]; pj = lambda o: print(json.dumps(o, ensure_ascii=False, indent=2, default=str))
    if cmd == "show": pj(load())
    elif cmd == "get" and len(a) > 1: pj(get(a[1]))
    elif cmd == "set" and len(a) > 2: pj(set(a[1], json.loads(a[2])))
    elif cmd == "roots": pj(roots())
    elif cmd == "add-root" and len(a) > 1: print(add_root(a[1]))
    elif cmd == "remove-root" and len(a) > 1: print(del_root(a[1]))
    elif cmd == "migrate": pj({"moved": migrate()})
    else: print(__doc__.strip().splitlines()[-1])
