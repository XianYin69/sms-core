# 三平台对照表（PowerShell ↔ bash ↔ zsh）＋ SMS 改道规则

## 等价命令速查
| 目的 | PowerShell | bash | zsh |
|---|---|---|---|
| 列当前目录 | `Get-ChildItem` | `ls -la` | `ls -la` |
| 读全文 | `Get-Content -Raw f` | `cat f` | `cat f` |
| 写/覆盖 | `Set-Content f -Value x` | `printf '%s' x >f` | 同 bash |
| 找文件 | `Get-ChildItem -Recurse -Filter *.py` | `find . -name '*.py'` | `**/*.py` glob |
| 内容检索 | `Select-String pat -Path * -Recurse` | `grep -rn pat .` | `grep -rn` 或 `ls **/*.(py)#(pat)` |
| 环境变量 | `$env:NAME` | `$NAME`／`export NAME=v` | 同 bash |
| 退出码 | `$LASTEXITCODE` | `$?` | `$?` |
| 顺序链接 | `a; if ($?) { b }`（5.1）／`a && b`（pwsh7） | `a && b` | `a && b` |
| 后台 | `Start-Process x -PassThru` | `x & echo $!` | 同 bash |
| 杀进程 | `Stop-Process -Id p -Force` | `kill p`／`pkill -f n` | 同 bash |
| 端口占用 | `Get-NetTCPConnection -LocalPort n` | `ss -ltnp`／`lsof -i:n` | 同 bash |
| 临时目录 | `$env:TEMP` | `$TMPDIR`／`/tmp` | 同 bash |
| 家目录 | `$HOME`／`~` | `~` | `~` |
| JSON | `ConvertFrom-Json` | `jq -r` | `jq -r` |
| 下载 | `Invoke-WebRequest -OutFile` | `curl -o`／`wget` | 同 bash |
| 提权 | （以管理员重启壳） | `sudo -n` | `sudo -n` |

## 平台缺省
- Windows：pwsh 7 优先，回退 5.1；bash 仅认真 Git-Bash（`C:\Program Files\Git\bin\bash.exe`）。
- Linux：bash 默认；发行版有 zsh 则可选；无 `powershell` 即不进 PS 支。
- macOS：zsh 默认交互壳、`/bin/bash` 恒为 3.2；`open` 代替 `xdg-open`。

## SMS 改道规则（sys_shells）
1. 选定壳持久 `<SMS_HOME>/shell/shell_kind`；`:sh list` 看检出、`:sh select <kind>` 切换。
2. 选定 powershell/cmd 时，行首命中 unix 词表（ls/cat/grep/find/sed/awk/git/python…）且本机有真 bash/zsh → 自动改道执行；否则原样进 PowerShell（别名覆盖大半）。
3. WSL/商店 bash 桩恒拒（冷启 VM 每命令 ~32s，卡顿主源）。
4. 注入环境：`SMS_HOME`、`SMS_WORKSPACE`（cwd）、`SMS_TMP`（产物唯一去处）；`:sh export` 可 eval 联动。
5. 超时 `shell.exec_timeout`（默认 600s）到点强杀；行内出现停止词即协作收口（stop_channel）。
6. git 写命令（add/commit/reset/push…）恒门禁：当轮确认＋`:grant danger`（红线 2）。
7. 手册检索：`python -B skill/scripts/sys_shells.py manual [pwsh|powershell|cmd|bash|zsh|all]`；`register-manual` 登记 `<SMS_HOME>/shell/manual.json` 供壳/派发对话读取。
