#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_task_table_batch47.py — 批47「补投即开新表＝摸鱼滚雪球」根治回归（离线·tmp_path 隔离 TD）。

真源取证（2026-10-11）：qq_stall.nudge 补投文本经 agent_stream.ask 投进数据流＝每次输入必开新 conv
（红线17），旧版 attach() 把补投原文再走 task.decompose 标点粗分＝必建一张新种子表；而 pending()
只认 doc["conv"]==当前 conv、_mine() 禁越会话回写 → 原表永远「未完成」，新表自己也推不完，下轮再补投
再建新表（实测 08:00/08:08/08:19 三张表 intent 全是补投文本；另有无聊幽灵表 task-20261011-095214-045
单行 goal=noop，源于 plan(steps="noop") 被逐字拆成 n/o/o/p 四行）。

覆盖：
1. claim() 认领原表续推（接管 conv＋claims 留痕＋零新表＋守卫据此续推）；
2. 他 session 的表不夺权（批23/32 边界）——只提示、同样零新表；
3. 已收口/不在途的表 → 免表直答，绝不新建；
4. 垃圾行拒建（noop/纯表号/不足4字；steps 传字符串不再逐字拆）；
5. sweep() 清补投残表与全垃圾表（stopped＋归档），正常在途表不误伤；
6. 旧行为回归：常规多步意图仍建种子表、单步/问答免表、免表时列出本 conv 在途表。
跑法：pytest tests -q（全离线，不触网关不发 QQ）。
"""
import os
import sys
import time
import json
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "skill", "scripts")
sys.path.insert(0, S)
import chains            # noqa: E402
import task_table as tt  # noqa: E402


@pytest.fixture()
def td(tmp_path, monkeypatch):
    """隔离 TD/AD 到 tmp_path，并把 chains.ACTIVE 指向假 conv（用后复原）。"""
    d = str(tmp_path / "tasks"); a = str(tmp_path / "arch")
    os.makedirs(d, exist_ok=True); os.makedirs(a, exist_ok=True)
    monkeypatch.setattr(tt, "TD", d); monkeypatch.setattr(tt, "AD", a)
    saved = dict(chains.ACTIVE)
    real_sess = chains.cur_sess()
    yield d, a, real_sess
    chains.ACTIVE.clear(); chains.ACTIVE.update(saved)


def _files(d):
    return sorted(f[5:-5] for f in os.listdir(d) if f.endswith(".json"))


def _mk(conv, steps="核验A1A2A3落地并取真实数字, 清理工作树脏改动, 汇总报告入tmp"):
    chains.ACTIVE["conv"] = conv
    return tt.plan(steps)


def _nudge(short):
    return ("继续当前任务总览未完成行（看门狗补投·表 %s）：t1:核验A1A2A3落地并取真实数字、t2:清理工作树脏改动\n"
            "〔认领表 %s〕先 task_plan op=claim value=%s 接管该原表并逐行推进；禁止为本消息另建新任务总览；"
            "原表若已无未完成行则直答回报、免表。") % (short, short, short)


def test_seed_table_still_created(td):
    d, a, _ = td
    doc = _mk("conv-A")
    assert doc and len(doc["subtasks"]) == 3
    assert _files(d) == [doc["id"][5:]]


def test_claim_takes_over_without_new_table(td):
    d, a, sess = td
    doc = _mk("conv-A"); tid = doc["id"]; short = tid[-14:]
    chains.ACTIVE["conv"] = "conv-B"
    n0 = len(_files(d))
    out = tt.attach(_nudge(short))
    assert "补投认领原表 " + short in out, out[:200]
    assert len(_files(d)) == n0, "补投绝不能再建一张表"
    cur = tt._load(tid)
    assert cur["conv"] == "conv-B"
    assert len(cur.get("claims") or []) == 1
    assert cur["subtasks"][0]["status"] == "pending", "认领只转归属，不改行内容/状态"
    assert "核验A1A2A3" in tt.pending("conv-B"), "守卫须在原表上续推（批49：pending 以目的文本标识表）"


def test_claim_is_idempotent_for_same_conv(td):
    d, a, sess = td
    doc = _mk("conv-A"); tid = doc["id"]; short = tid[-14:]
    chains.ACTIVE["conv"] = "conv-B"
    tt.attach(_nudge(short)); tt.attach(_nudge(short))
    assert len(tt._load(tid).get("claims") or []) == 1


def test_other_session_table_not_poached(td, monkeypatch):
    d, a, sess = td
    doc = _mk("conv-A"); tid = doc["id"]; short = tid[-14:]
    doc = tt._load(tid); doc["conv"] = "conv-A"; doc["sess"] = "sess-OTHER"; tt._save(doc)
    chains.ACTIVE["conv"] = "conv-C"
    monkeypatch.setattr(chains, "cur_sess", lambda: "sess-ZZZ")
    n0 = len(_files(d))
    out = tt.attach(_nudge(short))
    assert "属他 session" in out, out[:200]
    assert len(_files(d)) == n0, "跨会话也不得另建同义新表"
    assert tt._load(tid)["conv"] == "conv-A", "不得越会话改他人表归属"


def test_closed_table_yields_no_table(td):
    d, a, sess = td
    doc = _mk("conv-A"); tid = doc["id"]; short = tid[-14:]
    doc = tt._load(tid)
    for x in doc["subtasks"]:
        x["status"] = "done"
    tt._save(doc)                       # 全终态 → 自动归档
    chains.ACTIVE["conv"] = "conv-D"
    n0 = len(_files(d))
    out = tt.attach(_nudge(short))
    assert ("已无未完成行" in out or "不在途" in out), out[:200]
    assert len(_files(d)) == n0
    assert os.path.exists(os.path.join(a, tid + ".json"))


def test_junk_rows_refused(td):
    d, a, sess = td
    chains.ACTIVE["conv"] = "conv-E"
    assert tt.plan("task-20261011-092240-742", steps="noop") is None
    assert tt.plan("010-203014-118", steps="010-203014-118") is None
    assert _files(d) == [], "noop/纯表号一律不建表（旧版逐字拆成 n/o/o/p 四行＝幽灵表根因）"
    assert tt._junk("占位") and tt._junk("t3") and not tt._junk("核验A1A2A3落地并取真实数字")


def test_sweep_clears_ghost_tables(td):
    d, a, sess = td
    doc = _mk("conv-A"); tid = doc["id"]
    ghost = {"id": "task-ghost0000001",
             "intent": "继续当前任务总览未完成行（看门狗补投·表 999-999999-999）：t1:x",
             "conv": "conv-F", "sess": sess, "created": "2026-10-11 00:00:00",
             "subtasks": [{"id": "t1", "goal": "核验", "skill": None, "status": "pending",
                           "lane": "fg", "res": []}]}
    tt._save(ghost)
    q = os.path.join(d, "task-ghost0000001.json")
    os.utime(q, (time.time() - 3600, time.time() - 3600))
    r = tt.sweep(20)
    assert "ghost0000001" in r, r
    assert not os.path.exists(q)
    swept = tt._load("task-ghost0000001")
    assert swept.get("swept") and swept["subtasks"][0]["status"] == "stopped"
    assert os.path.exists(os.path.join(d, tid + ".json")), "正常在途表不得误伤"


def test_sweep_keeps_fresh_and_real_tables(td):
    d, a, sess = td
    doc = _mk("conv-A")
    assert tt.sweep(20) == "清理补投残表/空转表 0 张"
    assert os.path.exists(os.path.join(d, doc["id"] + ".json"))


def test_free_pass_still_offered_for_simple_input(td):
    d, a, sess = td
    chains.ACTIVE["conv"] = "conv-G"
    assert "脚本未建" in tt.attach("今天天气如何")
    assert _files(d) == []


def test_no_table_hint_lists_my_open_table(td):
    d, a, sess = td
    doc = _mk("conv-A")
    chains.ACTIVE["conv"] = "conv-A"
    out = tt.attach("随便问一句")
    assert "禁止另开新表" in out and "核验A1A2A3" in out, out[:200]
    assert len(_files(d)) == 1


def test_sweep_detects_nudge_in_row_goal(td):
    """粗分常把补投整串塞进行目标（实测 repro 的新表 t1 goal 即补投原文）——intent 无标记也要认出来。"""
    d, a, sess = td
    ghost = {"id": "task-ghost0000002", "intent": "继续推进", "conv": "conv-H", "sess": sess,
             "created": "2026-10-11 00:00:00",
             "subtasks": [{"id": "t1", "skill": None, "status": "pending", "lane": "fg", "res": [],
                           "goal": "继续当前任务总览未完成行（看门狗补投·表 010-203014-118）：t6:核验四指标"}]}
    tt._save(ghost)
    q = os.path.join(d, "task-ghost0000002.json")
    os.utime(q, (time.time() - 3600, time.time() - 3600))
    r = tt.sweep(20)
    assert "ghost0000002" in r, r


def test_legit_table_from_nudge_steps_not_swept(td):
    """补投被粗分成有实义行的表（历史 08:00 三张即此类）＝真实工作记录，sweep 不得误删。"""
    d, a, sess = td
    doc = _mk("conv-A", steps="审计四张在途表未完成行的真实状态, 取证代码现状 shell_qt, 离线回归取真实数字")
    q = os.path.join(d, doc["id"] + ".json")
    os.utime(q, (time.time() - 7200, time.time() - 7200))
    assert tt.sweep(20) == "清理补投残表/空转表 0 张"
    assert os.path.exists(q)


def test_revise_ops_wired(td):
    d, a, sess = td
    doc = _mk("conv-A"); short = doc["id"][-14:]
    chains.ACTIVE["conv"] = "conv-B"
    assert "补投认领" in tt.revise("claim", "", "", _nudge(short))
    assert "清理" in tt.revise("sweep", "", "", "20")
    assert short in tt.revise("show", short, "", "")


def test_nudge_text_carries_claim_key_and_cap(td, monkeypatch):
    """qq_stall 侧：补投文案须带〔认领表 <尾14>〕键，且次数封顶后转 paused 不再刷屏。"""
    import qq_stall as qs
    d, a, sess = td
    doc = _mk("conv-A"); tid = doc["id"]; short = tid[-14:]
    cur = tt._load(tid); cur["src"] = "qq"; tt._save(cur)
    box = {}
    c = {"sms": d, "nudge": 1, "stall_repeat": 0, "nudge_max": 2}
    msgs = []
    monkeypatch.setattr(qs, "_pause", lambda doc, why, c: "PAUSED:" + why)
    import agent_stream as _A          # 真模块在场＝只换 ask（绝不允许真发网关）
    monkeypatch.setattr(_A, "ask", lambda text, on_line: msgs.append(text))
    for i in range(1, 4):
        r = qs.nudge(tt._load(tid), c, box)
        if i < 3:
            assert r == "nudge 已投", r
        else:
            assert str(r).startswith("PAUSED:"), r
    time.sleep(0.6)
    assert len(msgs) == 2, "补投次数须封顶（实投 %d）" % len(msgs)
    assert "〔认领表 " + short in msgs[0], "补投须携带原表尾号供 claim"
    assert "禁止为本消息另建新任务总览" in msgs[0]
