---
name: task_table
description: >
  任务拆分与任务表制表器子技能：脚本标点粗分作「自动种子」——仅复杂任务（拆步≥2且至少一步命中执行性技能）
  送网关前自动建种子表（task_table.py·特定步骤经 skill_route 指定特定 skill·行数无上限·模型首轮据实改表），
  落 <SMS_HOME>/tasks/<id>.json 供右栏任务表与顶栏进度条/剩余时间预测（latency 反应时间均值×未完成行预测）；
  模型每步完成经 task_plan 工具置行 done，中途发现表不合理同径 add/remove/skill 改表；
  批18 主流程守卫：pending(conv) 供 gateway 检测未完成行·禁止收口并注入续推提示（批23 对等对话：收口＝形式停止非实质完成·每派发自开独立 conv·未完成行由调度方或监视到它的对话续推）；无依赖子任务 task 工具并发（parallel=true·模型判定无冲突才并发·有依赖 parallel=false 依序）；
  批22 模型裁量：脚本判简单时仍注入〔任务表·脚本未建〕——复杂与否由模型定，判多步即 task_plan op=plan（或 task_table.py new <步骤逗号分隔>）自建表·用户无须写「制表」；开关 task.auto_table 与 task.auto_continue（F4）。
license: MIT
metadata:
  category: meta
  kind: sub_skill
---

# task_table — 任务拆分与任务表制表器

使用 `task_table` skill 来完成用户请求。SMS 的**制表**子技能：把「该拆步骤、该派技能、该看进度」的诉求收拢为一张任务表（真源 `<SMS_HOME>/tasks/<id>.json`），执行仍由网关工具循环按表推进、由 SMS 整合收口。

## 何时建表 / 免表

- 自动种子表（＝脚本判复杂·批14 用户指示「不是什么都建表」）：标点拆步≥2 **且**至少一步命中执行性技能（route 非 general_answer/constraint_arbiter）。
- 脚本判简单（单步/纯问答/无执行技能命中）＝不建表，但批22 注入〔任务表·脚本未建〕一行——复杂与否由模型判，**用户无须写出「制表」字样**；模型判多步动手即 `task_plan op=plan value=步骤逗号分隔`（或 `task_table.py new "<步骤>"`）自建表；纯问答/单步免表直送。
- 开关：`:config set task.auto_table false` 关自动制表（task_plan/手改仍可用）。

## 用法

```
python -B skill/scripts/task_table.py plan "<诉求>"        # 脚本粗分自动种子建表（输出〔任务表〕块）
python -B skill/scripts/task_table.py new "<步骤1，步骤2…>"  # 模型裁量自建表（批22·免标点门控）
python -B skill/scripts/task_table.py show <表id>          # 看行与状态
python -B skill/scripts/task_table.py next <表id>          # 下一个未完成行
python -B skill/scripts/task_table.py eta <表id>           # 剩余时间预测
python -B skill/scripts/task_table.py status <表id> t2 done
python -B skill/scripts/task_table.py add <表id> "<补漏步骤目标>"   # 自动路由指定技能
python -B skill/scripts/task_table.py remove <表id> t3 | skill <表id> t2 <技能id>   # 删行/改派（壳内 :task 同参数手改）
```

## 接线

- 建表口：[agent_stream.py](../../scripts/agent_stream.py) 原生网关分支 `attach()`＝话语前注入〔任务表〕块＋执行规则。
- 工具口：[agent_dispatch.py](../../scripts/agent_dispatch.py) `task_plan`（op=plan/new 建表＋show/next/eta/add/remove/status/skill·tid plan 免填）→ [gateway.py](../../scripts/gateway.py) SYS「按表推进·改表不绕表·复杂与否模型判」＋批18 主流程守卫（`tt.pending(conv)` 检测未完成行·depth==0 时禁止收口并注入续推·`task.auto_continue`/`task.max_continue` 控）。
- 进度/预测：[msg_flow.py](../../scripts/msg_flow.py) task 信封 meta（done/total/eta_s）→ 顶栏 `shell_tui_index._taskbar` 进度条＋右栏 [shell_tui_tasks.py](../../scripts/shell_tui_tasks.py) 表；均值样本来自 [latency.py](../../scripts/latency.py)。
- task 工具（[agent_task.py](../../scripts/agent_task.py)）与本表同 schema 同库，命中多技能话语由 SMS 直接经其并行派发并建表。

## 红线

- 改表唯一经本制表器（add/remove/status/skill 均落同一真源并重发进度信封），模型与用户不得旁改 JSON。
- 拆步不越权：行只是「目标＋指定技能」，执行仍按各技能自身门禁（grant/预览/stop）。
- 悬空链接 = 0；本文件 ≤ 50 行；SKILL.md 含 YAML frontmatter。
