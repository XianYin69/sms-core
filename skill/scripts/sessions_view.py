#!/usr/bin/env python3
"""sessions_view.py — 会话拓扑与冲突监视（批23·对等对话·多 session）：session＝多对话容器
（新建会话＝新 session，conv 每输入/每派发自动开收·二者不再混同）；对话间无主次、互任监视者·
指导者·训诫者，本模块供其"查看"的数据——rows() 按创建先后列各 session（先后顺序）附最后活动
时间（session 链 member→sess 边碎片 max ts）与未完成表行数；conflicts(cur) 列其他 session 的
未完成 task_table 与同技能跨会话并行（冲突线索·只报告不代裁）；overview(cur) 全量文本；
hint(cur) 一行提示——存在跨会话未完成时由 chains.conversation 注入〔会话拓扑〕，各对话据此负
监视/训诫/收口之责（批50：已完成未打标行系统自动跨对话补标，不要求用户 :session use 切换会话；
确未完成的行直接 task_plan 显式 tid 完成或说明由所属会话推进，不新建同义表）；多壳并行＝
各壳以 env SMS_SESSION 绑定自己的 session。纯读不落盘。用法：python -B sessions_view.py
overview|conflicts|hint

性能（2026-10-02 治 sms_shell 卡顿·规格 perf_spec.md·输出文案零回归）：旧版 overview() 里
_pend() 被 rows() 与 conflicts() 各算一遍、kind_of()/convs() 对每个 session 重读 41KB
sessions.json（N+1），且与 shell_tui_sessions 各扫一遍 session 链。现统一走 _memo() 一次快照
（TTL 默认 1s·同轮复用），rows/conflicts/overview 接收 sn 参数，kind_of/convs 接收 smap 参数
（旧签名与默认值保留＝既有调用点不变）；shell_tui_sessions 可复用同一份 session/dialogue 碎片。
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, chain_store, atomic_io
SMS = resolve_home.ensure()
_SNAP = {}   # key -> (时间戳, 值)：同轮共享快照（TTL 兜住跨轮新鲜度）
TTL = 1.0


def _memo(key, fn, ttl=None):
    """同轮共享快照：TTL 内复用（默认 1s·一次 overview 内 rows/conflicts 共用）。"""
    e = _SNAP.get(key)
    if e and time.time() - e[0] < (TTL if ttl is None else ttl): return e[1]
    v = fn(); _SNAP[key] = (time.time(), v); return v


def _smap():
    return _memo("smap", _read_smap)


def _read_smap():
    try: return atomic_io.rjson(os.path.join(SMS, "shell", "sessions.json")) or {}
    except Exception: return {}


def _pend():
    return _memo("pend", _read_pend)


def _read_pend():
    td = os.path.join(SMS, "tasks"); out = []
    for fn in (sorted(os.listdir(td)) if os.path.isdir(td) else []):
        try: doc = atomic_io.rjson(os.path.join(td, fn))
        except Exception: continue
        subs = doc.get("subtasks") or []
        # 批34：终态＝done/skipped/error/stopped——skipped＝用户指令弃置，不再算「未完成」
        rest = [x for x in subs if str(x.get("status") or "pending") not in ("done", "skipped", "error", "stopped")]
        if not (doc and rest): continue
        out.append({"tid": doc.get("id", fn[:-5]), "sess": doc.get("sess") or "?",
                    "conv": doc.get("conv") or "", "rows": len(rest), "total": len(subs),
                    "skills": sorted({str(x.get("skill") or "工具自办") for x in rest})})
    return out


def _store():
    return _memo("store", lambda: chain_store.Store(SMS), ttl=30)


def session_frags():
    """session 链碎片（本模块与 shell_tui_sessions 共用一次扫描·TTL 内复用）。"""
    return _memo("frags:session", lambda: _store().all_frags("session"))


def dialogue_frags():
    return _memo("frags:dialogue", lambda: _store().all_frags("dialogue"))


def _last():
    m = {}
    for f in session_frags():
        for e in f.get("edges") or []:
            if e[1] == "member": m[e[0]] = max(m.get(e[0], ""), str(f.get("ts", "")))
    return m


def snap():
    """一次快照（供右栏 _heavy 线程内取数后分发给两个视图·消除重复扫描）。"""
    return {"smap": _smap(), "pend": _pend(), "last": _last(),
            "session": session_frags(), "dialogue": dialogue_frags()}


def rows(cur="", sn=None):
    sn = sn or {}
    sm = sn.get("smap") or _smap(); lm = sn.get("last") or _last()
    pd = {}
    for p in (sn.get("pend") if sn.get("pend") is not None else _pend()):
        pd[p["sess"]] = pd.get(p["sess"], 0) + p["rows"]
    return [(sid, v.get("name", ""), v.get("created", ""), lm.get(sid, ""), pd.get(sid, 0),
             sid == cur) for sid, v in sorted(sm.items(),
                                              key=lambda kv: (str(kv[1].get("kind", "shell")),
                                                              str(kv[1].get("created", ""))))]


def kind_of(sid, smap=None):
    return str((smap if smap is not None else _smap()).get(sid, {}).get("kind", "shell"))


def convs(sid, smap=None):
    v = (smap if smap is not None else _smap()).get(sid) or {}
    return list(v.get("convs") or ([v["conv"]] if v.get("conv") else []))


def conflicts(cur="", sn=None):
    pend = sn.get("pend") if sn and sn.get("pend") is not None else _pend()
    other = [p for p in pend if p["sess"] != cur]
    if not other: return ""
    by = {}
    for p in pend:
        for sk in p["skills"]: by.setdefault(sk, set()).add(p["sess"])
    multi = ["%s（跨 %s）" % (k, "、".join(sorted(v))) for k, v in sorted(by.items()) if len(v) > 1]
    ls = ["跨会话未完成：" + "；".join("表 %s@%s 余 %d/%d 行〔conv %s〕"
         % (p["tid"][-14:], p["sess"], p["rows"], p["total"], p["conv"][-15:]) for p in other)]
    multi and ls.append("同技能跨会话并行（先后/冲突注意）：" + "；".join(multi))
    return "\n".join(ls)


def overview(cur="", sn=None):
    sn = sn or snap()
    ls = ["〔会话拓扑〕session 按创建先后（◎当前·行末为未完成表行数）："]
    sm = sn["smap"]
    for sid, n, c, l, un, cc in rows(cur, sn):
        ls.append("%s %s %s｜%s｜conv %d｜创建 %s｜活动 %s｜未完成 %d"
                  % ("◎" if cc else "·", sid, n, kind_of(sid, sm), len(convs(sid, sm)),
                     c[:16], l[5:16].replace("T", " ") or "-", un))
    cf = conflicts(cur, sn); cf and ls.append(cf)
    return "\n".join(ls) if len(ls) > 1 else "〔会话拓扑〕暂无登记 session（:session new 新建会话＝新 session）"


HINT_TAIL = ("\n——你是对等对话的监视者·指导者·训诫者（批50 跨对话完成口径）：已完成未打标的跨会话行由系统自动补标"
             "（对账/派发回写），不要求用户 :session use 切换会话去完成；确认未完成的行可直接用 task_plan（显式 tid）"
             "完成或按完成证据对账，或说明由所属会话推进，不新建同义表、不越权改他人行内容。")


def hint(cur=""):
    _SNAP.pop("pend", None)  # 训诫依据须当下真值：绕过 TTL 快照（成本＝一次 _pend·与旧版同）
    cf = conflicts(cur)
    return "" if not cf else "输出停止＝形式停止非实质完成。" + cf + HINT_TAIL


if __name__ == "__main__":
    a = sys.argv[1:] or ["overview"]
    import chains; cur = chains.cur_sess()
    print({"overview": lambda: overview(cur),
           "conflicts": lambda: conflicts(cur) or "（无跨会话未完成·各会话任务总览均已收口）",
           "hint": lambda: hint(cur) or "（无跨会话未完成事项）"}
          .get(a[0], lambda: (__doc__.strip().splitlines() or ["用法：python -B sessions_view.py [子命令]"])[0])())
