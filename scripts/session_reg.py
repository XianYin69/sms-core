#!/usr/bin/env python3
"""session_reg.py — session 提升为一等公民的唯一权威注册表（2026-09-29 用户诉求「我们现在需要重视session链：客户端会话各占用一个session，网页端访问各占用一个session，QQ等远程访问各占用一个session，计划任务会话各占用一个session，后台任务各占用一个session；session 的查看/新建/切换不用通过大模型，直接通过脚本完成」）：一条 session＝一个接入通道的归属容器，kind∈client|web|qq|cron|bg|shell（shell＝旧口径兼容），字段 {created,name,kind,key,pid,last_active,state,conv}；key＝通道内稳定标识（client＝壳 pid·web＝配对 token 摘要/指纹·qq＝openid·cron＝任务名·bg＝后台任务名）；ensure(kind,key,name) 同 (kind,key) 复用并 touch、否则新建（幂等·同 key 绝不重复建），bind() 各通道「只加一行」接线＝ensure＋beat＋把本进程 env SMS_SESSION 与 chains.ACTIVE 指到该 sid（异常全吞·不拖垮主流程），touch/beat 续活，set_state(sid,state) 供通道置 stalled/active，list_/get_/rename_/release 查改收（release 只置 finished 不删数据），current()＝env SMS_SESSION → shell/current_session → ensure("client",pid) 兜底，fresh(kind,secs) 供来源判定（QQ 看门狗 src 优先读它），migrate() 给旧条目补 kind="shell"、无 last_active 者置 state="finished"（只补字段·绝不删除旧条目）；写走 atomic_io 原子换入，读失败时 _OK 置假且 _w 拒绝覆盖写（防读空误删全表·实测教训），其余异常静默回空/False。数据仍存 <SMS_HOME>/shell/sessions.json（与 chains.py 同文件同口径）；查看/新建/切换经 session_cli.py 零模型直达，:session（shell_core）与 chains.py __main__ 共用此一口径。"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import resolve_home, atomic_io
KINDS = ("client", "web", "remote", "qq", "cron", "bg", "shell"); ALIAS = {"qq": "remote"}; _OK = [True]
_p = lambda sms=None: os.path.join(sms or resolve_home.ensure(), "shell", "sessions.json"); _c = lambda sms=None: os.path.join(sms or resolve_home.ensure(), "shell", "current_session"); _n = lambda: time.strftime("%Y-%m-%d %H:%M:%S"); _norm = lambda k: ALIAS.get(k, k) if (k in KINDS or k in ALIAS) else "shell"; _age = lambda s: (time.time() - time.mktime(time.strptime(s, "%Y-%m-%d %H:%M:%S"))) if s else 1e18; _rd = lambda p: open(p, encoding="utf-8").read().strip() if os.path.exists(p) else ""
def _r(sms=None):
    try: return atomic_io.rjson(_p(sms), default={}) or {}
    except Exception: _OK[0] = False; return {}
def _w(m, sms=None):
    if not _OK[0] and os.path.exists(_p(sms)): return False
    try: atomic_io.wjson(_p(sms), m); return True
    except Exception: return False
def find(kind, key, sms=None): return next((s for s, v in _r(sms).items() if isinstance(v, dict) and v.get("kind") in _ks(_norm(kind)) and str(v.get("key")) == str(key or "")), "")
def find(kind, key, sms=None): return next((s for s, v in _r(sms).items() if isinstance(v, dict) and v.get("kind") in _ks(_norm(kind)) and str(v.get("key")) == str(key or "")), "")
def _ks(k):
    return {k} | {a for a, b in ALIAS.items() if b == k}
def fresh(kind, secs=1800, sms=None): return _age(max([str(v.get("last_active") or "") for k, v in _r(sms).items() if isinstance(v, dict) and v.get("kind") in _ks(_norm(kind))] or [""])) < secs
def _uniq(b, m):
    """新建 sid 全局唯一：基础名冲突时追加自增短序号 -%03d 循环探测直至不存在，仍满则退化为随机后缀——绝不覆盖既有条目。"""
    if b not in m: return b
    for i in range(1, 1000):
        s = "%s-%03d" % (b, i)
        if s not in m: return s
    return "%s-%s" % (b, os.urandom(3).hex())
def ensure(kind, key, name="", sms=None):
    """同 (kind,key) 复用并 touch，否则新建——通道每轮调它都幂等，绝不重复建 session。"""
    kind = _norm(kind); k = str(key or ""); m = _r(sms); sid = find(kind, k, sms)
    if sid: m[sid].update(last_active=_n(), state="active", name=m[sid].get("name") or (str(name or "")[:40] or kind + ":" + k[:24])); _w(m, sms); return sid
    sid = _uniq("sess-" + time.strftime("%Y%m%d-%H%M%S"), m)
    m[sid] = dict(created=_n(), name=(str(name or "").strip()[:40] or kind + ":" + k[:24]), kind=kind, key=k, pid=os.getpid(), last_active=_n(), state="active", conv="", convs=[])
    _w(m, sms); return sid
def bind(kind, key, name="", conv="", sms=None):
    """通道接线一行＝ensure＋beat＋本进程 env/chains 指向该 sid（异常全吞·绝不拖垮主流程）。"""
    try: sid = ensure(kind, key, name, sms); beat(sid, conv, sms); os.environ["SMS_SESSION"] = sid; __import__("chains").set_active(sess=sid); return sid
    except Exception: return ""
def _up(sid, sms=None, **kv):
    m = _r(sms); v = m.get(sid)
    return sid if isinstance(v, dict) and (v.update({k: x for k, x in kv.items() if x is not None}) or _w(m, sms)) else ""
def touch(sid, sms=None): return _up(sid, sms, last_active=_n())
def beat(sid, conv="", sms=None): r = _up(sid, sms, last_active=_n(), state="active", pid=os.getpid(), conv=(str(conv or "")[:60] or None)); attach(conv, sid, sms); return r
def attach(conv="", sid=None, sms=None):
    """conv 挂所属 session 的 convs 历史（幂等·上限 60）——session＝多对话容器。"""
    try:
        sid = sid or current(sms); c = str(conv or "")[:60]; m = _r(sms); v = m.get(sid)
        if not c or not isinstance(v, dict): return False
        lst = v.setdefault("convs", [])
        if c not in lst: lst.append(c); del lst[:-60]
        v["conv"] = c; v["last_active"] = _n(); return _w(m, sms)
    except Exception: return False
def convs(sid="", sms=None):
    v = get_(sid or current(sms), sms); return list(v.get("convs") or [])
def list_(sms=None): return {k: v for k, v in _r(sms).items() if isinstance(v, dict)}
def get_(sid, sms=None): return list_(sms).get(sid) or {}
def rename_(sid, name, sms=None): return _up(sid, sms, name=str(name or "")[:40] or None)
def release(sid, sms=None): return _up(sid, sms, state="finished", last_active=_n())
def set_state(sid, state, sms=None): return _up(sid, sms, state=str(state or "active"))
def set_current(sid, sms=None):
    try: open(_c(sms), "w", encoding="utf-8").write(sid); return sid
    except Exception: return ""
def current(sms=None):
    """当前 session＝env SMS_SESSION → shell/current_session → ensure("client",pid) 兜底（脚本可直达·不经大模型）。"""
    try: prune(sms)
    except Exception: pass
    sid = os.environ.get("SMS_SESSION") or _rd(_c(sms))
    return touch(sid, sms) if sid and sid in list_(sms) else ensure("client", os.getpid(), "壳" + str(os.getpid()), sms)
def migrate(sms=None):
    """旧条目补 kind="shell"＋缺项字段；无 last_active＝历史遗留 → state="finished"；绝不删除任何条目。"""
    m = _r(sms); n = 0
    for sid, v in m.items():
        if isinstance(v, dict) and v.get("kind") and not v.get("convs") and v.get("conv"):
            v["convs"] = [v["conv"]]  # 已带 kind 的旧条目：最后 conv 回填进历史（不伪造·不计入 migrate 数）
        if isinstance(v, dict) and not v.get("kind"):
            v["kind"] = "shell"; n += 1; v.setdefault("key", sid); v.setdefault("pid", 0); v.setdefault("conv", ""); v.setdefault("convs", [])
            if not v.get("convs") and v.get("conv"): v["convs"] = [v["conv"]]  # 旧条目回填：最后 conv 入历史（不伪造历史）
            if not v.get("last_active"): v["last_active"] = v.get("created") or _n(); v["state"] = "finished"
    _w(m, sms); return n
def _alive(pid):
    """pid 是否还活着（nt＝OpenProcess 句柄探测·posix＝signal 0）；<=0/自身＝True 由调用方排除。"""
    try: pid = int(pid or 0)
    except Exception: return False
    if pid <= 0: return False
    if pid == os.getpid(): return True
    try:
        if os.name == "nt":
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h: return False
            ctypes.windll.kernel32.CloseHandle(h); return True
        os.kill(pid, 0); return True
    except Exception: return False
_PR = [0.0]
def prune(sms=None, force=False, every=60):
    """死壳清理（2026-09-30 用户「重启完 SMS 会有两个进程，只保留重启之后的」残留面）：kind∈client/shell 且 pid 已不存在的 active 条目置 finished——重启/崩溃后 :session ls 与拓扑注入不再列出幽灵壳；60s 节流·force＝立即·绝不删数据，只改 state。"""
    now = time.time()
    if not force and now - _PR[0] < every: return 0
    _PR[0] = now
    m = _r(sms); n = 0
    for sid, v in m.items():
        if not isinstance(v, dict) or v.get("state") != "active": continue
        k = v.get("kind")
        if k in ("client", "shell") and not _alive(v.get("pid")): v["state"] = "finished"; n += 1
        elif k in ("web", "remote") and _age(str(v.get("last_active") or v.get("created") or "")) > 86400: v["state"] = "finished"; n += 1
    if n: _w(m, sms)
    return n
