#!/usr/bin/env python3
"""agent_task.py — 任务工具 task/task_detail（诉求拆分·按技能实例并行对等对话·合并·批23：每实例自开独立 conv 独立链归属·无主次）：tsk.decompose 拆子任务→逐笔 skill_route 路由，同一技能多次命中编号为实例（skill 两派＝sk_1/sk_2·各开独立对等对话·流前缀 ⧉实例▸·agent_ctx 线程隔离防串台）→ThreadPool 并行（settings task.max_parallel 默认 3·全部子任务同时跑可加大·批18：parallel=false 改依序串行·由模型判定子任务有无依赖/冲突）；子任务异常记 error 不中断其余；每完成一笔经 atomic_io 落 <SMS_HOME>/tasks/<id>.json＋msg_flow task 进度信封（meta.done/total→顶栏实时）；subsession/skill_call 链在 run_skill 内按实例名记；收口生成合并报告（逐实例状态＋全结果＋技能×次数统计），task_detail 复算并再发进度信封（模型/顶栏共用同一进度真源）。用法：python -B agent_task.py run "<诉求>" | detail [task-id]"""
import os, sys, json, time, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import resolve_home, chains, skill_route, task as tsk, agent_tools as at, agent_ctx as ac, atomic_io, settings, stop_channel as stop, task_table as tt
SMS = resolve_home.ensure()
def _tf(tid): return os.path.join(SMS, "tasks", tid + ".json")
def _save(doc): os.makedirs(os.path.join(SMS, "tasks"), exist_ok=True); atomic_io.wjson(_tf(doc["id"]), doc)
def task(intent, parallel=True, lane="fg"):
    """批26 前台/后台双车道：lane=bg＝本表由后台线程跑完（调用方用 bg() 立即拿句柄），表内行与前台共用同一套 status/进度/顶栏（地位相同）；
    唯一差别＝主流程守卫不被后台行卡住（task_table.pending 排除 lane=bg），前台可继续收口。"""
    if str(lane or "fg") == "bg" and threading.current_thread().name != "bg-task": return bg(intent, parallel)
    from concurrent.futures import ThreadPoolExecutor
    subs = tsk.decompose(str(intent)); tid = "task-" + time.strftime("%Y%m%d-%H%M%S") + "-" + "%03d" % (time.time() * 1000 % 1000)  # 毫秒后缀：同秒连发两任务不再互相覆盖 tasks/<id>.json（实测 task2 撞名 IndexOverwrite）
    doc = {"id": tid, "intent": str(intent), "conv": chains.ACTIVE["conv"], "sess": chains.cur_sess(), "created": time.strftime("%Y-%m-%d %H:%M:%S"), "src": __import__("qq_stall").src(chains.ACTIVE["conv"]), "lane": str(lane or "fg"),
      "subtasks": [(dict(x, lane=str(lane or "fg")) if isinstance(x, dict) else {"id": "t%d" % (i + 1), "goal": str(x), "status": "pending", "lane": str(lane or "fg")}) for i, x in enumerate(subs)]}; _save(doc)
    at.emit("task", "任务 " + tid + "：拆出 " + str(len(subs)) + " 子任务·" + ("并行派发" if parallel is not False else "依序串行") + "（剩余时间预测见顶栏）", tool="task", meta={"id": tid, "done": 0, "total": len(subs), "eta_s": tt.eta(doc)})
    lk = threading.Lock(); cnt = {}; parent = ac.cur()
    def one(st):
        ac.adopt(parent); stop.check(); sid, _ = skill_route.route(st["goal"]); sk = (sid or "").split(",")[0] or None
        with lk:
            if sk: cnt[sk] = cnt.get(sk, 0) + 1
            st["skill"] = sk; st["inst"] = (sk + "_" + str(cnt.get(sk, 0))) if sk else st["id"]; st["status"] = "running"
        try: st["result"] = str(at.run_skill(sk, st["goal"], tag=st["inst"]) if sk else at.ask(st["goal"]))[:600]; st["status"] = "done"
        except stop.Stopped: st["result"] = "用户停止（stop）——子任务在检查点收口"; st["status"] = "stopped"
        except Exception as e: st["result"] = "执行失败：" + str(e)[:180]; st["status"] = "error"; __import__("skill_errors").record(SMS, sk or "gateway", "task_subtask", str(e)[:200], True)
        with lk: dn = sum(1 for x in subs if x["status"] == "done"); _save(doc)
        at.emit("task", "任务 " + tid + " 进度 " + str(dn) + "/" + str(len(subs)) + "（" + st["inst"] + " " + st["goal"][:30] + (" " + st["status"] if st["status"] != "done" else "") + "）", tool="task_detail", meta={"id": tid, "done": dn, "total": len(subs), "eta_s": tt.eta(doc)})
        return st
    workers = 1 if parallel is False else max(1, min(max(1, int(settings.get("task.max_parallel", 3))), len(subs)))
    with ThreadPoolExecutor(max_workers=workers) as ex: res = list(ex.map(one, subs))
    stat = "、".join(k + "×" + str(v) for k, v in sorted(cnt.items())) or "无技能命中（子问答作答）"
    merged = "任务 " + tid + " 完成（" + str(len(subs)) + " 子任务 · " + stat + " · 成功 " + str(sum(1 for r in res if r["status"] == "done")) + "/" + str(len(res)) + "）：\n" + "\n".join("[" + r["status"] + "] " + r["inst"] + " · " + r["goal"][:40] + " → " + r["result"] for r in res)
    chains.record("event", "task " + tid + " 收口 " + str(len(subs)) + " 子任务（" + stat + "）", [[chains.ACTIVE["conv"] or "", "ref", 1], [chains.cur_sess(), "member", 1]])
    _save(doc); return merged[:6000]
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
    return "已转后台执行（lane=bg·与前台任务表同一地位·不阻塞本对话）：新建表稍后可用 task_detail 查（清单里 lane=bg 者即后台表）；前台可继续收口，守卫不受后台行阻挡"

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
    at.emit("task", "任务 " + tid + " " + str(dn) + "/" + str(len(doc["subtasks"])), tool="task_detail", meta={"id": tid, "done": dn, "total": len(doc["subtasks"]), "eta_s": tt.eta(doc), "subtasks": doc["subtasks"]})
    return json.dumps({k: doc[k] for k in ("id", "intent", "conv", "sess", "subtasks")}, ensure_ascii=False)[:1500]
if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "run" and len(a) > 1: at.bind(on_line=lambda s: print(s, file=sys.stderr)); print(task(" ".join(a[1:])))
    elif a and a[0] == "detail": print(task_detail(a[1] if len(a) > 1 else ""))
    else: print(__doc__.strip().splitlines()[-1])
