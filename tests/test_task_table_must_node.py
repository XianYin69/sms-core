#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_task_table_must_node.py — 批51「用户有明确指令或有处理复杂任务意图时，必须建立任务节点」回归钉。

用户诉求（2026-10-17）：「sms core 添加 当用户有明确指令或有处理复杂任务意图时 必须建立任务节点」。

真源：task_table.task_intent（明确指令/复杂任务意图判据）＋ plan() 门槛（批51：脚本判非复杂但 task_intent
命中＝必建任务节点，免模型裁量）；纯问句/闲聊/垃圾文本仍免表直送（宁缺勿滥与批47 摸鱼根治口径不变）。

覆盖：
1. 明确指令（单步·无执行技能命中）＝必建任务节点（旧行为免表）；
2. 复杂任务意图（多分句/顺序连词/计划性表述）＝必建；
3. 多步但无技能命中＝仍建（明确指令优先于「无技能命中」门槛）；
4. 纯问句/闲聊/垃圾＝免表直送，attach 仍注入〔脚本未建〕且提示必建规则；
5. attach() 对明确指令直接建节点（不再只给〔脚本未建〕提示）；
6. block() 执行规则含「建立任务节点是必须动作」。
跑法：pytest tests -q（全离线·不触网关不发 QQ·TD 用 tmp_path 隔离）。
"""
import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "skill", "scripts")
sys.path.insert(0, S)
import chains            # noqa: E402
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


def _files(d):
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json"))


# ---------------- ① 明确指令必建任务节点 ----------------
def test_explicit_single_step_builds_node(td):
    d, _ = td
    doc = tt.plan("帮我写一个部署脚本")
    assert doc is not None, "明确指令＝必须建立任务节点（旧行为脚本判单步免表）"
    assert len(doc["subtasks"]) >= 1
    assert _files(d) == [doc["id"]]


def test_explicit_no_skill_hit_still_builds(td):
    d, _ = td
    doc = tt.plan("把这两个文件合并成一个并按大小排序")
    assert doc is not None, "明确指令优先于「无执行技能命中」门槛＝仍必建任务节点"
    assert "合并成一个" in str(doc["subtasks"][0].get("goal"))


def test_explicit_imperative_verbs(td):
    d, _ = td
    doc = tt.plan("整理桌面文件并归档到对应文件夹")
    assert doc is not None
    assert doc["intent"] == "整理桌面文件并归档到对应文件夹"


# ---------------- ② 复杂任务意图必建任务节点 ----------------
def test_complex_multiclause_builds_node(td):
    d, _ = td
    doc = tt.plan("取证现有代码结构，设计树形字段方案，实现合并逻辑")
    assert doc is not None and len(doc["subtasks"]) == 3


def test_complex_sequence_builds_node(td):
    d, _ = td
    doc = tt.plan("先扫描目录，然后生成报告，最后推送通知")
    assert doc is not None, "顺序连词（先…然后…）＝复杂任务意图＝必建"


def test_complex_planning_words_builds_node(td):
    d, _ = td
    doc = tt.plan("制定一个完整的项目方案，覆盖多个阶段")
    assert doc is not None, "计划性/覆盖性表述＝复杂任务意图＝必建"


# ---------------- ③ 免表口径不变（纯问句/闲聊/垃圾） ----------------
def test_pure_question_still_free_pass(td):
    d, _ = td
    assert tt.plan("今天天气如何") is None
    assert _files(d) == []


def test_casual_chat_still_free_pass(td):
    d, _ = td
    chains.ACTIVE["conv"] = "conv-B"
    assert tt.plan("随便问一句") is None
    assert _files(d) == []


def test_junk_still_refused(td):
    d, _ = td
    assert tt.plan("010-203014-118", steps="noop") is None
    assert _files(d) == []


def test_attach_question_injects_must_rule(td):
    d, _ = td
    out = tt.attach("今天天气如何")
    assert "脚本未建" in out and "必须建立任务节点" in out, out[:200]
    assert _files(d) == [], "纯问句不得因新规则建表"


# ---------------- ④ attach 对明确指令直接建节点 ----------------
def test_attach_explicit_builds_node(td):
    d, _ = td
    out = tt.attach("帮我写一个部署脚本")
    assert "〔任务总览" in out and "脚本未建" not in out, out[:200]
    assert len(_files(d)) == 1


# ---------------- ⑤ 执行规则含必建口径 ----------------
def test_block_contains_must_rule(td):
    d, _ = td
    doc = tt.plan("把文档与配置口径同步到新的总览名称", "同步 scripts.md 登记, 更新子技能文档口径")
    blk = tt.block(doc)
    assert "建立任务节点是必须动作" in blk, blk[:200]
