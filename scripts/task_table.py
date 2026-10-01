#!/usr/bin/env python3
"""task_table.py — 任务表制表器（SMS 子技能 task_table·批12②·批14①复杂门控·批18 行数无上限＋主流程守卫·批22 模型裁量）：脚本标点粗分（task.decompose）只作「自动种子」——拆步≥2 且至少一步命中执行性技能时 attach() 先建种子表；批22：判简单时不再沉默，注入〔任务表·脚本未建〕一行把复杂判定权交还模型——模型判复杂即 task_plan op=plan（new_table·免用户写「制表」字样）自建表；〔任务表〕块命令模型据实改表（行数无上限·不得只跑一两行就停）按行推进·每步 task_plan status done·中途 add/remove/skill 改表；pending(conv)＝本对话未完成行清单供 gateway 主流程守卫续推（未完成不得收口·无依赖 task 工具并发·有依赖依序）。落 <SMS_HOME>/tasks/<id>.json＋msg_flow task 信封（顶栏进度/剩余·eta＝未完成行×latency 均值）。用法：python -B task_table.py plan <诉求>|new <步骤逗号分隔>|show <tid>|next <tid>|eta <tid>|status <tid> <t#> <状态>|add <tid> <目标> [技能id]|remove <tid> <t#>|skill <tid> <t#> <技能id>|pending [conv]"""
import os, sys, json, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import resolve_home, chains, task as tsk, skill_route, settings, atomic_io, latency, msg_flow, qq_report
SMS = resolve_home.ensure(); GEN = ("general_answer", "constraint_arbiter"); TD = os.path.join(SMS, "tasks")
def _tf(tid): return os.path.join(TD, tid + ".json")
def _save(doc): os.makedirs(TD, exist_ok=True); atomic_io.wjson(_tf(doc["id"]), doc)
def _load(tid):
    try: return atomic_io.rjson(_tf(tid))
    except Exception: return None  # noqa
def eta(doc): llm = latency.avg("llm|" + str(settings.get("llm_gateway.model", "auto"))) or 45000; return round(sum(((latency.avg("skill|" + str(x.get("skill"))) or llm) if x.get("skill") else llm) for x in (doc.get("subtasks") or []) if x.get("status") in ("pending", "running")) / 1000)
def emit(doc, note="任务表"):
    import agent_tools as at; subs = doc.get("subtasks") or []; dn = sum(1 for x in subs if x.get("status") == "done"); at.emit("task", note + " " + str(doc["id"])[-14:] + "：" + str(dn) + "/" + str(len(subs)) + " " + msg_flow.fmt(eta(doc)), tool="task", meta={"id": doc["id"], "done": dn, "total": len(subs), "eta_s": eta(doc)}); qq_report.progress(doc, note)  # emit
def _rows(subs): return [{"id": "t%d" % (i + 1), "goal": (g := x["goal"] if isinstance(x, dict) else str(x)), "skill": (h := (skill_route.route(g)[0] or "").split(",")[0] or None), "inst": h or ("t%d" % (i + 1)), "status": "pending", "lane": "fg"} for i, x in enumerate(subs)]
def _mkdoc(intent, subs): tid = "task-" + time.strftime("%Y%m%d-%H%M%S") + "-" + "%03d" % (time.time() * 1000 % 1000); doc = {"id": tid, "intent": str(intent), "conv": chains.ACTIVE["conv"], "sess": chains.cur_sess(), "created": time.strftime("%Y-%m-%d %H:%M:%S"), "table": "task_table", "src": __import__("qq_stall").src(chains.ACTIVE["conv"]), "subtasks": subs}; _save(doc); emit(doc, "任务表（粗分种子·首轮据实改表）"); return doc
CUT = "，,。;；、 \n\"'“”‘’「」[]()（）"
def _steps(value): return [x.strip(CUT) for x in re.split(r"[\n,，;；、]", str(value)) if x.strip(CUT)]
def plan(intent, steps=None):
    subs = _rows(steps) if steps is not None else _rows(tsk.decompose(str(intent)))
    if steps is None and (len(subs) < 2 or not any(x["skill"] and x["skill"] not in GEN for x in subs)): return None
    return _mkdoc(intent, subs) if subs else None
def block(doc): return "\n〔任务表 " + doc["id"] + "（预测" + msg_flow.fmt(eta(doc)) + "）〕\n" + "\n".join("%s %s%s%s" % (x["id"], str(x["goal"])[:70], ("〔技能:" + str(x["skill"]) + "〕" if x.get("skill") else "〔工具自办〕"), "〔后台·不阻前台收口〕" if str(x.get("lane", "fg")) == "bg" else "") for x in doc["subtasks"]) + "\n〔执行规则〕这是脚本粗分种子或你自建的表——复杂与否由你判、按真实步骤推进（task_plan add/remove/skill 随时改表），行数无上限、不得只跑一两行就停；按行推进：〔技能:x〕调 skill 派发、〔工具自办〕用 exec/read/write/glob/grep 自办；子任务无依赖可用 task 工具并发派发（你判断无冲突才并发·有依赖 parallel=false 或依序逐 skill）；每步完成立刻 task_plan status <表id> <行id> done（顶栏进度据此刷新）；全部行 done 才输出整合结果收口——派发对话收口＝形式停止·调度方继续未完成行（批23 对等对话），禁止把单个派发完成当作整段任务结束。\n"
def attach(intent): return "" if not settings.get("task.auto_table", True) else (block(d) if (d := plan(intent)) else "\n〔任务表·脚本未建〕标点粗分判非复杂或无执行技能命中——复杂与否由你定：判定需≥2步动手执行时，先 task_plan op=plan value=你拆的各步骤（逗号分隔）自建表并按表推进；单步/问答直接办，勿为表而表。\n")
def pending(conv=""):
    c = conv or chains.ACTIVE.get("conv") or ""; out = []
    for tid in ([fn[:-5] for fn in sorted(os.listdir(TD)) if fn.endswith(".json")] if os.path.isdir(TD) else []):
        doc = _load(tid); rest = [x for x in (doc.get("subtasks") or []) if x.get("status") != "done" and str(x.get("lane", "fg")) != "bg"] if doc and doc.get("conv") == c else []
        rest and out.append("〔任务表 " + tid[-14:] + "〕未完成 " + str(len(rest)) + "/" + str(len(doc.get("subtasks") or [])) + "：" + "；".join(str(x.get("id")) + "｜" + str(x.get("skill") or "工具自办") + "｜" + str(x.get("goal"))[:40] + "〔" + str(x.get("status", "pending")) + "〕" for x in rest)[:600])
    return "\n".join(out)
def unfinished():
    """未完成计划表 [(tid, done, total)]＝仍有非 done 行的表（＝尚未生成最终输出）·底栏停止/继续按钮可见性判据。"""
    out = []
    if not os.path.isdir(TD): return out
    for fn in sorted(os.listdir(TD)):
        if not fn.endswith(".json"): continue
        doc = _load(fn[:-5]); subs = (doc or {}).get("subtasks") or []
        if not subs: continue
        dn = sum(1 for x in subs if x.get("status") == "done")
        if dn < len(subs): out.append((fn[:-5], dn, len(subs)))
    return out

def new_table(intent, sv): rows = _steps(sv); d = plan(intent, steps=rows) if rows else None; return ("已建任务表 " + d["id"] + "（" + str(len(d["subtasks"])) + " 行·据实推进）\n" + block(d)) if d else "建表失败：步骤为空——value/参数＝你拆的步骤（逗号/顿号分隔）"
def _all(): return sorted([f[:-5] for f in (os.listdir(TD) if os.path.isdir(TD) else []) if f.endswith(".json")])
def _find(t): k = [i for i in _all() if (t := str(t or "").strip()) and (i == t or i.endswith(t) or t in i)]; return k[-1] if k else ""
def _latest():
    sc = lambda d: 0 if (c := chains.ACTIVE.get("conv") or "") and d.get("conv") == c else 1 if d.get("sess") == chains.cur_sess() else 2
    op_ = [(d, t) for t in _all() if (d := _load(t)) and any(x.get("status") != "done" for x in (d.get("subtasks") or []))]
    return sorted(op_, key=lambda z: (sc(z[0]), z[1]))[-1][1] if op_ else ""
def revise(op, tid="", row="", value=""):
    if op in ("new", "plan"): st = _steps(value or tid); return new_table(str(tid or value)[:200] if (value or tid) else "未命名任务表", st) if st else "建表失败：value＝你拆的步骤（逗号/顿号分隔）"
    doc = _load(_find(tid) or _latest())
    if not doc: return "无任务表：" + str(tid) + "（task_plan op=plan value=<步骤逗号分隔> 先建表；op=show 看全部）"
    if not row and re.search(r"pending|running|error|stopped", str(value or "")): row, value = str(value), "done"
    subs = doc.get("subtasks") or []; x = next((s for s in subs if s.get("id") == row), None)
    if op == "show": return json.dumps({"id": doc["id"], "sess": doc.get("sess"), "conv": doc.get("conv"), "subtasks": subs}, ensure_ascii=False)[:1800]
    if op == "next": p = next((s for s in subs if s.get("status") == "pending"), None); return (p and (str(p["id"]) + "｜" + str(p.get("skill") or "工具自办") + "｜" + str(p["goal"])[:80])) or "全部完成"
    if op == "eta": return "剩余预测 " + msg_flow.fmt(eta(doc))
    if op == "lane":
        if not x: return "无此行：" + str(row)
        x["lane"] = "bg" if str(value or "").strip().lower() in ("bg", "后台", "back", "background") else "fg"
        _save(doc); emit(doc, "任务表（行转%s）" % ("后台" if x["lane"] == "bg" else "前台"))
        return "行 %s 车道＝%s（后台行不阻前台收口·表内地位相同）" % (row, x["lane"])
    if op == "add": n = 1 + max([int(str(s["id"])[1:]) for s in subs if str(s["id"]).startswith("t") and str(s["id"])[1:].isdigit()] or [0]); sid, _ = skill_route.route(str(value)); h = (sid or "").split(",")[0] or None; subs.append({"id": "t%d" % n, "goal": str(value), "skill": h, "inst": h or "t%d" % n, "status": "pending"}); _save(doc); emit(doc, "任务表加行"); return "已加 t%d｜%s%s" % (n, str(value)[:60], ("·指定技能 " + h) if h else "")
    if op == "remove" and x: subs.remove(x); _save(doc); emit(doc, "任务表删行"); return "已删 " + str(row)
    if op == "status" and x: x["status"] = value if value in ("pending", "running", "done", "error", "stopped") else "done"; _save(doc); emit(doc, "任务表步进"); return str(row) + " → " + x["status"] + "（" + str(sum(1 for s in subs if s.get("status") == "done")) + "/" + str(len(subs)) + "·" + msg_flow.fmt(eta(doc)) + "）"
    if op == "skill" and x: x["skill"] = str(value); x["inst"] = str(value); _save(doc); emit(doc, "任务表改派"); return str(row) + " 指定技能：" + str(value)
    return "用法 task_plan new|show|next|eta|add|remove|status|skill <表id/步骤> [行id] [值]"
