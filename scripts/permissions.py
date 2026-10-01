#!/usr/bin/env python3
"""permissions.py — 权限：grant/deny/check/status/audit + 角色批量 + TTL 自动到期 + 按 id 绑定授予；生效优先级＝今日显式授予（audit 记过的键·含 TTL）＞ 配置默认 skills.json permissions_default（danger 不随默认）＞ 内置默认——F4 改 permissions_default 即与运行时一致；danger 键控高危（红线16）：默认拒绝、不随角色批量、须当轮单独 grant；remote 键控「远程会话越过默认安全名单执行受控元指令」——同样不随 admin 角色批量；按 id（QQ openid／web 会话 sid／client sid／友好名）的专属授予落 <SMS_HOME>/permissions/ids.json，TTL 到期自动失效，未记过的键回落全局/配置默认——无 --id 时行为与今天完全一致（向后兼容）；SOLO 模式（solo.py）开启时 status 附 solo 段并把自审授予的键来源标为「SOLO 自审授予」，收回＝:grant revoke <键>（:grant <键> 0 是永久授予非收回）——solo.py 缺失时输出与今天逐字一致。用法：python -B permissions.py status | check <键|角色> [--id <id>] | grant|deny <键|角色> [分钟] [--id <id>] | revoke <键> --id <id> | unbind <id> | ids | resolve <名> [--write]"""
import os, sys, json, time
from datetime import datetime, timedelta
KEYS = ("read", "write", "execute", "network", "privacy", "vault", "verify", "danger", "remote")
ROLES = {"readonly": ["read"], "worker": ["read", "write", "execute"], "net": ["read", "write", "execute", "network"],
         "privacy": ["read", "privacy"], "secrets": ["read", "vault", "verify"], "admin": [k for k in KEYS if k not in ("danger", "remote")]}
DEFAULT_GRANTS = dict(zip(KEYS, [True, False, False, False, False, False, False, False, False]))
DATE = time.strftime("%Y-%m-%d")
def _path(sms): return os.path.join(sms, "sessions", DATE, "permissions.json")
def _ipath(sms): return os.path.join(sms, "permissions", "ids.json")
def _ids(sms):
    """按 id 授予的存储（缺/坏＝{}——绝不因文件问题拖垮准入判定）。"""
    try:
        import atomic_io; d = atomic_io.rjson(_ipath(sms), default={}) or {}
        return d if isinstance(d, dict) else {}
    except Exception: return {}
def _save_ids(sms, d):
    try: import atomic_io; atomic_io.wjson(_ipath(sms), d); return True
    except Exception: return False
def check(doc, key):
    v = doc["grants"].get(key)
    if isinstance(v, dict): return bool(v.get("on")) and time.strftime("%Y-%m-%dT%H:%M:%S") < str(v.get("until", ""))
    if isinstance(v, str): return v.strip().lower() in ("true", "1", "on", "yes", "开")
    return bool(v)
def _seed(sms=None):
    d = dict(DEFAULT_GRANTS)
    try:
        import skills_config
        for k, v in (skills_config.get("permissions_default", {}, sms) or {}).items():
            if k in KEYS and k != "danger": d[k] = check({"grants": {k: v}}, k)
    except Exception: pass
    return d
def _doc(path, sms=None):
    if not os.path.exists(path): return {"date": DATE, "audit": [], "grants": _seed(sms)}
    doc = json.load(open(path, encoding="utf-8")); doc.setdefault("grants", {}); doc.setdefault("audit", []); return doc
def _solo_view(sms, doc, e, src):
    """SOLO 自审分支（solo.py 缺失/异常＝None·status 输出与今天一致）：SOLO 开启时把自审授予的键来源
    标注为 SOLO，并附开关/allow_danger/永不自审键/当日放行数，供 :grant status 与 F10 权限总览同源显示。"""
    try:
        import solo
    except Exception:
        return None
    try:
        st = solo.status(sms)
    except Exception:
        return None
    if not isinstance(st, dict):
        return None
    if st.get("enabled"):
        for k in KEYS:
            if e.get(k) and any(a.get("action") == "grant" and a.get("key") == k and a.get("solo")
                                for a in (doc.get("audit") or [])):
                src[k] = "SOLO 自审授予（:grant revoke %s 收回）" % k
        if not st.get("allow_danger") and not e.get("danger"):
            src["danger"] = "SOLO 开但 allow_danger=false——仍须当轮 :grant danger（红线16）"
    return {"enabled": bool(st.get("enabled")), "allow_danger": bool(st.get("allow_danger")),
            "never": list(st.get("never") or []), "ttl_min": st.get("ttl_min"),
            "max_ttl_min": st.get("max_ttl_min"), "gateway_ok": bool(st.get("gateway_ok")),
            "granted_today": int(st.get("granted_today") or 0)}

def _eff(sms):
    doc = _doc(_path(sms), sms); ex = {a.get("key") for a in doc["audit"] if a.get("action") in ("grant", "deny")}
    e = _seed(sms); src = {k: "配置默认" for k in KEYS}
    for k in KEYS:
        if k in ex and k in doc["grants"]: e[k] = check(doc, k); src[k] = "今日授予" + ("（TTL）" if isinstance(doc["grants"][k], dict) else "")
    src["danger"] = "仅今日单独 grant（红线16）" if e.get("danger") or "danger" in ex else "恒默认拒绝"
    src["remote"] = "仅按 id 授予或今日单独 grant" if e.get("remote") else "恒默认拒绝（远程走安全名单）"
    solo = _solo_view(sms, doc, e, src)
    out = {"effective": e, "source": src, "grants": doc["grants"], "config_default": _seed(sms)}
    if solo: out["solo"] = solo
    return out
def resolve(name, sms=None):
    """友好名/sid/openid → 真 id：先 ids.json（key 与 name·大小写不敏感·前缀匹配），再 session_reg（sid/name/key），再 qq.json（openid/allow）；不命中原样返回（绝不因解析失败阻断授予）。"""
    s = str(name or "").strip()
    if not s: return s
    try: sms = sms or __import__("resolve_home").ensure()
    except Exception: return s
    low = s.lower(); d = _ids(sms)
    for k in d:
        if str(k).lower() == low: return k
    for k in d:
        if str(k).lower().startswith(low) or str((d.get(k) or {}).get("name") or "").lower().startswith(low): return k
    try:
        import session_reg; rows = session_reg.list_(sms) or {}
        for sid, v in rows.items():
            if low in (str(v.get("name") or "").lower(), str(v.get("key") or "").lower()) and low: return sid
        for sid in rows:
            if str(sid).lower().startswith(low): return sid
    except Exception: pass
    try:
        import qq_push; c = qq_push.conf(sms)
        cand = [str(x) for x in ([c.get("openid")] + list(c.get("allow") or [])) if x]
        return next((x for x in cand if x.lower() == low), None) or next((x for x in cand if x.lower().startswith(low)), s)
    except Exception: return s
def _idkind(sms, rid):
    """id 归属通道＝session_reg 的 kind（qq/web/client/cron/bg）→ qq.json 命中＝qq → 其余＝session。"""
    try:
        import session_reg
        for sid, v in (session_reg.list_(sms) or {}).items():
            if rid in (sid, str(v.get("key") or "")): return v.get("kind") or "session"
    except Exception: pass
    try:
        import qq_push; c = qq_push.conf(sms)
        if rid in [str(c.get("openid") or "")] + [str(x) for x in (c.get("allow") or [])]: return "qq"
    except Exception: pass
    return "session"
def id_check(sms, key, id):
    """ids.json 里该 id 的该键走 check() 同一语义（dict 带 until 判 TTL）。"""
    g = ((_ids(sms).get(str(id)) or {}).get("grants") or {})
    return check({"grants": {key: g.get(key)}}, key)
_BG_KEYS = ("SMS_BG", "SMS_NONINTERACTIVE", "SMS_DREAM")
_SOLO_BUSY = [False]
_NONINTERACTIVE = [False]
def set_noninteractive(on):
    """后台/非交互总闸（dream_bg／auto_compress／dep_fetch／deploy 启动时置 True）：置位后 allow 不走 SOLO 自审，权限判定回到纯授予/配置默认，防无人应答时阻塞与成本失控。"""
    _NONINTERACTIVE[0] = bool(on)
def _solo_gate(sms, key, id=None):
    """SOLO 自审放行分支（solo.py 缺失/异常/后台＝False·行为与今天逐字一致）：
    重入保护——solo.gate 内部回调本模块 allow()，置 _SOLO_BUSY 令其只走纯授予判定，绝不自审套自审。"""
    if _SOLO_BUSY[0] or _NONINTERACTIVE[0]: return False
    if any(os.environ.get(k) for k in _BG_KEYS): return False
    try:
        import solo
    except Exception:
        return False
    _SOLO_BUSY[0] = True
    try:
        ok, _note = solo.gate(sms, str(key), {"id": id})
        return bool(ok)
    except Exception:
        return False
    finally:
        _SOLO_BUSY[0] = False
def allow_base(sms, key, id=None):
    """纯授予判定（不含 SOLO 自审·SOLO 关闭时行为与此逐字一致）：id 为空＝原全局逻辑；id 非空＝优先该 id 专属授予（含 TTL），未记过的键回落 _eff。solo 模块与后台路径用此函数。"""
    if not id: return _eff(sms)["effective"].get(key, False)
    if str(key) in ((_ids(sms).get(str(id)) or {}).get("grants") or {}): return id_check(sms, key, id)
    return _eff(sms)["effective"].get(key, False)
def allow(sms, key, id=None):
    """授予判定＋SOLO 自审放行分支：allow_base 判「未授予」时才问自审（solo.enabled=false／solo.py 缺失／后台＝恒 False，与今天逐字一致）。"""
    if allow_base(sms, key, id): return True
    return _solo_gate(sms, key, id)
def _list_ids(sms):
    """ids 视图：每 id 的 name/kind/未过期授予键与 until/最近 audit 3 条。"""
    out = {}
    for rid, v in _ids(sms).items():
        v = v or {}; g = v.get("grants") or {}
        out[rid] = {"name": str(v.get("name") or ""), "kind": v.get("kind") or _idkind(sms, rid),
                    "grants": {k: (x.get("until", "") if isinstance(x, dict) else "永久") for k, x in g.items() if check({"grants": {k: x}}, k)},
                    "audit": (v.get("audit") or [])[-3:]}
    return {"ids": out, "count": len(out), "note": "按 id 专属授予·TTL 到期自动失效"}
def apply(sms, cmd, target, dry, ttl=0, id=None):
    """带 --id 的 grant/deny/check/revoke 与 unbind/ids/resolve 走 ids.json；其余＝原全局逻辑（无 --id 行为不变）。"""
    if cmd == "status": return _eff(sms)
    if cmd == "ids": return _list_ids(sms)
    if cmd == "resolve": return {"query": target, "id": resolve(target, sms)}
    rid = resolve(str(id).strip(), sms) if id else ""
    if cmd == "unbind":
        bid = rid or resolve(str(target or "").strip(), sms); d = _ids(sms); had = bid in d
        if dry: return {"dry_run": True, "id": bid, "removed": had, "grants": (d.get(bid) or {}).get("grants") or {}}
        d.pop(bid, None); _save_ids(sms, d)
        return {"id": bid, "removed": had, "note": "该 id 整条绑定已删除（下次授予重新建档）"}
    if rid and cmd in ("grant", "deny"):
        d = _ids(sms); ent = d.get(rid) or {"name": "", "kind": _idkind(sms, rid), "grants": {}, "audit": []}
        ent.setdefault("grants", {}); on = cmd == "grant"
        for k in ROLES.get(target, [target]):
            ent["grants"][k] = {"on": True, "until": (datetime.now() + timedelta(minutes=ttl)).strftime("%Y-%m-%dT%H:%M:%S")} if on and ttl else bool(on)
        ent["audit"] = (ent.get("audit") or [])[-49:] + [{"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "action": cmd, "key": target, "ttl_min": ttl, "id": rid}]
        ent["kind"] = ent.get("kind") or _idkind(sms, rid); d[rid] = ent
        if dry: return {"dry_run": True, "id": rid, "grants": ent["grants"]}
        _save_ids(sms, d)
        return {"id": rid, "kind": ent["kind"], "grants": ent["grants"], "note": "该 id 专属授予·TTL 到期自动失效"}
    if cmd == "check":
        keys = ROLES.get(target, [target])
        if rid: return {"target": target, "id": rid, "allowed": {k: allow(sms, k, id=rid) for k in keys}}
        return {"target": target, "allowed": {k: allow(sms, k) for k in keys}}
    if rid and cmd == "revoke":
        d = _ids(sms); ent = d.get(rid) or {"name": "", "kind": _idkind(sms, rid), "grants": {}, "audit": []}
        ent.setdefault("grants", {})[str(target)] = False
        ent["audit"] = (ent.get("audit") or [])[-49:] + [{"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "action": "revoke", "key": target, "ttl_min": 0, "id": rid}]
        ent["kind"] = ent.get("kind") or _idkind(sms, rid); d[rid] = ent
        if dry: return {"dry_run": True, "id": rid, "grants": ent["grants"]}
        _save_ids(sms, d)
        return {"id": rid, "grants": ent["grants"], "note": "该 id 的 " + str(target) + " 已置 False（显式拒绝·不回落全局）"}
    path, doc = _path(sms), _doc(_path(sms), sms); on = cmd == "grant"
    for k in ROLES.get(target, [target]):
        doc["grants"][k] = {"on": True, "until": (datetime.now() + timedelta(minutes=ttl)).strftime("%Y-%m-%dT%H:%M:%S")} if on and ttl else on
        doc.setdefault("audit", []).append({"ts": time.strftime("%H:%M:%S"), "action": cmd, "key": k, "ttl_min": ttl})
    if dry: return {"dry_run": True, "grants": doc["grants"]}
    os.makedirs(os.path.dirname(path), exist_ok=True); import atomic_io; atomic_io.wjson(path, doc)
    return {"grants": doc["grants"], "note": "未显式授予的键恒随配置 permissions_default（F4 可改）"}
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import resolve_home
    sms = resolve_home.ensure(); a = sys.argv[1:] or ["status"]
    cmd = a[0]; target = a[1] if len(a) > 1 and not a[1].startswith("--") else "write"; ttl = next((int(x) for x in a[2:] if x.isdigit()), 0)
    iv = a.index("--id") if "--id" in a else -1; idv = a[iv + 1] if 0 <= iv < len(a) - 1 else None
    print(json.dumps(apply(sms, cmd, target, "--write" not in a, ttl, idv), ensure_ascii=False, indent=2))
