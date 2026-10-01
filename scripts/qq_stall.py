#!/usr/bin/env python3
"""qq_stall.py — QQ 来源任务表的「卡住」看门狗（2026-09-29 用户「QQ 发起的会话其任务表因网络问题停滞时，主动推一条 ⚠任务表卡住 到我的 QQ」；同日升级·用户诉求「卡住看门狗分清原因＋不误杀＋带重试计数」：判据不再只看 mtime 停滞就喊「疑似网络中断」，而是先经 stall_class.classify(doc,age,cfg) 分因——busy（phase∈{exec,llm,llm_stream} 且 runtime.ts 在宽限窗内＝shell.exec_timeout / llm_gateway.timeout×(剩余重试+1)，或该表派发仍在跑）与 unknown 一律静默：不告警、不消耗重试、不重发（根治长脚本/长思考被误杀）；network（err_kind/last_err 指向 URLError·超时·断连·5xx·429 或曾 gaveup）/model（4xx 不可重试·网关空返回）/process（runtime.pid 已死＝ctypes OpenProcess 判活不依赖 psutil，或监听器僵尸、壳心跳 shell/alive.json 过期）才推「⚠任务表卡住 <tid尾14> <done>/<total> ▶<行> 已<N>s 无进展｜原因=<网络|模型|进程>｜已重试X次 还剩Y次｜<detail>」，计数取自 runtime_rec 活性记录 <SMS_HOME>/runtime.json{attempt,retries}；nudge()＝真卡住时后台线程向 agent_stream.ask 补投「继续当前任务表未完成行」（只投 src==qq 的表），同表每 stall_repeat 窗口最多一次、记 qq/stall.json 的 nudged 字段；重试用尽（runtime.retries<=0）则推「⚠已暂停：重试用尽」并置 doc["paused"]=原因（task_table._save 落盘）且不再 nudge；去重＝qq/stall.json{tid:{sig,last,nudged}}，同 sig 在 stall_repeat 内不重发（表真挪动→sig 变→可再报）；开关阈值＝config/qq.json 的 stall/stall_after/stall_repeat/stall_tick（qq_cli conf k=v 改，本模块绝不写用户实值）。后台范式照旧：daemon 线程＋节流＋异常全静默，绝不影响数据流。用法：python -B qq_stall.py check|tick|status|nudge <tid>。"""
import os, sys, time, json, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, qq_push as qp, runtime_rec as rr, stall_class as sc, atomic_io as ai
_last = {"t": 0.0}
KIND = {"network": "网络", "model": "模型", "process": "进程", "busy": "在跑", "unknown": "未知"}
def _td(sms=None): return os.path.join(sms or resolve_home.ensure(), "tasks")
def _tf(tid, sms=None): return os.path.join(_td(sms), tid + ".json")
def src(conv="", sms=None):
    """建表侧来源标记：优先 session_reg.fresh("qq")（qq 通道 session 30min 内活跃＝qq 发起），拿不到再退回 qq/active.json 的 ts 距今 <1800s 兜底（保守不误报；ask 内才新建 conv、与派发时 conv 不同，故按时间窗判不按 conv 匹配）。"""
    try:
        import session_reg as R
        if R.fresh("qq", 1800, sms): return "qq"
    except Exception: pass
    try: return "qq" if time.time() - float((qp._ld(qp._f(sms or resolve_home.ensure(), "active.json"), {}) or {}).get("ts") or 0) < 1800 else "shell"
    except Exception: return "shell"
def _sid(doc, sms=None):
    """该任务表所属 session＝doc["sess"]，缺失按 conv 反查（异常回空·绝不抛）。"""
    try:
        import session_reg as R; m = R.list_(sms)
        sid = str(doc.get("sess") or "")
        if sid in m: return sid
        cv = str(doc.get("conv") or "")
        return next((k for k, v in m.items() if cv and v.get("conv") == cv), "")
    except Exception: return ""
def _state(doc, s, sms=None):
    """告警触发＝该 conv 所属 session 置 stalled；恢复进展＝回 active（session_reg.set_state·异常全吞）。"""
    try:
        import session_reg as R; sid = _sid(doc, sms); return sid and R.set_state(sid, s, sms)
    except Exception: return ""
def _busy_sids(sms=None, c=None):
    """仍在盯的 session＝卡住候选表 ∪ 已 paused（重试用尽）表——这些不算恢复进展。"""
    out = set()
    try: out |= {str(d.get("sess") or "") for d, _, _ in stalled(sms, c)}
    except Exception: pass
    try:
        d = _td(sms)
        for fn in (os.listdir(d) if os.path.isdir(d) else []):
            if fn.endswith(".json"):
                doc = qp._ld(os.path.join(d, fn), {}) or {}
                if doc.get("paused"): out.add(str(doc.get("sess") or ""))
    except Exception: pass
    return out
def _sync(c):
    """恢复进展回 active：被置 stalled 的 qq session 若其表已不在卡住/暂停清单 → state=active。"""
    try:
        import session_reg as R
        ids = {k for k, v in R.list_(c["sms"]).items() if v.get("kind") == "qq" and v.get("state") == "stalled"}
        for sid in ids - _busy_sids(c["sms"], c): R.set_state(sid, "active", c["sms"])
    except Exception: pass

def _i(v, d=0):
    try: return int(v)
    except Exception: return d
def _stat(s): return (sum(1 for x in s if x.get("status") == "done"), len(s), next((str(x.get("id")) for x in s if x.get("status") == "running"), ""))
def _rt(c):
    """取活性记录（测试可经 cfg["rt"] 注入伪造态）。"""
    return c.get("rt") if isinstance(c.get("rt"), dict) else rr.read(c.get("sms"))

def stalled(sms=None, c=None):
    """卡住候选表清单 [(doc,(done,total,running行),age_s)]：只认 src=="qq"、未 paused 且仍有 pending/running 行的表，mtime＝最后一次改表（进展）时刻。"""
    c = c or qp.conf(sms); after = float(c.get("stall_after", 180)); now = time.time(); out = []; d = _td(sms)
    for fn in sorted(x for x in (os.listdir(d) if os.path.isdir(d) else []) if x.endswith(".json")):
        try: doc = qp._ld(os.path.join(d, fn), {}) or {}; subs = doc.get("subtasks") or []
        except Exception: continue
        if doc.get("src") != "qq" or doc.get("paused") or not any(x.get("status") in ("pending", "running") for x in subs): continue
        try: age = int(now - os.path.getmtime(os.path.join(d, fn)))
        except OSError: continue
        if age > after: out.append((doc, _stat(subs), age))
    return out
def _text(doc, st, age, kind, detail, rt):
    """告警文本（用户口径）：⚠任务表卡住 <tid尾14> <done>/<total> ▶<行> 已<N>s 无进展｜原因=…｜已重试X次 还剩Y次｜<detail>。"""
    dn, tot, run = st; att = _i(rt.get("attempt")); ret = _i(rt.get("retries"))
    return "\u26a0任务表卡住 %s %d/%d %s 已 %ds 无进展｜原因=%s｜已重试%d次 还剩%d次｜%s" % (
        str(doc.get("id") or "")[-14:], dn, tot, ("\u25b6" + run) if run else "\u25bd", age, KIND.get(kind, kind), att, ret, str(detail)[:90])
def nudge(doc, c=None, box=None):
    """真卡住补投：后台线程向 agent_stream.ask 投「继续当前任务表未完成行」（仅 src==qq 表·同表每 stall_repeat 最多一次·异常静默）。"""
    try:
        c = c or qp.conf(); tid = str(doc.get("id") or "")
        if not tid or doc.get("src") != "qq": return None
        if int(c.get("nudge", 1)) == 0: return "nudge 关"
        st = box if box is not None else (qp._ld(qp._f(c["sms"], "stall.json"), {}) or {})
        v = st.get(tid) or {}
        if time.time() - float(v.get("nudged") or 0) < float(c.get("stall_repeat", 600)): return "nudge 节流"
        subs = doc.get("subtasks") or []; pend = [x for x in subs if x.get("status") in ("pending", "running")]
        if not pend: return None
        rows = "、".join("%s:%s" % (x.get("id"), x.get("goal") or x.get("target") or x.get("intent") or "") for x in pend[:6])
        msg = "继续当前任务表未完成行（看门狗补投·表 %s）：%s" % (tid[-14:], rows)
        v["nudged"] = time.time(); st[tid] = v
        if box is None: qp._wj(qp._f(c["sms"], "stall.json"), st)
        def _go():
            try:
                import agent_stream as A; A.ask(msg, lambda s: None)
            except Exception as e:
                try: import chain_error; chain_error.hook("gate", "qq_stall", "nudge " + str(e)[:160])
                except Exception: pass
        threading.Thread(target=_go, daemon=True, name="qq-nudge").start(); return "nudge 已投"
    except Exception: return None

def _pause(doc, why, c):
    """重试用尽＝置表 paused 标记（doc["paused"]=原因·atomic_io 落盘）并推「⚠已暂停：重试用尽」，此后不再 nudge。"""
    try:
        doc["paused"] = str(why)[:120]; ai.wjson(_tf(str(doc.get("id") or ""), c["sms"]), doc)
        txt = "\u26a0已暂停：重试用尽（%s·表 %s）——改表或恢复后可继续" % (str(why)[:40], str(doc.get("id") or "")[-14:])
        qp.push(txt, "QQ·暂停", c); return txt
    except Exception: return None
def check(sms=None, c=None):
    """扫一遍：先分因，busy/unknown 静默（不告警、不消耗重试、不写去重）；network/model/process 才推，重试用尽转暂停。返回已推文本列表。"""
    try:
        c = dict(c or qp.conf(sms)); c.setdefault("sms", sms or resolve_home.ensure())
        if not c.get("stall", True) or not qp.ready(c): return []
        st = qp._ld(qp._f(c["sms"], "stall.json"), {}) or {}; rt = _rt(c); hits = []
        for doc, stat, age in stalled(c["sms"], c):
            kind, detail = sc.classify(doc, age, c, rt)
            if kind in ("busy", "unknown"): continue
            tid = str(doc.get("id")); dn, tot, run = stat
            sig = "%s|%s|%d/%d|%s" % (tid[-14:], kind, dn, tot, run); v = st.get(tid) or {}
            if v.get("sig") == sig and time.time() - float(v.get("last") or 0) < float(c.get("stall_repeat", 600)): continue
            if int(rt.get("retries") or 0) <= 0 and int(rt.get("attempt") or 0) > 0:
                t = _pause(doc, "重试用尽·%s" % KIND.get(kind, kind), c)
            else:
                t = _text(doc, stat, age, kind, detail, rt); qp.push(t, "QQ·卡住", c); nudge(doc, c, st)
            if t: hits.append(t); _state(doc, "stalled", c["sms"])
            st[tid] = {"sig": sig, "last": time.time(), "nudged": float((st.get(tid) or {}).get("nudged") or 0)}
        qp._wj(qp._f(c["sms"], "stall.json"), st); _sync(c); return hits
    except Exception: return []
def tick(sms=None):
    """节流入口（stall_tick 默认 30s）：监听线程每轮调一次，未到窗口回「节流」。"""
    c = qp.conf(sms); now = time.time()
    if now - _last["t"] < float(c.get("stall_tick", 30)): return "节流"
    _last["t"] = now; return check(sms, c) or "无卡住"
def start(sms=None):
    """起 daemon 线程循环（幂等·qq_listen.run 进 Session 循环前调用）：每 5s 醒一次，tick 自按 stall_tick 节流；线程随进程亡，绝不拖住退出。"""
    if getattr(start, "_t", None): return start._t
    def loop():
        while True:
            try: time.sleep(5); tick(sms)
            except Exception: pass
    start._t = threading.Thread(target=loop, daemon=True, name="qq-stall"); start._t.start(); return start._t
def status(sms=None, c=None):
    c = c or qp.conf(sms); rt = _rt(c)
    return {"stall": bool(c.get("stall", True)), "after": c.get("stall_after"), "repeat": c.get("stall_repeat"),
            "tick": c.get("stall_tick"), "nudge": c.get("nudge", 1), "watching": len(stalled(c["sms"], c)),
            "thread": bool(getattr(start, "_t", None)), "runtime": {k: rt.get(k) for k in ("phase", "pid", "attempt", "retries", "err_kind")},
            "state": qp._ld(qp._f(c["sms"], "stall.json"), {}) or {}}
if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]
    if a[0] == "status": print(json.dumps(status(), ensure_ascii=False, indent=1))
    elif a[0] == "check": print(json.dumps(check(), ensure_ascii=False))
    elif a[0] == "tick": print(str(tick()))
    elif a[0] == "nudge":
        import task_table as T; print(nudge(T.load(a[1]) if hasattr(T, "load") else qp._ld(_tf(a[1]), {})))
    else: print(__doc__.strip()[:400])
