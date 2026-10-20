# CHANGELOG

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

*最后更新：2026-10-19 | 分支收口 main*
