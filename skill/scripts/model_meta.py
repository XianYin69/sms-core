#!/usr/bin/env python3
"""model_meta.py — 自动从上游获取模型 Token/上下文长度/RPM 等信息：GET {base_url}/models 读扩展字段（context_length·max_model_len·max_completion_tokens·rate_limits）＋对当前 model 一次 min 探测读 x-ratelimit 响应头；批29 越界反推真实硬限——listing 常无元数据（实测 SCNet-Max 只回 id/object/ownedBy，defaults 的 8192 被当真窗口显示、每轮误报超限）：max_tokens 传超大读「between 1 and N」得输出上限（实测 131072）、超长正文读「Input length must be between 1 and N」得输入上限（实测 983616）；缓存 <SMS_HOME>/config/models.json（source＝upstream/probe/listing/default，auto_refresh 超 refresh_interval_min 自动重抓）。用法：python -B model_meta.py refresh|show|get <model>|context <model>|probe [model]|selftest。"""
import os, sys, json, re, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, settings, gateway, dsm
def path(): return os.path.join(resolve_home.ensure(), "config", "models.json")
def load():
    try: return json.load(open(path(), encoding="utf-8"))
    except Exception: return {}
def _wj(d):
    os.makedirs(os.path.dirname(path()), exist_ok=True); json.dump(d, open(path(), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
def _pick(m, *ks): return next((m[k] for k in ks if isinstance(m.get(k), int)), None)
LIM = [r"between\s+1\s+and\s+(\d{3,9})", r"maximum\s+context\s+length\s+is\s+(\d{3,9})",
       r"context\s+length\s+(?:of\s+)?(\d{3,9})\s+tokens", r"input\s+length[^\d]{0,20}(\d{3,9})",
       r"max(?:imum)?\s*_?(?:tokens?|output)[^\d]{0,20}(\d{3,9})"]
def parse_limit(txt):
    t = str(txt or "")
    for p in LIM:
        m = re.search(p, t, re.I)
        if m: return int(m.group(1))
    return None
def _post(payload, timeout=90):
    """越界探测取 (data, err_text)——探测专用，不走重试（要的就是报错原文）。
    端点＝smsocket 的 OpenAI-compat /v1/chat/completions（base_url 已由 smsocket_boot.attach 指向
    smsocket 网关）：探测要的是**上游报错原文**（「between 1 and N」）与 x-ratelimit 响应头，
    DSM 信封响应（decode_to_openai_shape 后）由 smsocket 出口层改写 usage 口径且不透传这些头，
    故越界探测保留 OpenAI-compat 端点；DSM 是**对话出站**唯一通道，本探测属诊断旁路、非对话流。"""
    c = gateway.cfg()
    req = urllib.request.Request(dsm.api_url("/chat/completions", str(c.get("base_url", ""))), data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + str(c.get("api_key", "")), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=int(timeout)) as r: return json.loads(r.read().decode("utf-8", "replace")), ""
    except Exception as e:
        try: return None, e.read().decode("utf-8", "replace")[:600]
        except Exception: return None, str(e)[:300]
def probe_output(model):
    """max_tokens 传超大 → 报错文案里的上限＝真实输出上限（SCNet-Max 实测 131072）。"""
    d, e = _post({"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 10 ** 8})
    return None if d else parse_limit(e)
def probe_context(model, fill=None):
    """填充正文超窗 → 报错文案里的上限＝真实输入上限（SCNet-Max 实测 983616）。
    填充默认 200 万字（中文≈0.55 tok/字≈109 万 tok），对 ≤100 万 tok 的模型必超；上游不校验＝回 None。"""
    n = int(fill or settings.eff()["model_meta"].get("probe_fill_chars", 2000000))
    d, e = _post({"model": model, "messages": [{"role": "user", "content": "越界探测填充。" * max(1, n // 7)}], "max_tokens": 1}, 180)
    return None if d else parse_limit(e)
def _probe(model):
    """RPM 探测（x-ratelimit-limit-requests 响应头）——读 smsocket 网关端点（base_url 已由
    smsocket_boot.attach 指向 smsocket）：对话出站统一走 DSM 信封，本探测属诊断旁路保留响应头读取。"""
    try:
        c = gateway.cfg(); req = urllib.request.Request(dsm.api_url("/chat/completions", str(c.get("base_url", ""))),
            data=json.dumps({"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}).encode(),
            headers={"Authorization": "Bearer " + str(c.get("api_key", "")), "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=int(c.get("timeout", 120))) as r: return r.headers.get("x-ratelimit-limit-requests")
    except Exception: return None
def refresh():
    # /models 列表＝经 smsocket 网关（base_url 已由 smsocket_boot.attach 指向 smsocket），
    # 与 gateway.__main__ "models" 同一端点；非对话流诊断旁路。
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
    if settings.eff()["model_meta"].get("probe_limits", True):
        e = models.setdefault(cur, {"context_length": None, "max_output_tokens": None, "rpm": None, "tpm": None, "source": "listing"})
        if not e.get("max_output_tokens"):
            v = probe_output(cur)
            if v: e["max_output_tokens"] = v; e["source"] = "probe"
        if not e.get("context_length"):
            v = probe_context(cur)
            if v: e["context_length"] = v; e["source"] = "probe"
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
    elif cmd == "probe":
        m = (a[1:] or [gateway.cfg().get("model") or "auto"])[0]
        print(json.dumps({"model": m, "max_output_tokens": probe_output(m), "context_length": probe_context(m)}, ensure_ascii=False))
    elif cmd == "selftest":
        ok = parse_limit('{"error":{"message":"Input length must be between 1 and 983616."}}') == 983616 and parse_limit("max_tokens must be between 1 and 131072.") == 131072 and parse_limit("This model's maximum context length is 8192 tokens, however you requested 9000 tokens") == 8192 and parse_limit("no digits here") is None
        print("model_meta selftest: " + ("OK" if ok else "FAIL")); raise SystemExit(0 if ok else 1)
    else: print(__doc__.strip().splitlines()[-1])
