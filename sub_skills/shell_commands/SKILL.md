---
name: shell_commands
description: >
  SMS 运行指令层三平台命令手册子技能（Windows PowerShell / Linux·Unix bash / zsh）：
  供 :sh、`!命令`、F7 直通、gateway exec 在写系统指令前查阅；含 powershell、bash、zsh 三份手册与
  platform_map 跨平台对照；登记 <SMS_HOME>/shell/manual.json 供壳内检索。
license: MIT
metadata:
  category: reference
  kind: sub_skill
---

# shell_commands — 运行指令层三平台手册

使用 `shell_commands` skill 来完成用户请求。本技能**只供查阅**，不作答、不执行：SMS 命令层（[sys_shells.py](../../scripts/sys_shells.py) `:sh`/`!命令`、[shell_core.py](../../scripts/shell_core.py) 确定性路由、[shell_help.py](../../scripts/shell_help.py) 速查）据本手册选壳、写命令、判退出码。

## 手册（按目标平台取用）

- [powershell.md](powershell.md)：Windows PowerShell 5.1 与 pwsh 7——cmdlet/别名陷阱、`-NoProfile -NonInteractive`、`$LASTEXITCODE`、`&&` 差异、编码与路径。
- [bash.md](bash.md)：Linux/Unix GNU bash（含 macOS bash 3.2、Git-Bash）——`set -euo pipefail`、展开/引号、heredoc、find·xargs、WSL 桩坑。
- [zsh.md](zsh.md)：macOS 默认壳与 Linux zsh——glob qualifier、数组下标 1 起、默认不分词、`INTERACTIVE_COMMENTS`、与 bash 不兼容点。
- [platform_map.md](platform_map.md)：三平台等价对照（命令/路径/环境变量/退出码/服务/网络诊断）＋SMS 改道规则。

## 与命令层的接线

1. 壳选择：`:sh list` 看检出结果，`:sh <kind>` 选定（持久 `<SMS_HOME>/shell/shell_kind`）；`pwsh|powershell|cmd|bash|zsh` 五类。
2. 单发：`!dir` / `:sh ls -la`——unix 风格命令仅当真 bash 在场才改道，否则 PowerShell 直跑（`ls/cat/grep/git/python` PS 原生可用）。
3. 查手册：`python -B skill/scripts/sys_shells.py manual [kind]` 打印当前壳对应手册绝对路径；`manual all` 打印四篇清单。
4. 登记检索：`python -B skill/scripts/sys_shells.py register-manual` 把四篇绝对路径写 `<SMS_HOME>/shell/manual.json`（供 `:cmds`/F2 索引与派发对话读取，数据不落 skill 目录）。
5. 门禁不变：git 写操作恒须 `grant danger`（红线 2）；cwd＝`SMS_WORKSPACE`，产物只入 `SMS_TMP`；超时 `shell.exec_timeout`；输出行内出现 `stop/停止` 即协作收口（stop_channel）。

## 红线

- 手册只增知识，不得放宽既有门禁；命令示例一律非破坏性，破坏性写法须注明须 `grant danger`＋用户当轮确认。
- 本目录 .md 全部 ≤50 行、悬空链接 = 0；平台事实有变须走 update 审批（[resistance](../../resistance/resistance.md)）。
