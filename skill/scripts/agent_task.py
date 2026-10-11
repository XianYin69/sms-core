#!/usr/bin/env python3
"""agent_task.py — 任务工具 task/task_detail（诉求拆分·按技能实例并行对等对话·合并·批23：每实例自开独立 conv 独立链归属·无主次）：tsk.decompose 拆子任务→逐笔 skill_route 路由，同一技能多次命中编号为实例（skill 两派＝sk_1/sk_2·各开独立对等对话·流前缀 ⧉实例▸·agent_ctx 线程隔离防串台）→ThreadPool 并行（settings task.max_parallel 默认 3·全部子任务同时跑可加大·批18：parallel=false 改依序串行·由模型判定子任务有无依赖/冲突）；子任务异常记 error 不中断其余；每完成一笔经 atomic_io 落 <SMS_HOME>/tasks/<id>.json＋msg_flow task 进度信封（meta.done/total→顶栏实时）；subsession/skill_call 链在 run_skill 内按实例名记；收口生成合并报告（逐实例状态＋全结果＋技能×次数统计），task_detail 复算并再发进度信封（模型/顶栏共用同一进度真源）。用法：python -B agent_task.py run "<诉求>" | detail [task-id]"""
import os, sys, json, time, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import resolve_home, chains, skill_route, task as tsk, agent_tools as at, agent_ctx as ac, atomic_io, settings, stop_channel as stop, task_table as tt, task_res as tr
SMS = resolve_home.ensure()
def _tf(tid): return os.path.join(SMS, "tasks", tid + ".json")
def _save(doc): os.makedirs(os.path.join(SMS, "tasks"), exist_ok=True); atomic_io.wjson(_tf(doc["id"]), doc)
def _row_fn(doc, subs, lk, cnt, tid, parent, own_ids=None):
    """单行执行闭包（task 工具与 task_plan op=run 共用同一真源）：路由→run_skill/ask→写行
    result/status→落盘＋进度信封。异常只标该行（error＋skill_errors 台账），用户停止＝stopped——
    失败隔离由 task_res.run_rows 的批内并发保证。
    own_ids 非空（批48 跨树并发派发）＝落盘只覆盖本线程负责的这些行、其余行取磁盘最新值：
    后台派发线程与模型本地自办行（task_plan status）同轮写同一张总览时不再互相整表覆盖丢更新。"""
    def one(st):
        ac.adopt(parent); stop.check()
        sid, _ = skill_route.route(st["goal"]); sk = (sid or "").split(",")[0] or None
        with lk:
            if sk: cnt[sk] = cnt.get(sk, 0) + 1
            st["skill"] = sk
            st["inst"] = (sk + "_" + str(cnt.get(sk, 0))) if sk else st["id"]
            st["status"] = "running"
            st["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")  # 批33 缺陷C：置 running 即记行级时间戳
        try:
            r = at.run_skill(sk, st["goal"], tag=st["inst"]) if sk else at.ask(st["goal"])
            st["result"] = str(r)[:600]; st["status"] = "done"
        except stop.Stopped:
            st["result"] = "用户停止（stop）——子任务在检查点收口"; st["status"] = "stopped"
        except Exception as e:
            st["result"] = "执行失败：" + str(e)[:180]; st["status"] = "error"
            se = __import__("skill_errors")
            se.record(SMS, sk or "gateway", "task_subtask", se.describe(e), True)
        with lk:
            dn = sum(1 for x in subs if x["status"] == "done")
            _own_save(doc, own_ids) if own_ids is not None else _save(doc)
        at.emit("task", "任务 " + str(doc.get("intent") or "")[:16] + " 进度 " + str(dn) + "/" + str(len(subs)) + "："
                + st["inst"] + " " + st["goal"][:30]
                + (" " + st["status"] if st["status"] != "done" else "") + "。",
                tool="task_detail", meta={"id": tid, "done": dn, "total": len(subs), "eta_s": tt.eta(doc)})
        return st
    return one


def task(intent, parallel=True, lane="fg"):
    """批26 前台/后台双车道：lane=bg＝本表由后台线程跑完（调用方用 bg() 立即拿句柄），表内行与前台共用同一套 status/进度/顶栏（地位相同）；
    唯一差别＝主流程守卫不被后台行卡住（task_table.pending 排除 lane=bg），前台可继续收口。"""
    if str(lane or "fg") == "bg" and threading.current_thread().name != "bg-task": return bg(intent, parallel)
    subs = tsk.decompose(str(intent)); tid = "task-" + time.strftime("%Y%m%d-%H%M%S") + "-" + "%03d" % (time.time() * 1000 % 1000)  # 毫秒后缀：同秒连发两任务不再互相覆盖 tasks/<id>.json（实测 task2 撞名 IndexOverwrite）
    doc = {"id": tid, "intent": str(intent), "conv": chains.ACTIVE["conv"], "sess": chains.cur_sess(), "created": time.strftime("%Y-%m-%d %H:%M:%S"), "src": __import__("qq_stall").src(chains.ACTIVE["conv"]), "lane": str(lane or "fg"),
      "subtasks": [(dict(x, lane=str(lane or "fg")) if isinstance(x, dict) else {"id": "t%d" % (i + 1), "goal": str(x), "status": "pending", "lane": str(lane or "fg")}) for i, x in enumerate(subs)]}; _save(doc)
    at.emit("task", "任务 " + str(doc.get("intent") or "")[:16] + "：拆出 " + str(len(subs)) + " 子任务·" + ("并行派发" if parallel is not False else "依序串行") + "（剩余时间预测见顶栏）", tool="task", meta={"id": tid, "done": 0, "total": len(subs), "eta_s": tt.eta(doc)})
    lk = threading.Lock(); cnt = {}; one = _row_fn(doc, subs, lk, cnt, tid, ac.cur())
    workers = 1 if parallel is False else max(1, min(max(1, int(settings.get("task.max_parallel", 3))), len(subs)))
    out = tr.run_rows(subs, one, limit=workers, timeout=(0 if parallel is False else settings.get("task.row_timeout", 0)), src=tid)
    res = out["results"]
    stat = "、".join(k + "×" + str(v) for k, v in sorted(cnt.items())) or "无技能命中（子问答作答）"
    merged = "任务 " + tid + " 完成（" + str(len(subs)) + " 子任务 · " + stat + " · 成功 " + str(sum(1 for r in res if r["status"] == "done")) + "/" + str(len(res)) + "）：\n" + "\n".join("[" + r["status"] + "] " + r["inst"] + " · " + r["goal"][:40] + " → " + r["result"] for r in res)
    chains.record("event", "task " + tid + " 收口 " + str(len(subs)) + " 子任务（" + stat + "）", [[chains.ACTIVE["conv"] or "", "ref", 1], [chains.cur_sess(), "member", 1]])
    merged += "\n并发批次：" + "｜".join("+".join(b) for b in out["batches"]) + "（批间串行＝资源冲突或超并行度·批内并发≤" + str(workers) + "·墙钟 " + str(out["wall_s"]) + "s·失败 " + str(out["error"]) + "·超时 " + str(out["timeout"]) + "）"
    _save(doc); return merged[:6000]
def run_table(doc, rows=None):
    """task_plan op=run：把表内未完成行按资源互斥自动组成并发批次一次执行（task_res.batches→run_rows）——
    批内并发≤task.batch_parallel、每行独立超时 task.row_timeout、失败隔离（异常/超时只标该行并写 error 链），
    行状态与进度信封仍落 tasks/<id>.json＋顶栏（与 task 工具同一真源）。"""
    subs = doc.get("subtasks") or []
    rows = rows if rows is not None else [x for x in subs if x.get("status") in ("pending", "running")]
    if not rows: return "无未完成行——本表已清空"
    lk = threading.Lock(); cnt = {}; tid = doc["id"]
    out = tr.run_rows(rows, _row_fn(doc, subs, lk, cnt, tid, ac.cur()), limit=max(1, int(settings.get("task.batch_parallel", 3) or 3)), src=tid)
    _save(doc); tt.emit(doc, "任务总览（并发批次执行）")
    return "并发批次执行完成：批 %d 个〔%s〕·成功 %d/%d·失败 %d·超时 %d·墙钟 %ss（剩余预测已按批内最大值）" % (
        len(out["batches"]), "｜".join("+".join(b) for b in out["batches"]), out["done"], len(rows), out["error"], out["timeout"], out["wall_s"])

def subs_of(d):
    return ((d or {}).get("subtasks") or [])


def _own_save(doc, ids):
    """后台并发批次写盘保护（批48·跨任务并行＋本地处理同轮进行的关键）：
    只把本线程负责的行（ids）覆盖进磁盘上的最新总览，其余行保持磁盘值——
    否则「后台派发线程写」与「模型本地自办行 task_plan status 写」会互相整表覆盖丢更新。"""
    d = tt._load(str(doc.get("id") or "")) or doc
    by = {str(x.get("id")): x for x in (doc.get("subtasks") or []) if str(x.get("id")) in ids}
    d["subtasks"] = [by.get(str(x.get("id")), x) or x for x in (d.get("subtasks") or [])]
    tt._save(d)
    return d


def run_tree(doc, wait=False):
    """op=run value=tree（批48·多任务多步骤与子步骤并行）：整棵总览（根任务＋全部延申任务）的未完成
    叶子行按资源互斥组批，**发送处理**行（〔发〕＝有技能命中）交后台线程并发派发对等对话，
    **本地处理**行（〔本〕＝无技能/目标写 self=）当场列回模型自办——两路同时进行（＝用户要的
    「并行发送处理和本地处理」）；只动本对话可归属的表（批32 越会话拒写口径不变），他对话表跳过并列出。
    wait=True（op=run value=tree:wait）＝同步等批次跑完再回（保守口径）。"""
    docs = []
    try:
        docs = tt.T.tree_of(doc) if tt._tree_on() else [doc]
    except Exception: docs = [doc]
    mine, skip = [], []
    for d in docs:
        (mine if tt._mine(d) else skip).append(d)
    lk = threading.Lock(); cnt = {}; send, local = [], []
    fns = {}; own_docs, own_rows = [], []
    for d in mine:
        subs = d.get("subtasks") or []
        fn = _row_fn(d, subs, lk, cnt, d["id"], ac.cur(),
                 own_ids={str(r.get("id")) for r in subs})
        for x in tt.open_rows(d):
            if str(x.get("status")) not in ("pending", "running"): continue
            if tt.T and tt.T.chan(x) == "send":
                send.append(x); fns[id(x)] = fn
                own_docs.append(d); own_rows.append(x)
            else:
                local.append(x)
    if not send and not local:
        return "整棵树无可执行未完成叶子行" + ("（跳过他对话表 %d 张·:session use 接续）" % len(skip) if skip else "")
    if not send:
        return ("本树无可派发（〔发〕）行，%d 行全为本地处理行，请按清单用 exec/read/write 自办%s"
                % (len(local), "；他对话表 %d 张未代改" % len(skip) if skip else "")) + "\n" + _local_list(local)
    lim = max(1, int(settings.get("task.batch_parallel", 3) or 3))
    runner = lambda r: fns[id(r)](r)
    ids = {str(r.get("id")) for r in send}
    own = {id(r): d for d, r in zip(own_docs, own_rows)}   # 行→属主表（跨表并发各写各的表）
    src = str(doc["id"])
    if wait:
        out = tr.run_rows(send, runner, limit=lim, src=src)
        for d in mine:
            tt._save(d); tt.emit(d, tt.LABEL + "（整棵树并发批次执行·同步）")
        bt = "+".join("×".join(b) for b in out["batches"])
        return ("跨表跨层级并发批次完成：树内 %d 张表·本批 %d 行分 %d 批〔%s〕·成功 %d·失败 %d·超时 %d·墙钟 %ss"
                % (len(mine), len(send), len(out["batches"]), bt,
                   out["done"], out["error"], out["timeout"], out["wall_s"])
                + ("；他对话表 %d 张未代改" % len(skip) if skip else "")
                + ("\n另有本地处理行（同轮自办）：\n" + _local_list(local) if local else ""))

    def _bg_run():
        try:
            tr.run_rows(send, runner, limit=lim, src=src,
                        on_row=lambda r, st: _own_save(
                            own.get(id(r), doc), {str(r.get("id"))}))
            for d in mine:
                tt.emit(d, tt.LABEL + "（整棵树发送处理并发批次收口）")
        except Exception as e:
            __import__("chain_error").hook("run_tree", src, repr(e)[:200])
    th = threading.Thread(target=_bg_run, daemon=True, name="bg-tree")
    th.start()
    return ("已并发派发 %d 行（〔发〕·跨 %d 张表·后台线程组批跑·批内≤%d·失败隔离只标该行），"
            "另有 %d 行是〔本〕本地处理行——请本轮就用 exec/read/write/glob/grep 自办（与派发同时进行，"
            "进度照常落总览＋顶栏，稍后 task_detail 查）%s\n本地待办清单：\n%s"
            % (len(send), len(mine), lim, len(local),
               ("；他对话表 %d 张未代改（:session use 接续）" % len(skip) if skip else ""),
               _local_list(local) if local else "（无）"))


def _local_list(rows):
    """本地处理行清单（回给模型自办）。"""
    return "\n".join("〔本〕%s｜%s" % (r.get("id"), str(r.get("goal"))[:70]) for r in rows) or "（无）"


def bg(intent, parallel=True):
    """后台车道（并行处理）：另起线程跑 task(lane=bg)，本对话立刻拿句柄继续干别的；进度照常落 tasks/<id>.json＋顶栏。"""
    def _run():
        _prev = dict(chains.ACTIVE); _pe = os.environ.get("SMS_SESSION"); _sid = ""
        try:
            import session_reg as sreg
            _sid = sreg.bind("bg", "bg-" + str(int(time.time() * 1000) % 100000000), "后台·" + str(intent)[:24])
            _cv = chains.session_id(); chains.set_active(conv=_cv); sreg.attach(_cv, _sid)
        except Exception: pass
        try: task(intent, parallel, lane="bg")
        except stop.Stopped:
            try:
                d = os.path.join(SMS, "tasks")
                for f in sorted([x for x in os.listdir(d) if os.path.isfile(os.path.join(d, x)) and x.endswith(".json")])[-1:]:
                    doc = atomic_io.rjson(os.path.join(d, f))
                    for x in doc.get("subtasks") or []:
                        x["status"] = x.get("status") if x.get("status") == "done" else "stopped"
                    atomic_io.wjson(os.path.join(d, f), doc)
            except Exception: pass
        except Exception as e:
            __import__("chain_error").hook("bg-task", str(intent)[:40], repr(e)[:200])
        finally:
            try:
                chains.ACTIVE.clear(); chains.ACTIVE.update(_prev)
                if _pe is None: os.environ.pop("SMS_SESSION", None)
                else: os.environ["SMS_SESSION"] = _pe
                try:
                    if _sid: __import__("session_reg").release(_sid)  # 后台任务收口＝session 置 finished（数据留）
                except Exception: pass
            except Exception: pass
    th = threading.Thread(target=_run, daemon=True, name="bg-task")
    th.start()
    return "已转后台执行（lane=bg·与前台任务总览同一地位·不阻塞本对话）：新建表稍后可用 task_detail 查（清单里 lane=bg 者即后台表）；前台可继续收口，守卫不受后台行阻挡"

def task_detail(tid=""):
    d = os.path.join(SMS, "tasks"); ids = sorted(x[:-5] for x in (os.listdir(d) if os.path.isdir(d) else []) if x.endswith(".json") and os.path.isfile(os.path.join(d, x)))
    if not tid:
        mark = []
        for i in ids[-5:]:
            d = atomic_io.rjson(_tf(i)) or {}
            mark.append(i + ("〔后台〕" if d.get("lane") == "bg" else "〔前台〕"))
        return "任务清单：" + ("、".join(mark) or "（无）")
    try: doc = atomic_io.rjson(_tf(tid))
    except Exception: return "无任务：" + tid
    dn = sum(1 for x in doc["subtasks"] if x.get("status") == "done")
    at.emit("task", "任务 " + str(doc.get("intent") or "")[:16] + " " + str(dn) + "/" + str(len(doc["subtasks"])), tool="task_detail", meta={"id": tid, "done": dn, "total": len(doc["subtasks"]), "eta_s": tt.eta(doc), "subtasks": doc["subtasks"]})
    return json.dumps({k: doc[k] for k in ("id", "intent", "conv", "sess", "subtasks")}, ensure_ascii=False)[:1500]
if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "run" and len(a) > 1: at.bind(on_line=lambda s: print(s, file=sys.stderr)); print(task(" ".join(a[1:])))
    elif a and a[0] == "detail": print(task_detail(a[1] if len(a) > 1 else ""))
    else: print(__doc__.strip().splitlines()[-1])
