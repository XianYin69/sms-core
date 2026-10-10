#!/usr/bin/env python3
"""tests/test_error_ledger_batch40.py — 批40 A1/A2/A3 回归钉：
A1 同因合并（路径/版本/行列号差异不得裂成多条）、resolved 再现重开、非缺陷自动判定、migrate 幂等；
A2 空提交分类（nothing to commit ≠ 失败）；
A3 脏消息（换行/NUL/未配对代理项）登记不抛穿、describe() 带 filename/errno/栈帧、
   atomic 写失败降级 fallback、debug.error 失败仍登记。
用 tmp_path 独立 SMS_HOME，permissions/solo 走 monkeypatch，不污染他测。"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skill", "scripts"))
import skill_errors as SE  # noqa: E402
import chains_git as CG  # noqa: E402


@pytest.fixture
def sms(tmp_path, monkeypatch):
    for d in ("errors", "shell", "logs"):
        (tmp_path / d).mkdir(exist_ok=True)
    (tmp_path / "shell" / "debug").write_text("")  # debug 开启＝error 通道走 debug.log
    import permissions
    monkeypatch.setattr(permissions, "allow", lambda *a, **k: True)
    import chain_error
    monkeypatch.setattr(chain_error, "hook", lambda *a, **k: None)  # 不往真 error 链灌噪声
    return str(tmp_path)


SAME_CAUSE = [
    "版本解析 ValueError: invalid literal for int() with base 10: 'v1.2.3' at C:\\a\\x.py:12",
    "版本解析 ValueError: invalid literal for int() with base 10: 'v1.2.4' at C:\\a\\x.py:19",
    "版本解析 ValueError: invalid literal for int() with base 10: 'v9' at C:\\b\\y.py:3",
]


def _entries(sms):
    return json.load(open(SE._p(sms), encoding="utf-8"))["entries"]


def test_merge_same_cause(sms):
    for m in SAME_CAUSE:
        SE.record(sms, "sms_stress_test", "scripts/mine_canary.py", m, True)
    e = _entries(sms)
    assert len(e) == 1 and e[0]["count"] == 3, e


def test_reopen_after_resolve(sms):
    SE.record(sms, "gw", "ask", "boom [Errno 22] Invalid argument: 'C:\\a\\b.log'", True)
    SE.resolve(sms, "gw", True)
    SE.record(sms, "gw", "ask", "boom [Errno 22] Invalid argument: 'C:\\a\\c.log'", True)
    e = [x for x in _entries(sms) if x["skill"] == "gw"]
    assert len(e) == 1 and e[0]["status"] == "open" and e[0]["count"] == 2 and e[0].get("reopened"), e


def test_not_defect_timeout(sms):
    r = SE.record(sms, "sk", "run_watch", "run_watch 超时收口 silent=321", True)
    assert r["status"] == "not_defect", r


def test_dirty_msg_never_raises(sms):
    SE.record(sms, "sk3", "ask", "l1\nl2\t\x00nul\udfff" + "x" * 3000, True)
    m = [x for x in _entries(sms) if x["skill"] == "sk3"][0]["msg"]
    assert "\n" not in m and "\x00" not in m and len(m) <= 400, len(m)


def test_describe_keeps_filename(sms):
    try:
        open(os.path.join(sms, "errors", "a\nb.txt"), "w").write("x")
    except OSError as e:
        d = SE.describe(e)
        assert "errno=22" in d and "@" in d and "filename=" in d, d
    else:
        pytest.fail("预期 Errno 22 未发生")


def test_atomic_fail_degrades(sms):
    import atomic_io
    real = atomic_io.wjson

    def boom(path, obj, *a, **k):
        raise OSError(22, "Invalid argument", path)

    atomic_io.wjson = boom
    try:
        r = SE.record(sms, "sk4", "save", "atomic-will-fail", True)
    finally:
        atomic_io.wjson = real
    assert r.get("ok") or "error" in r, r  # 关键＝不抛穿


def test_debug_error_fail_still_records(sms, monkeypatch):
    import debug

    def boom(*a, **k):
        raise OSError(22, "Invalid argument: '<stdout>'")

    monkeypatch.setattr(debug, "error", boom)
    r = SE.record(sms, "sk5", "ask", "logging-broken", True)
    assert r.get("ok"), r


def test_migrate_idempotent(sms):
    doc = {"entries": [
        {"skill": "s", "where": "w", "msg": "boom 1 at C:\\a\\x.py", "count": 1, "status": "resolved", "first": "2026-10-09", "last": "2026-10-09"},
        {"skill": "s", "where": "w", "msg": "boom 2 at C:\\a\\y.py", "count": 2, "status": "open", "first": "2026-10-10", "last": "2026-10-10"},
        {"skill": "q", "where": "w", "msg": "other", "count": 1, "status": "not_defect", "first": "2026-10-01", "last": "2026-10-01"}]}
    import atomic_io
    atomic_io.wjson(SE._p(sms), doc)
    m = SE.migrate(sms, True)
    assert m["before"] == 3 and m["after"] == 2 and m["merged"] == 1, m
    m2 = SE.migrate(sms, True)
    assert m2["merged"] == 0 and m2["after"] == 2, m2


def test_empty_commit_not_failure():
    assert CG._empty("On branch main\nnothing to commit, working tree clean")
    assert not CG._empty("fatal: unable to write index")
    assert "index.lock" in CG.LOCKFAIL
