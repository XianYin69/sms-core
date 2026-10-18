---
name: task_table
description: >
  任务拆分与任务总览（树形·批48）制表器子技能：脚本标点粗分只作「自动种子」——复杂任务（拆步≥2且至少一步命中执行性技能）送网关前自动建种子总览（task_table.py＋树引擎 task_tree.py·行数无上限·模型首轮据实改表），落 <SMS_HOME>/tasks/<id>.json 供右栏任务总览与顶栏进度/剩余时间预测；树形＝所有任务都是根任务的延申：表带 root/parent（新表自动认最近一张「目的不同」的在途表为父）、行带 pid（op=add 第3参数＝父行 id 即挂子步骤）；父行＝汇总节点（状态自动 rollup、不派工、不入 open_rows/eta/守卫）；目的相同的任务或步骤自动合并（命中 task.merge_sim 即 graft 并入原总览、绝不另建同义新表；op=merge 跨表并表）；
  批18 主流程守卫 pending(conv)＝有未完成叶子行禁止收口并注入续推（批23 收口＝形式停止非实质完成）；批22 判简单仍注入〔任务总览·脚本未建〕，复杂与否由模型判；批29/48 并行真可用（task_res.py）：行资源 files=/dir=/reads=/port=/device=/skill= ＋互斥判定（写写·写读互斥，只读共享，端口/设备恒互斥）＋ op=conflict（value=all 跨表·value=tree 整棵树）回「哪几行可并发、哪几行必须串行」＋ op=run（value=tree＝跨任务跨层级把整棵树的未完成子步骤组批一次跑完）＋〔发〕发送处理（派技能对等对话）×〔本〕本地处理（exec/read/write 自办）同批混跑·行级独立超时·失败隔离写 error 链；批30-33 auto_done/reconcile/stale_requeue 行状态自动回写与陈旧自愈。
license: MIT
metadata:
  category: meta
  kind: sub_skill
---
# task_table — 任务拆分与任务总览制表器（树形·批48）
使用 `task_table` skill 完成诉求。SMS 的**制表**子技能：把「该拆步骤、该派技能、该看进度、该并行」收拢成一棵任务总览（真源 `<SMS_HOME>/tasks/<id>.json`），执行仍由网关工具循环按表推进、由 SMS 整合收口。
## 编号制（批49）
- 只给任务树下的子节点（行/步骤）分配层级编号：顶层 1、2、3…，子行 1.1、2.3…，孙行继续追加段；行引用双口径（层级号或内部行号 t#）。
- 任务（根任务与延申任务·表级）完全不编号：注入块/树视图/顶栏/QQ 一律以目的文本标识、不出现表号；tid 免填＝本对话在途表（内部落盘键不变）。
- 旧「单表平铺」任务表设计完全废弃：task.tree 开关退役（on() 恒真），树形为唯一设计；仅 task_tree 导入失败才降级渲染防崩。

## 何时建表 / 免表
- **必须建表（批51 强制口径）**：用户有**明确指令**（祈使/执行动词，如「帮我…」「写…」「把…处理掉」）或有**处理复杂任务意图**（多步骤/多事项/计划性表述，如「先…然后…」/分步/多项/完整方案）时，一律建立任务节点——`task_table.plan()`/`attach()` 按 `task_intent()` 判据直接建表，不再留给模型裁量；模型侧 `task_plan op=plan` 同口径必建。
- 自动种子表（脚本判复杂·批14「不是什么都建表」）：拆步≥2 **且**至少一步命中执行性技能（非 general_answer/constraint_arbiter）——批51 后此门槛仅对**非明确指令**的输入生效。
- 脚本判简单且非明确指令＝不建表但注入〔任务总览·脚本未建〕：由模型判，**用户无须写「制表」**；判多步动手即 `task_plan op=plan value=步骤逗号分隔` 自建总览。纯问句/闲聊/寒暄（天气/自我介绍/随便聊聊）仍免表直送。开关 `:config set task.auto_table false`。
- 同目的自动合并（批48 反「同一件事堆三张表」）：建表前先找同目的在途表（`task_tree.find_merge`，相似度≥`task.merge_sim` 默认 0.62）——属本对话就 `graft()` 并入它（同义步骤去重并在既有行记 `also`，新步骤重新编号防撞号丢行、按相近度挂父行下），他对话表不代改（批32）但把新表挂其下作延申。
## 树形（批48·所有任务都是根任务的延申）
- 表级：`root`＋`parent`（首表自为根；`task_tree.stamp()` 认最近一张目的不同的在途表为父）；`op=tree` 渲染 根任务→延申任务→行→子行。
- 行级：`pid`（`op=add <表id> <父行id> <目标>`，或目标写 `t2：子步骤`／`parent=t2`）；层级上限 `task.tree_max_depth`（默认 3）；父行不存在即拒绝、删父行则子行升顶层。
- 父行＝汇总节点：`rollup` 按子行算状态（全 done→done／有 error→error／有 running→running），`open_rows()`/ETA/守卫只认叶子行。
- 跨表并表：`op=merge <表id> [对方表号]`＝同目的表整体搬进本表（行重新编号、pid 重映射、状态与 result 一字不改），对方 `merged_into`＋归档。
## 发送处理 × 本地处理（并行）
- `task_tree.chan(row)`：〔发〕＝调 `skill` 派对等对话（行 skill 命中且非通用问答）；〔本〕＝本对话 `exec/read/write/glob/grep` 自办（目标写 `self=`／`local=` 或 `manual=local` 强制本地、`manual=send` 强制派发）。两类行连同父表／子表／兄弟任务的步骤一起进并发批次：`op=conflict value=tree` 出分组；`op=run value=tree`→`agent_task.run_tree()` 一次跑完（批内≤`task.batch_parallel`·行级超时 `task.row_timeout`·失败隔离只标该行·他对话表一律不代改）。
## 子步骤并行判据（批29·每轮照做）
- 声明资源：`files=a.py,b.md`｜`dir=build`｜`reads=x.json`｜`port=8080`｜`device=mouse`｜`skill=xxx`；不声明则按 goal 自动抽路径/端口。
- 判互斥：同一资源被两行**写**占用＝冲突；写＋读＝冲突（`task.conflict_read_write false` 放行）；只读可共享；端口/设备/交互会话恒互斥；同技能默认不冲突（`task.conflict_skill true` 收紧）。
- 取分组：`op=conflict <表id>`（value=all＝连其他在途表一起判）→「批N〔可并发…〕＋串行依据」；`op=run <表id>` 一次跑互不冲突的行；ETA＝各批「批内最大值」求和（`task.eta_parallel`）。
## 用法
```
python -B skill/scripts/task_table.py plan "<诉求>" | new "<步骤1，步骤2>" | show|next|eta|tree|merge <表id>
python -B skill/scripts/task_table.py conflict <表id> [all|tree]   # 哪几行可并发、哪几行必须串行（tree＝整棵树）
python -B skill/scripts/task_table.py run <表id> [tree]            # 组批并发执行（tree＝跨任务跨层级整棵树）
python -B skill/scripts/task_table.py add <表id> "<目标>" [父行id] # 第3参数＝父行 id 即挂子步骤
python -B skill/scripts/task_table.py status <表id> t2 done | remove <表id> t3 | skill <表id> t2 <技能id>
python -B skill/scripts/task_table.py lane <表id> t3 bg | res <表id> t2 "files=a.py,dir=build" | pending|stale|reconcile|sweep [分钟] | claim <表尾号> | attach <文本>
```
## 行状态自动回写与对账（批30-33）
- `auto_done`（agent_dispatch/agent_task 返回后调）：未 done 叶子行中「行 skill 同名」优先、goal 匹配次之 → done＋result[:600]；判假→error；只动本对话的表；`status` 传乱值不改行（批33 缺陷D）。
- `reconcile`（agent_stream 收口 finally）：行 result 非空或写资源本轮新落盘 → 补 done；汇总父行跳过（其状态由 rollup 得出）。
- `stale_requeue`：按行级 `started_at` 超 `task.stale_min`（默认 30min）即 running→pending 移尾并记 error/logic 链；`pending()` 每 60s 顺带自愈；`sweep()` 清补投残表/全垃圾表，清表时把子表 parent 上移不留悬空。
## 接线
- 注入：agent_stream → `attach()`（〔任务总览〕块＋根任务声明＋执行规则）；守卫：gateway 用 `pending(conv)`/`guard_rows()`（`task.auto_continue`/`max_continue`）；工具口：agent_dispatch `task_plan`（op=plan/new/show/next/eta/tree/merge/conflict/run/res/add/remove/status/skill/lane/sweep/claim）。
- 结构真源：[task_tree.py](../../scripts/task_tree.py)（签名/相似度/父子/rollup/渲染/通道）；冲突与批次：[task_res.py](../../scripts/task_res.py)；进度信封与 QQ 回传：msg_flow＋qq_report。
## 红线
- 改表唯一经本制表器（各 op 均落同一真源并重发进度），模型与用户不得旁改 JSON；行只是「目标＋技能＋资源」，执行按各技能自身门禁。同目的必合并、不得另建同义新表；父行不得当派工对象；越会话表一律拒写；悬空链接 = 0；本文件 ≤ 50 行；SKILL.md 必含 YAML frontmatter。
