#!/usr/bin/env python3
"""task_table.py — 任务总览制表器（SMS 子技能 task_table·批49 编号制：只给任务树下的子节点分配层级编号（1、2、2.1…）·任务完全不编号·旧平铺设计废弃树为唯一设计·批12②·批14①复杂门控·批18 行数无上限＋主流程守卫·批22 模型裁量）：脚本标点粗分（task.decompose）只作「自动种子」——拆步≥2 且至少一步命中执行性技能时 attach() 先建种子表；批22：判简单时不再沉默，注入〔任务表·脚本未建〕一行把复杂判定权交还模型——模型判复杂即 task_plan op=plan（new_table·免用户写「制表」字样）自建表；〔任务表〕块命令模型据实改表（行数无上限·不得只跑一两行就停）按行推进·每步 task_plan status done·中途 add/remove/skill 改表；pending(conv)＝本对话未完成行清单供 gateway 主流程守卫续推（未完成不得收口·无依赖 task 工具并发·有依赖依序）；批29 子步骤并行真可用（task_res.py）：行资源声明 files=/dir=/reads=/port=/device=/skill= ＋冲突判定（写-写/写-读互斥·只读共享·端口设备互斥）＋ op=conflict 回传可并发/须串行分组 ＋ op=run 按互不冲突组并发批次执行（task.batch_parallel 上限·task.row_timeout 行级超时·失败隔离写 error 链）＋ eta 改批内最大值求和。批47 摸鱼根治（用户「你学会一直开新的任务表来摸鱼了是不是」·真源取证＝10-11 08:00/08:08/08:19 三张表 intent 全为看门狗补投文本，src=qq、conv 各不相同）：qq_stall.nudge 补投经 agent_stream.ask 投进数据流＝每次输入必开新 conv（红线17），旧版 attach() 把补投原文再标点粗分＝必建一张新种子表；而 pending() 只认 doc["conv"]==当前 conv、_mine() 又禁越会话回写，原表遂永远「未完成」，其新表自己也推不完 → 下轮再补投再建新表＝滚雪球（同一件事堆 3~4 张表＝看着像忙、实为摸鱼）。现 claim()＝按表尾号认领原表续推（同 session 才接管·claims 留痕·行内容零改·绝不另建；批50 他 session 的表先按完成证据自动补标、确未完成才说明由所属会话推进，已不要求 :session use，已收口只回免表提示）；plan() 垃圾行拒建（noop/纯表号/去符号不足4字，steps 传字符串不再逐字拆 n|o|o|p——实测幽灵表 task-20261011-095214-045 单行 goal=noop 即卡守卫）；sweep()＝补投残表/全垃圾表静默超时后逐行 stopped 落 archive；attach() 免表时若本 conv 已有在途表则列出（续推它、别开新表）。落 <SMS_HOME>/tasks/<id>.json＋msg_flow task 信封（顶栏进度/剩余·eta＝未完成行×latency 均值）。用法：python -B task_table.py plan <诉求>|new <步骤逗号分隔>|show <tid>|next <tid>|eta <tid>|status <tid> <行编号> <状态>|add <tid> <目标> [技能id]|remove <tid> <行编号>|skill <tid> <行编号> <技能id>|pending [conv]|stale [分钟]|reconcile [conv]|sweep [分钟]|claim <表尾号>|attach <文本>｜批51 用户有明确指令或有处理复杂任务意图时必须建立任务节点（task_intent 判据·plan 必建·免模型裁量·纯问句/闲聊仍免表）"""
import os, sys, json, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import resolve_home, chains, task as tsk, skill_route, settings, atomic_io, latency, msg_flow, qq_report, task_res as tr
SMS = resolve_home.ensure(); GEN = ("general_answer", "constraint_arbiter"); TD = os.path.join(SMS, "tasks")
# 批48 任务总览·树形引擎（真源 task_tree.py；导入失败即整体退回旧平铺口径，绝不断主链路）
try: import task_tree as T
except Exception: T = None
LABEL = "任务总览"
def _tree_on(): return bool(T)  # 批49：旧平铺表设计废弃·树为唯一设计（仅 task_tree 导入失败才降级＝防崩不防错）
def is_agg(doc, row): return bool(T) and bool(T.kids(doc, row.get("id")))
def open_rows(doc):
    """未完成行＝未完成「叶子行」（批48）：父行是子步骤的汇总节点、不自己干活，不计入待办与 ETA——
    否则父行永远催不完（＝「看着忙、实际推不动」的又一形态）。树引擎判失败退回降级口径。"""
    subs = (doc or {}).get("subtasks") or []
    if _tree_on():
        try: return [x for x in subs if open_row(x) and T.is_leaf(doc, x)]
        except Exception: pass  # noqa 退回平铺
    return [x for x in subs if open_row(x)]
def guard_rows(doc, conv_ok=None):
    """守卫催办集＝未完成叶子行∧非 bg 车道（conv_ok 传入时按其过滤归属）。"""
    if not doc: return []
    out = [x for x in open_rows(doc) if guard_row(x) and str(x.get("lane", "fg")) != "bg"]
    return out if conv_ok is None or conv_ok else []

def _tf(tid): return os.path.join(TD, tid + ".json")
TERMINAL = ("done", "skipped", "error", "stopped")  # 批34 终态集：skipped＝用户指令弃置/中止，不再算未完成
def open_row(x): return str((x or {}).get("status") or "pending") not in TERMINAL
def guard_row(x):  # 主流程守卫催办判据：skipped/stopped＝已闭不催，error＝仍需处置继续催
    return str((x or {}).get("status") or "pending") in ("pending", "running", "error")
_SIG = {}
def _lc(tid):
    """批29 P1-01：按 (mtime_ns,size) 缓存解析——tasks\\ 已 115 张/186KB，旧版每次全量 rjson 把 UI 线程打到 950ms/s 空转。"""
    q = _tf(tid)
    try: st = os.stat(q); sg = (st.st_mtime_ns, st.st_size)
    except Exception: sg = None
    c = _SIG.get(tid)
    if sg is not None and c and c[0] == sg: return c[1]
    d = _load(tid)
    if len(_SIG) > 3000: _SIG.clear()
    _SIG[tid] = (sg, d); return d
def _save(doc):
    if _tree_on():
        try: T.rollup(doc); T.order(doc)
        except Exception: pass  # noqa 汇总失败仍照常落盘，绝不断主链路
    os.makedirs(TD, exist_ok=True); atomic_io.wjson(_tf(doc["id"]), doc)
    subs = doc.get("subtasks") or []
    if subs and all(str(x.get("status")) in ("done", "skipped") for x in subs): _arch(doc["id"])
def _arch(tid):
    """批29 P3-12：全行 done 的表自动移入 tasks_archive\\，tasks\\ 只留在途表（P1-01 空转放大根因）。"""
    try:
        q = _tf(tid)
        if not os.path.exists(q): return ""
        os.makedirs(AD, exist_ok=True); os.replace(q, os.path.join(AD, tid + ".json"))
        _SIG.pop(tid, None); return tid
    except Exception: return 
AD = os.path.join(SMS, "tasks_archive")
def _load(tid):
    try:
        q = _tf(tid)
        if not os.path.exists(q): q = os.path.join(AD, tid + ".json")
        return atomic_io.rjson(q)
    except Exception: return None  # noqa
def _per_ms(llm):
    """单行预估毫秒：命中技能取该技能 latency 均值，否则取 llm 均值（旧口径不变）。"""
    def per(x): return (latency.avg("skill|" + str(x.get("skill"))) or llm) if x.get("skill") else llm
    return per
def eta(doc, parallel=None):
    """剩余时间预测（批29 修正）：默认按并发批次「批内最大值求和」（task.eta_parallel），
    旧版逐行累加在并行时高估耗时（实测 6 行表预测 240s·真实两批≈80s）；parallel=false 退回累加口径。"""
    llm = latency.avg("llm|" + str(settings.get("llm_gateway.model", "auto"))) or 45000
    rows = open_rows(doc)
    if not rows: return 0
    par = bool(settings.get("task.eta_parallel", True)) if parallel is None else bool(parallel)
    tot = tr.batch_eta(rows, _per_ms(llm)) if par else sum(_per_ms(llm)(x) for x in rows)
    return round(tot / 1000)
def _other_rows(tid="", conv=""):
    """跨表并行判定依据：同对话其他在途表的未完成行（多任务之间的子步骤并行也要有互斥证据）。"""
    c = conv or chains.ACTIVE.get("conv") or ""; out = []
    if not os.path.isdir(TD): return out
    for fn in sorted(os.listdir(TD)):
        t = fn[:-5]
        if not fn.endswith(".json") or t == tid: continue
        d = _lc(t)
        if not d or (c and d.get("conv") != c): continue
        out += open_rows(d)   # 批48：跨表并行判定同口径＝只取未完成叶子行（父行是汇总节点）
    return out
def emit(doc, note=LABEL):
    import agent_tools as at
    # 批48 进度口径：分母＝叶子步骤数（父行是子步骤的汇总节点，计入即「做了三个子步骤、进度只涨 1/4」的错觉）
    subs = doc.get("subtasks") or []
    lf = T.leaves(doc) if _tree_on() else subs
    tot, dn = len(lf), sum(1 for x in lf if x.get("status") == "done")
    at.emit("task", note + "：" + str(dn) + "/" + str(tot)
              + " " + msg_flow.fmt(eta(doc)), tool="task",
              meta={"id": doc["id"], "done": dn, "total": tot, "eta_s": eta(doc)})
    qq_report.progress(doc, note)  # emit
def _rows(subs):
    """种子行（批48 加树字段）：pid＝父行（空＝顶层·所有行皆为根任务的延申）、k＝目的签名（合并判据）。"""
    out = []
    for i, x in enumerate(subs):
        g = x["goal"] if isinstance(x, dict) else str(x)
        sid, _ = skill_route.route(g); h = (sid or "").split(",")[0] or None
        out.append({"id": "t%d" % (i + 1), "goal": g, "skill": h, "inst": h or ("t%d" % (i + 1)),
                    "status": "pending", "lane": "fg", "pid": "", "k": (T.sig(g) if T else g),
                    "res": sorted(tr.resources(g, h or "")[0])})
    return out


def _mkdoc(intent, subs, parent=None, root=None):
    """建总览文档（批48 多 root/parent 两键）：parent＝挂在哪张表下（＝其延申），root＝所在树根；
    parent 缺省时 T.stamp() 在本 conv/session 的在途表里认最近一张「目的不同」者为父（首表自为根）。"""
    tid = "task-" + time.strftime("%Y%m%d-%H%M%S") + "-" + "%03d" % (time.time() * 1000 % 1000)
    if _tree_on():
        p, r = (parent or ""), (root or "")
        if not p:
            try: p, r = T.stamp(str(intent))
            except Exception: p, r = "", ""
        if not r: r = p or tid
    else: p, r = "", tid
    doc = {"id": tid, "intent": str(intent), "conv": chains.ACTIVE["conv"],
           "sess": chains.cur_sess(), "created": time.strftime("%Y-%m-%d %H:%M:%S"),
           "table": "task_table",
           "parent": p or None, "root": r,
           "src": __import__("qq_stall").src(chains.ACTIVE["conv"]), "subtasks": subs}
    try: inher = _subtasks_inherit(subs)
    except Exception: inher = 0  # noqa 继承失败照常建表，绝不断主链路
    _save(doc)
    emit(doc, LABEL + ("（粗分种子·首轮据实改表·%d 行按完成证据自动置 done）" % inher
                       if inher else "（粗分种子·首轮据实改表）"))
    return doc


CUT = "，,。;；、 \n\"'“”‘’「」[]()（）"
def _steps(value): return [x.strip(CUT) for x in re.split(r"[\n,，;；、]", str(value)) if x.strip(CUT)]
JUNK = re.compile(r"^(noop|none|null|todo|tbd|placeholder|占位|空转|t\d+)$", re.I)
def _junk(g):
    """垃圾行判据（批47）：noop 类占位、纯表号/纯 tid 指代、去符号后不足 4 字＝宁缺勿滥，绝不建空转表。"""
    t = str(g or "").strip()
    if not t or JUNK.match(t): return True
    if re.match(r"^(task-)?\d{3}-?\d{6}-?\d{3}$", t): return True
    return len(re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", t.lower())) < 4


# 批51 明确指令/复杂任务意图判据（plan 必建任务节点·纯问句/闲聊仍免表）
_EXPL = re.compile(r"(帮我|帮我把|请|麻烦|把|将|做|写|创建|新建|生成|修改|更新|整理|分析|处理|执行|部署|设计|开发|实现|测试|检查|排查|调查|研究|制定|规划|准备|制作|翻译|转换|优化|重构|修复|解决|收集|汇总|统计|发布|安装|配置|初始化|搭建|组织|编排|拆分|合并|导出|导入|绘制|下载|上传|批量|自动|脚本|程序|任务|项目|方案|文档|报告|完成|清理|审计|验收|核对|核验|取证|验证|归档)", re.I)
_CMPL = re.compile(r"(先.{0,12}(再|然后|随后)|分步|一步一步|分步骤|分阶段|步骤|按计划|计划|流程|阶段|环节|多步|多项|多个|逐一|依次|同时|并且|以及|包括|涉及|覆盖|完整|全套|整个|总共|全部|拆解|分解)", re.I)
_ASK = re.compile(r"[？?]\s*$|(如何|怎么样|怎样|是什么|吗|呢|吧)\s*$|^(什么|怎么|如何|为啥|为什么|是否|哪|能不能|可否|有没有|请解释|解释一下)")


def task_intent(text):
    """批51：用户有「明确指令」或「处理复杂任务意图」＝必须建立任务节点——给的是要做的事（祈使/执行动词）
    或多步骤/多事项/计划性表述（连词/顺序/枚举/≥3 个分句）；纯问句/闲聊/寒暄/垃圾文本＝免表直送。"""
    t = str(text or "").strip()
    if not t or _junk(t): return False
    if _ASK.search(t): return False
    if _CMPL.search(t): return True
    if len([x for x in re.split(r"[，,。;；、\n]", t) if x.strip()]) >= 3: return True
    return bool(_EXPL.search(t))


def _maxn(subs):
    """表内最大行号＋1（新行编号真源）：并入/加行都从这里取号，避免与既有 t# 撞号（撞号即 DFS 去重丢行）。"""
    n = [int(str(x.get("id"))[1:]) for x in subs
         if str(x.get("id")).startswith("t") and str(x.get("id"))[1:].isdigit()]
    return 1 + max(n or [0])


def graft(doc, subs, note=""):
    """同目的自动并入（批48 核心动作）：①与既有行「目的相同」（≥task.merge_sim）的新步骤＝丢弃并记 also
    （＝步骤去重，绝不出现两行同义活）；②目的相近（≥阈值-0.2）的既有行＝作父行，本步骤成为其子步骤
    （层级≤task.tree_max_depth，超限则退回顶层行）；③都不相近＝顶层新行（＝根任务的新延申）。
    只动结构，不动已完成行的 result（不改工作成果、只并结构）。回 (新增行数, 去重行数)。"""
    subs2 = doc.get("subtasks") or []; added = dup = 0
    for x in subs:
        m, v = (T.match_row(doc, x.get("goal"), rows=subs2) if T else (None, 0))
        if m is not None:
            dup += 1
            m.setdefault("also", []).append(str(x.get("goal"))[:60])
            continue
        pid = ""
        if T:
            cand = [r for r in subs2 if str(r.get("status")) not in ("done", "skipped")]
            pm, pv = T.match_row(doc, x.get("goal"), rows=cand, at=max(0.45, T.th() - 0.2))
            if pm is not None and T.depth(doc, pm) < T.max_depth():
                pid = str(pm["id"])
        x["pid"] = pid or str(x.get("pid") or "")
        x["id"] = "t%d" % _maxn(subs2)      # 并入必须重新编号：种子行自带 t1..tN，与既有行同号即撞车
        x["merged_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        subs2.append(x); added += 1
    try: inher = _subtasks_inherit(subs2)
    except Exception: inher = 0  # noqa 继承失败照常并入，绝不断主链路
    doc["subtasks"] = subs2
    doc["merged"] = int(doc.get("merged") or 0) + added
    _save(doc)
    emit(doc, LABEL + "（同目的自动并入 " + str(added) + " 行·去重 " + str(dup) + " 行" + note
         + ("·%d 行按完成证据自动置 done）" % inher if inher else "）"))
    chains.log("tool", "task_table.graft:" + str(doc["id"])[-14:] + " 并入 " + str(added)
               + " 行、步骤去重 " + str(dup) + " 行")
    return added, dup


def _add(doc, subs, parent_row, value):
    """op=add（批48）：①同目的行已存在＝自动合并（不新增行，旧行记 also 同义表述）；②第 3 参数（或
    row 位）给父行编号（层级号 2.1 或 t#）／目标里写 parent=t3／目标以「t3：」「2.1：」开头＝把新步骤挂为其子步骤（层级≤tree_max_depth）；
    ③否则作顶层行（＝根任务的新延申）。"""
    g = str(value or "").strip()
    if not g or _junk(g): return "加行失败：目标为空或纯占位（noop/表号类）——不建垃圾行"
    pref = str(parent_row.get("id") if isinstance(parent_row, dict) else (parent_row or "")).strip()
    pid = pref
    m = re.match(r"^(t\d+|\d+(?:\.\d+)+|\d+)[：:]", g) or re.match(r"^(t\d+)[：:\s]", g)
    if m: pid, g = m.group(1), g[m.end():].strip()
    m2 = re.search(r"\bparent\s*=\s*(t\d+|\d+(?:\.\d+)*)", g, re.I)
    if m2: pid, g = m2.group(1), re.sub(r"\bparent\s*=\s*(t\d+|\d+(?:\.\d+)*)", " ", g, flags=re.I).strip()
    if pid and T:
        pr = T.resolve(doc, pid)
        if pr is not None:
            pid = str(pr.get("id"))
        elif not any(str(x.get("id")) == pid for x in subs):
            return "加行失败：父行 " + pid + " 不存在（用总览里的层级编号或内部行号 t#）——未新增"
    elif pid and not any(str(x.get("id")) == pid for x in subs):
        return "加行失败：父行 " + pid + " 不存在——未新增"
    if _tree_on():
        try:
            mm, v = T.match_row(doc, g, rows=subs)
            if mm is not None:
                mm.setdefault("also", []).append(g[:60])
                _save(doc); emit(doc, LABEL + "（步骤同目的自动合并）")
                return ("步骤同目的自动合并：并入既有行 " + str(mm["id"]) + "（相似 " + str(round(v, 2)) +
                        "≥task.merge_sim），未新增重复行——该行的目标/技能/资源保持不变")
            if pid:
                d0 = T.depth(doc, next(x for x in subs if str(x["id"]) == pid))
                if d0 >= T.max_depth():
                    return ("加行拒绝：超出层级上限 task.tree_max_depth=" + str(T.max_depth()) + "（" + pid +
                            " 已在第 " + str(d0) + " 层）——请并表或改挂上层")
        except Exception: pass  # noqa 判据异常退回普通加行
    n = _maxn(subs)
    sid, _ = skill_route.route(g); h = (sid or "").split(",")[0] or None
    row = {"id": "t%d" % n, "goal": g, "skill": h, "inst": h or ("t%d" % n), "status": "pending",
           "lane": "fg", "pid": pid, "k": (T.sig(g) if T else g),
           "res": sorted(tr.resources(g, h or "")[0])}
    subs.append(row)
    try: inh = _subtasks_inherit([row])
    except Exception: inh = 0  # noqa 继承失败照常加行，绝不断主链路
    _save(doc)
    emit(doc, LABEL + "加行" + ("（挂 " + pref + " 之下）" if pref else "")
         + ("（该步骤按完成证据自动置 done）" if inh else ""))
    return "已加 %s｜%s%s%s%s" % (T.label(doc, row) if T else "t%d" % n, g[:60],
                                 ("·指定技能 " + h) if h else "", ("·父行 " + pref) if pref else "",
                                 ("·完成证据命中自动置 done" if inh else ""))


def plan(intent, steps=None, parent=None, root=None, merge=True):
    """建总览（批48 合并优先）：①在途表里有「目的相同」的那张且属本对话 → graft 并入它、绝不另建同义新表；
    ②同目的表属他对话（同 session）→ 不越会话改他人表，但把新表挂到其下作延申（parent/root 先定）；
    ③无同目的表 → 正常建表，由 _mkdoc→task_tree.stamp() 认最近一张在途表为父。
    steps 给字符串＝按逗号/顿号拆（批47）；步骤全垃圾＝一律不建表。"""
    if isinstance(steps, str): steps = _steps(steps)
    raw = steps if steps is not None else tsk.decompose(str(intent))
    clean = [x for x in (raw or []) if not _junk(x["goal"] if isinstance(x, dict) else str(x))]
    subs = _rows(clean)
    if steps is None and not task_intent(str(intent)) and (len(subs) < 2 or not any(x["skill"] and x["skill"] not in GEN for x in subs)): return None
    if not subs: return None
    if _tree_on() and merge:
        try:
            d, v, ok = T.find_merge(str(intent))
            if d is not None and ok and _mine(d):
                graft(d, subs, note="·同目的 " + str(round(v, 2)))
                chains.log("tool", "task_table.plan 合并优先：命中同目的表 "
                           + str(d["id"])[-14:] + "（" + str(round(v, 2)) + "）→ 未另建新表")
                return d
            if d is not None:
                parent, root = str(d["id"]), str((T.root_of(d) or d).get("id"))
        except Exception: pass  # noqa 合并判定失败＝照常建表，绝不断主链路
    return _mkdoc(intent, subs, parent=parent, root=root)


RESUME = re.compile(r"(?:继续当前任务(?:总览|表)?未完成行|〔认领表)[^0-9A-Za-z_-]{0,14}([0-9A-Za-z_-]{6,24})")
_RESUME_INTENT = re.compile(r"继续|之前|上次|接着|沿用|接续|再次|续做|续推", re.I)
def _claim_tid(text):
    m = RESUME.search(str(text or ""))
    return (m.group(1) or "").strip() if m else ""
def _resume_intent(text):
    """「继续/之前/上次任务」类接续意图，无具体表号时由 attach() 自动认领本 session 最新在途表。"""
    t = str(text or "").strip()
    if not t or _ASK.search(t): return False
    return bool(_RESUME_INTENT.search(t))


def claim(text="", tid="", conv=""):
    """批47 认领原表续推（绝不另建新表）：补投/接续文本里的表尾号 → 同 session 内把本 conv 记为该表现行归属
    （claims 留痕·行内容与状态零改），令 pending/auto_done/reconcile 直接接管；已无未完成行＝只回免表提示；
    他 session 的表不夺权（批23/32 对等边界）＝先按完成证据自动补标（批50），确无证据才说明「属他 session 待该
    会话推进」，不再提示用户 :session use 切换会话，同样不另建表。"""
    try:
        t = str(tid or "").strip() or _claim_tid(text)
        if not t: return ""
        hit = _find(t) or ((lambda d: (d or {}).get("id") or "")(_load(t)))
        if not hit:
            return "〔补投认领〕表 " + t + " 不在途（多半已收口归档）——无需另建新表，直答回报即可。"
        doc = _load(hit)
        if not doc: return "〔补投认领〕表 " + t + " 读取失败——免表直答。"
        c = str(conv or chains.ACTIVE.get("conv") or "")
        sid = str(chains.cur_sess() or "")
        subs = doc.get("subtasks") or []
        rest = [x for x in subs if open_row(x)]
        if not rest:
            return ("〔补投认领〕表 " + hit[-14:] + " 已无未完成行（" + str(len(subs)) +
                    " 行全终态）——免表直答，勿另建一张。")
        if str(doc.get("conv") or "") != c:
            if sid and str(doc.get("sess") or "") not in ("", sid):
                ch = _reconcile_doc(doc)
                if ch:  # 批50：跨对话补标——已完成未打标不索要 :session use
                    _save(doc); emit(doc, LABEL + "（补投认领前·跨对话对账补标）")
                    chains.log("tool", "task_table.claim:" + hit[-14:] + " 跨会话补标 " + ",".join(ch))
                rest = [x for x in subs if open_row(x)]
                if not rest:
                    return ("〔补投认领〕表 " + hit[-14:] + " 已完成但未打标——已按完成证据自动补标 " + str(len(ch)) +
                            " 行并收口，无需 :session use、无需另建新表。")
                return ("〔补投认领〕表 " + hit[-14:] + " 属他 session（" + str(doc.get("sess") or "?") + "）余 " +
                        str(len(rest)) + "/" + str(len(subs)) + " 行尚无完成证据——不越会话代做、亦不另建新表，"
                        "由所属会话推进或直答回报。")
            doc.setdefault("claims", []).append({"from": str(doc.get("conv") or ""), "to": c,
                                                 "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                                                 "by": str(text or "")[:40]})
            doc["conv"] = c
            _save(doc)
            emit(doc, LABEL + "（补投认领·续推原表不建新表）")
            chains.log("tool", "task_table.claim:" + hit[-14:] + " conv→" + str(c) + " 未完成 " +
                       str(len(rest)) + "/" + str(len(subs)))
        return ("〔补投认领原表 " + hit[-14:] + "·本对话接管其未完成 " + str(len(rest)) + "/" + str(len(subs)) +
                " 行——禁止另建新表，逐行推进并 task_plan status 置 done〕\n" + block(doc))
    except Exception as e:
        try: chains.log("tool", "task_table.claim 跳过：" + str(e)[:80])
        except Exception: pass  # noqa 认领失败退回常规提示，绝不打断提示词构建
        return ""


def _adopt_children(doc):
    """表被清理/归档时把挂在其下的子表改挂到它的父表（批48 树完整性）：
    否则子表 parent 悬空——root_of 上溯断链、整棵树的并发分组会漏掉这批在途子任务。"""
    tid = str(doc.get("id") or "")
    if not tid: return 0
    p = str(doc.get("parent") or "")
    n = 0
    for t2 in _all():
        if t2 == tid: continue
        d2 = _lc(t2)
        if d2 and str(d2.get("parent") or "") == tid:
            d2["parent"] = p or None
            if not p: d2["root"] = t2
            _save(d2); n += 1
    if n:
        chains.log("tool", "task_table._adopt_children:" + tid[-14:] + " 子表改挂 "
                   + str(n) + " 张→" + (p[-14:] if p else "各自为根"))
    return n


def sweep(max_min=20):
    """批47 清幽灵表：在途表若 ①intent 或其首两行目标含补投/接续文本（粗分常把补投整串塞进行目标，
    故 intent＋前两行 goal 一并扫），或 ②全部行皆垃圾（noop/纯表号），且
    ③文件静默 ≥max_min 分钟 → 逐行置 stopped＋表记 swept 落 archive（守卫/顶栏/接续从此看不到它）。
    正常在途表一律不碰（只按终态收尾·留 swept 时间戳可审计）。"""
    try:
        now = time.time(); lim = float(max_min or 0) * 60; out = []
        for fn in (sorted(os.listdir(TD)) if os.path.isdir(TD) else []):
            if not fn.endswith(".json"): continue
            tid = fn[:-5]; doc = _load(tid)
            if not doc: continue
            subs = doc.get("subtasks") or []
            if not subs: continue
            it = str(doc.get("intent") or "") + " " + " ".join(
                str(x.get("goal") or "")[:48] for x in subs[:2])
            if not (_claim_tid(it) or all(_junk(x.get("goal")) for x in subs)): continue
            try:
                if lim and now - os.stat(_tf(tid)).st_mtime < lim: continue
            except Exception: continue
            for x in subs:
                if open_row(x):
                    x["status"] = "stopped"; x["swept"] = time.strftime("%Y-%m-%d %H:%M:%S")
            doc["swept"] = "补投残表/空转表清理（批47）"
            _save(doc); _adopt_children(doc); _arch(tid)
            out.append(tid[-14:] + "(" + str(len(subs)) + "行)")
        chains.log("tool", "task_table.sweep:" + ("；".join(out)[:200] if out else "无幽灵表"))
        return "清理补投残表/空转表 " + ("；".join(out) if out else "0 张")
    except Exception as e: return "sweep 跳过：" + str(e)[:80]
def _res_hint(x):
    """行占用提示（只列互斥资源：写路径/目录/端口/设备——只读不互斥，不占版面）。"""
    w = [t[2:] for t in (x.get("res") or []) if t.startswith(("w:", "d:", "p:", "v:"))]
    return ("〔占:" + "、".join(w[:3]) + ("…" if len(w) > 3 else "") + "〕") if w else ""
def _rowline(doc, x):
    """单行渲染：走树引擎（层级缩进＋子节点编号＋叶子/汇总＋〔发〕〔本〕通道）；仅树引擎导入失败才退回降级行式。"""
    if _tree_on():
        try: return T.rowline(doc, x)
        except Exception: pass  # noqa 渲染失败退回旧行式
    return "%s %s%s%s%s" % (x["id"], str(x["goal"])[:70], ("〔技能:" + str(x["skill"]) + "〕" if x.get("skill") else "〔工具自办〕"), "〔后台·不阻前台收口〕" if str(x.get("lane", "fg")) == "bg" else "", _res_hint(x))
def block(doc):
    """〔任务总览〕注入块：根任务一行＋本表行（含层级缩进）＋执行规则。"""
    root = ((T.root_of(doc) if _tree_on() else None) or doc)
    head = "\n〔" + LABEL + "（预测" + msg_flow.fmt(eta(doc)) + "）〕\n"
    if _tree_on():
        head += ("根任务 " + str(root.get("intent") or "")[:70]
                 + ("（本表是其延申·挂其之下）" if root.get("id") != doc.get("id") else "（本表即根任务）") + "\n")
    return head + "\n".join(_rowline(doc, x) for x in (doc.get("subtasks") or [])) + "\n〔执行规则·任务总览〕批49 编号制：只给任务树下的子节点分配层级编号（1、2、2.1…·引用直接用编号·内部行号 t# 亦可），任务（根/延申表）完全不编号（tid 免填＝本对话在途表）；所有任务都是根任务的延申（表带 parent/root、行带 pid，层级≤task.tree_max_depth）；父行＝子步骤的汇总节点（状态自动 rollup·不派工·不计待办），拆子步骤用 op=add 传父行编号（第 4 参数＝父行编号）；目的相同的任务/步骤一律自动合并（建表前按 task.merge_sim 命中即并入原表·op=merge 手动并表，绝不另建同义新表）；行标〔发〕＝发送处理（调 skill 派对等对话）、〔本〕＝本地处理（exec/read/write/glob/grep 自办），两者连同父表/子表的兄弟步骤一起进同一并发批次：op=conflict（value=all＝跨表跨层级同判资源互斥）取分组、op=run（value=tree＝整棵树一次并发跑完·失败隔离只标该行），或用 task 工具 parallel=true；每完成一行立刻 op=status <行编号> done（任务不编号·tid 免填＝本对话在途表；顶栏进度/剩余时间据此刷新）；全部叶子行 done 才算实质完成（派发对话收口只是形式停止·批23）——禁止只跑一两行就停、禁止口头宣告完成；用户有明确指令或有处理复杂任务意图时，建立任务节点是必须动作（批51·task_plan op=plan 先建表再推进）。\n"
def attach(intent):
    """每轮注入的任务总览段（批47 三岔＋批48 合并优先）：①补投/接续文本＝claim 认领原总览续推（绝不另建）；
    ②标点粗分命中＝同目的自动并入既有总览、无同目的才建种子总览；
    ③都不命中＝一行〔任务总览·脚本未建〕把复杂判定权交回模型，且本 conv 已有在途总览时列出未完成行（续推它、别开新表）。"""
    if not settings.get("task.auto_table", True): return ""
    c = claim(text=str(intent or ""))
    if c: return "\n" + c + "\n"
    # 接续意图但无具体表号：自动认领本 session 最新在途表（续推，不另建新表）
    if _resume_intent(intent):
        t = _latest()
        if t:
            return claim(text="", tid=t) or ""
    d = plan(intent)
    if d: return block(d)
    mine = ""
    try: mine = pending(chains.ACTIVE.get("conv") or "")
    except Exception: pass  # noqa 提示性信息，取不到不拦提示词构建
    return ("\n〔" + LABEL + "·脚本未建〕标点粗分判非复杂或无执行技能命中——复杂与否由你定：当用户有明确指令或有处理"
            "复杂任务意图时，必须建立任务节点：先 task_plan op=plan value=你拆的各步骤（逗号分隔）自建总览并按表推进；"
            "纯问句/闲聊/单步问答可直接办，勿为表而表；"
            "同目的的既有总览会自动并入，无须自己找。"
            + ("本对话已有在途总览，续推它即可、禁止另开新表：" + mine + "\n" if mine else "\n"))
def pending(conv=""):
    if time.time() - _STALE_TS[0] > 60:  # 批30 P1 自愈：守卫每轮查未完成行即顺带降级超时 running 行（批50 增对账补标）
        _STALE_TS[0] = time.time()
        try: stale_requeue()
        except Exception: pass  # noqa 自愈失败不影响守卫
    c = conv or chains.ACTIVE.get("conv") or ""; out = []
    for tid in ([fn[:-5] for fn in sorted(os.listdir(TD)) if fn.endswith(".json")] if os.path.isdir(TD) else []):
        doc = _load(tid); rest = guard_rows(doc, bool(doc) and doc.get("conv") == c)
        lf = len(T.leaves(doc)) if _tree_on() else len(doc.get("subtasks") or [])
        if rest:
            det = "；".join("%s｜%s｜%s〔%s〕" % (T.label(doc, x) if T else x.get("id"), x.get("skill") or "工具自办",
                                             str(x.get("goal"))[:40], x.get("status", "pending"))
                            for x in rest)[:600]
            out.append("〔" + LABEL + "·" + str((doc or {}).get("intent") or "")[:24] + "〕未完成 " + str(len(rest)) + "/" + str(lf)
                       + "（叶子步骤·父行为汇总）：" + det)
    return "\n".join(out)
def unfinished():
    """未完成计划表 [(tid, done, total)]＝仍有非 done 行的表（＝尚未生成最终输出）·底栏停止/继续按钮可见性判据。"""
    out = []
    if not os.path.isdir(TD): return out
    for fn in sorted(os.listdir(TD)):
        if not fn.endswith(".json"): continue
        doc = _lc(fn[:-5]); subs = (doc or {}).get("subtasks") or []
        if not subs: continue
        dn = sum(1 for x in subs if x.get("status") == "done")
        if guard_rows(doc): out.append((fn[:-5], dn, len(subs)))
    return out

def _gmatch(goal, row):
    """goal 与行目标互匹配：前 24 字前缀互含或整串包含（技能名留空时的次选判据）。"""
    g, r = str(goal or "").strip().lower(), str(row.get("goal") or "").strip().lower()
    if not g or not r: return False
    return g.startswith(r[:24]) or r.startswith(g[:24]) or g in r or r in g


def _reuse_done(goal):
    """同目标已完成证据（批50）：在途表＋已归档表里找「同目标（相似≥merge_sim 或互含）且 done＋result 非空」
    的行，回其 result——重建同一任务时新节点自动继承完成证据，不再以 pending 卡本轮守卫；无证据返 None。"""
    gv = str(goal or "").strip()
    if not gv: return None
    dirs = []
    if os.path.isdir(TD): dirs += [os.path.join(TD, fn) for fn in os.listdir(TD) if fn.endswith(".json")]
    if os.path.isdir(AD): dirs += [os.path.join(AD, fn) for fn in os.listdir(AD) if fn.endswith(".json")]
    for q in dirs:
        try: d = atomic_io.rjson(q)
        except Exception: continue
        for x in (d or {}).get("subtasks") or []:
            if str(x.get("status")) != "done" or not str(x.get("result") or "").strip(): continue
            try: same = (T and T.sim(gv, x.get("goal")) >= T.th()) or _gmatch(gv, x)
            except Exception: same = _gmatch(gv, x)
            if same: return str(x.get("result"))[:600]
    return None


def _subtasks_inherit(subs):
    """新行自动继承完成证据（批50 打标修复·新建节点不再滞留 pending）：每行未终态且无 result 的新行，若同目标
    在既有表（含归档）已 done 有 result → 置 done＋继承其 result＋auto="inherit"。回继承行数。"""
    n = 0
    for x in subs or []:
        if not open_row(x) or str(x.get("result") or "").strip(): continue
        rt = _reuse_done(x.get("goal"))
        if rt is None: continue
        x["status"] = "done"; x["result"] = rt; x["auto"] = "inherit"
        x["auto_at"] = time.strftime("%Y-%m-%d %H:%M:%S"); n += 1
    return n


def _reconcile_doc(doc):
    """单表收口对账（批50 抽核）：仅对有显式 result 内容的非终态叶子行补标 done，
    不以文件产物（可能先存在）或跨表复用结果作为单独证据，防止过早收口。"""
    subs = doc.get("subtasks") or []; ch = []
    for x in subs:
        if not open_row(x) or is_agg(doc, x): continue
        result = str(x.get("result") or "").strip()
        if not result: continue
        x["status"] = "done"; x["auto"] = "reconcile"
        x["auto_at"] = time.strftime("%Y-%m-%d %H:%M:%S"); ch.append(str(x["id"]))
    return ch


def _mine(doc, conv=""):
    """批32 回写安全边界：自动回写只允许动「本对话的表」——表 conv 为空（无主表）或等于当前 conv 才可写，
    否则视为越会话代改他人表（批23 对等对话·sessions_view 同口径）拒写。当前 conv 取 chains.ACTIVE。"""
    c = str(conv or chains.ACTIVE.get("conv") or "")
    d = str((doc or {}).get("conv") or "")
    return d == "" or (bool(c) and d == c)


def _remove(doc, subs, x, row):
    """删行（批48 树形补口）：删的是父行时其直接子行升为顶层（pid 置空并留 orphaned 痕），
    绝不留下指向已删行的悬空 pid（悬空即行渲染层级/rollup 全乱）。"""
    ks = T.kids(doc, row) if _tree_on() else []
    subs.remove(x)
    for k in ks:
        kk = next((r for r in subs if r.get("id") == k.get("id")), None)
        if kk is not None:
            kk["pid"] = ""; kk["orphaned"] = str(row)
    _save(doc); emit(doc, LABEL + "删行")
    return ("已删 " + str(row) + ("（其 " + str(len(ks)) + " 个子步骤升为顶层行：" +
            "、".join(str(k["id"]) for k in ks) + "）" if ks else ""))


def _auto_cands(sk="", goal=""):
    """auto_done 候选表（批50 打标目标修复）：按 本对话→同 session→其他 逐表找「行 skill 同名优先、goal 匹配
    次之」的未终态叶子行——aut 版只看最新一张在途表，多表在途时（树形延申/先后两张任务）其行不匹配就直接返 "",
    正在推进的那张表就永不被打标、拖到收口对账才补（=不会自动打标＋延迟打标实证）。同 conv 内优先「有 running 行」
    的表（＝正在派发的表）→ 最近活动（文件 mtime）→ 新建序。生成器逐个 yield (doc, 命中行)。"""
    c = str(chains.ACTIVE.get("conv") or "")
    s = str(chains.cur_sess() or "")
    docs = []
    for t in _all():
        d = _lc(t)
        if not d or str(d.get("table") or "") not in ("task_table", ""):
            continue
        rows = open_rows(d)
        if not rows: continue
        if _pick_row(rows, sk, goal) is None: continue  # 行都不像＝该表无本次派发对应，跳过省一轮 _mine/写盘
        sc = 0 if d.get("conv") == c else 1 if s and d.get("sess") == s else 2
        try: mt = os.stat(_tf(t)).st_mtime
        except Exception: mt = 0.0
        act = 2 if any(r.get("status") == "running" for r in rows) else 1 if mt else 0
        docs.append((sc, -act, -mt, t, d))
    docs.sort(key=lambda z: z[:4])
    for _, _, _, t, d in docs:
        x = _pick_row(open_rows(d), sk, goal)
        if x is not None:
            yield d, x


def _sk(v):
    return str(v or "").strip().lower()


def _pick_row(rows, sk, goal):
    """行命中判据：skill 同名（running>pending>error 优先取正被派发的那行）→ goal 文本互含（_gmatch）→ 无命中 None。"""
    if sk:
        same = [r for r in rows if str(r.get("skill") or "").strip().lower() == sk]
        for st in ("running", "pending", "error"):
            hit = next((r for r in same if r.get("status") == st), None)
            if hit is not None: return hit
        if same: return same[0]
    if str(goal or "").strip():
        return next((r for r in rows if _gmatch(goal, r)), None)
    return None


def auto_done(skill="", goal="", result="", ok=True, tid=""):
    """批30 P0：技能/task 派发成功即自动回写行状态——模型按〔任务总览〕派发后常漏 task_plan status，
    行滞留 pending/running 令 flow_guard 反复续推。批50：打标目标不再只看最新一张在途表——逐表（本对话→同
    session→其他）找到「行 skill 同名优先、goal 匹配次之」的未终态叶子行即回写；skill 同名时优先置 running 的
    那行（＝正被派发的行）再退 pending；命中他会话表也照常回写（跨对话补标·只动 status/result/auto 三字段，
    不再要求 :session use 切换会话）。ok 真且命中→ done＋result[:600]＋auto="skill"；ok 假→ error。整体吞
    异常返 ""（绝不打断工具循环）。"""
    try:
        if str(tid or "").strip():
            hit = _find(str(tid).strip())
            doc = _load(hit) if hit else None
            cands = [(doc, _pick_row(open_rows(doc), _sk(skill), str(goal or ""))) for doc in [doc] if doc]
        else:
            cands = list(_auto_cands(_sk(skill), str(goal or "")))
        for doc, x in cands:
            if x is None: continue
            cross_d = not _mine(doc)  # 批50：跨对话补标——他人会话的同目标行同样回写（只动 status/result/auto 三字段）
            if skill and ok and not dispatch_ok(result): ok = False  # 批33 缺陷B：核侧同判据（空输出/无输出占位串≠成功）
            x["status"] = "done" if ok else "error"
            x["result"] = str(result or "")[:600]
            x["auto"] = "skill"; x["auto_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _save(doc); emit(doc, LABEL + ("（派发成功自动置行" + ("·跨对话" if cross_d else "") + "）"))
            chains.log("tool", "task_table.auto_done:" + str(doc["id"])[-14:] + "/" + str(x["id"]) + "=" + x["status"] + ("跨对话" if cross_d else ""))
            return "行 " + str(x["id"]) + (" 自动置 done（派发回写" + ("·跨对话" if cross_d else "") + "）" if ok else " 自动置 error（派发失败回写）")
        return ""
    except Exception as e:
        try: chains.log("tool", "task_table.auto_done 跳过：" + str(e)[:80])
        except Exception: pass  # noqa 回写绝不影响派发主路
        return ""


def _since(doc):
    """表 created（"%Y-%m-%d %H:%M:%S"）解析为新鲜度基准；缺失/解析失败回 0.0＝一律视为无产物（宁缺勿滥）。"""
    ts = str((doc or {}).get("created") or "").strip()
    if not ts: return 0.0
    try: return time.mktime(time.strptime(ts, "%Y-%m-%d %H:%M:%S"))
    except Exception: return 0.0  # noqa created 不可解析＝无基准，不补标


def dispatch_ok(s):
    """派发输出成功判据（壳 agent_dispatch 与核 auto_done 共用·防两侧口径漂移）：空串、
    「无托管技能/拒绝/（技能 x 无输出）」前缀、含「无输出」「SKILL.md 读取失败」者＝失败。"""
    t = str(s or "").strip()
    if not t: return False
    if t.startswith(("无托管技能", "拒绝", "（技能")): return False
    return not any(h in t for h in ("无输出", "SKILL.md 读取失败"))


def _artifacts(row, since=0.0):
    """行写资源是否**本轮新落盘**（w:/d: token 经 task_res._norm 归一＝去盘符·小写·正斜杠）——收口对账判据。
    批33 缺陷A：写目标常在行执行前就存在（改既有文件、写 config.json），旧版只判「存在且 size>0」＝把
    从未做过的行补标 done（假阳性·与需求相反）；现加新鲜度——文件 mtime（目录取其中最新文件 mtime）
    须 ≥ since（表 created 解析值），无基准一律视为无产物。"""
    if not since: return False
    for t in (row.get("res") or []):
        k, _, v = str(t).partition(":")
        if k not in ("w", "d") or not v: continue
        for q in (v, os.path.join(SMS, v.replace("/", os.sep)),
                  os.path.splitdrive(SMS)[0] + os.sep + v.replace("/", os.sep)):
            try:
                if os.path.isfile(q) and os.path.getsize(q) > 0 and os.path.getmtime(q) >= since:
                    return True
                if os.path.isdir(q):
                    fs = [os.path.join(q, f) for f in os.listdir(q)
                          if os.path.isfile(os.path.join(q, f))]
                    if any(os.path.getsize(f) > 0 and os.path.getmtime(f) >= since for f in fs):
                        return True
            except Exception: continue  # noqa 路径不可读＝视为无产物
    return False


def reconcile(conv=""):
    """批30 P1 收口对账＋批50 跨对话补标：全部在途表（不限本 conv）的非终态叶子行，行 result 非空或写资源
    本轮新落盘（mtime≥表 created·批33 缺陷A 新鲜度）→ 补置 done（auto="reconcile"）。已完成而未打标的表
    从此即时被补标：守护不再对着已完成任务死循环，也不需要用户 :session use 切换会话去完成他会话的任务。
    挂在 agent_stream 收口与 pending() 周期自愈两处；跨对话补标只写 status/result/auto 三字段，行内容零改。"""
    try:
        c = conv or chains.ACTIVE.get("conv") or ""; hits = []; cross = []
        tids = [fn[:-5] for fn in sorted(os.listdir(TD)) if fn.endswith(".json")] if os.path.isdir(TD) else []
        for tid in tids:
            doc = _load(tid)
            if not doc: continue
            ch = _reconcile_doc(doc)
            if not ch: continue
            _save(doc)
            emit(doc, LABEL + ("（收口对账补标" + ("·跨对话" if not _mine(doc, c) else "") + "）"))
            hits.append(str(doc["id"])[-14:] + ":" + ",".join(ch))
            if not _mine(doc, c): cross.append(str(doc["id"])[-14:])
        chains.log("tool", "task_table.reconcile:" + ("；".join(hits)[:200] if hits else "无补标")
                   + ("｜跨对话补标 " + str(len(cross)) + " 张：" + ",".join(cross)[:120] if cross else ""))
        return "收口对账补标 " + ("；".join(hits) if hits else "0 行") \
            + ("（其中跨对话 " + str(len(cross)) + " 张）" if cross else "")
    except Exception as e: return "收口对账跳过：" + str(e)[:80]


_STALE_TS = [0.0]


def _row_age(row, now, tbl_age):
    """行活动度（批33 缺陷C）：优先行级 started_at——旧版用表文件 mtime，同表任一行改状态即刷新 mtime，
    卡死的 running 行永不超阈（正是「长期无活动的执行中行」漏网）；无 started_at 才回落表 mtime（旧表兼容）。"""
    ts = str(row.get("started_at") or "").strip()
    if not ts: return tbl_age
    try: return max(0.0, now - time.mktime(time.strptime(ts, "%Y-%m-%d %H:%M:%S")))
    except Exception: return tbl_age  # noqa 时间戳不可解析＝回落表 mtime


def stale_requeue(max_min=None):
    """批30 P1：running 行长期无活动＝降级回 pending、移到 subtasks 尾部、记 stale 时间戳、emit 一次并写
    error/logic 链——修「派发无回写即永久卡守卫」。批33 缺陷C：活动度改行级 started_at（表 mtime 仅兜底），
    同表其他行的活动不再掩盖本行卡死。"""
    try:
        lim = float(max_min if max_min is not None else settings.get("task.stale_min", 30))
        now = time.time(); out = []
        tids = [fn[:-5] for fn in sorted(os.listdir(TD))
                if fn.endswith(".json")] if os.path.isdir(TD) else []
        for tid in tids:
            doc = _load(tid); subs = (doc or {}).get("subtasks") or []
            run = [x for x in subs if x.get("status") == "running"]
            if not run: continue
            try: tbl_age = now - os.stat(_tf(tid)).st_mtime
            except Exception: continue  # noqa 表文件不可读即跳过
            moved = []; ages = []
            for x in run:
                age = _row_age(x, now, tbl_age)
                if age < lim * 60: continue
                x["status"] = "pending"; x["stale"] = time.strftime("%Y-%m-%d %H:%M:%S")
                x["stale_age_s"] = int(age); subs.remove(x); subs.append(x)
                moved.append(str(x["id"])); ages.append(int(age))
            if not moved: continue
            _save(doc); emit(doc, LABEL + "（running 超时降级重排）")
            # 批39：走 chain_error.record（err:<kind>:<src> 原子口径＋同签名去重 bump），
            # 旧版直接 chains.record("error", 自由语句) 绕过前缀，令 stats/migrate 出假 kind
            try:
                import chain_error as _ce
                _ce.record("script", "task_table.stale_requeue",
                           "stale_requeue " + tid[-14:] + " 行 " + ",".join(moved)
                           + " running>" + str(int(lim)) + "min 回 pending 移尾")
            except Exception:
                chains.record("error", "err:script:task_table.stale_requeue " + tid[-14:] + " 行 " + ",".join(moved))
            chains.record("logic", "stale_requeue 阈值 task.stale_min=" + str(int(lim)) + "·表 "
                          + tid[-14:] + " 行级 started_at 超 " + str(max(ages) // 60)
                          + "min（无该字段才回落表 mtime）")
            out.append(tid[-14:] + ":" + ",".join(moved))
        return "降级重排 " + ("；".join(out) if out else "无")

    except Exception as e: return "stale 检查跳过：" + str(e)[:80]


def merge_tables(doc, other, why=""):
    """表级自动合并（批48·目的相同的任务＝并成同一棵总览）：把 other 的**全部行**（含已完成行的 result
    与状态一字不改）重新编号并入 doc，other 随即标记 merged_into＋落 archive（＝从此只看一张总览，
    不再出现「同一件事三张表」）；行内 pid 关系随新编号同步重映射，层级深的行仍挂在自己的父行下。
    越会话拒写口径不变：other 非本对话可归属时一律不动。回 (并入行数, 归档表号)。"""
    a = doc.get("subtasks") or []; b = (other or {}).get("subtasks") or []
    if not b or not _mine(other):
        return 0, ""
    base = max([int(str(x["id"])[1:]) for x in a if str(x["id"]).startswith("t") and str(x["id"])[1:].isdigit()] or [0])
    mp = {}
    for i, x in enumerate(b):
        nid = "t%d" % (base + i + 1)
        mp[str(x.get("id"))] = nid
        x["id"] = nid; x["from"] = str(other.get("intent") or "")[:10]
    for x in a + b:
        p = str(x.get("pid") or "")
        if p in mp: x["pid"] = mp[p]
    doc["subtasks"] = a + b
    doc["merged_rows"] = int(doc.get("merged_rows") or 0) + len(b)
    doc.setdefault("merged_from", []).append({"tid": other["id"], "rows": len(b),
                                             "why": str(why or "")[:60],
                                             "at": time.strftime("%Y-%m-%d %H:%M:%S")})
    other["merged_into"] = doc["id"]; other["subtasks"] = []
    _save(other); _arch(str(other["id"]))
    _save(doc); emit(doc, LABEL + "（同目的任务自动合并 " + str(len(b)) + " 行←" + str(other.get("intent") or "")[:10] + "）")
    chains.log("tool", "task_table.merge_tables:" + str(other["id"])[-14:] + " → " + str(doc["id"])[-14:] +
               " 并入 " + str(len(b)) + " 行（同目的合并·原表归档）")
    return len(b), str(other["id"])[-14:]


def merge_auto(doc, value=""):
    """手动并表（op=merge）：value＝要并进来的表号（逗号/顿号分隔多个），留空＝把本对话在途表里
    「目的与本表相同」的全并进来。回结论串。"""
    if not _tree_on(): return "树引擎不可用（task_tree 导入失败）——不支持跨表合并"
    tids = [x.strip() for x in re.split(r"[,，、;；]", str(value or "")) if x.strip()]
    out = []
    if tids:
        for t in tids:
            hit = _find(t); d2 = _load(hit) if hit else None
            if not d2 or d2["id"] == doc["id"]:
                out.append(str(t) + "（未命中或即本表）"); continue
            n, arc = merge_tables(doc, d2, why="op=merge 手动并表")
            out.append(str(t) + "（" + str((d2 or {}).get("intent") or "")[:10] + "）并入 " + str(n) + " 行→" + arc)
        return "自动合并：" + "；".join(out)
    n_all = 0
    for d2 in [x for x in (_lc(t) for t in _all()) if x and x["id"] != doc["id"]]:
        if str(d2.get("conv") or "") != str(doc.get("conv") or "") or not (d2.get("subtasks") or []):
            continue
        same_p = str(d2.get("root") or "") == str(doc.get("root") or "")
        if T.sim(d2.get("intent"), doc.get("intent")) >= T.th() or same_p:
            n, _ = merge_tables(doc, d2, why="op=merge 同目的自动发现")
            n_all += n
    if n_all:
        return ("自动合并完成：同目的表并入 " + str(n_all) + " 行（本表 " + str(doc.get("intent") or "")[:12]
                + " 现有 " + str(len(doc.get("subtasks") or [])) + " 行）")
    return "没有在可并的同目的在途表（阈值 task.merge_sim=" + str(T.th()) + "）"


def new_table(intent, sv): rows = _steps(sv); d = plan(intent, steps=rows) if rows else None; return ("已建任务总览（" + str(len(d["subtasks"])) + " 行·据实推进）\n" + block(d)) if d else "建表失败：步骤为空——value/参数＝你拆的步骤（逗号/顿号分隔）"
def _all(): return sorted([f[:-5] for f in (os.listdir(TD) if os.path.isdir(TD) else []) if f.endswith(".json")])
def _find(t): k = [i for i in _all() if (t := str(t or "").strip()) and (i == t or i.endswith(t) or t in i)]; return k[-1] if k else ""
def _latest(table=""):
    """在途表挑选：本 conv 优先→同 sess→其他，同级取最新（tid 大者＝时间戳即序）；table 非空＝只认该
    来源的表（task_table 制表器建的表与 task 工具自建的子任务表同源不同表，派发回写须只认前者）。
    批32 修：旧版 sorted(key=(sc,tid))[-1] 取的是 sc 最大＝最差的他人表，与本 docstring 相反（实测他
    conv 表被选中、本 conv 表漏选→auto_done 返 ""），改 max(key=(-sc,tid)) 使语义与 docstring 一致。"""
    sc = lambda d: 0 if (c := chains.ACTIVE.get("conv") or "") and d.get("conv") == c else 1 if d.get("sess") == chains.cur_sess() else 2
    op_ = [(d, t) for t in _all() if (d := _lc(t)) and (not table or d.get("table") == table)
           and any(x.get("status") != "done" for x in (d.get("subtasks") or []))]
    return max(op_, key=lambda z: (-sc(z[0]), z[1]))[1] if op_ else ""
def revise(op, tid="", row="", value=""):
    if op in ("new", "plan"): st = _steps(value or tid); return new_table(str(tid or value)[:200] if (value or tid) else "未命名任务总览", st) if st else "建表失败：value＝你拆的步骤（逗号/顿号分隔）"
    _tid = str(tid or "").strip()
    if _tid:
        _hit = _find(_tid)
        if not _hit: return "无此表：" + _tid + "（tid 未命中即拒绝·不回落他人表·task_plan show 看全部）"
        doc = _load(_hit)
    else:
        doc = _load(_latest())
    if not doc: return "无任务总览：" + str(tid) + "（task_plan op=plan value=<步骤逗号分隔> 先建表；op=show 看全部）"
    if op == "status" and not row:  # 批30 P0：状态词回落只认 status——旧版对所有 op 生效，op=add 的行文案含 running/pending 即被整条换成 "done"
        v = str(value or "").strip()
        m = re.match(r"^(t\d+|\d+(?:\.\d+)*)\s+(pending|running|done|error|stopped|skipped)$", v, re.I)
        if m: row, value = m.group(1), m.group(2).lower()
        elif re.fullmatch(r"(pending|running|done|error|stopped|skipped)", v, re.I): row, value = v, "done"
    subs = doc.get("subtasks") or []
    if row:  # 批49 编号制：行引用＝层级编号（2.1）或内部行号（t3）皆可
        rx = (T.resolve(doc, row) if T else None) or next((s for s in subs if str(s.get("id")) == str(row)), None)
        if rx: row = str(rx.get("id"))
    x = next((s for s in subs if s.get("id") == row), None)
    if op == "show":
        for x in subs: tr.res_of(x)
        return json.dumps({"id": doc["id"], "sess": doc.get("sess"), "conv": doc.get("conv"), "subtasks": subs}, ensure_ascii=False)[:2400]
    if op == "next": p = next((s for s in subs if s.get("status") == "pending"), None); return (p and (str(T.label(doc, p) if T else p["id"]) + "｜" + str(p.get("skill") or "工具自办") + "｜" + str(p["goal"])[:80])) or "全部完成"
    if op == "eta": return "剩余预测 " + msg_flow.fmt(eta(doc))
    if op == "lane":
        if not x: return "无此行：" + str(row)
        x["lane"] = "bg" if str(value or "").strip().lower() in ("bg", "后台", "back", "background") else "fg"
        _save(doc); emit(doc, LABEL + "（行转%s）" % ("后台" if x["lane"] == "bg" else "前台"))
        return "行 %s 车道＝%s（后台行不阻前台收口·表内地位相同）" % (row, x["lane"])
    if op == "add":
        return _add(doc, subs, row, value)

    if op == "remove" and x:
        return _remove(doc, subs, x, row)

    if op == "status" and x:
        v = str(value or "").strip().lower()
        if v not in TERMINAL + ("pending", "running"):
            return ("状态值非法：" + str(value) + "——合法集合 pending/running/done/error/stopped/skipped，"
                    "行 " + str(row) + " 状态未改（批33 缺陷D：旧版把乱值静默当 done＝误标完成）")
        if _tree_on() and is_agg(doc, x) and str(v) in TERMINAL:
            x["status"] = v
            _save(doc)
            return ("行 " + str(row) + " 是汇总父行：状态已按你的指令置 " + v + "，但落盘时由子行 rollup 重算"
                    "（当前子行汇总＝" + str(next((r for r in subs if r.get("id") == row), {}).get("status")) +
                    "）——要结束父行请把它的全部子步骤置 done")
        x["status"] = v
        if v == "running": x["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")  # 批33 缺陷C：行级活动度
        _save(doc); emit(doc, LABEL + "步进")
        return (str(row) + " → " + x["status"] + "（"
                + str(sum(1 for s in subs if s.get("status") == "done")) + "/" + str(len(subs))
                + "·" + msg_flow.fmt(eta(doc)) + "）")
    if op == "skill" and x: x["skill"] = str(value); x["inst"] = str(value); _save(doc); emit(doc, LABEL + "改派"); return str(row) + " 指定技能：" + str(value)
    if op == "conflict":
        rows = open_rows(doc)
        vv = str(value or "").strip().lower()
        if vv in ("tree", "总览", "整棵树"):
            rows = [r for _, r in T.tree_rows(doc)] if _tree_on() else rows
        elif vv in ("all", "cross", "跨表"): rows = rows + _other_rows(doc["id"])
        if not rows: return "无未完成行——本表已清空"
        cf = tr.conflicts(rows)
        return tr.report(rows) + ("\n结论：%d 行分 %d 批执行·%d 对资源冲突需串行（同批内行可一次并发·批间依序）" % (len(rows), len(tr.batches(rows)), len(cf)) if cf else "\n结论：无冲突——%d 行可一次全并发（op=run 或 task 工具 parallel=true）" % len(rows))
    if op == "run":
        import agent_task as atk
        vv = str(value or "").strip().lower()
        wait = ("wait" in vv or "同步" in vv or "等完" in vv)
        if _tree_on() and (vv in ("tree", "all", "cross", "总览", "整棵树", "跨表")
                           or vv.startswith("tree")):
            return atk.run_tree(doc, wait=wait)
        rows = [x for x in open_rows(doc) if x.get("status") in ("pending", "running")]
        if not rows: return "无未完成行——本表已清空"
        return atk.run_table(doc, rows)
    if op == "res" and x:
        toks = sorted(tr.resources(str(value), x.get("skill") or "")[0]) if value else sorted(tr.res_of(x))
        x["res"] = toks; x["res_decl"] = str(value or ""); _save(doc); emit(doc, LABEL + "声明资源")
        return "行 %s 资源＝%s（写占用即与他行互斥·只读可共享）" % (row, "、".join(toks) or "（未识别到资源——目标里写明 files=/dir=/reads=/port=）")
    if op == "sweep":
        try: return sweep(float(str(value or "").strip() or 20))
        except Exception: return sweep(20)
    if op == "claim": return claim(text=str(value or tid or ""), tid=str(tid or "")) or "非补投/接续消息（无表尾号）——按正常流程走"
    if op == "merge": return merge_auto(doc, value)
    if op == "tree":
        return (T.overview(doc) if _tree_on() else "树引擎不可用（task_tree 导入失败）")
    return ("用法 task_plan plan|new|show|next|eta|tree|merge|conflict|run|res|add|remove"
            "|status|skill|lane|sweep|claim|attach <表id/步骤> [行编号] [值]"
            "（add 的第 3 参数＝父行 id＝挂子步骤；run/conflict 的值写 tree＝整棵树）")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: print(__doc__.strip().splitlines()[-1])
    elif a[0] == "plan" and len(a) > 1: d = plan(" ".join(a[1:])); print(block(d) if d else "判非复杂或无执行技能命中——明确指令/复杂任务意图须 task_plan op=plan value=步骤逗号分隔 建任务节点")
    elif a[0] == "new" and len(a) > 1: print(new_table("模型自建表", _steps(a[1])))
    elif a[0] == "pending": print(pending(a[1] if len(a) > 1 else "") or "无未完成行")
    elif a[0] == "stale": print(stale_requeue(float(a[1]) if len(a) > 1 else None))
    elif a[0] == "reconcile": print(reconcile(a[1] if len(a) > 1 else ""))
    elif a[0] == "sweep": print(sweep(float(a[1]) if len(a) > 1 else 20))
    elif a[0] == "claim" and len(a) > 1: print(claim(text=" ".join(a[1:])) or "非补投/接续消息——免认领")
    elif a[0] == "attach" and len(a) > 1: print(attach(" ".join(a[1:])) or "免表注入（空串）")

    elif a[0] in ("show", "next", "eta", "tree", "merge", "conflict", "run") and len(a) > 1:
        print(revise(a[0], a[1], "", a[2] if len(a) > 2 else ""))
    elif a[0] == "add" and len(a) > 2: print(revise("add", a[1], a[3] if len(a) > 3 else "", a[2]))
    elif a[0] in ("status", "remove", "skill", "lane", "res") and len(a) > 2: print(revise(a[0], a[1], a[2], a[3] if len(a) > 3 else ""))
    else: print(__doc__.strip().splitlines()[-1])
