#!/usr/bin/env python3
"""cost_report.py — 费用台账聚合（批41 F1·缺口 G2 的读取端）：读 <SMS_HOME>/metrics/usage.jsonl
（由 usage_ledger.rec 每轮追加），按 日 / conv / skill / model 汇总 token 与费用。
口径：in＝prompt_tokens、out＝completion_tokens（含推理）、reason＝reasoning_tokens、
cache_read＝cached_tokens；cost 缺省（上游未回价格）时按 settings model_meta.prices
（每 1M token·{in,out}）估算并标 est=true，估不出来记 0。
用法：python -B cost_report.py [day|conv|skill|model|tail] [值]（默认 day＝逐日总账）；
:cost 元指令经 shell_core 转发到此。任何异常回空表不抛穿。"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import usage_ledger as UL


def rows(sms=None):
    p = usage_ledger_path(sms)
    try:
        return [json.loads(x) for x in open(p, encoding="utf-8").read().splitlines() if x.strip()]
    except Exception:
        return []


def usage_ledger_path(sms=None):
    return UL.path(sms)


def _day(t):
    return time.strftime("%Y-%m-%d", time.localtime(int(t or 0)))


def _price(model):
    """settings model_meta.prices.{model}.{in,out}（每 1M token）——缺配置回 None＝不估算。"""
    try:
        import settings
        p = (settings.eff().get("model_meta") or {}).get("prices") or {}
        return p.get(model) or p.get("default")
    except Exception:
        return None


def _est(r):
    """cost 缺失时按牌价估算（单位：每 1M token）；无牌价回 0.0。"""
    pr = _price(r.get("model") or "")
    if not pr:
        return 0.0
    return (int(r.get("in") or 0) * float(pr.get("in") or 0)
            + int(r.get("out") or 0) * float(pr.get("out") or 0)) / 1e6


def _num(r):
    cost = r.get("cost")
    est = cost is None
    return int(r.get("in") or 0), int(r.get("out") or 0), int(r.get("reason") or 0), \
        int(r.get("cache_read") or 0), (float(cost) if cost is not None else _est(r)), est


def agg(key, sms=None):
    """按维度聚合 → {值: {turns,in,out,reason,cache_read,cost,est}}"""
    out = {}
    for r in rows(sms):
        k = str(r.get(key) or "-") if key != "day" else _day(r.get("t"))
        b = out.setdefault(k, {"turns": 0, "in": 0, "out": 0, "reason": 0,
                               "cache_read": 0, "cost": 0.0, "est": 0})
        i, o, rs, cr, c, is_est = _num(r)
        b["turns"] += 1; b["in"] += i; b["out"] += o; b["reason"] += rs; b["cache_read"] += cr
        b["cost"] = round(b["cost"] + c, 6); b["est"] += is_est
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["cost"]))


def brief(key, sms=None, top=12):
    d = agg(key, sms)
    tot = {"turns": sum(v["turns"] for v in d.values()),
           "in": sum(v["in"] for v in d.values()), "out": sum(v["out"] for v in d.values()),
           "cost": round(sum(v["cost"] for v in d.values()), 6)}
    return {"by": key, "file": usage_ledger_path(sms), "rows": tot,
            "top": {k: d[k] for k in list(d)[:top]}}


if __name__ == "__main__":
    a = sys.argv[1:] or ["day"]
    if a[0] == "tail":
        r = rows()[-int(a[1] or 3):]
        print(json.dumps(r, ensure_ascii=False))
    elif a[0] in ("day", "conv", "skill", "model"):
        print(json.dumps(brief(a[0]), ensure_ascii=False, indent=1))
    else:
        print(__doc__.strip().splitlines()[0][:200])
