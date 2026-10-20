# CHANGELOG

## [2026-10-20]
### Added
- agent_stream 两阶段理解＋关键词泛洪：新增 `_extract_operation_keywords()`（从第一阶段理解回复抽取技能/工具/记忆操作关键词）与 `_inject_skill_summaries()`（按关键词仅注入命中的 top3 技能摘要，不再整表灌入）；`chains.conversation()` 新增 `pre` 形参承载该注入段。
- 涉及文件：`skill/scripts/agent_stream.py`、`skill/scripts/chains.py`
- 违反后果：上下文塞入全量技能目录 → token 浪费、路由命中率与派发裁量被噪声淹没。

### Changed
- `prompt_pack.pack()` 新增 `keywords` 形参：以操作关键词作向量种子做泛洪（DFS 未命中时回退全量扫描仍走同一关键词种子），提升相关记忆碎片召回。
- `skill_route.route()` 未命中提示瘦身：去掉逐条技能表全文，只留「可用技能参考（供裁量，不必逐条列出）」，与新的按需注入口径一致。
- `compose()` 调整拼装顺序（init 后置）；`task_table` 行级技能预标随动精简。
- 涉及文件：`skill/scripts/prompt_pack.py`、`skill/scripts/skill_route.py`、`skill/scripts/agent_stream.py`、`sub_skills/task_table/task_table.py`
- 违反后果：提示与注入段重复、每轮上下文膨胀。

### Verified
- 五个改动文件 `py_compile` 全通过；正式版分支 main 已推送远端，并回流 tech-preview（开发测试环境技术预览分支）。

## [2026-10-19]
### Fixed
- 修复 spin_guard 空转自愈误杀任务（用户报障「修复莫名奇妙的 spin-guard 空转自愈导致任务停止」）：
  ① `_escalate` hit#2 删除 `stop_channel.request("spin-guard 空转自愈")`——守护线程未绑任务致 `stop_channel._key()` 回空、触发**广播停止**停掉全部在跑任务（spin.log 实证 19:04/19:20 两次 hit#2 广播停）；改反复重置 `hide_req`（幂等·UI tick 藏 #prog）。
  ② `_watch` 新增合法长等待宽限期 `spin_legit_grace_s`（默认 120s）：`_legit_wait()` 为真即记 `ST["last_legit"]`，退出长等待后该窗口内不判自旋——治网关 LLM 请求返回后 STAGE 已 clear、壳处理响应/构建上下文期间高 CPU 无 beat 被误判 spin（hit#1 cpu=750 silent=64）。
  ③ 重启阈值由 hit#3 提至 `spin_selfheal_hits`（默认 6＝30s 持续自旋）。
- 涉及文件：`skill/scripts/spin_guard.py`
- 违反后果：并行任务被误停、壳被误重启、用户看到「莫名奇妙任务停止」。

## [2026-10-19]
### Changed
- 切换正式版分支：成员仓 SMS-core 由 dev 切到 main，并把 dev 的 10 个提交（批49 编号制 / 批50 跨对话对账 / 批51 行级 skill 预标 / A6 重试补正 / solo 守卫等）以 `git merge --ff-only dev` 无冲突并入 main，`git push origin main` 推送远程（HEAD=efa0256）。
- 改动范围：仅分支收口（快进合并），未新增代码改动。
- 涉及文件：CHANGELOG.md（本条）
- 违反后果：main 落后 dev → 正式版取到旧内核，任务树/对账/守卫修复不生效。

## [2026-10-17]
### Added
- 新增变更日志规范：每次修改/新增/删除操作完成后必须在根目录 `CHANGELOG.md` 记录变更（日期、改动范围、涉及文件、违反后果）；变更日志不可缺失、不可跳过、不可事后补录（漏记视为违规）。

---

*最后更新：2026-10-20 | 分支收口 main + tech-preview 回流*
