#!/usr/bin/env python3
"""task_tree.py — 任务总览树引擎（批48·用户「任务表改名为任务总览·使用树形思想·所有任务都是根任务的
延申·自动合并目的相同的任务或者步骤·支持多个任务多个步骤和它们的子步骤并行发送处理和本地处理」）：
只做「结构＋归并＋渲染＋通道标注」四件事，由 task_table.py 调用（不单独面向用户），落盘仍走
tasks/<id>.json 真源——本模块不写文件，纯结构计算与文本渲染，坏了也只影响渲染与判据（task_table
侧全部包 try，绝不反噬主链路）。

模型（旧表缺字段一律按顶层/自为根处理，零迁移）：
① 表级：每表带 root（所在树根）＋parent（父表·无＝自为根）。新建表时 stamp() 在本 conv/session 的
   在途表里认最近一张「目的不同」者为父 ⇒ 后建的任务＝先建任务的延申，一个 session 长成一棵总览树；
   目的相同（sim ≥ task.merge_sim）时不建新表，由 task_table.graft() 并进那张表（＝自动合并）。
② 行级：每行带 pid（父行·空＝顶层）。父行是「汇总节点」：状态由子行 rollup 得出（全 done→done、
   有 error→error、有 running→running），不派工、不计入待办与 ETA——守卫只催叶子行。
③ 通道：chan(row) 标 send（发送处理＝派发技能对等对话）／local（本地处理＝本对话 exec/read/write），
   行内可与父表、子表、兄弟任务的步骤一起进同一并发批次（编排见 task_table op=run tree=1）。
④ 渲染：rowline/render/overview 出缩进树文本，顶栏/QQ 进度/〔任务总览〕注入块共用一份真源。

批49 编号制：只给任务树下的子节点分配层级编号（1、2、2.1…），任务（根/延申表）完全不编号；旧「任务表」平铺设计完全废弃·树为唯一设计（task.tree 开关退役·on() 恒真）｜task.merge_sim（同目的合并阈值 0~1·默认 0.62）｜
task.tree_max_depth（子步骤最大层级·默认 3）。用法：python -B task_tree.py sig|sim|render|overview|tree|on。"""
import os, sys, re, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings, chains
LABEL = "任务总览"
OLD_LABEL = "任务表"
GEN = ("general_answer", "constraint_arbiter")


def _tt():
    import task_table as tt
    return tt


def on():
    """批49：旧「单表平铺」任务表设计完全废弃——树形为唯一设计，恒真（task.tree 开关退役）。"""
    return True


def th():
    """同目的合并阈值。"""
    try:
        return float(settings.get("task.merge_sim", 0.62) or 0.62)
    except Exception:
        return 0.62


def max_depth():
    try:
        return max(1, int(settings.get("task.tree_max_depth", 3) or 3))
    except Exception:
        return 3


# ---------------- 子节点编号（批49：只给任务树下的子节点分配编号·任务不编号） ----------------
def nummap(doc):
    """子节点层级编号真源（DFS 序）：顶层行＝1、2、3…；子行＝父编号.子序号（1.1、2.3…）；孙行继续追加段。
    编号只分配给任务树下的子节点（行）——任务/表（根任务与延申任务）完全不编号。内部行号 t# 仍是落盘引用键，
    显示与用户侧引用一律用层级编号。回 {内部行id: "2.1"}。"""
    out = {}
    subs = (doc or {}).get("subtasks") or []
    def walk(pid, prefix):
        n = 0
        for r in subs:
            if str(r.get("pid") or "") != str(pid or ""):
                continue
            n += 1
            num = str(n) if not prefix else prefix + "." + str(n)
            out[str(r.get("id"))] = num
            walk(r.get("id"), num)
    walk("", "")
    return out


def label(doc, row):
    """行的显示编号（层级号·异常退回内部行号，绝不因编号计算断渲染）。"""
    try:
        return nummap(doc).get(str((row or {}).get("id")), str((row or {}).get("id")))
    except Exception:
        return str((row or {}).get("id"))


def resolve(doc, ref):
    """行引用解析：层级编号（"2.1"）与内部行号（"t3"）双口径皆可，回行 dict 或 None。"""
    s = str(ref or "").strip()
    if not s:
        return None
    subs = (doc or {}).get("subtasks") or []
    for r in subs:
        if str(r.get("id")).lower() == s.lower():
            return r
    try:
        nm = nummap(doc)
        for r in subs:
            if nm.get(str(r.get("id"))) == s:
                return r
    except Exception:
        pass  # noqa
    return None


def sig(g):
    """目的签名：剥掉资源声明（files=/dir=/reads=/port=/device=/skill=）与一切符号空白，只留文字本体。"""
    t = re.sub(r"(files|dir|reads|port|device|skill)\s*=\s*[^,;、\s]+", " ",
               str(g or ""), flags=re.I)
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", t.lower())[:120]


def sim(a, b):
    """目的相似度 0~1（自动合并的判据·标定见 tests/test_task_tree_batch48.py）：
    签名全等＝1／一方包含另一方＝0.92／否则取「difflib 序列比」与「字符二元组 Dice」的较大者——
    纯序列比对中文语序敏感（「实现目的相同自动合并」vs「自动合并目的相同的任务」只得 0.30），
    补二元组可召回换序说法；宁缺勿滥：真正不相干的目的在实测 9730 对历史 intent 里最高只到 0.385，
    低于默认阈值 task.merge_sim=0.62 ⇒ 只并「近乎同一件事」（＝补投雪球那类），不并「相关但不同」的活。"""
    x, y = sig(a), sig(b)
    if not x or not y:
        return 0.0
    if x == y:
        return 1.0
    if x in y or y in x:
        return 0.92
    import difflib
    r = difflib.SequenceMatcher(None, x, y).ratio()
    ga = {x[i:i + 2] for i in range(len(x) - 1)} or {x}
    gb = {y[i:i + 2] for i in range(len(y) - 1)} or {y}
    d = 2.0 * len(ga & gb) / (len(ga) + len(gb))
    return max(r, d)


# ---------------- 行级（父行／子行） ----------------
def kids(doc, rid):
    """直接子行列表（rid 空＝顶层行）。"""
    subs = (doc or {}).get("subtasks") or []
    return [r for r in subs if str(r.get("pid") or "") == str(rid or "")]


def is_leaf(doc, row):
    return not kids(doc, row.get("id"))


def leaves(doc):
    return [r for r in ((doc or {}).get("subtasks") or []) if is_leaf(doc, r)]


def depth(doc, row, cap=8):
    """行层级：顶层＝1（根任务的直接延申），沿 pid 上溯计数（防环≤cap）。"""
    by = {r.get("id"): r for r in ((doc or {}).get("subtasks") or [])}
    d, cur, n = 1, row, 0
    while n < cap:
        p = str((cur or {}).get("pid") or "")
        if not p or p not in by:
            break
        cur, d, n = by[p], d + 1, n + 1
    return d


def rollup(doc):
    """父行状态＝其全部子行的汇总（父行不自己干活、不该被守卫催）：子行全终态无错→done、有 error→error、
    有 running→running、否则 pending。只改父行状态，子行零改。回被改动的父行数。"""
    ch = 0
    for r in (doc or {}).get("subtasks") or []:
        ks = kids(doc, r.get("id"))
        if not ks:
            continue
        st = ("done" if all(str(k.get("status")) in ("done", "skipped") for k in ks)
              else "error" if any(str(k.get("status")) == "error" for k in ks)
              else "running" if any(str(k.get("status")) == "running" for k in ks)
              else "pending")
        if str(r.get("status")) != st:
            r["status"] = st
            r["agg"] = "rollup"
            ch += 1
    return ch


def order(doc):
    """表序规范化＝深度优先（父先于子），行内容一律不改（父子靠 pid 引用，与顺序无关）。
    去重按「对象身份」而非行 id（批48 修：并入行若与既有行撞号，按 id 去重会静默丢行＝步骤凭空消失）。"""
    subs = (doc or {}).get("subtasks") or []
    out, seen = [], set()

    def walk(pid):
        for r in subs:
            if id(r) in seen or str(r.get("pid") or "") != str(pid or ""):
                continue
            seen.add(id(r))
            out.append(r)
            walk(r.get("id"))
    walk("")
    out += [r for r in subs if id(r) not in seen]
    doc["subtasks"] = out
    return doc


# ---------------- 表级（根任务／延申） ----------------
def _all_docs():
    tt = _tt()
    return [d for d in (tt._lc(t) for t in tt._all()) if d]


def root_of(doc, cap=8):
    """沿 parent 上溯到根表（防环≤cap）。旧表无 parent 字段＝自己即根。"""
    tt = _tt()
    cur, n = doc or {}, 0
    while n < cap:
        p = str((cur or {}).get("parent") or "")
        if not p:
            break
        nx = tt._load(p)
        if not nx or nx.get("id") == (cur or {}).get("id"):
            break
        cur, n = nx, n + 1
    return cur


def tree_of(doc):
    """本表所在总览树的全部表 [根→子孙]（BFS·只认在途表，归档表自然退出）。"""
    root = root_of(doc)
    out, q = [root], [root]
    while q:
        d = q.pop(0)
        for c in _all_docs():
            if str(c.get("parent") or "") == str(d.get("id")) and c.get("id") != d.get("id") \
               and not any(o.get("id") == c.get("id") for o in out):
                out.append(c)
                q.append(c)
    tt = _tt()
    try:      # 批48：只留在途表——已归档（收口）的表其行不再计入待办/ETA/并发分组，防幽灵步骤复活
        live = [d for d in out if d.get("id") and os.path.exists(tt._tf(str(d["id"])))]
        return live or [doc]
    except Exception: return out


def tree_rows(doc, only_open=True):
    """树上所有表的全部行 [(owning_doc, row)]——跨任务·跨层级并行与冲突判定的输入集。"""
    out = []
    for d in tree_of(doc):
        for r in d.get("subtasks") or []:
            if only_open and str(r.get("status")) in ("done", "skipped", "stopped"):
                continue
            out.append((d, r))
    return out


def stamp(intent, conv="", sess=""):
    """新表认父（树形的建立点）：本 conv／同 session 在途表里最近一张「目的不同」者为父表——
    所有后建任务都是它的延申；同目的的那张交给 graft 并进去、不认父。无候选＝本表自为根。
    回 (parent_id, root_id)。"""
    c = conv or chains.ACTIVE.get("conv") or ""
    s = sess or chains.cur_sess() or ""
    cands = [d for d in _all_docs() if (d.get("subtasks") or [])]
    cands = [d for d in cands
             if str(d.get("conv") or "") == c or (s and str(d.get("sess") or "") == s)]
    cands = [d for d in cands if sim(intent, d.get("intent")) < th()]
    if not cands:
        return "", ""
    cands.sort(key=lambda d: str(d.get("created") or "") + str(d.get("id")), reverse=True)
    p = cands[0]
    return str(p.get("id")), str((root_of(p) or p).get("id"))


def find_merge(intent, conv="", sess=""):
    """找「目的相同」的在途表（＝该并入而非另建）：表 intent 同目的，或其未完成行里 ≥半数与该诉求同目的。
    回 (doc, 相似度, 可否代改)——只有同 conv 才可代改（批32 越会话拒写口径不变）。"""
    c = conv or chains.ACTIVE.get("conv") or ""
    s = sess or chains.cur_sess() or ""
    best, bs, ok = None, 0.0, False
    for d in _all_docs():
        if not (d.get("subtasks") or []):
            continue
        same_c = str(d.get("conv") or "") == c
        if not same_c and not (s and str(d.get("sess") or "") == s):
            continue
        v = sim(intent, d.get("intent"))
        op = [r for r in d["subtasks"] if str(r.get("status")) in ("pending", "running", "error")]
        dup = sum(1 for r in op if sim(intent, r.get("goal")) >= th())
        v = max(v, (0.9 * dup / float(len(op))) if op else 0.0)
        if v > bs:
            best, bs, ok = d, v, same_c
    return (best, bs, ok) if (best is not None and bs >= th()) else (None, bs, False)


def match_row(doc, goal, rows=None, at=None):
    """表内同目的行匹配（≥阈值），回 (行, 相似度)；无命中回 (None, 见过的最高相似度)。"""
    lim = th() if at is None else at
    best, bs = None, 0.0
    for r in (rows if rows is not None else ((doc or {}).get("subtasks") or [])):
        v = sim(goal, r.get("goal"))
        if v > bs:
            best, bs = r, v
    return (best, bs) if bs >= lim else (None, bs)


# ---------------- 「发送处理／本地处理」双通道标注 ----------------
def chan(row):
    """行的处理方式（「并行发送处理＋本地处理」落到一行的判据）：
    send＝发送处理＝派发技能对等对话（行 skill 命中且非通用问答技能）；
    local＝本地处理＝本对话用 exec/read/write/glob/grep 自办。
    目标里写 self=／local= 一律强制本地；行上 manual=send 强制派发（模型可覆盖）。"""
    g = str(row.get("goal") or "")
    if re.search(r"\b(self|local)\s*=", g, re.I) or str(row.get("manual") or "").lower() == "local":
        return "local"
    if str(row.get("manual") or "").lower() == "send":
        return "send"
    sk = str(row.get("skill") or "").strip()
    return "send" if (sk and sk not in GEN) else "local"


def rowline(doc, row, term=None):
    """单行渲染（任务总览的行式真源·顶栏/QQ/注入块共用）：
    层级缩进＋子节点编号（1.2 式·批49）＋状态符号＋目标＋〔叶/汇总·N子〕＋〔发〕发送处理或〔本〕本地处理
    ＋技能＋后台车道＋资源占用＋同义并入痕＋并表来源痕。"""
    tt = _tt()
    d = max(1, depth(doc, row))
    st = str(row.get("status") or "pending")
    tag = {"done": "✔", "running": "▶", "error": "✖", "skipped": "⊘", "stopped": "■"}.get(st, "·")
    leaf = is_leaf(doc, row)
    kn = "叶" if leaf else ("汇总·%d子" % len(kids(doc, row.get("id"))))
    ch = ("〔发〕" if chan(row) == "send" else "〔本〕") if leaf else "〔↳〕"
    sk = "〔技能:%s〕" % row.get("skill") if row.get("skill") else ""
    lane = "〔后台〕" if str(row.get("lane", "fg")) == "bg" else ""
    hint = ""
    try:
        hint = tt._res_hint(row)
    except Exception:
        pass  # noqa 占用提示缺失不影响渲染
    als = "〔同义并入%d〕" % len(row.get("also") or []) if row.get("also") else ""
    frm = "〔←%s〕" % row.get("from") if row.get("from") else ""
    pre = ("    " * (d - 1)) + ("" if d == 1 else "└ ")
    fmt = "%s%s %s %s〔%s｜%s〕%s%s%s%s%s"
    return fmt % (pre, label(doc, row), tag, str(row.get("goal"))[:70],
                  kn, ch, sk, lane, hint, als, frm)


def render(doc, title=""):
    """一张总览表的树形文本（DFS 序·缩进）。"""
    order(doc)
    hd = "〔" + LABEL + "〕" + str(doc.get("intent") or "")[:60]
    ls = [title or hd]
    ls += [rowline(doc, r) for r in (doc.get("subtasks") or [])]
    return "\n".join(ls)


def _fmt(sec):
    """秒数格式化（顶栏/QQ/树视图共用 msg_flow 口径；导入失败退回 Ns）。"""
    try:
        import msg_flow
        return msg_flow.fmt(sec)
    except Exception:
        return str(sec) + "s"


def overview(doc):
    """整棵总览（根任务→延申任务→行→子行）——op=tree 与顶栏明细共用这一份渲染真源。"""
    tt = _tt()
    ls = []
    for i, d in enumerate(tree_of(doc)):
        op = [r for r in (d.get("subtasks") or [])
              if str(r.get("status")) not in ("done", "skipped", "stopped")]
        try:
            op = tt.guard_rows(d)
        except Exception:
            pass  # noqa 守卫口径取不到就退回未终态计数
        own = ("" if str(d.get("conv") or "") == (chains.ACTIVE.get("conv") or "")
               else "〔属他对话 " + str(d.get("conv") or "")[-8:] + "·勿代改〕")
        ls.append("%s %s｜待办 %d/%d｜预测 %s%s" % (
            "◆ 根任务" if i == 0 else "  ↳ 延申任务",
            str(d.get("intent") or "")[:56], len(op), len(d.get("subtasks") or []),
            _fmt(tt.eta(d)), own))
        for r in d.get("subtasks") or []:
            ls.append("  " + rowline(d, r))
    return "\n".join(ls)


def plan_batches(rows, limit=None):
    """树／跨表行集的并发批次编排（真源＝task_res 资源互斥）：回 (可并行执行的行, 文案)。
    rows 可传 [(doc,row)] 或 [row]——带 doc 时只取叶子行（父行是汇总节点不派工）。"""
    import task_res as tr
    rs = [(r if isinstance(r, dict) else
          (r[1] if isinstance(r, (tuple, list)) and len(r) > 1 and r[1] else {}))
          for r in (rows or [])]
    rs = [r for r in rs if r and str(r.get("status")) in ("pending", "running", "error")]
    bs = tr.batches(rs, limit)
    flat = [r for bt in bs for r in bt]
    return flat, tr.report(rs, limit)


if __name__ == "__main__":
    a = sys.argv[1:] or ["help"]
    if a[0] == "sig":
        print(sig(" ".join(a[1:])))
    elif a[0] == "sim":
        parts = " ".join(a[1:]).split("|")
        print("%.3f" % sim(parts[0], parts[1] if len(parts) > 1 else ""))
    elif a[0] in ("render", "overview", "tree"):
        import task_table as tt
        d = tt._load(tt._find(a[1])) if len(a) > 1 else (tt._load(tt._latest()) or None)
        print((overview(d) if a[0] != "render" else render(d)) if d else "无在途总览")
    elif a[0] == "on":
        print("tree=%s merge_sim=%s max_depth=%s" % (on(), th(), max_depth()))
    else:
        print(__doc__.strip().splitlines()[-1])
