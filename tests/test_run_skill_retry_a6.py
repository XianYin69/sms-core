#!/usr/bin/env python3
"""tests/test_run_skill_retry_a6.py — 批A6 回归钉：run_skill 派发对话空输出的**同参数单次自动重试**。
钉五条口径：① 首次空→重试一次拿到正文即返回，且不记 run_skill_empty；② 两次皆空→只重试一次
（禁循环）且 run_skill_empty 恰记一条；③ 重试与首次参数一字不差（body/max_rounds 同构）；
④ 用户 stop 或 run_watch 超时收口窗内一律不重试；⑤ 异常路径不重试、登记口径不变、会话 close: 恰一条。
全离线：桩 gateway.run/skill_doc/chains/skill_errors/session_reg，不发网络、不写真链与真账本。"""
import os
import sys
import time

import pytest

S = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skill", "scripts")
sys.path.insert(0, S)
import agent_tools as AT  # noqa: E402
import chains  # noqa: E402
import gateway  # noqa: E402
import latency  # noqa: E402
import session_reg  # noqa: E402
import settings as ST  # noqa: E402
import skill_doc  # noqa: E402
import skill_errors  # noqa: E402
import stop_channel  # noqa: E402

SKILL = {"id": "demo", "install_path": os.sep + "x", "entry": "SKILL.md"}


@pytest.fixture
def env(monkeypatch, tmp_path):
    """离线桩：可控两次 gateway 返回值/异常序列，记录链账、错误台账、派发参数。"""
    rec = {"gw": [], "errors": [], "sess": [], "sub": [], "sleep": []}
    ctl = {"outs": ["", ""], "excs": [None, None], "n": [0], "stopped": False, "why": ""}
    real_get = ST.get

    def fake_run(body, on_line, max_rounds=None):
        i = ctl["n"][0]
        ctl["n"][0] += 1
        rec["gw"].append({"body": body, "max_rounds": max_rounds, "attempt": i})
        e = ctl["excs"][i] if i < len(ctl["excs"]) else None
        if e:
            raise e
        out = ctl["outs"][i] if i < len(ctl["outs"]) else ""
        if out:
            on_line(out)          # 模拟 ⧉ 前缀实时上屏＝streamed 置真
        return out

    def fake_get(key, d=None):
        return 0 if key == "caps.skill_rounds" else real_get(key, d)

    monkeypatch.setattr(AT.skill_route, "skills", lambda *a, **k: [dict(SKILL)])
    monkeypatch.setattr(AT.resolve_home, "wtmp", lambda *a, **k: str(tmp_path))
    monkeypatch.setattr(skill_doc, "package", lambda *a, **k: "DOC-FULL")
    monkeypatch.setattr(session_reg, "attach", lambda *a, **k: None)
    monkeypatch.setattr(chains, "record", lambda ch, text, edges=None: rec["sess"].append(text) or "ok")
    monkeypatch.setattr(chains, "log", lambda kind, name, conv="": rec["sub"].append((kind, str(name))))
    monkeypatch.setattr(latency, "wrap", lambda kind, name, fn, *a, **k: fn(*a, **k))
    monkeypatch.setattr(ST, "get", fake_get)
    monkeypatch.setattr(skill_errors, "record",
                        lambda sms, sk, where, msg, b: rec["errors"].append((sk, where, msg)))
    monkeypatch.setattr(stop_channel, "stopped", lambda t=None: bool(ctl["stopped"]))
    monkeypatch.setattr(stop_channel, "why", lambda t=None: ctl["why"])
    monkeypatch.setattr(time, "sleep", lambda s: rec["sleep"].append(s))
    monkeypatch.setattr(gateway, "run", fake_run)
    AT.bind(on_line=lambda s: None, ev=False)
    AT.ac.cur().update(depth=0, chain=[], conv="", streamed=False)
    rec["ctl"] = ctl
    return rec


def test_retry_once_gets_body(env):
    """首次空输出→同参数重试一次拿到正文：不记 run_skill_empty、睡过 2s、会话 close: 恰一条。"""
    env["ctl"]["outs"] = ["", "派发正文内容"]
    r = AT.run_skill("demo", "诉求")
    assert len(env["gw"]) == 2, env["gw"]
    assert r.startswith(AT.WRAP) and "派发正文内容" in r, r[:80]
    assert [e for e in env["errors"] if e[1] == "run_skill_empty"] == [], env["errors"]
    assert env["sleep"] == [2], env["sleep"]
    assert any("空输出自动重试" in str(x) for x in env["sub"]), env["sub"]
    assert len([x for x in env["sess"] if str(x).startswith("close:")]) == 1, env["sess"]


def test_retry_is_single_shot(env):
    """两次皆空＝只重试一次（硬禁循环），run_skill_empty 恰记一条、返回无输出提示。"""
    env["ctl"]["outs"] = ["", "", "", ""]
    r = AT.run_skill("demo", "诉求")
    assert len(env["gw"]) == 2, env["gw"]
    e = [x for x in env["errors"] if x[1] == "run_skill_empty"]
    assert len(e) == 1, env["errors"]
    assert "无输出" in r, r


def test_retry_uses_identical_args(env):
    """重试参数与首次一字不差：body 与 max_rounds 同构（同参数重试·不改报文）。"""
    env["ctl"]["outs"] = ["", ""]
    AT.run_skill("demo", "诉求")
    a, b = env["gw"][0], env["gw"][1]
    assert a["body"] == b["body"] and a["max_rounds"] == b["max_rounds"], (a, b)


def test_no_retry_on_user_stop(env):
    """用户 stop 窗内不重试（停手即收口，不得借重试续命）。"""
    env["ctl"]["outs"] = ["", ""]
    env["ctl"]["stopped"] = True
    r = AT.run_skill("demo", "诉求")
    assert len(env["gw"]) == 1, env["gw"]
    assert env["sleep"] == [], env["sleep"]
    assert "无输出" in r, r


def test_no_retry_in_run_watch_window(env):
    """run_watch 超时收口窗内不重试也不记 run_skill_empty（批27 自收口不误报口径）。"""
    env["ctl"]["outs"] = ["", ""]
    env["ctl"]["stopped"] = True          # 真实时序：run_watch 超收＝旗标置真＋ why 前缀匹配
    env["ctl"]["why"] = "run_watch 超时收口 silent=321"
    r = AT.run_skill("demo", "诉求")
    assert len(env["gw"]) == 1, env["gw"]
    assert [x for x in env["errors"] if x[1] == "run_skill_empty"] == [], env["errors"]
    assert "无输出" in r, r


def test_exception_path_no_retry(env):
    """异常仍照旧登记 run_skill 并直接抛穿——不做第二次尝试（同参数重试只兜静默空输出）。"""
    boom = RuntimeError("gateway 503")
    env["ctl"]["excs"] = [boom, None]
    with pytest.raises(RuntimeError):
        AT.run_skill("demo", "诉求")
    assert len(env["gw"]) == 1, env["gw"]
    assert [x[1] for x in env["errors"]] == ["run_skill"], env["errors"]
    assert len([x for x in env["sess"] if str(x).startswith("close:")]) == 1, env["sess"]
    c = AT.ac.cur()
    assert c["depth"] == 0 and c["chain"] == [] and c["conv"] == "", c
