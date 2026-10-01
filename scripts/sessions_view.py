#!/usr/bin/env python3
"""sessions_view.py — 会话拓扑与冲突监视（批23·对等对话·多 session）：session＝多对话容器（新建会话＝新 session，conv 每输入/每派发自动开收·二者不再混同）；对话间无主次、互任监视者·指导者·训诫者，本模块供其“查看”的数据——rows() 按创建先后列各 session（先后顺序）附最后活动时间（session 链 member→sess 边碎片 max ts）与未完成表行数；conflicts(cur) 列其他 session 的未完成 task_table 与同技能跨会话并行（冲突线索·只报告不代裁）；overview(cur) 全量文本；hint(cur) 一行提示——存在跨会话未完成时由 chains.conversation 注入〔会话拓扑〕，各对话据此负监视/训诫之责（提示用户 :session use 接续或收口，勿越会话代改他人表）；多壳并行＝各壳以 env SMS_SESSION 绑定自己的 session。纯读不落盘。用法：python -B sessions_view.py overview|conflicts|hint"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import resolve_home, chain_store, atomic_io
SMS = resolve_home.ensure()
def _smap():
    try: return atomic_io.rjson(os.path.join(SMS, "shell", "sessions.json")) or {}
    except Exception: return {}
def _pend():
    td = os.path.join(SMS, "tasks"); out = []
    for fn in (sorted(os.listdir(td)) if os.path.isdir(td) else []):
        try: doc = atomic_io.rjson(os.path.join(td, fn))
        except Exception: continue
        subs = doc.get("subtasks") or []; rest = [x for x in subs if x.get("status") != "done"]
        if doc and rest: out.append({"tid": doc.get("id", fn[:-5]), "sess": doc.get("sess") or "?", "conv": doc.get("conv") or "", "rows": len(rest), "total": len(subs), "skills": sorted({str(x.get("skill") or "工具自办") for x in rest})})
    return out
def _last():
    m = {}
    for f in chain_store.Store(SMS).all_frags("session"):
        for e in f.get("edges") or []:
            if e[1] == "member": m[e[0]] = max(m.get(e[0], ""), str(f.get("ts", "")))
    return m
def rows(cur=""):
    sm, lm, pd = _smap(), _last(), {}
    for p in _pend(): pd[p["sess"]] = pd.get(p["sess"], 0) + p["rows"]
    return [(sid, v.get("name", ""), v.get("created", ""), lm.get(sid, ""), pd.get(sid, 0), sid == cur) for sid, v in sorted(sm.items(), key=lambda kv: (str(kv[1].get("kind", "shell")), str(kv[1].get("created", ""))))]
def kind_of(sid):
    return str(_smap().get(sid, {}).get("kind", "shell"))
def convs(sid):
    v = _smap().get(sid) or {}
    return list(v.get("convs") or ([v["conv"]] if v.get("conv") else []))
def conflicts(cur=""):
    other = [p for p in _pend() if p["sess"] != cur]
    if not other: return ""
    by = {}
    for p in _pend():
        for sk in p["skills"]: by.setdefault(sk, set()).add(p["sess"])
    multi = ["%s（跨 %s）" % (k, "、".join(sorted(v))) for k, v in sorted(by.items()) if len(v) > 1]
    ls = ["跨会话未完成：" + "；".join("表 %s@%s 余 %d/%d 行〔conv %s〕" % (p["tid"][-14:], p["sess"], p["rows"], p["total"], p["conv"][-15:]) for p in other)]
    multi and ls.append("同技能跨会话并行（先后/冲突注意）：" + "；".join(multi))
    return "\n".join(ls)
def overview(cur=""):
    ls = ["〔会话拓扑〕session 按创建先后（◎当前·行末为未完成表行数）："]
    for sid, n, c, l, un, cc in rows(cur): ls.append("%s %s %s｜%s｜conv %d｜创建 %s｜活动 %s｜未完成 %d" % ("◎" if cc else "·", sid, n, kind_of(sid), len(convs(sid)), c[:16], l[5:16].replace("T", " ") or "-", un))
    cf = conflicts(cur); cf and ls.append(cf)
    return "\n".join(ls) if len(ls) > 1 else "〔会话拓扑〕暂无登记 session（:session new 新建会话＝新 session）"
def hint(cur=""):
    cf = conflicts(cur)
    return "" if not cf else "输出停止＝形式停止非实质完成。" + cf + "\n——你是对等对话的监视者·指导者·训诫者：提醒用户 :session use <id> 接续或 task_plan 收口他人表，未经用户确认不越会话代改"
if __name__ == "__main__":
    a = sys.argv[1:] or ["overview"]
    import chains; cur = chains.cur_sess()
    print({"overview": lambda: overview(cur), "conflicts": lambda: conflicts(cur) or "（无跨会话未完成·各会话任务表均已收口）", "hint": lambda: hint(cur) or "（无跨会话未完成事项）"}.get(a[0], lambda: __doc__.strip().splitlines()[1])())
