#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_task_tree_batch48.py — 批48「任务表→任务总览·树形·同目的自动合并·跨层级并行」离线回归。

用户诉求（2026-10-11）：「任务表改名为任务总览·使用树形思想·所有任务都是根任务的延申·自动合并目的
相同的任务或者步骤·支持多个任务多个步骤和它们的子步骤并行发送处理和本地处理 sms core」。

实现真源：skill/scripts/task_tree.py（结构/归并/渲染/通道）＋ task_table.py（接线：_rows/_mkdoc/plan/
graft/_add/_remove/open_rows/guard_rows/block/op=tree/op=merge/op=conflict tree/op=run tree）＋
agent_task.run_tree（跨表跨层级并发批次·失败隔离）。旧表缺 root/parent/pid 一律按「自为根·顶层行」
处理＝零迁移向后兼容；批49：task.tree 开关退役·树为唯一设计（旧平铺口径废弃）。

覆盖：①表级树（首表自为根、目的不同自动认父、同目的 plan 并回原表不建新）；②步骤级合并（同义步骤去重、
非同义步骤并入并重新编号——撞号即静默丢行为已修的回归钉）；③op=add 挂父行（父行 id／目标内 t1：前缀／
parent=t1 三种写法）、父行不存在拒加、超层级拒加；④rollup（子行全 done→父行 done、子行回退→父行 pending）
与 open_rows/guard_rows 只认叶子行；⑤注入块改名〔任务总览〕＋根任务声明＋〔发〕〔本〕通道＋层级缩进；
⑥op=tree 渲染整棵树、op=conflict value=tree 跨表分组、task_res 互斥真把同写一文件的行拆到不同批；
⑦op=merge 表级并表（原表归档、行状态与 result 一字不动）；⑧批47 回归不破（补投认领新旧措辞都认、
noop/纯表号拒建、免表列出在途并禁开新表）；⑨sweep 清表时子表改挂父表（不留悬空 parent）。
跑法：pytest tests -q（全离线·不触网关不发 QQ·TD 用 tmp_path 隔离）。
"""
import os
import sys
import json
import time
import types
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "skill", "scripts")
sys.path.insert(0, S)
import chains            # noqa: E402
import task_tree as T    # noqa: E402
import task_res as tr    # noqa: E402
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


def files(d):
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json"))


def A1(td):
    return tt.plan("把任务总览改造成树形并支持同目的自动合并", "取证现有代码结构, 设计树形字段方案, 实现合并逻辑")


# ---------------- ① 表级树 ----------------
def test_first_table_is_root(td):
    d, _ = td
    doc = A1(td)
    assert doc and len(doc["subtasks"]) == 3
    assert doc["root"] == doc["id"] and not doc.get("parent"), "首表须自为根"
    assert all("pid" in x and "k" in x for x in doc["subtasks"]), "行须带树字段"


def test_second_table_adopts_parent(td):
    d, _ = td
    a = A1(td)
    b = tt.plan("把文档与配置口径同步到新的总览名称", "同步 scripts.md 登记, 更新子技能文档口径")
    assert b["parent"] == a["id"] and b["root"] == a["id"], "目的不同的后建任务＝根任务的延申"
    assert len(files(d)) == 2


def test_same_intent_merges_instead_of_new_table(td):
    d, _ = td
    a = A1(td); n0 = len(files(d))
    c = tt.plan("把任务总览改造成树形并支持同目的自动合并（补充核验）", "取证现有代码结构, 设计一套界面配色规范草案")
    assert c["id"] == a["id"], "同目的诉求必须并回原总览（旧版在此建新表＝雪球根因）"
    assert len(files(d)) == n0, "同目的一律不得新建表"


# ---------------- ② 步骤级自动合并 ----------------
def test_step_dedup_and_append(td):
    d, _ = td
    a = A1(td)
    tt.plan("把任务总览改造成树形并支持同目的自动合并（补充核验）", "取证现有代码结构, 设计一套界面配色规范草案")
    doc = tt._load(a["id"])
    assert sum(1 for x in doc["subtasks"] if "取证" in x["goal"]) == 1, "同义步骤必须去重"
    assert len(doc["subtasks"]) == 4, "非同义步骤须并入（3→4 行）"
    kid = next(x for x in doc["subtasks"] if "配色" in x["goal"])
    assert kid["id"] == "t4", "并入行必须重新编号（与既有 t# 撞号即 DFS 静默丢行）"
    assert kid.get("merged_at"), "并进行须留 merged_at 痕"


def test_dedup_marks_also(td):
    d, _ = td
    a = A1(td)
    tt.revise("add", a["id"][-14:], "", "取证现有代码结构")
    doc = tt._load(a["id"])
    row = next(x for x in doc["subtasks"] if x["id"] == "t1")
    assert row.get("also"), "同目的行须记同义表述（不新增重复行）"


# ---------------- ③ op=add 挂父行 ----------------
def test_add_under_parent(td):
    d, _ = td
    a = A1(td)
    tt.revise("add", a["id"][-14:], "t1", "拆细子骤甲：核验旧表字段兼容性")
    doc = tt._load(a["id"])
    row = next(x for x in doc["subtasks"] if "核验旧表字段兼容性" in x["goal"])
    assert row["pid"] == "t1" and T.depth(doc, row) == 2
    tt.revise("add", a["id"][-14:], "", "t1：拆细子骤乙：核验注入块缩进渲染")
    doc = tt._load(a["id"])
    assert any(x["pid"] == "t1" and "缩进渲染" in x["goal"] for x in doc["subtasks"]), "目标内写 t1：也须挂父"


def test_add_bad_parent_and_junk(td):
    d, _ = td
    a = A1(td)
    assert "不存在" in tt.revise("add", a["id"][-14:], "t99", "挂在不存在的父行下的测试步骤")
    assert len(tt._load(a["id"])["subtasks"]) == 3, "父行不存在＝整条拒绝，不得留下孤儿行"
    assert "加行失败" in tt.revise("add", a["id"][-14:], "", "noop")


# ---------------- ④ rollup 与守卫只认叶子行 ----------------
def test_rollup_parent_state(td):
    d, _ = td
    a = A1(td)
    tt.revise("add", a["id"][-14:], "t1", "子骤甲：核验字段兼容旧表结构")
    tt.revise("add", a["id"][-14:], "t1", "子骤乙：核验渲染树形缩进口径")
    doc = tt._load(a["id"])
    assert "t1" not in [x["id"] for x in tt.open_rows(doc)], "父行是汇总节点，不计入待办"
    for k in T.kids(doc, "t1"):
        k["status"] = "done"
    tt._save(doc); doc = tt._load(a["id"])
    par = next(x for x in doc["subtasks"] if x["id"] == "t1")
    assert par["status"] == "done" and par.get("agg") == "rollup", "子行全 done → 父行自动 done"
    kid = T.kids(doc, "t1")[0]
    next(x for x in doc["subtasks"] if x["id"] == kid["id"])["status"] = "pending"
    tt._save(doc); doc = tt._load(a["id"])
    assert next(x for x in doc["subtasks"] if x["id"] == "t1")["status"] == "pending", "子行回退 → 父行自动 pending"


def test_guard_rows_only_leaves(td):
    d, _ = td
    a = A1(td)
    tt.revise("add", a["id"][-14:], "t2", "子骤：核验 eta 只算叶子行")
    doc = tt._load(a["id"])
    leaf = {x["id"] for x in T.leaves(doc)}
    assert all(x["id"] in leaf for x in tt.open_rows(doc))
    assert all(x["id"] in leaf for x in tt.guard_rows(doc, True))
    assert tt.eta(doc) >= 0


# ---------------- ⑤ 注入块改名＋树形渲染 ----------------
def test_block_renamed_and_tree_shaped(td):
    d, _ = td
    a = A1(td)
    tt.revise("add", a["id"][-14:], "t1", "子骤：核验层级缩进")
    blk = tt.block(tt._load(a["id"]))
    assert "〔任务总览" in blk and "〔任务表" not in blk, "注入块标题须改名任务总览"
    assert "根任务" in blk, "块内须声明根任务"
    assert "所有任务都是根任务的延申" in blk
    assert "〔发〕" in blk and "〔本〕" in blk, "须写明发送处理／本地处理双通道"
    assert any("└" in l or l.startswith("        ") for l in blk.splitlines()), "行须按层级缩进渲染"


def test_op_tree_renders_whole_overview(td):
    d, _ = td
    a = A1(td)
    b = tt.plan("把文档与配置口径同步到新的总览名称", "同步 scripts.md 登记, 更新子技能文档口径")
    out = tt.revise("tree", b["id"][-14:])
    assert "根任务" in out and "延申任务" in out, "op=tree 须渲染整棵树"
    assert "把任务总览改造成树形" in out and "把文档与配置口径同步" in out, "批49：树视图以目的文本标识任务"
    assert a["id"][-14:] not in out and b["id"][-14:] not in out, "批49：任务不编号——树视图不出现表编号"


# ---------------- ⑥ 跨任务·跨层级并行分组 ----------------
def test_conflict_tree_and_batches(td):
    d, _ = td
    a = A1(td)
    b = tt.plan("把文档与配置口径同步到新的总览名称", "同步 scripts.md 登记, 更新子技能文档口径")
    cf = tt.revise("conflict", a["id"][-14:], "", "tree")
    assert ("批1" in cf) or ("无冲突" in cf), cf[:200]
    rows = [r for dd in T.tree_of(a) for r in (dd.get("subtasks") or []) if T.is_leaf(dd, r)]
    for r in rows:
        r["res"] = sorted(tr.resources(r["goal"], r.get("skill") or "")[0])
    flat, text = T.plan_batches([(None, r) for r in rows])
    assert isinstance(flat, list) and "并行度上限" in text
    x = [{"id": "a1", "goal": "改代码 files=same.py", "status": "pending"},
         {"id": "a2", "goal": "再改代码 files=same.py", "status": "pending"}]
    assert len(tr.batches(x)) == 2, "同写一文件的行必须拆到不同批（互斥真生效）"
    y = [{"id": "b1", "goal": "读甲 files=one.py", "status": "pending"},
         {"id": "b2", "goal": "读乙 files=two.py", "status": "pending"}]
    assert len(tr.batches(y)) == 1, "互不冲突的行必须同批并发"
    assert b["root"] == a["id"]


def test_run_tree_only_mine(td):
    """整棵树并发执行：只动本对话的表，他对话表须拒改（批32 边界不因并行放松）。"""
    d, _ = td
    a = A1(td)
    doc = tt._load(a["id"])
    for x in doc["subtasks"]:
        x["status"] = "done"; x["result"] = "x"
    tt._save(doc)
    other = {"id": "task-20990101-000000-001", "intent": "他对话的表", "conv": "conv-B", "sess": "sess-A",
             "created": "2026-10-11 00:00:00", "table": "task_table", "root": a["id"], "parent": a["id"],
             "subtasks": [{"id": "t1", "goal": "他人未完成步骤核验内容", "skill": None, "status": "pending",
                           "lane": "fg", "pid": "", "res": []}]}
    tt._save(other)
    import agent_task as atk
    r = atk.run_tree(tt._load(a["id"]))
    assert "无可执行" in r or "未代改" in r, r[:200]
    assert tt._load("task-20990101-000000-001")["subtasks"][0]["status"] == "pending", "他对话行状态不得被改"


# ---------------- ⑦ 表级并表 ----------------
def test_op_merge_tables(td):
    d, _ = td
    a = A1(td)
    b = tt.plan("把文档与配置口径同步到新的总览名称", "同步 scripts.md 登记, 更新子技能文档口径")
    doc = tt._load(b["id"])
    doc["subtasks"][0]["status"] = "done"; doc["subtasks"][0]["result"] = "已同步登记口径"
    tt._save(doc)
    n_before = len(tt._load(a["id"])["subtasks"])
    m = tt.revise("merge", a["id"][-14:], "", b["id"][-14:])
    assert "并入" in m, m[:160]
    doc = tt._load(a["id"])
    assert len(doc["subtasks"]) == n_before + 2, "并表须把对方全部行搬进来"
    assert not os.path.exists(os.path.join(d, b["id"] + "json")) or b["id"] not in files(d), "被并表须移出在途"
    moved = [x for x in doc["subtasks"] if x.get("from")]
    assert moved and all(x["status"] == "done" or x["status"] in ("pending", "skipped") for x in moved), "行状态一字不改"
    done = [x for x in moved if x.get("result")]
    assert done and done[0]["result"] == "已同步登记口径", "已完成行的 result 必须原样保留（不改工作成果）"


# ---------------- ⑧ 批47 回归不破 ----------------
def test_claim_still_works_both_wordings(td):
    d, _ = td
    a = A1(td); short = a["id"][-14:]; n0 = len(files(d))
    chains.ACTIVE["conv"] = "conv-C"
    new_w = ("继续当前任务总览未完成行（看门狗补投·表 %s）：t1:取证\n〔认领表 %s〕先 task_plan op=claim value=%s 接管该原表。"
             % (short, short, short))
    out = tt.attach(new_w)
    assert "补投认领" in out and len(files(d)) == n0, out[:150]
    old_w = "继续当前任务表未完成行（看门狗补投·表 %s）：t1:取证〔认领表 %s〕" % (short, short)
    assert "补投认领" in tt.attach(old_w), "旧「任务表」措辞必须继续认（历史补投文本/旧技能文案仍在流通）"


def test_junk_and_free_pass_unchanged(td):
    d, _ = td
    assert tt.plan("010-203014-118", steps="noop") is None
    A1(td)                                   # 表属 conv-A（fixture 设的）
    chains.ACTIVE["conv"] = "conv-D"
    assert "脚本未建" in tt.attach("今天天气如何")
    assert "禁止另开新表" not in tt.attach("随便问一句"), "他对话的表不得被列为可续推（批32 边界）"
    chains.ACTIVE["conv"] = "conv-A"
    assert "禁止另开新表" in tt.attach("随便问一句"), "本对话在途总览必须列出并禁开新表"


# ---------------- ⑨ 树完整性 ----------------
def test_tree_only_live_tables(td):
    d, _ = td
    a = A1(td)
    b = tt.plan("把文档与配置口径同步到新的总览名称", "同步 scripts.md 登记, 更新子技能文档口径")
    assert len(T.tree_of(a)) == 2
    doc = tt._load(b["id"])
    for x in doc["subtasks"]:
        x["status"] = "done"
    tt._save(doc)                       # 全行 done → 自动归档
    assert len([x for x in T.tree_of(tt._load(a["id"])) if x["id"] == b["id"]]) == 0, "归档表不得再进树（防幽灵步骤）"


def test_sweep_adopts_children(td):
    d, a_ = td
    ghost = {"id": "task-ghost0000009", "intent": "继续当前任务总览未完成行（看门狗补投·表 999-999999-999）：t1:x",
             "conv": "conv-E", "sess": "sess-A", "created": "2026-10-11 00:00:00", "table": "task_table",
             "root": "task-ghost0000009", "parent": None,
             "subtasks": [{"id": "t1", "goal": "核验", "skill": None, "status": "pending", "lane": "fg", "pid": "", "res": []}]}
    tt._save(ghost)
    child = {"id": "task-ghost0000010", "intent": "真实后续步骤内容", "conv": "conv-E", "sess": "sess-A",
             "created": "2026-10-11 00:00:01", "table": "task_table", "root": "task-ghost0000009",
             "parent": "task-ghost0000009",
             "subtasks": [{"id": "t1", "goal": "核验渲染口径", "skill": None, "status": "pending", "lane": "fg", "pid": "", "res": []}]}
    tt._save(child)
    q = os.path.join(d, "task-ghost0000009.json")
    os.utime(q, (time.time() - 3600, time.time() - 3600))
    r = tt.sweep(20)
    assert "ghost0000009" in r, r
    c2 = tt._load("task-ghost0000010")
    assert not c2.get("parent"), "父表被清理时子表 parent 须上移，不留悬空指针"
    assert c2["root"] == "task-ghost0000010"


# ---------------- ⑩ 开关与兼容 ----------------
def test_tree_always_on_batch49(td, monkeypatch):
    d, _ = td
    monkeypatch.setattr(T, "on", lambda: False)  # 批49：task.tree 开关退役——_tree_on 只认 task_tree 可导入
    a = A1(td)
    assert a["root"] == a["id"], "首表仍自为根"
    blk = tt.block(a)
    assert "〔任务总览" in blk and "根任务 " in blk, "批49：树为唯一设计·照常渲染根任务声明"
    assert a["id"] not in blk and a["id"][-14:] not in blk, "批49：任务不编号——注入块不出现表编号"
    assert "所有任务都是根任务的延申" in blk


def test_old_tables_without_tree_fields(td):
    d, _ = td
    old = {"id": "task-legacy0000001", "intent": "旧版建的历史表", "conv": "conv-A", "sess": "sess-A",
           "created": "2026-10-10 00:00:00", "table": "task_table",
           "subtasks": [{"id": "t1", "goal": "历史步骤一", "skill": None, "status": "pending", "lane": "fg"},
                        {"id": "t2", "goal": "历史步骤二", "skill": None, "status": "done", "lane": "fg"}]}
    tt._save(old)
    doc = tt._load("task-legacy0000001")
    assert [x["id"] for x in tt.open_rows(doc)] == ["t1"], "缺 pid/root/parent 的旧表必须照旧可用"
    assert tt.eta(doc) >= 0
    assert "历史步骤一" in tt.block(doc)


# ---------------- ⑪ 双通道：〔发〕发送处理 × 〔本〕本地处理（run_skill 打桩不外派） ----------------
def test_chan_classification(td):
    d, _ = td
    a = A1(td)
    doc = tt._load(a["id"])
    doc["subtasks"][0]["skill"] = "python-expert"
    doc["subtasks"][1]["skill"] = None
    assert T.chan(doc["subtasks"][0]) == "send", "行有技能＝发送处理（派对等对话）"
    assert T.chan(doc["subtasks"][1]) == "local", "无技能＝本地处理（本对话工具自办）"
    assert T.chan({"goal": "写报告 files=a.py self=1", "skill": "python-expert"}) == "local", "self= 强制本地"
    assert T.chan({"goal": "随便一步", "manual": "send"}) == "send", "manual=send 强制派发"


def test_run_tree_splits_send_and_local(td, monkeypatch):
    """op=run value=tree：只把〔发〕行交并发批次派发，〔本〕行不自动外派（同轮交回模型自办）。"""
    d, _ = td
    import agent_task as atk
    calls = []
    stub = types.SimpleNamespace(
        run_skill=lambda name, goal, tag="": (calls.append(("send", name)) or "〔桩〕派发完成"),
        ask=lambda q: (calls.append(("ask",)) or "〔桩〕本地问答完成"),
        emit=lambda *a, **k: None)
    monkeypatch.setattr(atk, "at", stub)
    a = tt.plan("给双通道并行做一次离线实演", "派技能写一份验收报告 skill=python-expert, 读本地文件取真实行数")
    doc = tt._load(a["id"])
    doc["subtasks"][0]["skill"] = "python-expert"
    doc["subtasks"][1]["skill"] = None
    tt._save(doc)
    r = atk.run_tree(tt._load(a["id"]), wait=True)
    assert "并发批次完成" in r, r[:200]
    assert len([c for c in calls if c[0] == "send"]) >= 1, "发送处理行必须被派发"
    assert not any(c[0] == "ask" for c in calls), "本地处理行不得被自动外派（同轮由模型自办）"
    disk = tt._load(a["id"])
    assert str(disk["subtasks"][0]["status"]) in ("done", "error"), "派发完的行状态须回写"


def test_run_tree_all_local_no_dispatch(td, monkeypatch):
    d, _ = td
    import agent_task as atk
    calls = []
    monkeypatch.setattr(atk, "at", types.SimpleNamespace(
        run_skill=lambda n, g, tag="": calls.append(1), ask=lambda q: calls.append(1),
        emit=lambda *a, **k: None))
    b = tt.plan("纯本地处理的一次实演丙", "本地读文件甲 reads=x1.json, 本地读文件乙 reads=x2.json")
    doc = tt._load(b["id"])
    for x in doc["subtasks"]:
        x["skill"] = None
    tt._save(doc)
    r = atk.run_tree(tt._load(b["id"]), wait=True)
    assert calls == [], "全本地行＝一次都不派发"
    assert "本地" in r, r[:160]


def test_own_save_does_not_clobber(td):
    """批48 并发写盘保护：后台线程落盘只覆盖自己负责的行，模型同轮改的其他行不被整表覆盖抹掉。"""
    d, _ = td
    import agent_task as atk
    a = A1(td)
    base = tt._load(a["id"])
    stale = json.loads(json.dumps(base))            # 后台线程手上的旧快照
    stale["subtasks"][1]["status"] = "pending"
    cur = tt._load(a["id"])
    cur["subtasks"][1]["status"] = "running"        # 模型同轮把该行置 running 落盘
    tt._save(cur)
    atk._own_save(stale, {str(base["subtasks"][0]["id"])})
    disk = tt._load(a["id"])
    assert disk["subtasks"][1]["status"] == "running", "_own_save 不得抹掉非负责行的磁盘值"


def test_op_run_wait_flag(td, monkeypatch):
    """op=run 的值写 tree:wait＝同步等批次；写 tree＝异步（立刻返回不阻塞前台收口）。"""
    d, _ = td
    import agent_task as atk
    seen = {}
    monkeypatch.setattr(atk, "run_tree", lambda doc, wait=False: seen.update(wait=wait) or "OK")
    a = A1(td)
    tt.revise("run", a["id"][-14:], "", "tree:wait")
    assert seen.get("wait") is True, seen
    tt.revise("run", a["id"][-14:], "", "tree")
    assert seen.get("wait") is False, seen
