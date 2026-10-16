#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_solo_b35.py — 批35 SOLO 失灵根治回归（四项根因，全离线·不依赖网关在线）。

1. _pos 正整数钳制：solo.review_max_tokens/analyze_max_tokens 被写成 0/负/脏值时，旧式 int() 无下限
   → 上游直接 400（实测复现：{"message":"One or more request parameters are invalid"}）→ 自审每次保守拒绝
   ＝用户看到的「SOLO 失灵」；ttl 0 值同理＝授予即过期、白烧一次审核。
2. _ask 请求体：默认带 chat_template_kwargs.enable_thinking=false（实测推理型上游开思考单次 13-25s 且
   无视 max_tokens，自审串在每次受门禁工具调用前＝卡顿主源）；上游不认该参数（400）必须自动回退旧体一次；
   fast_think=false 时逐字回到旧体（零回归）。
3. _extra 口径：审核器不得把「本轮话语为空/截断」当「用户没要求」（SMS 自身代码修复类 danger/git 写曾被
   反复误拒）；分析器根因必须逐字来自错误详情，禁止编造详情里没有的参数名（实测两次互斥归因）。
4. _conv_tail_user：取不到本轮 conv 时回落 <SMS_HOME>/shell/last_conv.json，且不得产生 core→shell 反向依赖。
5. dream_pending.auto_solo：续跑未成功但该行已落终态（fixed/failed/dropped）不再计入「未成」——旧写法把
   权限未备早退（不落态）与已终结行混计，空闲每轮刷屏并把 bad 当「无进展」误触守卫熔断。
跑法：pytest tests -q
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "skill", "scripts")
sys.path.insert(0, S)
import solo           # noqa: E402
import gateway        # noqa: E402
import dream_pending  # noqa: E402

# ---------- 1) 预算/ttl 下限钳制 ----------
def test_pos_clamps_non_positive():
    assert solo._pos(0, 200) == 200
    assert solo._pos(-5, 200) == 200
    assert solo._pos("x", 200) == 200
    assert solo._pos(None, 200) == 200
    assert solo._pos(500, 200) == 500, "合法值必须原样，不得反向钳小"
    assert solo._pos(0, 30) == 30, "ttl 0 值回落 solo.ttl_min（授予即过期＝白烧审核）"

def test_zero_review_budget_does_not_400(monkeypatch):
    """配置被写成 0 时，DSM 单发信封的预算必须是正数（0 会被上游判 400 全域哑火）。
    批36 后 SOLO 出站＝gateway._single_shot（DSM 单发）：max_tokens 经 budget.max_out 传，
    打桩 _single_shot 直接断言收到的 max_tokens 参数已被 _pos 钳成正数。"""
    seen = {}
    def fake(sysp, usr, mt, extra_body=None):
        seen["max_tokens"] = mt
        return {"choices": [{"message": {"content": '{"grant":true,"ttl_min":5,"reason":"t"}'}}]}, ""
    monkeypatch.setattr(gateway, "_single_shot", fake)
    monkeypatch.setattr(solo, "cfg", lambda: {"review_max_tokens": 0, "fast_think": True, "allow_danger": True,
                                              "ttl_min": 30, "max_ttl_min": 120, "notify": False})
    solo.review("write", {"tool": "write", "path": "x", "intent": "回归测试"})
    assert seen.get("max_tokens", 0) > 0, seen


# ---------- 2) 闭思考体＋400 回退（DSM 单发：闭思考参数经 extra_body 透传进信封 x 段） ----------
def _capture_calls(fail_first=False):
    calls = []
    def fake(sysp, usr, mt, extra_body=None):
        calls.append(dict(extra_body or {}))
        if fail_first and len(calls) == 1:
            return None, "HTTP Error 400: Bad Request {\"detail\":{\"error\":{\"message\":\"One or more request parameters are invalid.\"}}}"
        return {"choices": [{"message": {"content": '{"grant":true,"ttl_min":5,"reason":"ok"}'}}]}, ""
    return calls, fake

def test_fast_think_body_and_400_fallback(monkeypatch):
    g = solo.__dict__
    calls, fake = _capture_calls(fail_first=True)
    monkeypatch.setattr(gateway, "_single_shot", fake)
    g["gateway"] = gateway
    monkeypatch.setattr(solo, "cfg", lambda: {"review_max_tokens": 200, "fast_think": True, "allow_danger": True,
                                              "ttl_min": 30, "max_ttl_min": 120, "notify": False})
    g["gw_fail_reset"]()
    grant, why, ttl = solo.review("write", {"tool": "write", "path": "x", "intent": "回归测试"})
    assert len(calls) == 2, "闭思考体被 400 拒后必须回退旧体重发一次"
    assert calls[0].get("chat_template_kwargs") == {"enable_thinking": False}
    assert "chat_template_kwargs" not in calls[1], "回退体＝无闭思考参数"
    assert grant is True, (grant, why)

def test_fast_think_off_is_legacy_body(monkeypatch):
    calls, fake = _capture_calls()
    monkeypatch.setattr(gateway, "_single_shot", fake)
    solo.__dict__["gateway"] = gateway
    monkeypatch.setattr(solo, "cfg", lambda: {"review_max_tokens": 200, "fast_think": False, "allow_danger": True,
                                              "ttl_min": 30, "max_ttl_min": 120, "notify": False})
    solo.review("write", {"tool": "write", "path": "x", "intent": "回归测试"})
    assert len(calls) == 1 and "chat_template_kwargs" not in calls[0]

# ---------- 3) 审核/分析口径 ----------
def test_extra_review_context_rule():
    t = solo._extra("review")
    assert "不等于" in t or "不等于用户没提要求" in t, t
    assert "SMS 自身代码" in t, "自修类改动须视为已获要求的口径要在"
    assert "不得以" in t

def test_extra_analyze_no_fabrication():
    t = solo._extra("analyze")
    assert "逐字" in t and "猜测式归因" in t, t
    assert "401" in t and "400" in t, "已知真因表要在（0 预算→400·空密钥→401）"

def test_salvage_still_conservative():
    """批34 容错与批35 口径共存：缺判定位仍保守拒绝。"""
    assert solo._jsonline('{"grant":true,"ttl_min":30,"reason":"ok') == {"grant": True, "ttl_min": 30, "reason": "ok"}
    assert solo._jsonline("nothing here") is None

# ---------- 4) 兜底话语＋壳核分离 ----------
def test_conv_tail_user_reads_data_file_not_shell_module(monkeypatch, tmp_path):
    home = str(tmp_path)
    os.makedirs(os.path.join(home, "shell"), exist_ok=True)
    doc = {"conv": "conv-x", "sess": "sess-t", "ts": "2026-01-01 00:00:00",
           "turns": [["user", "修复 SOLO 自审"], ["agent", "好"]]}
    io.open(os.path.join(home, "shell", "last_conv.json"), "w", encoding="utf-8").write(json.dumps(doc, ensure_ascii=False))
    monkeypatch.setattr(solo, "SMS", home)
    monkeypatch.setattr(solo.chains, "cur_sess", lambda: "sess-t")
    got = solo._conv_tail_user()
    assert "修复 SOLO 自审" in got and got.startswith("〔本轮话语·壳接续缓存〕"), got
    monkeypatch.setattr(solo.chains, "cur_sess", lambda: "sess-other")
    assert solo._conv_tail_user() == "", "跨 session 缓存不得当本轮话语用"

def test_no_core_to_shell_import_edge():
    import sep_audit
    r = sep_audit.audit()
    assert r["verdict"] == "SEPARATED" and r["core_to_shell"] == 0, r["violations"]

# ---------- 5) 待批续跑计数 ----------
def _fake_pending(tmp_path, rows):
    d = os.path.join(str(tmp_path), "dream")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "pending.json")
    io.open(p, "w", encoding="utf-8").write(json.dumps(rows, ensure_ascii=False))
    return str(tmp_path)

def test_auto_solo_terminal_row_not_counted(monkeypatch, tmp_path):
    sms = _fake_pending(tmp_path, [{"id": "program-1", "kind": "program", "target": "t", "reason": "r",
                                    "how": {}, "first": "", "last": "", "count": 1, "status": "open"}])
    import dream_repair
    monkeypatch.setattr(dream_pending, "due", lambda s=None: [{"id": "program-1"}])
    # 模拟 resume 把行落到终态（failed）后回失败文案 → 旧写法计入 bad＝每轮刷屏＋守卫误判无进展
    state = {"status": "failed"}
    def fake_take(fid, s=None): return {"id": fid, "status": state["status"]}
    monkeypatch.setattr(dream_pending, "take", fake_take)
    monkeypatch.setattr(dream_repair, "resume", lambda fid, s=None: "续跑仍失败：未检出 Skill_Generator")
    monkeypatch.setattr(solo, "auto_pending", lambda: True)
    out = dream_pending.auto_solo(sms)
    assert out and "未成0" in out, out
    # 仍 open（权限未备早退不落态）→ 仍须计 bad，熔断语义不丢
    state["status"] = "open"
    out2 = dream_pending.auto_solo(sms)
    assert "未成1" in out2, out2
