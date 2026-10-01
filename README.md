# sms-core — SMS 核心（数据流引擎）

skill_manage_system 的核心侧：128 个模块，与界面壳（sms-shell）完全解耦（core→shell 反向依赖＝0）。

内容：原生大模型网关（gateway/gateway_sse·SOLO 分析后重试）、链记忆十二链（chains/chain_*）、
任务表与主流程守卫（task_table/flow_guard）、权限与 SOLO 自审（permissions/solo）、技能路由与派发
（skill_route/agent_dispatch/agent_tools*）、QQ 通道（qq_*）、计划任务（planned_tasks）、网页壳服务端
（web_shell/ext_net/net_util）、做梦链路（dream_*）、ff_lite/glob/grep 等工具件、schemas/config/sub_skills。

- 边界契约：见 `SEPARATION.md`
- 分离审计：`python -B scripts/sep_audit.py`
- 安装：与 sms-shell 合并覆盖到 `<SMS_HOME>/skill/scripts`（合体发行＝skill_manage_system）
