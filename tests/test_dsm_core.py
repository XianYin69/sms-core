#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_dsm_core.py — DSM v1 sms-core 侧接线验收（契约 §6 的 A/B/G/H ＋ DSM 唯一出站通道）。

零网络：DSM 路打桩，绝不打真实提供商；native /chat/completions 出站分支已删除
（统一经 smsocket DSM 协议），「降级」目的地改为显式拒绝＋留痕（红线：绝不静默）。
A＝dsm off → 显式拒绝（不再构造 native body）；B＝dsm on 信封→响应解码→工具循环形状不变；
G＝不变量（顶层泄漏/x 往返/mem 确定性/ROLE 双射/validate 封闭表）；
H＝服务端未装 DSM/空信封/冷却期 → 降级标记后显式拒绝 native 并留 warning（绝不静默）。
"""
import os
import sys
import json

import pytest

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "skill", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import dsm          # noqa: E402
import gateway      # noqa: E402
import gateway_sse  # noqa: E402

CFG = {"enabled": True, "base_url": "http://test.local/v1", "api_key": "sk-SECRET-DO-NOT-LOG",
       "api_key_env": None, "model": "test-model", "max_tokens": 1024, "timeout": 5,
       "temperature": None, "top_p": None, "reasoning_effort": None}
TOOLS = [{"type": "function", "function": {"name": "exec", "description": "run",
           "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}}}}]
MSGS = [{"role": "system", "content": "SYS-PROMPT"}, {"role": "user", "content": "只回一个字：好"}]


def _dsm(**kw):
    c = dict(dsm.DEFAULTS); c.update(kw); return c


class _Set:
    """gateway_sse 的 settings 替身：eff() 回 llm_gateway 段，get() 回默认值（不读真配置）。"""
    @staticmethod
    def eff(sms=None):
        return {"llm_gateway": dict(CFG)}

    @staticmethod
    def get(path, default=None, sms=None):
        return default


@pytest.fixture
def stub(monkeypatch, tmp_path):
    """打桩 cfg/tools/DSM 配置/链目录，并记录两条路各自收到的请求体（零网络）。"""
    box = {"legacy": [], "dsm": [], "warn": [], "chat": None, "schema": ({"ok": 1}, "", 200, dsm.CTYPE)}
    # DSM 降级冷却是进程级闩（真实运行＝一个壳一个进程，正是想要的语义）；
    # 测试之间必须清干净，否则前一个用例触发的降级会把后一个用例直接短路成 legacy。
    dsm.clear_broken()
    monkeypatch.setattr(gateway, "cfg", lambda: dict(CFG))
    monkeypatch.setattr(gateway.ad, "tools_schema", lambda: list(TOOLS))
    monkeypatch.setattr(gateway_sse, "settings", _Set)
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm())
    monkeypatch.setattr(dsm, "chains_dir", lambda: str(tmp_path / "chains"))
    monkeypatch.setattr(dsm, "sms_home", lambda: str(tmp_path))

    def _warn(text, on_line=None):
        box["warn"].append(str(text))
    monkeypatch.setattr(gateway, "_dsm_warn", _warn)

    def _post(path, body, accept=None, on_frame=None):
        (box["dsm"].append((path, body, accept)))
        if path == dsm.ENDPOINT_SCHEMA:
            got = box["schema"]
        else:
            got = box["chat"] if box["chat"] is not None else (_resp_env(), "", 200, dsm.CTYPE)
        # 打桩也模拟「到一帧回调一帧」：尾巴3 的行为差异（首字延迟）只有在这里
        # 真回调才测得出来——否则客户端逐帧上屏与整包缓冲在测试里长得一模一样。
        if on_frame and isinstance(got, list):
            for e in got:
                on_frame(e)
        return got
    monkeypatch.setattr(gateway, "_dsm_post", _post)

    def _legacy(path, body=None):
        box["legacy"].append((path, body))
        return {"choices": [{"message": {"role": "assistant", "content": "好"},
                             "finish_reason": "stop"}], "model": "test-model"}, ""
    monkeypatch.setattr(gateway, "_req", _legacy)
    return box


def _resp_env(tool=False):
    if tool:
        return {"v": 1, "sid": "s", "lane": "t1", "seq": 1, "reason": {"tokens": 9412, "summary": "想想"},
                "answer": [{"name": "exec", "arguments": {"cmd": "ls"}}], "stop": "tool_call",
                "usage": {"in": 467, "out_reason": 9412, "out_answer": 403, "cache_read": 320,
                          "cache_write": 0, "cost": 0.0495, "currency": "USD"}, "egress": "direct"}
    return {"v": 1, "sid": "s", "lane": "t1", "seq": 1, "reason": {"tokens": 5, "summary": "r"},
            "answer": "好", "stop": "end_turn",
            "usage": {"in": 10, "out_reason": 5, "out_answer": 1, "cache_read": 0, "cache_write": 0},
            "egress": "direct"}


# ---------- A) dsm off → 显式拒绝（DSM 是唯一出站通道，native /chat/completions 已删） ----------
def test_A_dsm_off_refuses(monkeypatch, stub):
    """dsm.enabled=false：不再构造 native OpenAI body（legacy 分支已删），显式报错指引启用 DSM。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=False))
    m, note = gateway.chat(MSGS)
    assert m is None, "dsm off 却出了正文（native 分支应已删除）"
    assert "DSM 未启用" in str(note), "拒绝消息未指引启用 DSM：%s" % note
    assert not stub["legacy"] and not stub["dsm"], "dsm off 不应发任何出站请求"


def test_A_sse_dsm_off_refuses(monkeypatch, stub):
    """gateway_sse._once 同口径：dsm off → 显式拒绝，不再构造 native SSE body（_req 已删）。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=False))
    m, note = gateway_sse._once(MSGS, lambda x: None)
    assert m is None and "DSM 未启用" in str(note), "SSE dsm off 未显式拒绝：%s" % note
    assert not stub["legacy"] and not stub["dsm"], "SSE dsm off 不应发任何出站请求"


def test_A_default_switch_is_off():
    """出厂默认＝DSM 关（灰度期安全默认）。注：native /chat/completions 出站分支已删除，
    操作员上线前须 dsm.py on 打开 DSM——DSM 是 sms-core 唯一出站通道（统一经 smsocket）。"""
    c = dsm.DEFAULTS
    assert c["enabled"] is False and c["openai_compat"] is True and c["fallback"] is True and c["out"] == "json"
    import settings
    # 出厂默认层（DEFAULTS）——操作员用 dsm.py on 打开 DSM 是运行期意图，
    # 拿 eff()（含 config.json 覆盖）断言"默认全关"会让测试随操作员状态红，故只看默认层。
    d = (settings.DEFAULTS.get("llm_gateway") or {}).get("dsm")
    assert d and d["enabled"] is False and d["fallback"] is True and d["out"] == "json"


# ---------- B) dsm on → 信封被接受、响应解码成 OpenAI 形状、tool_calls 完好 ----------
def test_B_envelope_path_and_tool_loop_shape(monkeypatch, stub):
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True))
    stub["chat"] = (_resp_env(tool=True), "", 200, dsm.CTYPE)
    m, note = gateway.chat(MSGS)
    assert note == "finish=tool_calls"
    tcs = m.get("tool_calls")
    assert tcs and tcs[0]["function"]["name"] == "exec", "tool_calls 未还原（下游工具循环会直接崩）"
    assert json.loads(tcs[0]["function"]["arguments"]) == {"cmd": "ls"}
    assert m["role"] == "assistant" and "content" in m and "reasoning_content" in m   # run() 依赖的形状
    assert not stub["legacy"], "dsm on 且服务端可用却回退 legacy"
    paths = [p for p, _b, _a in stub["dsm"]]
    assert paths == [dsm.ENDPOINT_SCHEMA, dsm.ENDPOINT], "首帧登记或 chat 端点不符契约 §1"
    env = stub["dsm"][-1][1]
    assert env["v"] == 1 and env["sch"].startswith("sha1:") and dsm.validate(env) == []
    assert env["x"]["sms.model"] == "test-model"


def test_B_content_type_is_dsm_json(monkeypatch, stub):
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True))
    gateway.chat(MSGS)
    assert all(a == dsm.CTYPE for _p, _b, a in stub["dsm"]), "未按契约 §1 声明 application/dsm+json"


def test_B_schema_registered_once_then_only_ref(monkeypatch, stub):
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True))
    gateway.chat(MSGS)
    n1 = len(stub["dsm"])
    gateway.chat(MSGS)
    assert len([p for p, _b, _a in stub["dsm"] if p == dsm.ENDPOINT_SCHEMA]) == 1, "sch 每帧重复登记（应幂等一次）"
    assert len(stub["dsm"]) > n1, "第二帧没发 chat"


def test_B_usage_three_way_ledger_maps_to_openai():
    o = dsm.decode_to_openai_shape(_resp_env(tool=True))["usage"]
    assert o["prompt_tokens"] == 467 and o["completion_tokens"] == 9412 + 403
    assert o["prompt_tokens_details"]["cached_tokens"] == 320          # 现状恒 0 的列，DSM 有值
    assert o["completion_tokens_details"]["reasoning_tokens"] == 9412  # 思考不再混在 completion 里
    assert o["dsm"]["cost"] == 0.0495


def test_B_delta_stream_merges_by_seq(monkeypatch, stub):
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True, out="delta"))
    stub["chat"] = ([{"v": 1, "seq": 2, "answer": "界"}, {"v": 1, "seq": 1, "answer": "世", "reason": {"summary": "想"}},
                     {"v": 1, "seq": 3, "stop": "end_turn", "usage": {"in": 1, "out_answer": 2, "out_reason": 0}}],
                    "", 200, dsm.CTYPE_STREAM)
    m, note = gateway.chat(MSGS)
    # finish 必须是 OpenAI 词表里的 stop（不是 DSM 的 end_turn）——legacy 与 DSM 两条路
    # 对同一个调用方必须给出同一个值，否则「工具循环零改动」是假话。
    assert m["content"] == "世界" and note == "finish=stop", "乱序 seq 未归并/stop 词泄漏"


def test_B_delta_stream_feeds_on_line(monkeypatch, stub):
    """流式路径（gateway_sse）：DSM delta 也照今天把增量喂 on_line，下游零改动。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True, out="delta"))
    stub["chat"] = ([{"v": 1, "seq": 1, "answer": "你好"}, {"v": 1, "seq": 2, "stop": "end_turn",
                      "usage": {"in": 1, "out_answer": 2}}], "", 200, dsm.CTYPE_STREAM)
    lines = []
    m, note, kind = gateway_sse._dsm_once(MSGS, lines.append)
    assert kind == "ok"
    assert m["content"] == "你好" and note.startswith("finish=")
    assert any("你好" in x for x in lines), "delta 未吐给 on_line（主屏会空）"


def test_B_delta_dsm_off_refuses(monkeypatch, stub):
    """dsm off：_once 显式拒绝（native SSE 已删）；_dsm_once 绝不被调用。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=False))
    called = []
    monkeypatch.setattr(gateway_sse, "_dsm_once", lambda *a, **k: called.append(1))
    m, note = gateway_sse._once(MSGS, lambda x: None)
    assert m is None and "DSM 未启用" in str(note), "dsm off 未显式拒绝：%s" % note
    assert not called, "dsm off 却进了信封路径"


# ---------- G) 不变量（泄漏 / 往返 / 确定性 / 双射 / 封闭表） ----------
def test_G_leak_check_empty_for_all_egresses(tmp_path):
    store = dsm.SchemaStore(path=str(tmp_path / "s.json"))
    env = {"v": 1, "sid": "s", "cid": "c", "lane": "t1", "dep": ["t0"], "sch": store.put("SYS", TOOLS),
           "d": [[1, "hi"]], "out": "json", "bill": {"to": "skill:x"}, "lat": {"ttft_ms": 1},
           "fan": {"n": 2}, "verify": [], "x": {"a.b": 1}}
    for body in (dsm.to_openai(env, store, "M"), dsm.to_anthropic(env, store, "M"), dsm.to_responses(env, store, "M")):
        assert dsm.leak_check(env, body) == [], "策略键泄漏到出网顶层"


def test_G_x_keys_survive_roundtrip(tmp_path):
    store = dsm.SchemaStore(path=str(tmp_path / "s.json"))
    env = {"v": 1, "sch": store.put("SYS", TOOLS), "d": [[1, "hi"]], "x": {"future.key": "keepme"}}
    assert env["x"]["future.key"] == "keepme" and dsm.validate(env) == []
    assert dsm.to_openai(env, store, "M")["model"] == "M"


def test_G_mem_order_and_dup_are_byte_identical(tmp_path):
    d = tmp_path / "chains"
    for fid, txt in (("aaaaaaaaaa", "甲"), ("bbbbbbbbbb", "乙"), ("cccccccccc", "丙")):
        os.makedirs(d / "memory", exist_ok=True)
        json.dump({"id": fid, "chain": "memory", "freq": 3, "text": txt},
                  open(d / "memory" / (fid + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
    old = dsm.chains_dir
    dsm.chains_dir = lambda: str(d)
    try:
        ids = ["aaaaaaaaaa", "bbbbbbbbbb", "cccccccccc"]
        b1 = dsm.canon_mem(ids).encode("utf-8")
        b2 = dsm.canon_mem(list(reversed(ids))).encode("utf-8")
        b3 = dsm.canon_mem(ids + ["aaaaaaaaaa"]).encode("utf-8")
        assert b1 == b2 == b3 and b1, "乱序/重复引用物化字节不同 → 前缀不可缓存"
    finally:
        dsm.chains_dir = old


def test_G_cross_session_id_is_rejected(tmp_path):
    d = tmp_path / "chains" / "tool_call"
    os.makedirs(d, exist_ok=True)
    json.dump({"id": "deadbeef01", "chain": "tool_call", "freq": 1, "text": "别的会话",
               "edges": [["sess-OTHER", "member", 1]]},
              open(d / "deadbeef01.json", "w", encoding="utf-8"), ensure_ascii=False)
    old = dsm.chains_dir
    dsm.chains_dir = lambda: str(tmp_path / "chains")
    try:
        assert dsm.canon_mem(["deadbeef01"], sid="sess-MINE") == "", "跨会话 id 被物化（红线 17 污染）"
        assert dsm.canon_mem(["deadbeef01"], sid="sess-OTHER") != "", "本会话 id 反而被拒"
    finally:
        dsm.chains_dir = old


def test_G_role_bijection_and_positional_bounds():
    assert [dsm.ROLE[dsm.RID[n]] for n in dsm.ROLE] == dsm.ROLE
    assert dsm.RID["constraint"] == 4 and dsm.RID["note"] == 5
    assert dsm.validate({"v": 1, "sch": "sha1:" + "0" * 12, "d": [[9, "x"]]}) != []


def test_G_validate_rejects_unknown_top_key(tmp_path):
    env = {"v": 1, "sch": dsm.fingerprint("s", []), "d": [[1, "x"]], "self": 1}
    assert any("未知顶层键" in e for e in dsm.validate(env))
    assert any("sch" in e for e in dsm.validate({"v": 1, "sch": "sha1:ZZZ", "d": []}))


def test_G_turn_positional_roundtrip_keeps_tool_calls():
    m = {"role": "assistant", "content": "", "tool_calls": [{"id": "x1", "type": "function",
                                                             "function": {"name": "exec", "arguments": "{\"cmd\":\"ls\"}"}}]}
    rid, txt = dsm.encode_turn(m)
    back = dsm.decode_turn(rid, txt)
    assert back["tool_calls"][0]["function"]["arguments"] == "{\"cmd\":\"ls\"}" and back["role"] == "assistant"
    t = {"role": "tool", "content": "结果", "tool_call_id": "x1"}
    assert dsm.decode_turn(*dsm.encode_turn(t))["tool_call_id"] == "x1"
    with pytest.raises(dsm.Unsupported):
        dsm.encode_turn({"role": "user", "content": [{"type": "text", "text": "多模态"}]})


def test_G_split_fan_dep_gate(tmp_path):
    env = {"v": 1, "sch": dsm.fingerprint("s", []), "d": [[1, "x"]], "lane": "t4", "dep": ["t1", "t2"],
           "fan": {"n": 3, "lane_ids": ["t4a", "t4b", "t4c"], "merge": "vote", "concurrency": 3}}
    f = dsm.split_fan(env, [])
    assert f["dispatchable"] is False and f["ready"] == [] and len(f["requests"]) == 3
    g = dsm.split_fan(env, ["t1", "t2"])
    assert g["dispatchable"] is True and g["ready"] == ["t4a", "t4b", "t4c"] and g["concurrency"] == 3
    assert all(r["lane"].startswith("t4") and "fan" not in r for r in g["requests"])


def test_G_no_api_key_in_envelope_or_egress(tmp_path):
    """密钥永不进信封、进出网 body、进任何新日志字段（硬约束）。"""
    store = dsm.SchemaStore(path=str(tmp_path / "s.json"))
    env = dsm.build_env(MSGS, tools=TOOLS, model="M", dsm_cfg=_dsm(), store=store, sms=str(tmp_path), resync=True)
    blob = json.dumps(env, ensure_ascii=False) + json.dumps(dsm.to_openai(env, store, "M"), ensure_ascii=False)
    assert "sk-SECRET-DO-NOT-LOG" not in blob and "api_key" not in blob


# ---------- H) 降级：服务端未装 DSM / 空信封 / 冷却期 → 不再回 native，显式报错＋留痕（绝不静默） ----------
@pytest.mark.parametrize("code", [404, 415])
def test_H_degraded_dsm_refuses_loudly(monkeypatch, stub, code):
    """_dsm_chat 回 kind=legacy（DSM 降级）时，chat() 不再构造 native body（已删），
    返回 (None, 显式消息) 并留一条 warning——红线「绝不静默」仍在，只是目的地变了。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True, fallback=True))
    stub["chat"] = (None, "HTTP %d no dsm route" % code, code, "")
    m, note = gateway.chat(MSGS)
    assert m is None, "DSM 降级后不应再有正文（native 分支已删）：%r" % m
    assert "统一经 smsocket" in str(note) or "smsocket" in str(note), \
        "降级消息应显式指向 smsocket DSM 协议：%s" % note
    assert not stub["legacy"], "DSM 降级却仍发了 native 请求（分支应已删除）"
    assert stub["warn"], "降级必须留痕（红线：绝不静默）"


def test_H_downgrade_when_schema_route_missing(monkeypatch, stub):
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True, fallback=True))
    stub["schema"] = (None, "HTTP 404", 404, "")
    m, note = gateway.chat(MSGS)
    assert m is None, "schema 路由缺失（降级）后不应再有正文（native 已删）：%r" % m
    assert not stub["legacy"] and stub["warn"], "schema 首帧 404 降级未告警/误发 native"
    assert not [p for p, _b, _a in stub["dsm"] if p == dsm.ENDPOINT], "已降级却仍继续发信封 chat"


def test_H_no_downgrade_when_fallback_false(monkeypatch, stub):
    """fallback=false → 报错不降级（openai_compat 与 fallback 是两个独立开关，不得互相兜底）。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True, fallback=False))
    stub["chat"] = (None, "HTTP 404", 404, "")
    m, note = gateway.chat(MSGS)
    assert m is None and stub["legacy"] == [] and stub["warn"], "fallback=false 却静默降级了"


# ---------- B4) 200 空信封绝不变成「空响应」（2026-10-06 用户报障：换 DSM 返回空响应） ----------
def test_B4_empty_envelope_refuses_loudly(monkeypatch, stub):
    """服务端回 200 但信封里没有正文/没有工具调用（上游只吐 reasoning 就被截断，
    或 _dsm_stream 收口帧 answer=""）——旧行为是把空 message 交给 gateway.run，
    于是用户看到「空响应（上游 200 无正文·多为并发过载）」。新行为：_dsm_chat 回 legacy 标记，
    chat() 显式拒绝（native 分支已删）＋留痕，绝不把空 message 交上去、也绝不重发 native。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True, fallback=True))
    stub["chat"] = ({"v": 1, "seq": 1, "stop": "end_turn", "answer": "",
                     "reason": {"tokens": 0, "summary": ""}}, "", 200, dsm.CTYPE)
    m, note = gateway.chat(MSGS)
    assert m is None, "空信封不应出正文（旧 native 重发已删）：%r / %s" % (m, note)
    assert not stub["legacy"], "空信封后误发 native 请求"
    assert stub["warn"], "降级必须留痕（契约：绝不静默）"
    assert "空信封" in "".join(stub["warn"])


def test_B4_empty_envelope_does_not_advance_watermark(monkeypatch, stub):
    """空轮次不得推进水位：否则下一轮 delta 少发一段历史，服务端 materialize 出残缺 body。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True, fallback=True))
    stub["chat"] = ({"v": 1, "seq": 1, "stop": "end_turn", "answer": "",
                     "reason": {"tokens": 0, "summary": ""}}, "", 200, dsm.CTYPE)
    msgs = [{"role": "system", "content": "S"}, {"role": "user", "content": "第一轮"}]
    m1, _n1 = gateway.chat(msgs)
    assert m1 is None, "空信封不应出正文（native 已删）"
    stub["chat"] = None                      # 这一轮恢复正常
    m2, _n2 = gateway.chat(msgs + [{"role": "assistant", "content": "答"}, {"role": "user", "content": "第二轮"}])
    env = stub["dsm"][-1][1]
    assert [t[1] for t in env["d"]][0] == "第一轮", \
        "空轮次被写进了水位：%s" % env["d"]
    assert m2 is not None, "恢复正常轮后应出正文"


def test_B4_empty_envelope_no_fallback_is_error_not_empty(monkeypatch, stub):
    """fallback=false：空信封＝报错（kind=err），绝不返回一个空 message 冒充成功。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True, fallback=False))
    stub["chat"] = ({"v": 1, "seq": 1, "stop": "end_turn", "answer": ""}, "", 200, dsm.CTYPE)
    m, note, kind = gateway._dsm_chat(MSGS)
    assert m is None and kind == "err" and "空信封" in str(note)
    assert stub["legacy"] == [], "fallback=false 不得偷发 native（native 分支已删，契约 §2 loud error）"


def test_B4_stream_empty_envelope_refuses(monkeypatch, stub):
    """流式路同义：out=json 且整包为空 → _dsm_once 回 legacy 标记，_once 显式拒绝（不再发 native）。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True, out="json", fallback=True))
    lines = []
    stub["chat"] = ({"v": 1, "seq": 1, "stop": "end_turn", "answer": "",
                     "reason": {"tokens": 0, "summary": ""}}, "", 200, dsm.CTYPE)
    m, note, kind = gateway_sse._dsm_once(MSGS, lines.append)
    assert kind == "legacy" and not lines, "流式空信封未回 legacy 标记：%s %s" % (kind, lines)
    m2, note2 = gateway_sse._once(MSGS, lines.append)
    assert m2 is None, "流式空信封经 _once 不应出正文（native 已删）：%r" % m2


def test_B4_partial_delta_is_not_treated_as_empty(monkeypatch, stub):
    """反向保护：逐帧已上屏（seen.n>0）就不算空信封——哪怕收口帧 answer=""。
    否则尾巴3 的真逐字流会被这条新守卫误杀成 legacy。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True, out="delta", fallback=True))
    frames = [{"v": 1, "seq": 1, "answer": "好"},
              {"v": 1, "seq": 2, "answer": "", "stop": "end_turn"}]

    def _post(path, body, accept=None, on_frame=None):
        if path != dsm.ENDPOINT:
            return ({"ok": 1}, "", 200, dsm.CTYPE)
        if on_frame:
            for e in frames:
                on_frame(e)
        return frames, "", 200, dsm.CTYPE_STREAM
    monkeypatch.setattr(gateway, "_dsm_post", _post)
    lines = []
    m, note, kind = gateway_sse._dsm_once(MSGS, lines.append)
    assert kind == "ok", "逐帧有字却被判空：%s" % note
    assert m["content"] == "好" and not stub["legacy"]


def test_H_openai_compat_false_refuses_loudly(monkeypatch, stub):
    """openai_compat=false → 客户端拒绝构造 legacy body 并报错（契约 §2·绝不静默降级）。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=False, openai_compat=False))
    m, note = gateway.chat(MSGS)
    assert m is None and "openai_compat" in str(note) and stub["legacy"] == []


# ---------- H2) 409 自愈：重置水位→全量重发一次→仍失败才降级并冷却 ----------
def test_H_409_resyncs_once_then_ok(monkeypatch, stub):
    """服务端水位不符（409）不得把同一水位再发一遍——必须 reset＋全量 resync。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True, fallback=True))
    gateway.chat(MSGS)                                   # 先成功一轮，把水位推到 1
    seen = []

    def _post(path, body, accept=None):
        if path == dsm.ENDPOINT_SCHEMA:
            return ({"ok": 1}, "", 200, dsm.CTYPE)
        seen.append((body["x"].get("sms.delta_from"), len(body["d"])))
        if len(seen) == 1:
            return None, "HTTP 409 state mismatch", 409, ""
        return _resp_env(), "", 200, dsm.CTYPE
    monkeypatch.setattr(gateway, "_dsm_post", _post)
    m, note = gateway.chat(MSGS + [{"role": "assistant", "content": "a"},
                                   {"role": "user", "content": "q2"}])
    assert (m or {}).get("content") == "好", "409 后没自愈成功"
    assert seen[0] == (1, 2), "第二轮本应发增量 (1,2)：%s" % (seen[0],)
    assert seen[1] == (0, 3), "409 后必须全量重发 (0,3)：%s" % (seen[1],)
    assert not dsm.broken(), "自愈成功必须清掉冷却"


def test_H_409_persistent_refuses_and_latches(monkeypatch, stub):
    """反复 409 → 一次重发后降级（_dsm_chat 回 legacy 标记），chat() 显式拒绝 native（已删）＋记冷却。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True, fallback=True))
    stub["chat"] = (None, "HTTP 409 state mismatch", 409, "")
    m, note = gateway.chat(MSGS)
    assert m is None, "409 耗尽降级后不应再有正文（native 已删）：%r" % m
    chats = [p for p, _b, _a in stub["dsm"] if p == dsm.ENDPOINT]
    assert len(chats) == 2, "应恰好重试一次：%d" % len(chats)
    assert dsm.broken(), "持续 409 必须记冷却"
    assert not stub["legacy"] and stub["warn"], "降级应显式拒绝 native 并留痕"


def test_H_cooldown_short_circuits_envelope(monkeypatch, stub):
    """冷却期内不再试信封：_dsm_chat 直接回 legacy 标记，chat() 显式拒绝 native（已删），0 次 DSM 往返。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True, fallback=True))
    dsm.mark_broken("unit test")
    m, note = gateway.chat(MSGS)
    assert m is None, "冷却期内不应再有正文（native 已删）：%r" % m
    assert not stub["dsm"], "冷却期内仍发了信封请求：%s" % stub["dsm"]
    assert not stub["legacy"], "冷却降级后误发 native"
    assert "降级" in str(note), "降级消息应指出 DSM 降级原因：%s" % note


def test_H_422_does_not_latch(monkeypatch, stub):
    """422 是「我们的信封不合法」，不是「服务端没装 DSM」——不得被冷却掩盖。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True, fallback=True))
    stub["chat"] = (None, "HTTP 422 invalid envelope", 422, "")
    m, note = gateway.chat(MSGS)
    assert m is None and not stub["legacy"], "422 不该降级 legacy"
    assert not dsm.broken(), "422 记冷却会把自身缺陷藏 120 秒"


def test_H_404_downgrade_refuses_and_latches(monkeypatch, stub):
    """服务端无 DSM 路由 → 降级标记后 chat() 显式拒绝 native（已删）＋记冷却（修好前别再反复试）。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True, fallback=True))
    stub["chat"] = (None, "HTTP 404", 404, "")
    m, note = gateway.chat(MSGS)
    assert m is None and dsm.broken(), "404 降级应拒绝 native 并记冷却：%r" % m
    assert not stub["legacy"], "404 降级后误发 native 请求"


def test_H_switch_flip_clears_latch(monkeypatch, stub):
    """操作员显式开关＝意图表达：必须立刻清冷却，不再白等 120 秒。"""
    written = {}
    monkeypatch.setattr(dsm.settings, "set", lambda path, val, sms=None: written.update({path: val}))
    monkeypatch.setattr(dsm.resolve_home, "conf", lambda sms=None: {"llm_gateway": {}})
    dsm.mark_broken("unit test")
    assert dsm.broken()
    dsm.set_enabled(True)
    assert not dsm.broken(), "开关翻转后冷却未清"
    assert written.get("llm_gateway.dsm", {}).get("enabled") is True


def test_H_build_env_failure_refuses_loudly(monkeypatch, stub):
    """信封装不下（多模态）→ _dsm_chat 回 legacy 标记，chat() 显式拒绝 native（已删）＋留痕，不静默。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True))
    msgs = [{"role": "system", "content": "S"},
            {"role": "user", "content": [{"type": "text", "text": "看这张图"}, {"type": "image_url", "image_url": {"url": "data:,"}}]}]
    m, note = gateway.chat(msgs)
    assert m is None, "多模态装不下信封时不应出正文（native 已删）：%r" % m
    assert not stub["legacy"] and stub["warn"], "降级应显式拒绝 native 并留痕"


def test_H_delta_watermark_only_new_turns(monkeypatch, stub):
    """d 只带新增轮次：同 sid/cid/lane 第二帧不得重发历史；请求失败不得推进水位。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True))
    msgs = [{"role": "system", "content": "S"}, {"role": "user", "content": "第一轮"}]
    gateway.chat(msgs)
    env1 = stub["dsm"][-1][1]
    assert len(env1["d"]) == 1
    msgs2 = msgs + [{"role": "assistant", "content": "答"}, {"role": "user", "content": "第二轮"}]
    gateway.chat(msgs2)
    env2 = stub["dsm"][-1][1]
    assert [t[1] for t in env2["d"]] == ["答", "第二轮"], "delta 水位失效：重发了历史 %s" % env2["d"]


def test_H_watermark_resyncs_when_history_shrinks(monkeypatch, stub):
    """历史被压缩/净化（前缀哈希不符）→ 全量重同步，绝不错发半截历史。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True))
    gateway.chat([{"role": "system", "content": "S"}, {"role": "user", "content": "A"}])
    m = stub["dsm"][-1][1]
    gateway.chat([{"role": "system", "content": "S"}, {"role": "user", "content": "完全不同的历史"}])
    assert stub["dsm"][-1][1]["d"][0][1] == "完全不同的历史", "前缀不符却没全量重同步"
    assert m["x"]["sms.delta_key"] == stub["dsm"][-1][1]["x"]["sms.delta_key"]


def test_H_cli_status_matrix_selftest_run():
    """CLI 三条命令必须真能跑（status 打印生效模式＋字节对比；matrix 打印真值表）。"""
    assert dsm.cli_matrix() == 0
    assert dsm.cli_selftest() == 0
    out = dsm.measure([{"role": "system", "content": "S"}, {"role": "user", "content": "hi"}], TOOLS, "M")
    assert out["legacy_bytes"] > 0 and out["envelope_bytes"] > 0


# ---------- 开关写入口：经 settings setter 最小写入（不钉默认值·不手改 JSON） ----------
def test_switch_setter_writes_only_enabled(tmp_path, monkeypatch):
    import chains
    monkeypatch.setattr(chains, "record", lambda *a, **k: None)   # 探针不往真实 event 链写垃圾
    sms = str(tmp_path)
    os.makedirs(os.path.join(sms, "config"), exist_ok=True)
    json.dump({"llm_gateway": {"model": "M", "dsm": {"out": "delta"}}},
              open(os.path.join(sms, "config", "config.json"), "w", encoding="utf-8"), ensure_ascii=False)
    dsm.set_enabled(True, sms=sms)
    raw = json.load(open(os.path.join(sms, "config", "config.json"), encoding="utf-8"))["llm_gateway"]["dsm"]
    assert raw == {"out": "delta", "enabled": True}, "把整份默认值钉进了用户配置（默认值今后改不动）"
    dsm.set_enabled(False, sms=sms)
    raw2 = json.load(open(os.path.join(sms, "config", "config.json"), encoding="utf-8"))["llm_gateway"]["dsm"]
    assert raw2["enabled"] is False, "False 被当成 None 而 pop 掉整块"
    assert "api_key" not in json.dumps(raw2)


def test_B_delta_emits_each_seq_in_order(monkeypatch, stub):
    """乱序到达的 seq 必须按序吐给 on_line（不是把合并后的整段重新切块）。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True, out="delta"))
    stub["chat"] = ([{"v": 1, "seq": 3, "answer": "C\n"}, {"v": 1, "seq": 1, "answer": "A\n",
                      "reason": {"summary": "R1"}}, {"v": 1, "seq": 2, "answer": "B\n"}], "", 200, dsm.CTYPE_STREAM)
    lines = []
    m, note, kind = gateway_sse._dsm_once(MSGS, lines.append)
    assert kind == "ok" and m["content"] == "A\nB\nC\n"
    got = "".join(lines)                       # 每行带 ◌ reasoning 信封前缀
    assert got.index("R1") < got.index("A") < got.index("B") < got.index("C"), "增量未按 seq 顺序吐字"
    assert len([x for x in lines if x.strip()]) == 4, "吐字次数不等于 seq 数（%s）" % lines
    assert all("A" not in x or "B" not in x for x in lines), "整段重切＝不是逐 seq 吐字"


def test_B_json_mode_keeps_reasoning_content(monkeypatch, stub):
    """out=json：reason.summary 必须留在 reasoning_content（run() 靠它走 ◌ 信封，不进主屏）。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True, out="json"))
    stub["chat"] = (_resp_env(), "", 200, dsm.CTYPE)
    m, note = gateway.chat(MSGS)
    assert m["reasoning_content"] == "r" and m["content"] == "好"

# ---------- stop→finish_reason 词表（契约 §4：DSM 停止词绝不进 OpenAI 槽位） ----------
def test_stop_vocabulary_maps_to_openai_finish_reason():
    cases = {"end_turn": "stop", "stop": "stop", "tool_call": "tool_calls",
             "length": "length", "max_tokens": "length", "content_filter": "content_filter",
             "": "stop", "some_future_word": "stop"}
    for stop, want in cases.items():
        env = {"v": 1, "seq": 1, "answer": "ok", "stop": stop,
               "usage": {"in": 1, "out_answer": 1, "out_reason": 0}}
        o = dsm.decode_to_openai_shape(env)
        got = o["choices"][0]["finish_reason"]
        assert got == want, "stop=%r 应映射为 %r，实得 %r" % (stop, want, got)
        assert got in ("stop", "length", "tool_calls", "content_filter"), \
            "finish_reason 越出 OpenAI 词表"
        assert o["dsm"]["stop"] == stop, "原始 stop 必须留在 dsm 段供归因"
    tool = {"v": 1, "seq": 1, "stop": "tool_call", "answer": [{"name": "exec",
            "arguments": {"cmd": "ls"}}], "usage": {"in": 1, "out_answer": 1}}
    o = dsm.decode_to_openai_shape(tool)
    assert o["choices"][0]["finish_reason"] == "tool_calls"
    assert o["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "exec"

# ---------- I) DSM 端点 URL 归一：base_url 已含 /v1 时绝不拼出 /v1/v1/dsm/* ----------
def test_I_dsm_url_normalization(monkeypatch):
    """DSM 端点常量自带 /v1 前缀，而 llm_gateway.base_url 通常已含 /v1——
    直接相加得到 /v1/v1/dsm/*，服务端 404，客户端据此每次降级 legacy，
    DSM 永远用不上（2026-10-06 实测根因）。_dsm_url 负责归一。"""
    import gateway as g
    for base in ("http://127.0.0.1:8011/v1", "http://127.0.0.1:8011/v1/", "http://127.0.0.1:8011/"):
        monkeypatch.setattr(g, "cfg", lambda b=base: {"base_url": b})
        assert g._dsm_url("/v1/dsm/chat") == "http://127.0.0.1:8011/v1/dsm/chat", base
        assert g._dsm_url("/v1/dsm/schema") == "http://127.0.0.1:8011/v1/dsm/schema", base
    # base 不含 /v1（如网关挂在根）→ 前缀原样保留
    monkeypatch.setattr(g, "cfg", lambda: {"base_url": "http://h:1"})
    assert g._dsm_url("/v1/dsm/chat") == "http://h:1/v1/dsm/chat"


# ---------- I2) 尾巴2 结构性根治：api_url 是唯一拼接口，/v1 绝不重复 ----------
def test_I2_api_url_invariant_all_base_shapes():
    """不变量＝最终 URL 里 '/v1' 至多出现一次，且 legacy 与 DSM 两类 path 都对：
    base 含 /v1（结尾或代理中段）、base 不含 /v1、带/不带尾斜杠，都得同一个正确结果。"""
    import dsm as D
    cases = [
        ("http://127.0.0.1:8011/v1", "http://127.0.0.1:8011"),
        ("http://127.0.0.1:8011/v1/", "http://127.0.0.1:8011"),
        ("http://127.0.0.1:8011", "http://127.0.0.1:8011"),
        ("http://127.0.0.1:8011/", "http://127.0.0.1:8011"),
        ("https://proxy.example/api/v1", "https://proxy.example/api"),
    ]
    for base, root in cases:
        for path, want in ((D.ENDPOINT, "/v1/dsm/chat"), (D.ENDPOINT_SCHEMA, "/v1/dsm/schema"),
                           ("/chat/completions", "/v1/chat/completions"), ("/models", "/v1/models")):
            u = D.api_url(path, base)
            assert u == root + want, (base, path, u)
            assert u.count("/v1") == 1, ("尾巴2 复发：/v1 重复", base, path, u)


def test_I2_gateway_dsm_url_delegates(monkeypatch):
    """_dsm_url 只是 dsm.api_url 的薄封装——调用点不可能再各写一套拼接。"""
    import gateway as g
    monkeypatch.setattr(g, "cfg", lambda: {"base_url": "http://127.0.0.1:8011/v1"})
    assert g._dsm_url("/v1/dsm/chat") == "http://127.0.0.1:8011/v1/dsm/chat"
    monkeypatch.setattr(g, "cfg", lambda: {"base_url": "http://gw.local/api/v1"})
    assert g._dsm_url("/v1/dsm/schema") == "http://gw.local/api/v1/dsm/schema"


def test_I2_no_hand_rolled_join_left():
    """静态守卫：scripts 目录里不得再出现 base_url + 裸拼路径（尾巴2 的防回归网）。

    唯一合法形式＝dsm.api_url(path, base) 或经 _dsm_url；这条测试是为了让「下一处手写
    拼接」在评审阶段就红，而不是等到线上 404 锁死降级才发现。
    """
    import glob as G
    import os as O
    import re
    scripts = O.path.abspath(O.path.join(O.path.dirname(__file__), "..", "skill", "scripts"))
    bad = re.compile(r"""base_url["']?\s*(?:,\s*""|\"\s*\)\s*)?.{0,40}?\.rstrip\(["']/["']\)\s*\+\s*["']/(?:chat|models|dsm)""")
    hits = []
    for f in G.glob(O.path.join(scripts, "*.py")):
        if O.path.basename(f) == "dsm.py":      # api_url 自己那处不算（它就是唯一拼接口）
            continue
        for i, l in enumerate(open(f, encoding="utf-8", errors="replace")):
            if "api_url" in l:
                continue
            if bad.search(l) or re.search(r"""get\(["']base_url["'].*rstrip\(.*\+""", l):
                hits.append("%s:%d %s" % (O.path.basename(f), i + 1, l.strip()[:110]))
    assert not hits, "仍有手写 URL 拼接（应走 dsm.api_url）：\n" + "\n".join(hits)

# ---------- B5) 收口帧的 tool_calls 数组必须胜出（merge_stream 不再吞掉工具调用） ----------
def test_B5_delta_final_frame_tool_calls_survive_merge(monkeypatch, stub):
    """服务端正文按 seq 先吐完、末帧才带 tool_calls。旧 merge_stream「非空字符串时丢弃
    数组」＝ delta 模式下工具循环整条断掉。归并后必须还原出 tool_calls＋finish=tool_calls。
    """
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True, out="delta"))
    stub["chat"] = ([{"v": 1, "seq": 1, "answer": "先看"},
                     {"v": 1, "seq": 2, "reason": {"tokens": 3, "summary": "想想"}},
                     {"v": 1, "seq": 3, "stop": "tool_call", "answer": [
                         {"id": "call_A", "type": "function",
                          "function": {"name": "exec", "arguments": "{\"cmd\":\"ls\"}"}}],
                      "usage": {"in": 10, "out_reason": 3, "out_answer": 2}}],
                    "", 200, dsm.CTYPE_STREAM)
    m, note, kind = gateway._dsm_chat(MSGS)
    assert kind == "ok", note
    tcs = m.get("tool_calls")
    assert tcs and tcs[0]["function"]["name"] == "exec", ("delta 归并吞掉 tool_calls", m)
    assert json.loads(tcs[0]["function"]["arguments"]) == {"cmd": "ls"}
    assert note == "finish=tool_calls", note
    assert m.get("reasoning_content") == "想想", ("reason 增量未归并", m)


# ---------- B3) 尾巴3 硬证：delta 必须「到一帧画一帧」，不是收口时一次性刷 ----------
def test_B3_delta_paints_per_frame_during_stream(monkeypatch, stub):
    """out=json 的老毛病＝整包读完才出字。这里把 _dsm_post 换成「逐帧回调」的真流替身，
    每帧回调后记一次 on_line 计数：首帧就该有字上屏（首字延迟与 legacy SSE 同级），
    且计数随帧增长。正文必须够长（>88 字＋句读）才会在帧内被 _emit 切出多段——
    5 字短答案只会在收口时刷一次，测不出增量（2026-10-06 实链冒烟踩过的坑）。"""
    monkeypatch.setattr(dsm, "cfg", lambda sms=None: _dsm(enabled=True, out="delta"))
    f1 = "甲" * 40 + "。" + "乙" * 40 + "。"
    f2 = "丙" * 40 + "。"
    frames = [{"v": 1, "seq": 1, "answer": f1},
              {"v": 1, "seq": 2, "answer": f2},
              {"v": 1, "seq": 3, "answer": "收尾", "stop": "end_turn"}]

    lines, timeline = [], []

    def _post(path, body, accept=None, on_frame=None):
        if path != dsm.ENDPOINT:   # schema 注册帧＝非流式，本就没有 on_frame
            return {"v": 1, "ok": True}, "", 200, dsm.CTYPE
        assert on_frame is not None, "delta 模式没传 on_frame＝客户端仍整包缓冲"
        for e in frames:
            on_frame(e)
            timeline.append(len(lines))     # 帧间计数＝证明「边到边画」而非末尾一次刷
        return frames, "", 200, dsm.CTYPE_STREAM
    monkeypatch.setattr(gateway, "_dsm_post", _post)

    m, note, kind = gateway_sse._dsm_once(MSGS, lines.append)
    assert kind == "ok", note
    assert timeline[0] >= 2, ("首帧到达时没立刻上屏 %s＝尾巴3 未修" % timeline)
    assert timeline == [2, 3, 3], ("未按帧增量上屏 %s" % timeline)
    assert lines[-1].endswith("收尾"), ("尾部不足一句的残段没收尾 %r" % lines[-1])
    joined = "".join(lines)
    assert joined.count("甲" * 40) == 1 and joined.count("丙" * 40) == 1, "逐帧上屏后重放＝丢字或重字"
    assert m["content"] == f1 + f2 + "收尾" and m.get("printed") is True
