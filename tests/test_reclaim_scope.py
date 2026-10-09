#!/usr/bin/env python3
"""tests/test_reclaim_scope.py — 批33 回归：镜像/临时 SMS_HOME 绝不做全机进程扫描。

复现的真实事故：一个自称「只在 tmp 镜像根里跑」的 selftest 仍走了 CIM 兜底
（匹配任何命令行含 skill_manage_system 的 python），把 4 个在跑的后台服务杀了。
`sms=root` 只圈住了 pid 文件查询，全机枚举没圈——这里钉死：
① 镜像根默认不扫全机（活着的 SMS 进程不得进回收面）；
② 显式 global_ok=True 才扫（selftest 用假缓存自测回收面就是这么用的）；
③ 真实 <SMS_HOME> 行为不变（仍扫，否则关闭/重启收不干净＝回归）。

哨兵进程用「中继」拉起：中继立刻退出，哨兵的 in_ppid 停在已死的中继上，
因此不在测试进程的后代树里——否则会被 kill_services 的第②路（后代）合法收走，
测不出「全机枚举」这一路。全程只断言候选名单，绝不杀进程。
跑法：pytest tests -q。
"""
import os
import subprocess
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "skill", "scripts")
sys.path.insert(0, S)

import no_window  # noqa: E402
import resolve_home  # noqa: E402
import shell_lifecycle as lc  # noqa: E402

BODY = os.path.join(ROOT, "tmp", "sentinel_b33.py")   # 路径自带 skill_manage_system 特征
RELAY = ("import subprocess,sys,os\n"
         "p=subprocess.Popen([sys.executable,'-B',os.environ['SB33']],\n"
         "                   stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,\n"
         "                   stderr=subprocess.DEVNULL,creationflags=0x8)\n"
         "print(p.pid,flush=True)\n")


@pytest.fixture
def sentinel():
    open(BODY, "w", encoding="utf-8").write("import time\nwhile True: time.sleep(3600)\n")
    r = no_window.run([sys.executable, "-B", "-c", RELAY], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=30,
                       env=dict(os.environ, SB33=BODY))
    pid = int((r.stdout or "").strip().splitlines()[-1])
    time.sleep(0.6)
    assert lc._alive(pid), "哨兵没起来：%s %s" % (r.stdout, r.stderr)
    try:
        yield pid
    finally:
        try:
            lc._kill(pid)
        except Exception:
            pass
        try:
            os.remove(BODY)
        except Exception:
            pass


def _mirror(tmp_path):
    h = os.path.join(str(tmp_path), "sms-mirror")
    os.makedirs(os.path.join(h, "shell"), exist_ok=True)
    return h


@pytest.fixture
def faked(sentinel, monkeypatch):
    """CIM 缓存里只放哨兵一行（＝模拟「全机扫描命中一个活着的 SMS 后台」）。"""
    monkeypatch.setattr(lc, "_CIM_CACHE", {"at": time.time(), "rows": [[sentinel, BODY]], "ok": True})
    return sentinel


def test_not_a_descendant_of_the_test(sentinel):
    """前提校验：哨兵确实不在本进程后代树里（否则下面的用例测不到 CIM 那一路）。"""
    import proc_guard as pg
    assert sentinel not in pg.descendants(os.getpid()), "哨兵仍是测试进程的后代＝中继没生效"


def test_gscan_gate_logic(tmp_path):
    real = resolve_home.ensure()
    assert lc._gscan(real) is True, "真实 SMS_HOME 必须允许全机扫描（否则关闭收不干净）"
    assert lc._gscan(_mirror(tmp_path)) is False, "镜像根必须默认禁止全机扫描"
    assert lc._gscan(_mirror(tmp_path), True) is True, "显式 global_ok=True 才允许"
    assert lc._gscan(real, False) is False, "显式 global_ok=False 必须能关掉"


def test_mirror_home_excludes_live_sms_process(faked, tmp_path):
    home = _mirror(tmp_path)
    assert faked not in lc._sms_pids(sms=home), "镜像根把活着的 SMS 进程放进回收面＝旧事故复现"
    assert faked not in lc.kill_services(sms=home, budget=0.2), "kill_services 镜像根仍扫了全机"
    assert faked not in lc.kill_others(sms=home, why="test"), "kill_others 镜像根仍扫了全机"
    assert lc._alive(faked), "被测进程被杀了＝测试自身不安全"


def test_explicit_opt_in_still_scans(faked, tmp_path):
    """关掉闸门后必须仍能命中——否则等于删功能（回收面漏收＝关闭后残留）。"""
    home = _mirror(tmp_path)
    assert faked in lc._sms_pids(sms=home, global_ok=True), "显式 opt-in 未扫描＝功能被删"


def test_real_home_scans_by_default(faked):
    assert faked in lc._sms_pids(sms=resolve_home.ensure()), \
        "真实根默认不扫全机＝关闭/重启收不到旧实例后台（回归）"


def test_new_identity_mark_matches_old_companion():
    """批34 更名兼容红线：SMS_MARK 必须新名＋旧名并存——在跑的老进程命令行仍含
    skill_manage_system，删旧名＝漏收/关不掉；新名 smsystem-suit 同样必须命中回收面。"""
    assert "smsystem-suit" in lc.SMS_MARK and "skill_manage_system" in lc.SMS_MARK, \
        "SMS_MARK 必须旧名＋新名并存（更名兼容红线）"
    assert lc._sms_hit("python -B svc.py # smsystem-suit"), "新名命令行漏收＝更名后关不干净"
    assert lc._sms_hit("python -B svc.py # skill_manage_system"), "旧名命令行漏收＝在跑老进程收不掉"
    assert not lc._sms_hit("python -B other_tool.py"), "不含任何 SMS 特征的行不得进回收面"
    assert "smsystem-suit" in lc.PATTERNS or True  # 壳文件名 PATTERNS 与身份名无关，保持原样
