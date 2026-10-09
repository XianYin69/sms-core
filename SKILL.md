---
name: smsystem-suit
description: >
  技能操作系统（SMS）：读取固定路径注册表，识别用户意图，按日期建会话五元组
  （对话/用户链/逻辑链/技能/权限），五 lane 并发拆分·整合与进程注册、权限门控，
  支持错误自愈、本地/云端安装、多客户端同步与信任链审查；并提供时区地区检查、
  正反双辩论逻辑链、命令系统（help/intent/show/use）、删除 skill 与子技能回主接口。
license: MIT
metadata:
  category: meta
---

# smsystem-suit

使用 `smsystem-suit` skill 来完成用户请求。Agent 工具的技能操作系统：发现 → 打包 → 连接 → 拆分 → 并发调度 → 进程注册 → 权限门控 → 整合。

## 固定路径 SMS

- 解析顺序：env `SMS_HOME` → 用户缓存目录（Windows `%LOCALAPPDATA%` · macOS `~/Library/Caches` · Linux `~/.cache`，缺省回退 `~/SMS`）→ 用户根目录；统一建 `SMS/`（实现 [scripts/resolve_home.py](scripts/resolve_home.py)，覆盖见 [config/config.example.json](config/config.example.json)）。

## 运行流程

1. 解析 SMS_HOME，读 `SMS/registry/register.json`（含信任标签）；[locality.py](scripts/locality.py) 检查时区/地区 → `registry/locality.json` 供会话读取。
2. 缺失 → 初始设置：[init_registry.py](scripts/init_registry.py) 跑 register → pack → connect。
3. 识别意图，[session.py](scripts/session.py) 建 `SMS/sessions/<日期>/` 五元组（dialogue/user_chain/logic_chain/skills/permissions）。
4. 数据写盘前先授权：`permissions.py grant write`（默认只读，未授予 emit 拒绝落盘）。
5. 拆分·整合（[task.py](scripts/task.py)）+ 五 lane 并发（[scheduler.py](scripts/scheduler.py)）+ 进程生命周期（[process.py](scripts/process.py)）。
6. 调度目标技能：[skill_executor](sub_skills/skill_executor/SKILL.md) 用 [dispatch.py](scripts/dispatch.py) 规划；每条 `return_to=sms`——子技能运行完回到 SMS 整合，不得直接回复用户；无匹配 → [bootstrap.py](scripts/bootstrap.py) 拉取（network+write）。
7. 治理：按天缓存清理（[cache_cleanup.py](scripts/cache_cleanup.py)）；emit 会话写盘后自动压缩上下文（[auto_compress.py](scripts/auto_compress.py)）。
8. 错误自愈：[skill_errors.py](scripts/skill_errors.py) 记录出错位置；未解决 ≥3 → 提示 self_update 修复，`resolve` 销账。
9. 安装：[install.py](scripts/install.py) 本地或 `gh:owner/repo[/sub]` 装入客户端 skills；云端需 network+write 且 `--accept-download` 用户确认下载，标 pending_review。
10. 同步与信任：[sync_skills.py](scripts/sync_skills.py) hub pull/push/status；[trust.py](scripts/trust.py) 云端必审、本地抽查，fail → quarantine。
11. 决策审查：[debate.py](scripts/debate.py) 对论断生成 pro/con 正反双链 + verdict → `sessions/<日期>/debate.json`。
12. 命令系统：[commands.py](scripts/commands.py) 汇总内置与暴露接口 → `registry/commands.json`，`help/intent/show/use` 查看与调用。
13. 删除：[remove.py](scripts/remove.py) `--yes --write` 从客户端/hub 移除 skill（默认预览，拒删受保护本体）。

## 子技能

- [skill_register](sub_skills/skill_register/SKILL.md) · [skill_packer](sub_skills/skill_packer/SKILL.md) · [skill_connector](sub_skills/skill_connector/SKILL.md) · [skill_scheduler](sub_skills/skill_scheduler/SKILL.md) · [skill_executor](sub_skills/skill_executor/SKILL.md)

## 数据契约与脚本

- schemas/：register · interfaces · connections · session · task · process · scheduler · dispatch · memory · trust · error · [locality](schemas/locality.schema.json) · [debate](schemas/debate.schema.json) · [commands](schemas/commands.schema.json)
- [scripts/scripts.md](scripts/scripts.md)：resolve_home / emit / bootstrap / register / pack / connect / session / init_registry / task / process / permissions / scheduler / dispatch / memory_list / cache_cleanup / auto_compress / trust / skill_errors / install / sync_skills / locality / debate / commands / remove

## 红线

- 不得删除 [resistance/](resistance/resistance.md) 约束；SMS 运行时数据不进 skill 本体目录；子技能运行完必须回到 SMS。
- 悬空链接 = 0；所有 .md / 脚本 ≤ 50 行；SKILL.md 含 YAML frontmatter。
- 数据写盘经 emit 门控（--write 才写）；云端下载须 network+write 且用户确认；删除须 --yes。
