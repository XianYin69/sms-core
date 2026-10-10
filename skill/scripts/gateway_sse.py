#!/usr/bin/env python3
"""gateway_sse.py — 原生网关 SSE 流式（2026-09-26 治「运行慢」观感·ps1 壳已流式而 python 壳整轮等待）：stream(msgs, on_line) 以 stream:true 请求 /chat/completions，按 index 合并 delta.tool_calls 分片（id/name/arguments 拼接），返回与 gateway.chat 同构的 (message, note)。批7 返工②（用户 2026-09-27 截图：思考混在 delta.content 里直刷主屏——上游 auto 不总用 reasoning_content 字段）：流式期间 content 与 reasoning 段一律经「◌ 」reasoning 信封只进 F9 过程流；轮末由 gateway.run 判定——无 tool_calls 才把整段正文送主输出，有 tool_calls 则该轮正文＝过程话永不上主屏（printed=True 防重复吐显·纯思考模型兜底 content=思考）。「残缺」根治（批4）：v2 全程另存 acc 完整正文，返回 content=acc 全文；上游不支持 event-stream 时读整包按非流式同构返回·思考走 ◌ 信封正文由 run 整段上屏；异常回 (None, err)。llm_gateway.stream=false 即回退整轮 chat()。用法：经 gateway.chat 调用；python -B gateway_sse.py "<文本>" 直连验证流式。"""
import os, sys, json, time, urllib.request, msg_flow, stop_channel as stop, settings
import retry_io as rio, runtime_rec as rr
import urllib.error
import dsm
import usage_ledger as ul  # 批41 F1 费用台账落盘
class _NoRetry(Exception): pass
SENT = "。！？；!?…"
def _req(msgs):
    import agent_dispatch as ad
    c = settings.eff()["llm_gateway"]; body = {"model": c.get("model") or "auto", "messages": msgs, "max_tokens": int(c.get("max_tokens", 1024)), "tools": ad.tools_schema(), "stream": True, **{k: c[k] for k in ("temperature", "top_p", "reasoning_effort") if c.get(k) is not None}}
    key = (os.environ.get(c.get("api_key_env") or "") or "").strip() or str(c.get("api_key") or "")  # 空 env 不覆盖配置密钥（同 gateway.cfg 口径）
    return urllib.request.Request(dsm.api_url("/chat/completions", str(c.get("base_url", ""))), data=json.dumps(body).encode("utf-8"), headers={"Authorization": "Bearer " + str(key), "Content-Type": "application/json", "Accept": "text/event-stream"}), int(c.get("timeout", 120))
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
def _dsm_once(msgs, on_line):
    """dsm.enabled=true 的流式路径（契约 §4）：out=json → 单条信封解码后按今天非流式同构返回；
    out=delta → application/x-ndjson 逐条信封按 seq 归并，增量文本经 _emit 上 ◌ reasoning 信封。
    回 (message, note, kind)，kind∈ok|legacy|err；legacy＝落回今天完全相同的路径。"""
    import gateway as g
    c = dsm.cfg()
    if dsm.broken():
        # 冷却期内不再试信封：直接落回今天完全相同的 legacy 流式路
        return None, "DSM 暂不可用（%s）→legacy" % dsm.broken_info()[1], "legacy"
    pl = lambda x: x and x.strip() and on_line(_rline(x))   # 空/None 段直接吞（信封无 reason 时）
    try:
        mem = None
        if c.get("mem_ref"):
            q = " ".join(str(m.get("content") or "") for m in msgs[-2:] if m.get("role") in ("user", "tool"))[:600]
            mem = dsm.mem_ids(q) or None
        env = dsm.build_env(msgs, tools=__import__("agent_dispatch").tools_schema(),
                            model=g.cfg().get("model") or "auto", dsm_cfg=c, mem=mem)
    except Exception as e:
        g._dsm_warn("信封构造失败（语义装不下）→legacy：" + str(e)[:120], on_line); return None, str(e)[:150], "legacy"
    if c.get("schema_ref") and dsm.needs_register(env["sch"]):
        data, err, code, _ct = g._dsm_post(dsm.ENDPOINT_SCHEMA, dsm.schema_frame(env), dsm.CTYPE)
        if code in (404, 415):
            if c.get("fallback"):
                g._dsm_warn("服务端 DSM schema 路由缺失(%d)→降级 legacy" % code, on_line); dsm.mark_broken("sse schema route %d" % code); return None, err, "legacy"
            return None, err, "err"
        if code == 200:
            dsm.mark_registered(env["sch"])
    out = c.get("out") or "json"
    seen = {"n": 0}
    pbuf = [""]

    def _frame(e):
        """ndjson 到一帧就上屏一帧（尾巴3 的正解）：reason 进 ◌ 推理信封，answer 走
        _emit 断句。收口帧的 answer 是数组（tool_calls）——不画正文，归并后交 run()。"""
        if out != "delta" or not isinstance(e, dict):
            return
        seen["n"] += 1
        rs = e.get("reason") or {}
        pl(rs.get("summary") if isinstance(rs, dict) else str(rs))
        a = e.get("answer")
        if isinstance(a, str):
            pbuf[0] = _emit(pbuf[0] + a, pl)
    data, err, code, ct = g._dsm_post(dsm.ENDPOINT, env, dsm.CTYPE_STREAM if out == "delta" else dsm.CTYPE,
                                     on_frame=_frame if out == "delta" else None)
    if code in (404, 415):
        if c.get("fallback"):
            g._dsm_warn("服务端未提供 DSM(%d)→降级 legacy（dsm.fallback=true）" % code, on_line); dsm.mark_broken("sse dsm chat %d" % code); return None, err, "legacy"
        g._dsm_warn("服务端未提供 DSM(%d)且 fallback=false→报错不降级" % code, on_line); return None, err, "err"
    if code == 409:
        # 水位不符：丢水位、整段历史重发一次（resync）——带着同一个水位重试只会 409 到底。
        g._dsm_warn("服务端 DSM 水位不符(409)→重置 delta 并全量重发一次", on_line)
        dsm.reset_delta((env.get("x") or {}).get("sms.delta_key") or "")
        try:
            env = dsm.build_env(msgs, tools=__import__("agent_dispatch").tools_schema(),
                                model=g.cfg().get("model") or "auto", dsm_cfg=c, mem=mem, resync=True)
        except Exception as e:
            if c.get("fallback"):
                g._dsm_warn("重同步信封构造失败→legacy：" + str(e)[:120], on_line); dsm.mark_broken("sse resync build_env"); return None, str(e)[:150], "legacy"
            return None, str(e)[:150], "err"
        if c.get("schema_ref") and dsm.needs_register(env["sch"]):
            data, err, code, _ct = g._dsm_post(dsm.ENDPOINT_SCHEMA, dsm.schema_frame(env), dsm.CTYPE)
            if code in (404, 415) and c.get("fallback"):
                g._dsm_warn("服务端 DSM schema 路由缺失(%d)→降级 legacy" % code, on_line); dsm.mark_broken("sse resync schema %d" % code); return None, err, "legacy"
            if code == 200:
                dsm.mark_registered(env["sch"])
        data, err, code, ct = g._dsm_post(dsm.ENDPOINT, env, dsm.CTYPE_STREAM if out == "delta" else dsm.CTYPE,
                                         on_frame=_frame if out == "delta" else None)
        if code in (404, 415) and c.get("fallback"):
            g._dsm_warn("服务端未提供 DSM(%d)→降级 legacy" % code, on_line); dsm.mark_broken("sse resync chat %d" % code); return None, err, "legacy"
    if data is None:
        if code == 409 and c.get("fallback"):
            g._dsm_warn("DSM 重同步仍失败(409)→降级 legacy 并冷却", on_line); dsm.mark_broken("sse 409 resync failed"); return None, str(err)[:150], "legacy"
        return None, str(err)[:150], "err"
    resp = dsm.merge_stream(data) if isinstance(data, list) else data   # ndjson 已按 seq 归并成一条信封
    m = dsm.decode_to_openai_shape(resp)
    ch = (m.get("choices") or [{}])[0]; msg = dict(ch.get("message") or {})
    if not seen["n"] and not (msg.get("tool_calls") or []) and not ((msg.get("content") or "") + (msg.get("reasoning_content") or "")).strip():
        # 同 gateway._dsm_chat：200 空信封绝不落到上层变成「空响应」；也不推进水位。
        # seen.n>0 说明已逐帧上过屏（信封非空），不走这条。
        if c.get("fallback"):
            g._dsm_warn("DSM 空信封（200 无正文/无工具调用）→legacy 全量重发一次", on_line)
            return None, "dsm empty envelope → legacy", "legacy"
        g._dsm_warn("DSM 空信封且 dsm.fallback=false→报错不降级", on_line)
        return None, "DSM 空信封（200 无正文·fallback=false）", "err"
    dsm.commit_from_env(env, msgs)
    dsm.clear_broken()
    ul.rec(m.get("usage"), model=m.get("model"), skill=ul.cur_skill())
    msg["content"] = (msg.get("content") or "").replace("\x00", "").replace("\r", "\n")
    if out == "delta":
        # 逐 seq 增量吐字（契约 §4）：每段先进 ◌ reasoning 信封＝今天流式的口径。
        # 已在 _frame 回调里逐帧上屏的（seen.n>0）绝不重放，只把尾部不足一句的残段收尾；
        # 没拿到回调的旧路（整包读）退回按 seq 排序重放——两条路都不丢字也不重字。
        if seen["n"]:
            if pbuf[0]:
                pl(pbuf[0]); pbuf[0] = ""
        else:
            buf = ""
            for e in sorted([x for x in (data or []) if isinstance(x, dict)], key=lambda x: int(x.get("seq") or 0)):
                rs = e.get("reason") or {}
                pl(rs.get("summary") if isinstance(rs, dict) else str(rs))
                if isinstance(e.get("answer"), str): buf = _emit(buf + e["answer"], pl)
            buf and pl(buf)
        msg["printed"] = True
    tcs = msg.get("tool_calls")
    return msg, "finish=" + str(ch.get("finish_reason") or (resp or {}).get("stop") or "stop"), "ok"


def _once(msgs, on_line):
    if dsm.enabled():
        m, note, kind = _dsm_once(msgs, on_line)
        if kind != "legacy": return m, note
    if rf := dsm.legacy_refused(): return None, rf   # openai_compat=false → 拒绝构造 legacy body
    req, tout = _req(msgs); buf = ""; rbuf = ""; acc = ""; racc = ""; tcs = {}; fr = ""; u = {}; maxch = max(1000, int(settings.get("llm_gateway.stream_max_chunks", 20000) or 20000)); pl = lambda s: s.strip() and on_line(_rline(s))
    try:
        with urllib.request.urlopen(req, timeout=tout) as r:
            if "text/event-stream" not in str(r.headers.get("content-type") or ""):
                d0 = json.loads(r.read().decode("utf-8", "replace")); ul.rec(d0.get("usage"), model=d0.get("model"), skill=ul.cur_skill())
                m, note = _msg(d0); rc = m.pop("reasoning_content", "") or ""; rc and on_line(_rline(rc)); return m, note
            for _, raw in zip(range(maxch), r):  # 批12 防卡死：慢速无限吐流按 chunk 上限截停（默认 2 万·正常远达不到·F4 llm_gateway.stream_max_chunks）
                stop.check(); ln = raw.decode("utf-8", "replace").strip()
                if not ln.startswith("data:"): continue
                p = ln[5:].strip()
                if p == "[DONE]": break
                try: d = json.loads(p)
                except Exception: continue
                ch = (d.get("choices") or [{}])[0]; de = ch.get("delta") or {}; fr = ch.get("finish_reason") or fr
                u = d.get("usage") or u  # 批41 F1：上游末帧 usage（有则记，无则不影响）
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
    ul.rec(u, model=str(u.get("model") or ""), skill=ul.cur_skill())
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
