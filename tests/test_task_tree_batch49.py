#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_task_tree_batch49.py — 批49「只给任务树下的子节点分配编号·任务完全不编号·旧任务表设计废弃」离线回归钉。
用户诉求（2026-10-11）：「只给任务树下的子节点分配编号 任务数完全不编号 完全废弃以前的任务表设计 完全使用现在的任务树设计」。
真源：task_tree.py nummap/label/resolve＋渲染去表号；task_table.py _tree_on 只认导入·block/pending/emit/next 不出现表编号·
revise/_add 行引用认层级号。跑法：pytest tests -q（全离线·TD 用 tmp_path 隔离）。"""
import os
import sys
import pytest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "skill", "scripts")
sys.path.insert(0, S)
import chains            # noqa: E402
import task_tree as T    # noqa: E402
import task_table as tt  # noqa: E402


@pytest.fixture()
def td(tmp_path, monkeypatch):
    d = str(tmp_path / "tasks"); a = str(tmp_path / "arch")
    os.makedirs(d, exist_ok=True); os.makedirs(a, exist_ok=True)
    monkeypatch.setattr(tt, "TD", d); monkeypatch.setattr(tt, "AD", a)
    saved = dict(chains.ACTIVE)
    chains.ACTIVE["conv"] = "conv-A"; chains.ACTIVE["sess"] = "sess-A"
    yield d, a
    chains.ACTIVE.clear(); chains.ACTIVE.update(saved)


def _doc():
    return {"id": "task-x000000000001", "intent": "编号制回归", "subtasks": [
        {"id": "t1", "goal": "步骤甲", "pid": "", "status": "pending"},
        {"id": "t2", "goal": "步骤乙", "pid": "", "status": "pending"},
        {"id": "t3", "goal": "乙之子", "pid": "t2", "status": "pending"},
        {"id": "t4", "goal": "乙之孙", "pid": "t3", "status": "pending"}]}


def test_on_always_true():
    assert T.on() is True, "批49：task.tree 开关退役·树为唯一设计"


def test_nummap_hierarchical():
    assert T.nummap(_doc()) == {"t1": "1", "t2": "2", "t3": "2.1", "t4": "2.1.1"}


def test_label_and_resolve():
    d = _doc()
    assert T.label(d, d["subtasks"][2]) == "2.1"
    assert T.resolve(d, "2.1")["id"] == "t3"
    assert T.resolve(d, "t3")["id"] == "t3"
    assert T.resolve(d, "9.9") is None


def test_rowline_shows_number_not_internal_id():
    d = _doc()
    ln = T.rowline(d, d["subtasks"][2])
    assert "2.1" in ln and "t3" not in ln, ln


def test_render_overview_no_task_number(td):
    d, _ = td
    doc = tt.plan("编号制改造整体验收", "核验层级编号渲染是否成行, 核验表级不编号口径是否落地")
    txt = T.render(doc)
    assert "〔任务总览〕" in txt
    assert doc["id"] not in txt and doc["id"][-14:] not in txt, "任务不编号——渲染不出现表编号"
    out = T.overview(doc)
    assert doc["id"][-14:] not in out and "根任务 " in out


def test_block_pending_no_tid(td):
    d, _ = td
    doc = tt.plan("编号制注入块验收", "核验注入块标题不带表号是否可行, 核验守卫行以目的文本标识是否落地")
    blk = tt.block(doc)
    assert doc["id"] not in blk and doc["id"][-14:] not in blk
    assert "批49 编号制" in blk
    pend = tt.pending("conv-A")
    assert doc["id"][-14:] not in pend and "编号制注入块验收" in pend


def test_revise_status_by_hier_number(td):
    d, _ = td
    doc = tt.plan("层级编号引用验收", "父步骤：承载子步骤挂载点角色, 另一独立步骤隔离无关活")
    tt.revise("add", doc["id"][-14:], "1", "细查层级号引用解析是否可行")
    doc = tt._load(doc["id"])
    kid = next(x for x in doc["subtasks"] if "层级号引用解析" in x["goal"])
    assert kid["pid"] == "t1"
    r = tt.revise("status", doc["id"][-14:], T.label(doc, kid), "done")
    assert "done" in r, r
    assert next(x for x in tt._load(doc["id"])["subtasks"] if x["id"] == kid["id"])["status"] == "done"


def test_add_goal_prefix_and_parent_eq(td):
    d, _ = td
    doc = tt.plan("目标内层级号挂父验收", "父步骤：承载挂载点角色用, 另一独立步骤隔离杂务")
    tt.revise("add", doc["id"][-14:], "1", "子步骤：作为中间层节点存在")
    doc = tt._load(doc["id"])
    kid = next(x for x in doc["subtasks"] if "中间层节点" in x["goal"])
    assert kid["pid"] == "t1"
    tt.revise("add", doc["id"][-14:], "", "1.1：孙步骤：目标内层级号写法挂父")
    doc = tt._load(doc["id"])
    gd = next(x for x in doc["subtasks"] if "目标内层级号写法挂父" in x["goal"])
    assert gd["pid"] == kid["id"]
    tt.revise("add", doc["id"][-14:], "", "parent=1 旁支步骤：等号写法解析单段编号")
    doc = tt._load(doc["id"])
    g2 = next(x for x in doc["subtasks"] if "等号写法解析单段编号" in x["goal"])
    assert g2["pid"] == "t1"


def test_add_bad_hier_parent_rejected(td):
    d, _ = td
    doc = tt.plan("层级号拒加验收", "步骤一：核验不存在编号被拒加, 步骤二：隔离无关步骤项")
    r = tt.revise("add", doc["id"][-14:], "7.7", "挂在不存在的层级号下的步骤")
    assert "不存在" in r, r
