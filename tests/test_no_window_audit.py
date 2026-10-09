#!/usr/bin/env python3
"""tests/test_no_window_audit.py — 静态审计测试：全仓禁止裸 subprocess/os.system。

红线：一切子进程经 no_window.run/Popen（闪黑框·抢前台根治）；
有意可见控制台点用 `# sms-visible` 标记，封装本体 no_window.py 走文件名白名单。
跑法：pytest tests -q（或 python -B skill/scripts/no_window_audit.py 单跑）。
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "skill", "scripts")
sys.path.insert(0, S)
import no_window  # noqa: E402
import no_window_audit as aud  # noqa: E402


def test_repo_has_no_bare_subprocess():
    r = aud.scan(ROOT)
    assert r["scanned"] > 100, "扫描面异常（应覆盖全仓脚本）：%s" % r["scanned"]
    assert r["violations"] == [], "存在裸子进程调用（会闪黑框/抢前台）：%s" % r["violations"]


def test_whitelist_and_marker_contract():
    assert "no_window.py" in aud.WHITELIST, "封装本体必须在白名单"
    assert aud.MARK in open(os.path.join(S, "shell_gui.py"), encoding="utf-8").read(), \
        "GUI 起 TUI 的可见控制台点必须带 # sms-visible 标记"
    assert aud.MARK in open(os.path.join(ROOT, "sms.py"), encoding="utf-8").read(), \
        "入口交棒 sms-shell-tui/sms-shell-gui 必须带 # sms-visible 标记"


def test_hits_detects_bare_call():
    bad = aud.hits("import subprocess\nsubprocess.run(['x'])\n", "mem.py")
    assert len(bad) == 1 and bad[0]["line"] == 2
    ok = aud.hits("import subprocess\n# sms-visible：有意开窗\nsubprocess.run(['x'])\n", "mem.py")
    assert ok == []
    alias = aud.hits("from subprocess import run\nrun(['x'])\n", "mem.py")
    assert len(alias) == 1, "别名绕过必须被检出"


@pytest.mark.skipif(os.name != "nt", reason="CREATE_NO_WINDOW 仅 Windows")
def test_child_gets_no_console():
    r = no_window.selftest()
    assert r["rc"] == 0 and r["silent"], "子进程仍拿到控制台：%s" % r
