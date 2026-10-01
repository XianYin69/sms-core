#!/usr/bin/env python3
"""qq_flow.py — 数据流→QQ 的口径适配（2026-09-29 用户「只发送主要信息：除大模型思考、工具调用、代码运行、shell 初始化提示之外，所有由大模型输出的信息」）：feed(line)＝按 msg_flow.kindof 分类——llm_out（模型正文）累积进 <SMS_HOME>/qq/buf.json 不逐行发（防 30qpm 限频刷屏），notice（user_send 正文）与 err（告警）即时发，tool/skill/edit/sh/step/task/reasoning（思考·工具·代码·过程）一律丢弃；close(tag)＝对话收口把缓冲正文合并成一条推送（超 max_len 由 qq_chunk 按行装箱分段·不丢字；QQ 简洁模式生效时先经 qq_brief.cap 限长 brief_len、超出以「…（余下见 SMS 壳）」收尾），顺带补发 outbox；ask(q)＝模型向用户提问即时推送；pending(row)＝做梦修复待批即时推送。全部 best-effort：任何异常吞掉返回 None，绝不影响数据流与收口。用法：python -B qq_flow.py feed "<行>"|close|ask "<问题>"|pending "<项>"|buf"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import msg_flow, qq_push as qp
def _bp(): return qp._f(qp.conf()["sms"], "buf.json")
def buf(): return qp._ld(_bp(), []) or []
def _wb(rows):
    p = _bp()
    if rows: qp._wj(p, rows)
    elif os.path.exists(p): os.remove(p)
def _add(t): _wb((buf() + [t])[-40:]); return len(buf())
def feed(line, c=None):
    try:
        c = c or qp.conf(); t = str(line or "").strip()
        if not t or not qp.ready(c): return None
        k, _ = msg_flow.kindof(t)
        if k == "llm_out": return _add(t)
        if k in ("notice", "err"): return qp.push(msg_flow.SUB.sub("", t).strip(), "QQ·" + k, c)
        return None
    except Exception: return None
def close(tag="收口", c=None):
    try:
        c = c or qp.conf(); rows = buf(); _wb([]); import qq_report, qq_brief; s = qq_report.snapshot(); rows = (rows + [s]) if s else rows
        if not rows: return None
        r = qp.push(qq_brief.cap("\n".join(rows), c), "QQ·" + tag, c); qq_report.flush(c); qp.flush(); return r
    except Exception: return None
def wrap(fn):
    return lambda *a, **k: (feed(a[0]) if a else None, fn(*a, **k))[1]
def fire(tag, arg=""):
    try:
        return ask(arg) if tag == "ask" else pending(arg) if tag == "pending" else qp.push(arg, "QQ·" + str(tag))
    except Exception: return None
def ask(q, c=None): return qp.push("❓需要你确认：" + str(q)[:300], "QQ·提问", c or qp.conf())
def pending(row, c=None):
    r = row or {}
    return qp.push("⚠修复待批：%s·%s（原因：%s）→ 空闲时 :repair go %s" % (r.get("kind"), r.get("target"), r.get("reason"), r.get("id")), "QQ·待批", c or qp.conf())
if __name__ == "__main__":
    a = sys.argv[1:] or ["buf"]
    print(json.dumps(buf()[-5:], ensure_ascii=False, indent=1) if a[0] == "buf"
          else str(feed(" ".join(a[1:]))) if a[0] == "feed"
          else str(close(a[1] if len(a) > 1 else "收口")) if a[0] == "close"
          else str(ask(" ".join(a[1:]))) if a[0] == "ask"
          else str(pending({"kind": "test", "target": "t", "reason": "r", "id": "x"})) if a[0] == "pending" else "?")
