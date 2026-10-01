---
name: skill_connector
description: >
  依据 register.json 与 interfaces.json，生成技能间上下文连接链，
  输出 SMS/registry/connections.json，供 skill_manage_system 调度。
license: MIT
metadata:
  category: meta
---

# skill_connector

使用 `skill_connector` skill 来完成用户请求。 处理不同技能之间的**上下文连接**，生成 `SMS/registry/connections.json`。

## 输入

- `SMS/registry/register.json`（[skill_register](../skill_register/SKILL.md)）。
- `SMS/registry/interfaces.json`（[skill_packer](../skill_packer/SKILL.md)）。

## 步骤

1. 读取 register.json 的 `skills[]`，建立可用技能 id 集合。
2. 固定流水线：register → packer → connector。
3. 依据 interfaces.json 的 `dependencies` 追加依赖边。
4. 写出 chains（id / from / to / context / handoff）。

## 输出

`SMS/registry/connections.json`，契约见 [connections.schema.json](../../schemas/connections.schema.json)。

## 脚本

- [connect.py](../../scripts/connect.py)：默认预览，`--write` 且已授予 write 才写盘。

## 红线

- 只写 `SMS/registry/` 下的文件；连接只描述不执行。
- 悬空链接为 0；本文件 ≤ 50 行；SKILL.md 含 YAML frontmatter。