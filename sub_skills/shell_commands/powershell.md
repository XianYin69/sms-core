# PowerShell 手册（Windows·5.1 与 pwsh 7）

SMS 在 Windows 的系统壳默认 pwsh→powershell 顺序检出（sys_shells.detect）；`!命令`/`:sh`/gateway exec 都经此。

## 启动形态
- 交互：`powershell` / `pwsh`；脚本：`pwsh -NoProfile -File a.ps1`。
- SMS 注入固定参数：`-NoProfile -NonInteractive`（免档案/AutoRun 拖慢·无交互不死等）。
- 5.1 的 `-File` 会吞裸 `:token` 参数——含冒号参数改 `-Command "& 'x.ps1' @args"`（bin/sms-shell.cmd 同法）。

## 常用 cmdlet
| 目的 | 命令 |
|---|---|
| 列目录 | `Get-ChildItem`（`ls/dir` 为别名） |
| 读文件 | `Get-Content -Raw`（多行用 `-Raw` 防逐行处理） |
| 写文件 | `Set-Content`／追加 `Add-Content` |
| 环境变量 | `$env:SMS_HOME`（读写皆此前缀） |
| 退出码 | `$LASTEXITCODE`（原生程序）；`?` 不存在 |
| 找命令 | `Get-Command`；`where.exe` 才是 where |
| JSON | `ConvertFrom-Json` / `ConvertTo-Json -Depth 5` |

## 语法坑
- 5.1 不支持 `&&`/`||`；链接用 `cmd1; if ($?) { cmd2 }`，或 pwsh7 `cmd1 && cmd2`。
- 字符串：双引号插值 `".. $var .."`，单引号字面量；转义用反引号 `` ` ``。
- 子表达式 `$(...)`、数组 `@(...)`；带空格路径须调用符 `& "C:\a b\x.exe" args`。
- 参数名连字符：`-LiteralPath` 优先（通配符 `[]*?` 不生效）。
- 管道对象是 .NET 对象非文本：`| Select-Object Name,Length`、`| ForEach-Object { $_.Name }`。

## 编码与文件
- 含中文的 .ps1/.json 给 5.1 读必须 UTF-8 **BOM**，否则按 ANSI/GBK 误读（ConvertFrom-Json 少括号）。
- `cmd /c "prog > f.txt"` 在 pwsh7 下 `>` 被 pwsh 截获→文件 UTF-16LE；裸 `prog > f` 写 UTF-8 无 BOM。解析前探测 BOM。
- 5.1 默认输出宽度截断：表格用 `| Format-List` 或 `$FormatEnumerationLimit=-1`。

## 进程与服务
- 后台：`Start-Process -NoNewWindow -FilePath x -ArgumentList ... -PassThru`；TTS 常驻 worker 即此形态（tts_worker.ps1）。
- 杀进程：`Stop-Process -Id <pid> -Force`；查：`Get-Process`／`Get-NetTCPConnection -LocalPort 31415`。
- 服务：`Get-Service 名`；启动项诊断 `Get-CimInstance Win32_StartupCommand`。

## SMS 相关
- 部署包：`sms-shell.cmd`（双击/cmd）与 `sms-shell`（pwsh 内 `& .\sms-shell`）。
- 高危：`rm -r` 级删除、写用户目录＝红线 2——先预览＋`:grant danger`；git 写命令由 sys_shells.GITW 拦截。
- unix 风格（ls/cat/grep…）默认改道真 Git-Bash；无 bash 时 PowerShell 别名原生可用（`ll` 除外）。
