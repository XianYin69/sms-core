---
name: file_ops
description: >
  基本操作子技能：文件读写（file_ops.py）· 路径查询（path_ops.py）· 浏览器联网操作
  （ff_lite.py firefox lite 内核搜索/取页/下载）。写盘经 emit 门控、高危（复制/移动/删除/覆盖）
  须 --yes 且 grant danger；联网须 grant network；产物只落 <SMS_HOME>/，禁写 skill 本体。
license: MIT
metadata:
  category: basic-ops
---

# file_ops

使用 `file_ops` skill 来完成用户请求。SMS 的**基本操作**子技能：把「文件读写、路径查询、浏览器操作」这三类底层动作收拢到一个可被 dispatch 的目标，统一受权限门控与十一链登记，运行完回 SMS 整合（`return_to=sms`，红线 6）。

## 三类操作

- **文件读写** — [`file_ops.py`](scripts/file_ops.py)：`read`/`write`(`--text`|`--from`，`--append`)/`copy`/`move`/`delete`/`list`/`stat`。读只读开放；写盘默认预览，`--write` 且会话已 `grant write` 才落盘；复制/移动/删除＝高危，须 `--yes` 且 `grant danger`（红线 16）；拒绝写/删 skill 本体目录与 `<SMS_HOME>/`。
- **路径查询** — [`path_ops.py`](scripts/path_ops.py)：`resolve`(可 `--sms` 回退 `<SMS_HOME>/`)/`temp`(分配 `<SMS_HOME>/tmp/` 子目录)/`which`/`exists`/`glob`/`tree`/`env`。全部只读。
- **浏览器操作** — [`ff_lite.py`](../../scripts/ff_lite.py)：firefox lite 内核 `search`/`fetch`/`download`（渲染优先 playwright 无头 Firefox，缺则回退 urllib，绝不自动装依赖）。动作须 `grant network`；下载只落 `<SMS_HOME>/downloads/`，覆盖须 `--force` 且 `grant danger`。

## 用法

```
python -B skill/sub_skills/file_ops/scripts/file_ops.py read <path> [--max n]
python -B skill/sub_skills/file_ops/scripts/file_ops.py write <path> --text ".." --write
python -B skill/sub_skills/file_ops/scripts/path_ops.py resolve <path> --sms | which <cmd> | tree <dir>
python -B skill/scripts/ff_lite.py  search "关键词" 5 | fetch <url> | download <url> 名
```

## 联动

- 每条动作经 [`chains.py`](../../scripts/chains.py) `log tool` 记 tool_call 链；`download`/`fetch` 命中的知识可交 [`learn.py`](../../scripts/learn.py) 蒸馏入 knowledge/logic 链并触发做梦。
- 壳内等价入口：`:file …` · `:path …` · `:net …`（见 [shell_core.py](../../scripts/shell_core.py)）。

## 红线

- 未授予对应权限（write/danger/network）一律拒绝并 audit；缓存与产物不落任何 skill 目录（红线 2）。
- 运行完必须回 SMS 整合，不得直接回复用户（红线 6）。
- 悬空链接 = 0；本文件 ≤ 50 行；SKILL.md 含 YAML frontmatter。
