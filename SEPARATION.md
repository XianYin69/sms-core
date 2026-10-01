# 壳 / 核边界契约（批27）

**唯一接缝＝`runtime_bind.py`**（属 sms-core）。core 侧任何模块不得 `import shell_*`；需要「把一句话语交给壳执行」或「跑壳侧待办」时，只能经接缝注册的回调：

| 方向 | 机制 | 调用点 |
|---|---|---|
| shell → core | 直接 import（合法·单向·50 条边） | shell_core / shell_tui / shell_lifecycle 等 |
| core → shell | `runtime_bind.set_runner(handle)` / `set_pending(run_pending)` 由壳在自身 import 时登记 | net_util.chat、planned_tasks._default_runner、qq_inbound.deliver |

壳未安装/未 import 时：`rb.run()` 回明确错误串「未绑定壳运行器」，`rb.pending_run()` 静默跳过——core 绝不因此崩溃。

审计：`python -B scripts/sep_audit.py` → `{"core_to_shell": 0, "verdict": "SEPARATED"}`（seam→shell 2 条为契约允许）。

合体发行仓库＝ https://github.com/XianYin69/skill_manage_system （core+shell 覆盖安装到同一 `<SMS_HOME>/skill/scripts`）。
