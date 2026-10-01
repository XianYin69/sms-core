#!/usr/bin/env python3
"""latency.py — skill/工具/路由/LLM 调用时长度量（批6·用户「测试调用时长」）：rec/wrap 追加 JSONL 到 <SMS_HOME>/metrics/latency.jsonl（≤600KB 自动裁尾 5000 行），report 按 k|n 聚合计数/均值/p50/p95/max。埋点＝skill_route.route/agent_dispatch.execute/agent_tools.run_skill/gateway.chat 经 wrap 自动记一笔（settings latency.enabled 默认 true·开销≈perf_counter＋一次 append）。用法：python -B latency.py report|reset"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import resolve_home, settings
def _f(): return os.path.join(resolve_home.ensure(), "metrics", "latency.jsonl")
def on(): return bool(settings.get("latency.enabled", True))
def rec(kind, name, ms):
    if not on(): return
    p = _f(); os.makedirs(os.path.dirname(p), exist_ok=True)
    try: open(p, "a", encoding="utf-8").write(json.dumps({"k": kind, "n": name, "ms": round(ms, 2), "t": int(time.time())}, ensure_ascii=False) + "\n")
    except Exception: pass
    if os.path.exists(p) and os.path.getsize(p) > 600000:
        ls = open(p, encoding="utf-8").read().splitlines(); open(p, "w", encoding="utf-8").write("\n".join(ls[-5000:]) + "\n")
def wrap(kind, name, fn, *a, **k):
    t = time.perf_counter()
    try: return fn(*a, **k)
    finally: rec(kind, name, (time.perf_counter() - t) * 1000)
def _pct(s, p): return s[min(len(s) - 1, int(len(s) * p))]
def avg(k): e = report().get(k); return e and e["mean"]
def report():
    try: ls = [json.loads(x) for x in open(_f(), encoding="utf-8").read().splitlines() if x.strip()]
    except FileNotFoundError: return {}
    g = {}
    for e in ls: g.setdefault(e["k"] + "|" + str(e["n"]), []).append(e["ms"])
    return {k: {"n": len(v), "mean": round(sum(v) / len(v), 1), "p50": round(sorted(v)[len(v) // 2], 1), "p95": round(_pct(sorted(v), .95), 1), "max": round(max(v), 1)} for k, v in g.items()}
def reset(): p = _f(); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w", encoding="utf-8").write(""); return "已清空 latency 度量"
if __name__ == "__main__":
    a = sys.argv[1:] or ["report"]
    print(json.dumps(report(), ensure_ascii=False, indent=1) if a[0] == "report" else (reset() if a[0] == "reset" else __doc__.strip().splitlines()[1][:200]))
