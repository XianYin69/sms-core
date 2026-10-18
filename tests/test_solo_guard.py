#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_solo_guard.py — SOLO 授权链与容错回归（批34 根治三项·批36 统一 DSM 单发）。

覆盖：
1. 密钥口径：api_key_env 指向的环境变量**存在但为空**时不得覆盖 config 里的密钥（旧写法
   os.environ.get(k, 默认) 只挡「不存在」，空串照样取用 → "Bearer " → 网关 401，SOLO 自审全线哑火）。
2. 失败留痕诚实性：不可重试的 4xx（401/404/405）不得被记成「提供商访问失败重试」（查链误判风暴）。
3. 审核器容错：回复被截断时抢救判定位（grant/decision），缺判定位仍保守拒绝；网关连续失败进冷却窗，
   窗内不再重复发必然失败的请求（旧行为＝每次权限判定都白烧一次调用）。
SOLO 自审/故障分析出站统一经 gateway._single_shot（DSM 单发·native /chat/completions 已删），
测试全部离线（monkeypatch _single_shot），不依赖网关在线。跑法：pytest tests -q。
"""
import io
import json
import os
import sys
import urllib.error

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "skill", "scripts")
sys.path.insert(0, S)
import gateway  # noqa: E402
import solo  # noqa: E402


def _http_error(code=401):
    body = b'{"detail":{"error":{"message":"invalid api key","type":"authentication_error"}}}'
    return urllib.error.HTTPError("http://127.0.0.1:8011/v1/chat/completions", code,
                                  "Unauthorized", {}, io.BytesIO(body))


# ---------- 1) key source: empty env must not shadow config key ----------
def test_empty_env_does_not_shadow_config_key(monkeypatch):
    import resolve_home
    conf = json.load(io.open(os.path.join(resolve_home.ensure(), "config", "config.json"), encoding="utf-8"))
    base = conf.get("llm_gateway") or {}
    env_name = base.get("api_key_env")
    cfg_key = base.get("api_key") or ""
    if not env_name or not cfg_key:
        pytest.skip("配置未同时给 api_key_env 与 api_key，密钥兜底路径不适用")
    monkeypatch.setenv(env_name, "")          # 存在但为空＝旧实现的中毒态
    c = gateway.cfg()
    assert c.get("api_key") == cfg_key, "空环境变量覆盖了配置密钥（401 根因复现）"
    assert c.get("key_source") == "config", c.get("key_source")
    assert solo._env_empty() is True, "doctor 必须看得见「env 空」这个信号"
    monkeypatch.setenv(env_name, cfg_key)
    assert gateway.cfg().get("key_source") == "env"


# ---------- 2) non-retryable 4xx must not be logged as a retry ----------
def test_nonretryable_4xx_leaves_no_retry_trace(monkeypatch):
    logs = []
    monkeypatch.setattr(gateway.chains, "log",
                        lambda *a, **k: logs.append(str(a[1] if len(a) > 1 else a)))

    def fake_open(*a, **k):
        raise _http_error(401)

    monkeypatch.setattr(gateway.urllib.request, "urlopen", fake_open)
    req = gateway.urllib.request.Request("http://127.0.0.1:8011/v1/chat/completions", data=b"{}")
    data, err = gateway._send(req)
    assert data is None and "401" in str(err)
    assert not [x for x in logs if "重试" in x], "不可重试的 401 被记成重试：%s" % logs


# ---------- 3) salvage of truncated reviewer replies ----------
TRUNC_TRUE = '{"grant": true, "ttl_min": 3, "reason": "用户明确要求修 SOLO，最小'
CLEAN_FALSE = '前置话 {"grant": false, "ttl_min": 0, "reason": "越权"} 尾巴'
FENCE_DECISION = '```json\n{"decision": "fix", "reason": "密钥为空"}\n```'


@pytest.mark.parametrize("txt,key,val", [
    (TRUNC_TRUE, "grant", True),
    (TRUNC_TRUE, "ttl_min", 3),
    (CLEAN_FALSE, "grant", False),
    (FENCE_DECISION, "decision", "fix"),
])
def test_salvage_keeps_decision(txt, key, val):
    j = solo._jsonline(txt)
    assert isinstance(j, dict), txt
    assert j.get(key) == val, (txt, j)


def test_conservative_refusal_never_opens_the_door(monkeypatch):
    """保守拒绝红线：不可解析＝拒绝；抢救出的 grant=false 也绝不因「解析成功」而放行。"""
    assert solo._jsonline("抱歉，我需要更多信息才能判断") is None
    assert solo._jsonline("") is None

    def reply(txt):
        def _f(*a, **k):
            return {"choices": [{"message": {"content": txt}}]}, ""
        return _f

    for txt, exp in (('{"grant": false, "ttl_min": 9, "reason": "越权且与诉求无关', False),
                    (TRUNC_TRUE, True)):
        monkeypatch.setattr(gateway, "_single_shot", reply(txt))
        solo.gw_fail_reset()
        g, why, ttl = solo.review("danger", {"tool": "write", "path": "x"})
        assert g is exp, (txt, g, why)
    solo.gw_fail_reset()


# ---------- 4) gateway failure cooldown (one outage ≠ one wasted call per gate) ----------
def test_review_cooldown_after_gateway_failure(monkeypatch):
    calls = {"n": 0}

    def fail(*a, **k):
        calls["n"] += 1
        return None, "HTTP Error 401: Unauthorized invalid api key"

    monkeypatch.setattr(gateway, "_single_shot", fail)
    solo.gw_fail_reset()
    g1, w1, _ = solo.review("danger", {"tool": "write", "path": "x"})
    g2, w2, _ = solo.review("danger", {"tool": "write", "path": "x"})
    assert g1 is False and g2 is False, "网关失败必须保守拒绝"
    assert calls["n"] == 1, "冷却窗内仍重复发 _single_shot 请求：%d 次" % calls["n"]
    assert "冷却" in w2, w2
    assert solo.gw_cooling() is True and "401" in solo.gw_fail_note()
    solo._GW_FAIL["ts"] -= solo._cool() + 1          # 窗过期＝恢复尝试，不永久锁死
    solo.review("danger", {"tool": "write", "path": "x"})
    assert calls["n"] == 2, calls["n"]
    solo.gw_fail_reset()


def test_success_clears_cooldown(monkeypatch):
    solo.gw_fail_reset()
    solo._GW_FAIL.update({"ts": __import__("time").time(), "err": "HTTP Error 401", "sig": "x"})

    def ok(*a, **k):
        return {"choices": [{"message": {"content": '{"grant": false, "ttl_min": 0, "reason": "拒绝"}'}}]}, ""

    monkeypatch.setattr(gateway, "_single_shot", ok)
    assert solo.gw_cooling() is True
    solo.review("danger", {"tool": "write", "path": "x"})   # 冷却中＝直接拒
    solo.gw_fail_reset()
    solo.review("danger", {"tool": "write", "path": "x"})   # 成功响应清窗
    assert solo.gw_cooling() is False, "拿到有效响应未清冷却"


def test_cooldown_config_and_status_surface(monkeypatch):
    monkeypatch.setattr(solo, "cfg", lambda: {"gw_fail_cooldown_sec": 15})
    assert solo._cool() == 15.0
    monkeypatch.setattr(solo, "cfg", lambda: {})
    assert solo._cool() == 60.0, "缺配置须回默认 60s"
    st = solo.status()
    for k in ("review_cooling", "gw_fail_cooldown_sec", "key_source"):
        assert k in st, "solo.status 缺字段 %s（doctor 可见性回归）" % k


def test_never_key_and_danger_gate_never_burn_tokens(monkeypatch):
    """SOLO 开启＝所有权限默认通过（含 danger 与 remote），不再询问用户、不再走自审流程。
    两者都不许发网关请求——直接授予，不烧 token。"""
    n = {"c": 0}

    def spy(*a, **k):
        n["c"] += 1
        return None, "x"

    monkeypatch.setattr(gateway, "_single_shot", spy)
    solo.gw_fail_reset()
    g, why = solo._decide(solo.SMS, "remote", {"tool": "exec", "intent": "x"})
    assert g is True and "SOLO" in why, why
    monkeypatch.setattr(solo, "cfg", lambda: {"enabled": True, "allow_danger": False})
    g2, why2 = solo._decide(solo.SMS, "danger", {"tool": "write", "path": "x"})
    assert g2 is True and "SOLO" in why2, why2
    assert n["c"] == 0, "SOLO 模式下仍去请求网关（不该烧 token）"


def test_err_sig_distinguishes_auth_from_transient():
    e401 = "HTTP Error 401: Unauthorized invalid api key"
    e503 = "HTTP Error 503: Service Unavailable"
    assert solo.err_sig(e401) != solo.err_sig(e503), "401/503 塌缩同签＝熔断口径失真"
    assert solo.err_sig(e401) == solo.err_sig("HTTP Error 401: UNAUTHORIZED Invalid API Key"), \
        "同一 401 的大小写/措辞漂移致异签＝同错熔断形同虚设（批34 根治）"
    a = 'HTTP Error 401: Unauthorized {"detail":{"error":{"message":"invalid api key","type":"authentication_error"}},"id":"chatcmpl-aa11bb22cc33dd44ee55ff66"}'
    b = a.replace("aa11bb22cc33dd44ee55ff66", "998877665544332211ffaabbcc")
    assert solo.err_sig(a) == solo.err_sig(b), "易变请求 id 落进签名区＝同错异签（熔断口径失真）"
    solo.err_count(reset=True)
    assert solo.err_count(e401) == 1 and solo.err_count(e401) == 2
    solo.err_count(reset=True)


def test_solo_selfcheck_still_passes():
    """python -B solo.py check 的签名/计数自证不得因本次改动退化（子进程走 no_window 封装·红线）。"""
    import no_window
    r = no_window.run([sys.executable, "-B", os.path.join(S, "solo.py"), "check"],
                      capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout[-400:] + r.stderr[-400:]
    assert json.loads(r.stdout)["check"] == "pass"

def test_analyze_shares_the_cooldown(monkeypatch):
    """分析器与审核器共用冷却窗：一次网关故障不得让后续每轮错误都白烧一次必然失败的请求。"""
    calls = {"n": 0}

    def fail(*a, **k):
        calls["n"] += 1
        return None, "HTTP Error 503: Service Unavailable"

    monkeypatch.setattr(gateway, "_single_shot", fail)
    solo.gw_fail_reset()
    assert solo.analyze("llm", "HTTP Error 503: Service Unavailable", {"same": 1}) is None
    assert solo.analyze("llm", "HTTP Error 503: Service Unavailable", {"same": 2}) is None
    assert calls["n"] == 1, "冷却窗内分析器仍重复请求：%d 次" % calls["n"]
    assert solo.gw_cooling() is True
    solo.gw_fail_reset()
