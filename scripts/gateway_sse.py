#!/usr/bin/env python3
"""gateway_sse.py — 原生网关 SSE 流式（2026-09-26 治「运行慢」观感·ps1 壳已流式而 python 壳整轮等待）：stream(msgs, on_line) 以 stream:true 请求 /chat/completions，按 index 合并 delta.tool_calls 分片（id/name/arguments 拼接），返回与 gateway.chat 同构的 (message, note)。批7 返工②（用户 2026-09-27 截图：思考混在 delta.content 里直刷主屏——上游 auto 不总用 reasoning_content 字段）：流式期间 content 与 reasoning 段一律经「◌ 」reasoning 信封只进 F9 过程流；轮末由 gateway.run 判定——无 tool_calls 才把整段正文送主输出，有 tool_calls 则该轮正文＝过程话永不上主屏（printed=True 防重复吐显·纯思考模型兜底 content=思考）。「残缺」根治（批4）：v2 全程另存 acc 完整正文，返回 content=acc 全文；上游不支持 event-stream 时读整包按非流式同构返回·思考走 ◌ 信封正文由 run 整段上屏；异常回 (None, err)。llm_gateway.stream=false 即回退整轮 chat()。用法：经 gateway.chat 调用；python -B gateway_sse.py "<文本>" 直连验证流式。"""
import os, sys, json, time, urllib.request, msg_flow, stop_channel as stop, settings
import retry_io as rio, runtime_rec as rr
class _NoRetry(Exception): pass
SENT = "。！？；!?…"
def _req(msgs):
    import agent_dispatch as ad
    c = settings.eff()["llm_gateway"]; body = {"model": c.get("model") or "auto", "messages": msgs, "max_tokens": int(c.get("max_tokens", 1024)), "tools": ad.tools_schema(), "stream": True, **{k: c[k] for k in ("temperature", "top_p", "reasoning_effort") if c.get(k) is not None}}
    key = os.environ.get(c.get("api_key_env") or "", "") or c.get("api_key", "")
    return urllib.request.Request(str(c.get("base_url", "")).rstrip("/") + "/chat/completions", data=json.dumps(body).encode("utf-8"), headers={"Authorization": "Bearer " + str(key), "Content-Type": "application/json", "Accept": "text/event-stream"}), int(c.get("timeout", 120))
def _emit(buf, on_line):
    while buf:
        i = next((j for j, ch in enumerate(buf) if ch == "\n" or (ch in SENT and j > 24)), -1)
        if i < 0 and len(buf) < 88: break
        seg = buf[:i + 1] if i >= 0 else buf[:88]
        on_line(seg.rstrip("\n")); buf = buf[i + 1:] if i >= 0 else buf[88:]
    return buf
def _msg(d):
    m = (d.get("choices") or [{}])[0].get("message") or {}; m["content"] = (m.get("content") or "").replace("\x00", "").replace("\r", "\n"); return m, str((d.get("choices") or [{}])[0].get("finish_reason"))
def _rline(s): return msg_flow.brief(msg_flow.make("reasoning", s))
def _once(msgs, on_line):
    req, tout = _req(msgs); buf = ""; rbuf = ""; acc = ""; racc = ""; tcs = {}; fr = ""; maxch = max(1000, int(settings.get("llm_gateway.stream_max_chunks", 20000) or 20000)); pl = lambda s: s.strip() and on_line(_rline(s))
    try:
        with urllib.request.urlopen(req, timeout=tout) as r:
            if "text/event-stream" not in str(r.headers.get("content-type") or ""):
                m, note = _msg(json.loads(r.read().decode("utf-8", "replace"))); rc = m.pop("reasoning_content", "") or ""; rc and on_line(_rline(rc)); return m, note
            for _, raw in zip(range(maxch), r):  # 批12 防卡死：慢速无限吐流按 chunk 上限截停（默认 2 万·正常远达不到·F4 llm_gateway.stream_max_chunks）
                stop.check(); ln = raw.decode("utf-8", "replace").strip()
                if not ln.startswith("data:"): continue
                p = ln[5:].strip()
                if p == "[DONE]": break
                try: d = json.loads(p)
                except Exception: continue
                ch = (d.get("choices") or [{}])[0]; de = ch.get("delta") or {}; fr = ch.get("finish_reason") or fr
                dt = de.get("content") or ""; rt = de.get("reasoning_content") or ""
                acc += dt; racc += rt; buf = _emit(buf + dt, pl); rbuf = _emit(rbuf + rt, pl)
                for t in de.get("tool_calls") or []:
                    e = tcs.setdefault(t.get("index", 0), {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                    f = t.get("function") or {}; e["id"] = e["id"] or (t.get("id") or ""); e["function"]["name"] += f.get("name") or ""; e["function"]["arguments"] += f.get("arguments") or ""
    except stop.Stopped: raise
    except Exception as e:
        detail = ""
        try: detail = e.read().decode("utf-8", "replace")[:200]
        except Exception: pass
        msg = str(e)[:150] + " " + detail
        raise rio.Retryable(msg) if rio.transient(e) else _NoRetry(msg)
    pl(buf); pl(rbuf)
    if not acc.strip() and racc.strip(): acc = racc.strip()
    return {"role": "assistant", "content": acc.replace("\x00", "").replace("\r", "\n"), "tool_calls": list(tcs.values()) if tcs else None, "reasoning_content": "", "printed": True}, "finish=" + (fr or "stop")
def stream(msgs, on_line):
    """提供商流式访问失败＝有限次重试（settings llm_gateway.retries·默认 3·指数退避 1.2s 起封顶 10s）：只在尚未吐字时重试（已吐过正文重试会重复上屏），HTTP 4xx 与 stop 不重试；耗尽回 (None, "重试耗尽(N次) ...")，gateway.run 见标记不再整轮重发。"""
    n = max(0, int(settings.get("llm_gateway.retries", 3))); box = {"out": 0}; bx = {"i": 0}
    def _w(x): box["out"] += 1; on_line(x)
    def _go():
        bx["i"] += 1; rr.rec("llm_stream", attempt=bx["i"] - 1, retries=max(0, n - bx["i"] + 1))
        m, err = _once(msgs, _w)
        if m is None and box["out"]: raise _NoRetry(str(err)[:150])
        rr.rec("llm_stream", attempt=bx["i"] - 1, retries=max(0, n - bx["i"] + 1), err="")
        return m, err
    try:
        return rio.call(_go, n, base=1.2, cap=10.0, retry_on=lambda e: not isinstance(e, _NoRetry) and rio.transient(e),
                        on_try=lambda i, k, e, d: on_line(msg_flow.brief(msg_flow.make("reasoning", "提供商访问失败自动重试 %d/%d：%s" % (i, k, str(e)[:80])))))
    except _NoRetry as e: rr.rec("llm_stream", attempt=bx["i"], retries=0, err=e); return None, str(e)[:150]
    except rio.Retryable as e: rr.rec("llm_stream", attempt=bx["i"], retries=0, err=e); return None, str(e)[:200]

if __name__ == "__main__":
    t = " ".join(sys.argv[1:]) or "你好，用一句话介绍 SMS"; m, err = stream([{"role": "user", "content": t}], lambda s: print(s, flush=True))
    print(json.dumps({"ok": bool(m), "err": err, "chars": len((m or {}).get("content") or ""), "tool_calls": bool((m or {}).get("tool_calls"))}, ensure_ascii=False) if m else "ERR " + err)
