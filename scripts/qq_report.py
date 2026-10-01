#!/usr/bin/env python3
"""qq_report.py — 任务表→QQ 的实时回传（2026-09-29 用户「回传到qq的消息还要有任务表 并且要实时回传进度」）：task_table.emit 是每次改表（plan/status/add/remove/skill）的唯一咽喉，本模块挂在它后面＝进度一落地就回传，不轮询、不改调用方签名；渲染＝标题行「〔任务表 id〕done/total ▓░进度条 约剩Ns」（Ns＝task_table.eta 实测均值）＋逐行「✓done ▶running ·pending ✗error ■stopped」；节流＝签名 sig（表id＋done/total＋当前 running 行）未变则不发（纯改技能/删行不刷屏），变了但距上次推送 < task_gap（默认 8s·官方 30qpm）则把最新快照合并写进 <SMS_HOME>/qq/progress.json 的 pend 只留最后一份（天然去抖），由 flush() 在收口时补发；开关与阈值＝config/qq.json 的 task_push/task_gap（走 qq_cli conf k=v 改）；snapshot() 供 qq_flow.close 与 qq_inbound 把当前表快照附在回给 QQ 的正文末尾——被动回复窗口内走 qq_reply 不占主动 1000 条/天配额，过期自动回落主动推送。与 task_table 互为延迟 import 防循环依赖；任何异常一律吞掉返回 None，绝不断数据流与收口。用法：python -B qq_report.py render|snapshot|flush|test "<文本>"。"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qq_push as qp, msg_flow
MARK = {"done": "✓", "running": "▶", "error": "✗", "stopped": "■"}
def _pf(c): return qp._f(c["sms"], "progress.json")
def _sp(c): return qp._ld(_pf(c), {}) or {}
def _dn(s): return sum(1 for x in s if x.get("status") == "done")
def _sig(d):
    s = d.get("subtasks") or []
    return "%s|%d/%d|%s" % (str(d.get("id"))[-14:], _dn(s), len(s), next((str(x.get("id")) for x in s if x.get("status") == "running"), ""))
def render(d):
    import task_table as tt
    s = d.get("subtasks") or []; n = len(s); dn = _dn(s)
    head = "〔任务表 %s〕%d/%d %s %s" % (str(d.get("id"))[-14:], dn, n, "▓" * dn + "░" * (n - dn), msg_flow.fmt(tt.eta(d)))
    return (head + "\n" + "\n".join("%s%s %s" % (MARK.get(x.get("status"), "·"), x.get("id"), str(x.get("goal"))[:38]) for x in s))[:460]
def progress(doc, note=""):
    try:
        c = qp.conf()
        if not (doc and qp.ready(c) and c.get("task_push", True)): return None
        st = _sp(c); now = time.time(); sig = _sig(doc); txt = render(doc)
        if sig == st.get("sig") and not st.get("pend"): return "进度未变·不发"
        if now - float(st.get("last") or 0) < float(c.get("task_gap", 8)):
            qp._wj(_pf(c), dict(st, pend=txt, psig=sig, tid=str(doc.get("id")))); return "间隔内·合并待补发"
        qp._wj(_pf(c), dict(st, sig=sig, last=now, pend="", tid=str(doc.get("id"))))
        return qp.push(txt, ("QQ·进度·" + note) if note else "QQ·进度", c)
    except Exception: return None
def flush(c=None):
    try:
        c = c or qp.conf(); st = _sp(c); t = str(st.get("pend") or "")
        if not t: return None
        qp._wj(_pf(c), dict(st, pend="", sig=str(st.get("psig") or ""), last=time.time()))
        return qp.push(t, "QQ·进度·补发", c)
    except Exception: return None
def snapshot(tid=""):
    try:
        import task_table as tt, chains
        k = tt._find(tid) or tt._latest(); d = tt._load(k) if k else None
        if d is None:
            d = next([x for x in [tt._load(str(_sp(qp.conf()).get("tid") or ""))] if x and x.get("conv") == chains.ACTIVE.get("conv")], None)
        return render(d) if d else ""
    except Exception: return ""
if __name__ == "__main__":
    a = sys.argv[1:] or ["help"]; DEMO = {"id": "task-demo000", "subtasks": [{"id": "t1", "goal": "示例完成项", "status": "done"}, {"id": "t2", "goal": "示例进行中", "status": "running"}, {"id": "t3", "goal": "示例待办", "status": "pending"}]}
    print(snapshot(a[1] if len(a) > 1 else "") if a[0] == "snapshot" else str(flush()) if a[0] == "flush"
          else str(progress(DEMO, "自测")) if a[0] == "test" else render(DEMO) if a[0] == "render" else __doc__.strip()[:300])
