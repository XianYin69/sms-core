---
name: skill_scheduler
description: >
  技能调度中心：把用户意图拆为子任务并整合，五 lane（理解/拆分/注册/权限/整合）
  并发执行，进程式注册生命周期，权限门控写盘与执行。
license: MIT
metadata:
  category: meta
---

# skill_scheduler

使用 `skill_scheduler` skill 来完成用户请求。调度中心，像 OS 的 CPU + 进程表一样，把单个用户意图拆成子任务、并发调度、再整合结果。

## 输入

- 用户意图（字符串）。
- （可选）并发槽数 `--slots`，默认 = lane 数。

## 五 lane（任务字段，并发）

1. `understand` 理解意图（[task.py](../../scripts/task.py)）。
2. `decompose` 拆分子任务（task.py）。
3. `register` 进程式注册：spawn（[process.py](../../scripts/process.py)）。
4. `permit` 权限检查（[permissions.py](../../scripts/permissions.py)）。
5. `integrate` 整合子任务结果（task.py）。

## 输出

- `SMS/registry/scheduler.json`：slots + 各 lane 结果。
- register lane 随 `--write` 落盘（需已授予 write）；permit lane 只读报告 write 是否已授权。
- 契约 [scheduler.schema.json](../../schemas/scheduler.schema.json)。

## 脚本

- [scheduler.py](scripts/scheduler.py)：默认预览，`--write` 且已授予 write 才写盘；`--slots N` 指定并发槽。

## 红线

- 只写 `SMS/registry/` 与 `SMS/sessions/`；进程生命周期受权限门控；未指定路径的新建目录经 `resolve_home.temp` 落 `<SMS_HOME>/tmp/`，工程任务优先使用 `sandbox.py` 的 `<SMS_HOME>/tmp/sandbox/<id>`。
- 悬空链接 = 0；本文件 ≤ 50 行；SKILL.md 含 YAML frontmatter。