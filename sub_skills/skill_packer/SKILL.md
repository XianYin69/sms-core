---
name: skill_packer
description: >
  读取 skill_register 的 register.json，描述每个技能的可用接口与用途，
  生成 SMS/registry/interfaces.json。
license: MIT
metadata:
  category: meta
---

# skill_packer

使用 `skill_packer` skill 来完成用户请求。 描述用户电脑上技能的**可用接口**与**用途**，生成 `SMS/registry/interfaces.json`。

## 输入

- `SMS/registry/register.json`（由 [skill_register](../skill_register/SKILL.md) 生成）。

## 步骤

1. 读取 register.json 的 `skills[]`。
2. 从每个技能 `SKILL.md` 抽取标题作为 capabilities / interfaces。
3. 汇总 `purpose` / `capabilities` / `interfaces` / `context_in` / `context_out` / `dependencies`。
4. 写出 interfaces.json。

## 输出

`SMS/registry/interfaces.json`，契约见 [interfaces.schema.json](../../schemas/interfaces.schema.json)。

## 脚本

- [pack.py](../../scripts/pack.py)：默认预览，`--write` 且已授予 write 才写盘。

## 红线

- 只写 `SMS/registry/` 下的文件；不篡改 register.json 之外的源数据。
- 悬空链接为 0；本文件 ≤ 50 行；SKILL.md 含 YAML frontmatter。