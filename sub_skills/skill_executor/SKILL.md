---
name: skill_executor
description: >
  Agent 工具调度员：读取当前 task 与 registry，把每个子任务映射到技能与工具集，
  按 permissions.json 门控逐项调用 agent 工具，并把结果回填 dispatch.json。
license: MIT
metadata:
  category: meta
---

# skill_executor

使用 `skill_executor` skill 来完成用户请求。调度执行器：像 OS 的系统调用分发器一样，把 SMS 的 subtask 映射到具体的 agent 工具调用。

## 输入

- `SMS/sessions/<日期>/task.json`（子任务列表）
- `SMS/registry/register.json`（技能 id 与其所用 agent 工具 tools）
- `SMS/sessions/<日期>/permissions.json`（read/write/execute/network grants）

## 步骤

1. `dispatch.py` 依据 register 的 tools 生成 `dispatches[]`（每 subtask → skill_id + tools + requires）。
2. Agent 按 `dispatches[i]` 顺序调用：
   - `needs_new=true` → 转 bootstrap / Skill_Generator 新建后重新登记。
   - 否则按 `tools[]` 调用对应 agent 工具。
   - 需新建目录且用户未指定路径 → 调用 `../../scripts/resolve_home.py temp <name> --mkdir`，目录必须落 `<SMS_HOME>/tmp/`。
   - 需完整工程沙盒 → 调用 `../../scripts/sandbox.py create --name <task>`；交付用 `deliver --id I --to P --yes --write`，清理用 `clean --id I --yes`。
3. 调用前按工具→权限映射核对 grants（未授予则拒绝并记 audit）：
   - `read/glob/grep/semantic_search/skill/question/board_read` → `read`
   - `write/edit/memory_create_*` → `write`；`bash/task/agent_manager/background_process` → `execute`
   - `websearch/webfetch/generate_image/board_post` → `network`
4. 结果写回 `dispatches[i].result`。
5. **回到 SMS**：每条 `dispatch.return_to=sms`——子技能执行完（无论成功/失败）必须把控制权交回 SMS 整合 lane，禁止在子技能内直接结束或直接回复用户。

## 输出

- `SMS/registry/dispatch.json`：dispatches[] 与每项结果。
- 契约 [dispatch.schema.json](../../schemas/dispatch.schema.json)。

## 脚本

- [dispatch.py](scripts/dispatch.py)：默认预览，`--write` 且已授予 write 才写盘。

## 红线

- 只写 `SMS/registry/dispatch.json`；未授予对应权限的工具必须拒绝并 audit。
- 子技能运行完必须回到 SMS（`return_to=sms`），不得在子技能内直接结束或直接回复用户；SMS 只整合 skill 结果作答，不用模型自身知识代答。
- 悬空链接 = 0；本文件 ≤ 50 行；SKILL.md 含 YAML frontmatter。