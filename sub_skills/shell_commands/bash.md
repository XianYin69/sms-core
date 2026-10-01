# Bash 手册（Linux/Unix·GNU bash·含 macOS 3.2 与 Git-Bash）

SMS 在 Linux/macOS/Git-Bash 检出 `bash` 后可 `:sh select bash`；unix 命令在 ps 壳语境本会自动改道 bash（sys_shells.kind_for）。

## 启动形态
- 交互：`bash -i`；脚本：`bash file.sh`；单发：`bash -c '命令'`（SMS run 即用 `-c`）。
- shebang：`#!/usr/bin/env bash`；bin/sms-shell 为 `#!/bin/sh` POSIX 壳（不依赖 bash 扩展）。
- macOS 默认 `/bin/bash` 是 3.2（无关联数组/`&>>`）；brew bash 5 在 `/opt/homebrew/bin/bash`。

## 严谨模式
- 脚本头：`set -euo pipefail`（未定义变量即错·管道中段失败也失败）。
- 判断退出码：`cmd || { echo "失败 $?" >&2; exit 1; }`；`$?` 只看上一条。
- 条件：`[[ ]]` 支持正则/glob（bash 扩展）；`[ ]` 可移植；`(( ))` 算术。

## 引用与展开
- 永远双引号包变量：`"$f"`（空格/中文不断词）；`"${arr[@]}"` 逐元素。
- 单引号字面量；`$'a\nb'` 转义生效；heredoc：`<<EOF` 展开变量，`<<'EOF'` 不展开。
- 命令替换用 `$(...)`（可嵌套），别用反引号。

## 文本与文件
- 查找：`find . -name '*.py' -type f -print0 | xargs -0 grep -l pattern`。
- 就地编辑：`sed -i.bak 's/a/b/' f`（BSD sed 需 `-i ''`，GNU 直 `-i`——跨平台注意）。
- 取字段：`awk -F: '{print $1}'`；JSON 用 `jq -r '.a.b'`。
- 行/字数：`wc -l`；diff：`diff -u a b`；补丁：`git apply`/`patch -p1`。

## 进程与权限
- 后台：`cmd & echo $!`；守护：`nohup cmd >log 2>&1 &`；杀：`kill -9 <pid>`／`pkill -f 名称`。
- 端口：`ss -ltnp`（新）/`netstat -antp`（旧）；macOS：`lsof -iTCP -sTCP:LISTEN`。
- 服务：`systemctl status x`（systemd）/`launchctl list`（macOS）；提权 `sudo -n`（非交互，勿盲等密码）。

## SMS 相关坑
- WSL/商店 `bash.exe`（`/system32/`、`/windowsapps/`）是冷启 VM 桩——每条命令 ~32s，SMS detect 已拒认，只认真 Git-Bash。
- Git-Bash 路径互转：`/c/Users/...` ↔ `C:\Users\...`；`cygpath -w "$p"` 出 Windows 路径。
- 环境变量透传：`:sh export` 打印 `export SMS_HOME=... SMS_WORKSPACE=... SMS_TMP=...; cd "$SMS_WORKSPACE"`。
- 破坏性示例（`rm -rf`/覆盖 mv）：须用户当轮确认＋`:grant danger`（红线 2），手册只录非破坏命令。
