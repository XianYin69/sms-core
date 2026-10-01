#!/usr/bin/env python3
"""sandbox.py — SMS 沙盒：未指定路径的工作目录建在 <SMS_HOME>/tmp/sandbox；create/list/deliver/clean。"""
import os, sys, time, shutil, json
def _base(sms): return os.path.join(sms, "tmp", "sandbox")
def _meta(p): return os.path.join(p, ".sms_sandbox.json")
def _guard(sms, p):
    b = os.path.realpath(_base(sms)); r = os.path.realpath(p)
    if r != b and not r.startswith(b + os.sep): raise SystemExit("拒绝：沙盒必须位于 SMS/tmp/sandbox")
def _read(p): return json.load(open(_meta(p), encoding="utf-8")) if os.path.exists(_meta(p)) else {}
def _write(p, state, target=None):
    d = _read(p); d.update({"id": os.path.basename(p), "state": state, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")})
    if target: d["target"] = target
    json.dump(d, open(_meta(p), "w", encoding="utf-8"), ensure_ascii=False, indent=2); return d
def _files(p): return sum(len(f) for _, _, f in os.walk(p))

def create(sms, name):
    r = _base(sms); os.makedirs(r, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in (name or "task"))[:40] or "task"
    p = os.path.join(r, time.strftime("%Y%m%d-%H%M%S") + "-" + safe); os.makedirs(p, exist_ok=True)
    _write(p, "active"); return p

def listed(sms):
    r = _base(sms); return sorted(d for d in os.listdir(r) if os.path.isdir(os.path.join(r, d))) if os.path.isdir(r) else []

def deliver(sms, sid, to, yes, w):
    p = os.path.join(_base(sms), sid or ""); _guard(sms, p); t = os.path.abspath(to) if to else ""
    if not os.path.isdir(p): return {"error": "沙盒不存在"}
    if not t: return {"error": "须由用户指定目标路径 --to"}
    if os.path.isdir(t) and os.listdir(t): return {"error": "目标非空，拒绝覆盖"}
    if not (yes and w): return {"preview": True, "copy": p + " -> " + t, "hint": "--yes --write 执行"}
    import permissions
    if not permissions.allow(sms, "write"): return {"denied": "会话未授予 write"}
    os.makedirs(os.path.dirname(t), exist_ok=True); shutil.copytree(p, t, dirs_exist_ok=True); _write(p, "delivered", t); return {"copied": t, "files": _files(t)}

def clean(sms, sid, yes):
    p = os.path.join(_base(sms), sid or ""); _guard(sms, p)
    if not os.path.isdir(p): return {"error": "沙盒不存在"}
    if not yes: return {"preview": True, "remove": p, "hint": "--yes 删除"}
    shutil.rmtree(p); return {"removed": p}

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home
    a = sys.argv[1:]; f = lambda k: a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else ""
    cmd = a[0] if a else "list"; sms = resolve_home.ensure()
    if cmd == "create": print(create(sms, f("--name")))
    elif cmd == "list": print(json.dumps(listed(sms), ensure_ascii=False))
    elif cmd == "deliver": print(json.dumps(deliver(sms, f("--id"), f("--to"), "--yes" in a, "--write" in a), ensure_ascii=False, indent=2))
    elif cmd == "clean": print(json.dumps(clean(sms, f("--id"), "--yes" in a), ensure_ascii=False, indent=2))
    else: print("用法: create --name N | list | deliver --id I --to P [--yes --write] | clean --id I [--yes]")
