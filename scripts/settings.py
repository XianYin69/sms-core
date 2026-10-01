#!/usr/bin/env python3
"""settings.py — 配置系统：dot-path get/set，模型输入参数存 <SMS_HOME>/config/config.json（DEFAULTS=config/settings.default.json 深合并保旧配置兼容）；段＝llm_gateway（api_key/base_url/model/温度·top_p）· model_meta（上游模型 Token·上下文·RPM 抓取）· chains（各链启用/修剪/合并）· dream（做梦开关·时间）· web_shell（本地加密网页壳）· external（对外端口）· ui（TUI 界面模式 chat|exec|view·shell_tui_mode 读写）。视图统一存储分离：eff/flat 同时读出 skills.json 技能列表段（scan_roots/skill_generator/sync_clients/Source_Remote/permissions_default），其写回按属主路由 skills_config.set（AGENTS #9 不变）。api_key 恒掩码；变更记 event 链。用法：python -B settings.py status|show|get <path>|set <path> <json>|unset <path>|schema。"""
import os, sys, json, time
from functools import reduce; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import resolve_home, chains, skills_config, atomic_io
DEFAULTS = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "settings.default.json"), encoding="utf-8"))
CH = [c for c in chains.CHAINS if c != "knowledge"]; _G = {"t": 0.0, "d": None}  # get 级 0.4s TTL 缓存（TUI 高频读免全量深合并）；set 即失效
def _dm(a, b):
    for k, v in b.items():
        if k != "comment": a[k] = _dm(a.get(k, {}) if isinstance(a.get(k), dict) else {}, v) if isinstance(v, dict) else v
    return a
def eff(sms=None):
    sms = sms or resolve_home.ensure(); c = resolve_home.conf(sms); c.pop("dream_interval_min", None)
    d = _dm(_dm(json.loads(json.dumps(DEFAULTS)), c), skills_config.load(sms))
    (d.get("dream") or {}).pop("next_run", None)  # interval_min＝用户设置；next_run 运行时间戳恒程序按间隔计算，不随配置进
    return d
def _walk(d, path): return reduce(lambda a, k: a.get(k) if isinstance(a, dict) else None, path.split("."), d)
def get(path, default=None, sms=None):
    if _G["d"] is None or time.time() - _G["t"] > 0.4: _G.update(t=time.time(), d=eff(sms))  # 0.4s TTL：set 置 t=0 即时失效；TUI 顶栏/右栏高频读不再全量深合并
    return default if (v := _walk(_G["d"], path)) is None else v
def maskv(k, v): return "***" if k == "api_key" and v else v
def mask(d): return {k: (mask(v) if isinstance(v, dict) else maskv(k, v)) for k, v in d.items() if k != "comment"}
def flat(d=None, pre=""):
    d = eff() if d is None else d
    rows = [x for k, v in d.items() if k != "comment" for x in (flat(v, pre + k + ".") if isinstance(v, dict) else [{"path": pre + k, "value": maskv(k, v), "default": _walk(DEFAULTS, pre + k)}])]
    if pre == "chains.":
        b = d.get("default") or {}; have = {r["path"] for r in rows}
        rows += [{"path": p, "value": {**b, **(d.get(c) or {})}.get(k), "default": b.get(k)} for c in CH for k in ("enabled", "merge_thr", "prune_days", "min_freq") if (p := "chains.%s.%s" % (c, k)) not in have]
    return rows
def set(path, value, sms=None):
    if path.split(".")[0] in skills_config.SKILL_KEYS: return skills_config.set(path, value, sms)
    sms = sms or resolve_home.ensure(); p = os.path.join(sms, "config", "config.json"); ks = path.split(".")
    doc = atomic_io.rjson(p, default={}) if os.path.exists(p) else {}
    cur = reduce(lambda a, k: a.setdefault(k, {}), ks[:-1], doc)
    cur.update({ks[-1]: value}) if value is not None else cur.pop(ks[-1], None)
    atomic_io.wjson(p, doc); _G["t"] = 0; chains.record("event", "config set " + path + "=" + str(maskv(ks[-1], value))[:80]); return get(path, sms=sms)
def status(sms=None):
    import model_meta, dream, net_util, ext_net, ff_lite, tts
    sms = sms or resolve_home.ensure(); e = eff(sms); g = e["llm_gateway"]; base = e["chains"].get("default", {}); key = os.environ.get(g.get("api_key_env") or "", "") or g.get("api_key")
    return {"gateway": {"enabled": g.get("enabled"), "base_url": g.get("base_url"), "model": g.get("model"), "api_key": "set" if key else "missing", "temperature": g.get("temperature"), "top_p": g.get("top_p"), "max_tokens": g.get("max_tokens"), "reasoning": g.get("reasoning_effort"), "retries": g.get("retries")},
     "model_meta": model_meta.summary(), "agent_tools": __import__("agent_dispatch").tools_status(),
     "dream": {"enabled": e["dream"]["enabled"], "interval_min": dream.interval_min(sms), "next_run": dream.next_run(sms), "due": dream.due(sms)},
     "chains": {c: {**base, **(e["chains"].get(c) or {})} for c in CH}, "hud": e.get("hud"),
     "web_shell": {**e["web_shell"], "running": net_util.running("web_shell")}, "external": {**e["external"], "running": net_util.running("external"), "backend": ext_net.backend()}, "ff_lite": ff_lite.status(), "tts": json.loads(tts.status())}
if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]; cmd = a[0]; pj = lambda o, i=None: print(json.dumps(o, ensure_ascii=False, default=str, indent=i))
    if cmd == "status": pj(status(), 1)
    elif cmd == "show": pj(mask(eff()), 1)
    elif cmd in ("get", "unset", "schema"): pj(get(a[1]) if cmd == "get" else set(a[1], None) if cmd == "unset" else flat(DEFAULTS))
    elif cmd == "set" and len(a) > 2: pj(set(a[1], json.loads(a[2])))
    else: print(__doc__.strip().splitlines()[-1])
