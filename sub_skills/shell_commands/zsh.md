# zsh 手册（macOS 默认壳·Linux 可选）

SMS 检出 `zsh` 后可 `:sh select zsh`；单发经 `zsh -c`。多数 bash 习惯可用，差异如下。

## 启动形态
- 交互：`zsh`；脚本：`zsh file.zsh` 或 shebang `#!/usr/bin/env zsh`；单发 `zsh -c '命令'`。
- 配置：`.zshrc`（交互）`.zprofile`（登录）；非交互 `-c` 默认只读 `.zshenv`——放变量于此。

## 与 bash 的关键差异
- 数组 **1 起**：`${arr[1]}` 是首元素；全部 `"${arr[@]}"`（0 起索引会空一项）。
- 变量默认**不分词**：`$unquoted` 不拆词（无 word splitting 惊喜）；要拆用 `${=var}`。
- `echo` 默认解析转义（`\n` 直接生效）；要字面量用 `print -r --`。
- 关联数组：`typeset -A map; map[key]=v`（bash 4 才等价）。
- 数学：`(( a = b + c ))` 兼容；另有 `$[ ]` 弃用——用 `(( ))`。
- glob 即匹配空也报错：`ls nomatch*` 直接 `no matches found`（bash 原样传）；放宽 `setopt NULL_GLOB`。
- 行内注释交互默认可用；脚本中 `setopt INTERACTIVE_COMMENTS` 才允许。

## 强大 glob（限定符）
- `**/*.(py|md)` 多后缀；`*(.)` 仅文件、`*(/)` 仅目录、`*(-)` 符号链接。
- `*(m-1)` 一天内修改；`*(R)` 递归含隐藏；`#(l:1000000:)(.)` 大于 1MB。
- 排序修饰 `*(on)` 按名、`*(om/)` 按时间；`ls -l *(.)` 免 find。

## 编程习惯
- 保留字循环：`for f in *.py(.); do head -1 "$f"; done`。
- 条件等价 bash：`[[ ]]` 可用且更稳（无分词陷阱）。
- 管道/退出码/heredoc 与 bash 相同；`print -P` 展开提示转义。

## SMS 相关
- macOS 默认交互壳是 zsh，但 SMS 自动改道 unix 命令优先 bash→zsh 顺序；显式选定：`:sh select zsh`（持久 `<SMS_HOME>/shell/shell_kind`）。
- `:sh export` 的 `export ...; cd` 片段可直接 `eval` 进 zsh。
- 破坏性写法同 bash 条目约束：须 `:grant danger`＋当轮确认。
- 迁移速查：把 bash 脚本交 zsh 跑前检查 `echo` 转义依赖、`$*` 分词、`(f)(s)` 风格 glob 未加引号三处。
