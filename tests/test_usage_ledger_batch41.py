#!/usr/bin/env python3
"""tests/test_usage_ledger_batch41.py — 批41 回归钉：
F1 费用台账 split/rec（缺字段 0 值、全零不写、写失败静默降级不抛穿、聚合口径正确）；
F2 无参/错参调用不再 IndexError（docstring 单行取首行、空 doc 回用法句）；
F4 审计多根口径（core 根干净、roots 逐项计数、技能根命中带 root 字段）。
全离线：tmp_path 独立 SMS_HOME，不发网络、不碰真账本、不写 skill 目录。"""
import json
import os
import sys

S = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skill", "scripts")
sys.path.insert(0, S)
import no_window as nw  # noqa: E402  本仓红线：子进程一律经静默封装
import usage_ledger as UL  # noqa: E402
import cost_report as CR  # noqa: E402


def test_split_openai_shape():
    r = UL.split({"prompt_tokens": 10, "completion_tokens": 4,
                  "prompt_tokens_details": {"cached_tokens": 3},
                  "completion_tokens_details": {"reasoning_tokens": 2},
                  "cost": 0.05, "currency": "USD"}, model="m", skill="s", conv="c", sess="x")
    assert r["in"] == 10 and r["out"] == 4 and r["reason"] == 2 and r["cache_read"] == 3, r
    assert r["cost"] == 0.05 and r["skill"] == "s" and r["conv"] == "c"


def test_split_tolerates_junk():
    r = UL.split(None, model=None, skill=None)
    assert r["in"] == 0 and r["cost"] is None and r["model"] == "", r


def test_rec_writes_and_skips_zero(tmp_path):
    assert UL.rec({"prompt_tokens": 1, "completion_tokens": 1}, model="m", sms=str(tmp_path),
                  conv="c1", sess="s1") is True
    assert UL.rec({"prompt_tokens": 0, "completion_tokens": 0}, sms=str(tmp_path)) is False
    ls = [json.loads(x) for x in open(UL.path(str(tmp_path)), encoding="utf-8").read().splitlines()]
    assert len(ls) == 1 and ls[0]["conv"] == "c1", ls


def test_rec_degrades_silently(tmp_path):
    home = tmp_path / "home.txt"          # 数据根位置是文件 → makedirs 必失败
    home.write_text("x", encoding="utf-8")
    assert UL.rec({"prompt_tokens": 5}, sms=str(home)) is False   # 关键＝不抛穿
    assert UL.rec(None, sms=str(tmp_path)) is False               # 全零/坏输入不写


def test_cost_report_aggregates(tmp_path):
    for i in range(3):
        UL.rec({"prompt_tokens": 100, "completion_tokens": 10,
                "completion_tokens_details": {"reasoning_tokens": 6}},
               model="m1", skill="sk", sms=str(tmp_path), conv="c%d" % i, sess="s")
    d = CR.agg("skill", str(tmp_path))
    assert d["sk"]["turns"] == 3 and d["sk"]["in"] == 300 and d["sk"]["out"] == 30, d
    b = CR.brief("conv", str(tmp_path))
    assert b["rows"]["in"] == 300 and len(b["top"]) == 3, b


def test_broken_docstring_usage_no_crash():
    for f in ("skill_route.py", "chains.py", "latency.py", "agent_tools.py",
              "agent_dispatch.py", "agent_tools3.py", "sessions_view.py"):
        p = nw.run([sys.executable, "-B", os.path.join(S, f), "__nope__"],
                   capture_output=True, timeout=60)
        err = (p.stderr or b"").decode("utf-8", "replace")
        assert "IndexError" not in err, (f, err[-200:])


def test_audit_multiroot_contract():
    import no_window_audit as aud
    r = aud.report([aud.scan(os.path.dirname(S), "core")])
    assert r["violations"] == [] and r["roots"][0]["root"] == "core", r["roots"]
    assert r["scanned"] > 100


def test_audit_skills_root_reported(tmp_path):
    import no_window_audit as aud
    (tmp_path / "b.py").write_text("import subprocess\nsubprocess.run(['x'])\n", encoding="utf-8")
    r = aud.scan(str(tmp_path), "skills")
    assert r["violations"] and r["violations"][0]["root"] == "skills", r["violations"]
    assert aud.report([r])["roots"][0]["violations"] == 1
