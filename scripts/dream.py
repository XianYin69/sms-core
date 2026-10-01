#!/usr/bin/env python3
"""dream.py — 做梦机制（时间戳调度·红线17 审计·批17 后台化）：间隔＝用户设置（settings `dream.interval_min`·默认 360 分·程序钳 5–720），next_run_ts 运行时间戳由程序按间隔自动计算写 chains/（到点触发·非配置键不可手动设）——合并近义/修剪低频/钉选记忆/审计未收口对话与派发对话（批23 对等：每 conv 均应有 open:/close: 配对）/记忆沉淀（dream_mem：高频有用碎片→memory 链·私人信息经 privacy 变换入 privacy/ 供个性化）/错误自修（dream_fix：skill_errors≥3 open→直调 Skill_Generator self_update report 登记修复）/网络漫游（dream_roam：话题→ff_lite 搜索→蒸馏入 knowledge/logic 链·须 grant network）；执行＝分离子进程后台跑（dream_bg·stdout→logs/dream.log），对话前台零占用；CLI `run` 默认同步跑完并回 JSON（--async 才后台拉起）。用法：python -B dream.py status|run [--async]|schedule|maybe。"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, chain_store as cs, chains, dream_fix, dream_mem, dream_bg, dream_steps, dream_watch, dream_pending
def _now(): return time.strftime("%Y-%m-%dT%H:%M:%S")
def _read_ts(sms, k):
    try: return float(open(os.path.join(sms, "chains", k)).read())
    except Exception: return 0.0
def _fmt(t): return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t)) if t else None
def interval_min(sms=None):
    v = 360
    try:
        import settings; v = int(settings.get("dream.interval_min", 360, sms=sms))
    except Exception: pass
    return max(5, min(720, v))
def next_run(sms): return _fmt(_read_ts(sms, "next_run_ts"))
def due(sms): nxt = _read_ts(sms, "next_run_ts"); None if nxt else schedule(sms); return bool(nxt) and time.time() >= float(nxt)
def schedule(sms): open(os.path.join(sms, "chains", "next_run_ts"), "w").write(str(time.time() + interval_min(sms) * 60)); return _now()
def maybe(sms): return due(sms) and dream_bg.spawn(sms)
def run(sms):
    try: __import__("session_reg").bind("cron", "dream", "做梦")
    except Exception: pass
    dream_watch.beat("起首"); st = cs.Store(sms); r = dream_steps.core(sms); top = dream_steps.top(sms)
    os.makedirs(os.path.join(sms, "chains"), exist_ok=True); open(os.path.join(sms, "chains", "retrieval.md"), "w", encoding="utf-8").write("\n".join("[%s·f%d] %s" % (f["id"], f["freq"], f["text"]) for f in top) or "（暂无）\n")
    r["pinned"] = _mem(sms, top); dream_mem.absorb(sms, top, r); _audit(sms, r); dream_fix.fix(sms, r); dream_steps.repair(sms, r)
    import dream_roam; dream_bg.stamp(sms); r["roam"] = dream_roam.roam(sms, r); dream_bg.stamp(sms)
    open(os.path.join(sms, "chains", "last_run"), "w").write(str(time.time()))
    r["task"] = "做梦完成：双向边%d 合并%d 修剪%d 加强%s 原子%d 钉选%d 记忆%d 隐私%d 升级%d 上报%d 修复%d 待批%d 违规%d 漫游%s" % (r.get("symmetrized", 0), r["merged"], r["pruned"], (r.get("reinforced") or {}).get("promoted", 0), r.get("atoms", 0), r["pinned"], r.get("memorized", 0), r.get("privatized", 0), r.get("escalated", 0), r.get("reported", 0), r.get("repair", 0), r.get("pending", 0), len(r.get("violations", [])), r.get("roam", "-"))
    chains.record("event", r["task"]); schedule(sms); dream_steps.close(sms, r); dream_bg.unlock(sms); return r
def _ldw(p): import atomic_io; return atomic_io.rjson(p, default={})  # default=None 会让缺文件重抛 FileNotFoundError（fresh HOME 首跑崩溃·潜亏修复）
def _wj(p, d): import atomic_io; atomic_io.wjson(p, d)
def _mem(sms, top):
    p = os.path.join(sms, "memory.json"); doc = _ldw(p) or {"updated": _now(), "entries": []}
    have = {e["note"] for e in doc["entries"]}; nid = max([e["id"] for e in doc["entries"]], default=0); n = 0
    for f in [x for x in top if x["chain"] == "knowledge" and x["freq"] >= 3][:10]:
        if f["text"] not in have: nid += 1; doc["entries"].append({"id": nid, "date": f["ts"][:10], "path": "chains/knowledge/" + f["id"], "note": f["text"]}); n += 1
    if n: doc["updated"] = _now(); _wj(p, doc); return n
    return 0
def _ack(sms):
    p = os.path.join(sms, "chains", "violations_ack.md"); return {l.strip() for l in open(p, encoding="utf-8")} if os.path.exists(p) else set()
def _audit(sms, r):
    fs = cs.Store(sms).all_frags("session"); ack = _ack(sms); keep = lambda c: c not in ack and "-test" not in c; opens = {f["text"].split(":", 1)[1] for f in fs if f["text"].startswith("open")}; closes = {f["text"].split(":", 1)[1] for f in fs if f["text"].startswith("close")}
    subs = {f["text"].rsplit("@", 1)[-1] for f in cs.Store(sms).all_frags("subsession")}
    r["violations"] = sorted(c for c in list(opens - closes) + list(subs - closes) if keep(c))
    open(os.path.join(sms, "chains", "violations.md"), "w", encoding="utf-8").write("\n".join(r["violations"]))
if __name__ == "__main__":
    sms = resolve_home.ensure(); cmd = sys.argv[1] if len(sys.argv) > 1 else "status"; import settings
    if cmd == "run": print(json.dumps(run(sms), ensure_ascii=False, indent=2) if "--async" not in sys.argv else ("spawned" if maybe(sms) else "未到期"))  # 默认同步：旧版起 daemon 线程即退出，做梦实际未执行（last_run 不更新·status 恒 due）
    elif cmd == "schedule": schedule(sms); print("间隔＝用户设置（dream.interval_min=%d 分·钳 5–720）：程序已算下次触发 %s" % (interval_min(sms), next_run(sms)))
    elif cmd == "maybe": print("spawned" if maybe(sms) else "未到期")
    else: print(json.dumps({"last_run": _read_ts(sms, "last_run") or None, "next_run_ts": _read_ts(sms, "next_run_ts") or None, "next_run": next_run(sms), "interval_min": interval_min(sms), "interval_by": "user(dream.interval_min)", "ts_by": "program", "bg": dream_bg.running(sms), "watch": dream_watch.state(sms), "pending": len(dream_pending.open_rows(sms)), "roam": settings.get("dream.roam", True, sms=sms), "due": due(sms)}, ensure_ascii=False))
