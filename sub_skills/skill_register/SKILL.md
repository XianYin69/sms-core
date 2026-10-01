---
name: skill_register
description: >
  标记用户电脑上技能的安装位置与所用工具，扫描各安装根目录，
  生成 SMS/registry/register.json。
license: MIT
metadata:
  category: meta
---

# skill_register

使用 `skill_register` skill 来完成用户请求。 标记用户电脑上技能的**安装位置**与**所用工具**，生成 `SMS/registry/register.json`。

## 输入

- 扫描根目录（默认 `~/.kilocode/skills`；可追加本系统 sub_skills 目录）。

## 步骤

1. 遍历每个根目录下含 `SKILL.md` 的文件夹。
2. 解析 YAML frontmatter：`name` / `description`。
3. 匹配工具清单，抽取 `tools`（read/write/edit/glob/grep/bash/task/skill/websearch/webfetch…）。
4. 汇总写出 register.json（字段：id / install_path / entry / kind / tools / status / updated_at）。

## 输出

`SMS/registry/register.json`，契约见 [register.schema.json](../../schemas/register.schema.json)。

## 脚本

- [register.py](../../scripts/register.py)：默认预览，`--write` 且已授予 write 才写盘。

## 红线

- 只写 `SMS/registry/` 下的文件；不得修改被扫描技能的源文件。
- 悬空链接为 0；本文件 ≤ 50 行；SKILL.md 含 YAML frontmatter。