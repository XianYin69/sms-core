#!/usr/bin/env python3
"""session_cli.py — session 脚本直达 CLI（2026-09-29 用户诉求「session 的查看/新建/切换不用通过大模型，直接通过脚本完成」）：零模型纯脚本读写 <SMS_HOME>/shell/sessions.json（真源＝session_reg.py），子命令 ls|list（列全部·kind/key/state/当前●）、new <kind> <key> [名]（通道登记·同 kind+key 幂等复用并切当前；旧口径 new [名]＝每次新建一条 shell 会话）、use <sid>（切当前）、cur|current、show <sid>（单条 JSON）、touch <sid>、rename <sid> <名>、release <sid>（置 finished·不删数据）、migrate（旧条目补 kind="shell"）、overview|conflicts（转 sessions_view 看先后顺序与跨会话未完成）；本 CLI 是 :session（shell_core._meta）与 chains.py __main__ session 分支的唯一转调口，避免两套口径；main() 供壳内进程直调（返回文本·并把命中的 sid 写 env SMS_SESSION＋LAST[0]，壳据此同步 chains.set_active 免重开壳）。用法：python -B session_cli.py <子命令> [参数…]。"""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import session_reg as R
LAST = [""]
def _bind(sid):
    LAST[0] = sid; os.environ["SMS_SESSION"] = sid
    try: import chains; chains.set_active(sess=sid)
    except Exception: pass
def _ls():
    try: R.prune(force=True)
    except Exception: pass
    cur = R.current(); out = []
    for sid, v in sorted(R.list_().items(), key=lambda kv: str(kv[1].get("created", ""))):
        out.append("%s %s｜%-6s｜%s｜%s｜conv %d｜活 %s｜key=%s" % ("●" if sid == cur else "·", sid, v.get("kind", "shell"), str(v.get("name", ""))[:20], v.get("state", "?"), len(v.get("convs") or []), str(v.get("last_active") or v.get("created", ""))[5:16], str(v.get("key", ""))[:18]))
    return "\n".join(out) or "（暂无 session）——session_cli new <kind> <key> [名] 新建"
def _new(a):
    if a and a[0] in R.KINDS:
        if len(a) < 2: return "用法 :session new <kind> <key> [名]（kind＝" + "|".join(R.KINDS) + "）"
        sid = R.ensure(a[0], a[1], " ".join(a[2:])); R.set_current(sid); _bind(sid)
        return "已登记会话 %s（kind=%s·key=%s·当前）——同 (kind,key) 复用不重复建" % (sid, a[0], a[1])
    nm = " ".join(a).strip(); sid = R.ensure("shell", "%s-%d" % (nm or "manual", int(time.time())), nm)
    R.set_current(sid); _bind(sid); return "已新建并切入会话（session）" + sid + "——新建会话＝新 session 非 conv·conv 每输入/派发自动开收"
def main(a):
    a = list(a or []); c = (a[0] if a else "ls").lower()
    if c in ("ls", "list"): return _ls()
    if c == "new": return _new(a[1:])
    if c == "use":
        sid = a[1] if len(a) > 1 else ""
        if sid not in R.list_(): return "无此会话：" + sid + "（session ls 查看）"
        R.set_current(sid); R.touch(sid); _bind(sid); return "已切换会话 " + sid
    if c in ("cur", "current"): return "当前会话（session）" + R.current() + "·通道 kind＝client|web|remote|cron|bg|shell（qq→remote 别名）·conv 每输入/派发自动开收"
    if c == "show": return json.dumps(R.get_(a[1]) or {"err": "无此会话 " + a[1]}, ensure_ascii=False, indent=1) if len(a) > 1 else "用法 :session show <sid>"
    if c == "touch": return "已刷新活跃 " + a[1] if len(a) > 1 and R.touch(a[1]) else "无此会话或用法 :session touch <sid>"
    if c == "rename": return "已改名 " + a[1] if len(a) > 2 and R.rename_(a[1], " ".join(a[2:])) else "无此会话或用法 :session rename <sid> <名>"
    if c == "release": return "已收口（state=finished·数据保留）" + a[1] if len(a) > 1 and R.release(a[1]) else "无此会话或用法 :session release <sid>"
    if c == "migrate": return "已补 kind/last_active 字段 %d 条（旧条目一条未删）" % R.migrate()
    if c in ("overview", "conflicts"):
        import sessions_view as sv
        return sv.overview(R.current()) if c == "overview" else (sv.conflicts(R.current()) or "（无跨会话未完成·各会话任务表均已收口）")
    return __doc__.strip().splitlines()[-1]
if __name__ == "__main__":
    print(main(sys.argv[1:]))
