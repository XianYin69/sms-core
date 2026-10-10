#!/usr/bin/env python3
"""usage_ledger.py — 费用台账落盘（批41 F1·缺口 G2）：网关每轮把 OpenAI 口径 usage 追加写
<SMS_HOME>/metrics/usage.jsonl，行格式 {t,conv,sess,skill,model,in,out,reason,cache_read,
cost,currency}。此前 usage 只在 dsm.py 协议层归一、没有任何落盘聚合面（metrics 只有
latency.jsonl＝耗时），费用无从统计。写失败一律静默降级（绝不因记账把主链路拖崩），
文件超 600KB 裁尾 3000 行（同 latency 口径）。rec(usage, model=, skill=) 由
gateway/gateway_sse 收口处调用，聚合与查询见 cost_report.py。"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, chains


def path(sms=None):
    return os.path.join(sms or resolve_home.ensure(), "metrics", "usage.jsonl")


def _i(v):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ids():
    """conv/sess 归属＝agent_tools.emit 同口径：先取线程上下文（批23 派发对话/批27 并行
    worker 各自的 conv），再落 chains.ACTIVE，最后 session 兜底——绝不抛穿。"""
    conv = sess = ""
    try:
        import agent_ctx as ac
        conv = str(ac.cur().get("conv") or "")
    except Exception:
        pass
    try:
        conv = conv or str(chains.ACTIVE.get("conv") or "")
        sess = str(chains.cur_sess() or "")
    except Exception:
        pass
    return conv, sess


def split(usage, model="", skill="", conv=None, sess=None):
    """OpenAI 口径 usage → 台账行 dict（纯函数·不落盘；缺字段一律 0/None）。"""
    u = usage if isinstance(usage, dict) else {}
    d = u.get("prompt_tokens_details") or {}
    c = u.get("completion_tokens_details") or {}
    dc, ds = _ids()
    return {"t": int(time.time()), "conv": str(conv if conv is not None else dc or ""),
            "sess": str(sess if sess is not None else ds or ""),
            "skill": str(skill or ""), "model": str(model or ""),
            "in": _i(u.get("prompt_tokens")), "out": _i(u.get("completion_tokens")),
            "reason": _i(c.get("reasoning_tokens")), "cache_read": _i(d.get("cached_tokens")),
            "cost": _f(u.get("cost")), "currency": str(u.get("currency") or "")}


def rec(usage, model="", skill="", sms=None, conv=None, sess=None):
    """追加一行台账；任何异常静默（返回 bool 仅供自检·调用方无需处理）。
    全零 usage（旧网关不回计量）不写，免灌噪声行。"""
    row = split(usage, model, skill, conv, sess)
    if not (row["in"] or row["out"] or row["cost"]):
        return False
    p = path(sms)
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        if os.path.getsize(p) > 600000:
            ls = open(p, encoding="utf-8").read().splitlines()
            with open(p, "w", encoding="utf-8") as f:
                f.write("\n".join(ls[-3000:]) + "\n")
        return True
    except Exception:
        return False


if __name__ == "__main__":
    a = sys.argv[1:] or ["tail"]
    if a[0] == "tail":
        ls = [x for x in open(path(), encoding="utf-8").read().splitlines() if x.strip()] \
            if os.path.exists(path()) else []
        print(json.dumps({"file": path(), "rows": len(ls), "last": ls[-3:]}, ensure_ascii=False))
    elif a[0] == "selftest":
        tmp = a[1] if len(a) > 1 else os.environ.get("SMS_TMP") or "."
        ok = rec({"prompt_tokens": 11, "completion_tokens": 22,
                  "completion_tokens_details": {"reasoning_tokens": 7},
                  "prompt_tokens_details": {"cached_tokens": 3},
                  "cost": 0.003, "currency": "USD"}, model="t", skill="selftest",
                 sms=tmp, conv="conv-x", sess="sess-x")
        p = path(tmp)
        line = json.loads(open(p, encoding="utf-8").read().splitlines()[-1]) if ok else {}
        print(json.dumps({"ok": bool(ok), "path": p, "row": line}, ensure_ascii=False))
        raise SystemExit(0 if ok and line.get("in") == 11 and line.get("reason") == 7 else 1)
    else:
        print(__doc__.strip().splitlines()[0][:200])


def cur_skill():
    """当前归属技能名（批41 F1 台账 skill 列）：取 agent_ctx 线程上下文的派发链末位，
    无派发（主对话自身）＝smsystem-suit。绝不在模块顶 import agent_tools（循环导入）。"""
    try:
        import agent_ctx as ac
        ch = ac.cur().get("chain") or []
        return str(ch[-1]) if ch else "smsystem-suit"
    except Exception:
        return "smsystem-suit"
