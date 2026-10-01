#!/usr/bin/env python3
"""model_meta.py — 自动从上游获取模型 Token/上下文长度/RPM 等信息：GET {base_url}/models 读扩展字段（context_length·max_model_len·max_completion_tokens·rate_limits）＋对当前 model 一次 min 探测读 x-ratelimit 响应头；缓存 <SMS_HOME>/config/models.json（source＝upstream/probe/listing/default，auto_refresh 超 refresh_interval_min 自动重抓）。用法：python -B model_meta.py refresh|show|get <model>|context <model>。"""
import os, sys, json, time, urllib.request, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, settings, gateway
def path(): return os.path.join(resolve_home.ensure(), "config", "models.json")
def load():
    try: return json.load(open(path(), encoding="utf-8"))
    except Exception: return {}
def _wj(d):
    os.makedirs(os.path.dirname(path()), exist_ok=True); json.dump(d, open(path(), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
def _pick(m, *ks): return next((m[k] for k in ks if isinstance(m.get(k), int)), None)
def _probe(model):
    try:
        c = gateway.cfg(); req = urllib.request.Request(str(c.get("base_url", "")).rstrip("/") + "/chat/completions",
            data=json.dumps({"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}).encode(),
            headers={"Authorization": "Bearer " + str(c.get("api_key", "")), "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=int(c.get("timeout", 120))) as r: return r.headers.get("x-ratelimit-limit-requests")
    except Exception: return None
def refresh():
    models = {}; doc = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "ts_epoch": time.time(), "base_url": gateway.cfg().get("base_url"), "models": models, "err": ""}
    data, err = gateway._req("/models")
    if not data: doc["err"] = err; _wj(doc); return doc
    for m in data.get("data", []):
        rl = m.get("rate_limits") or {}
        up = any([_pick(m, "context_length", "max_model_len"), _pick(m, "max_completion_tokens", "max_output_tokens"), rl, m.get("rpm"), m.get("tpm")])
        models[m.get("id")] = {"context_length": _pick(m, "context_length", "max_model_len"), "max_output_tokens": _pick(m, "max_completion_tokens", "max_output_tokens"),
            "rpm": rl.get("requests") or m.get("rpm"), "tpm": rl.get("tokens") or m.get("tpm"), "source": "upstream" if up else "listing"}
    cur = gateway.cfg().get("model") or "auto"; rpm = _probe(cur)
    if models.get(cur) is not None and rpm: models[cur]["rpm"] = rpm; models[cur]["source"] = "probe"
    _wj(doc); return doc
def maybe():
    c = settings.eff()["model_meta"]; d = load()
    if c.get("auto_refresh") and time.time() - d.get("ts_epoch", 0) > c.get("refresh_interval_min", 720) * 60:
        try: refresh()
        except Exception: pass
def get(model=None):
    d = load(); e = (d.get("models") or {}).get(model or gateway.cfg().get("model") or "auto", {}); dd = settings.eff()["model_meta"]["defaults"]
    return {k: (e.get(k) if e.get(k) is not None else dd.get(k)) for k in ("context_length", "max_output_tokens", "rpm", "tpm")} | {"source": e.get("source", "default")}
def context(model=None): return get(model)["context_length"]
def summary(): d = load(); return {"ts": d.get("ts"), "count": len(d.get("models") or {}), "err": d.get("err") or None, "current": get()}
if __name__ == "__main__":
    a = sys.argv[1:] or ["show"]; cmd = a[0]
    if cmd == "refresh": print(json.dumps(refresh(), ensure_ascii=False, indent=1)[:1800])
    elif cmd == "show": print(json.dumps({"ts": load().get("ts"), "models": load().get("models")}, ensure_ascii=False, indent=1)[:3000])
    elif cmd == "get" and a[1:]: print(json.dumps(get(a[1]), ensure_ascii=False))
    elif cmd == "context" and a[1:]: print(context(a[1]))
    else: print(__doc__.strip().splitlines()[-1])
