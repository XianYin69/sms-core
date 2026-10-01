#!/usr/bin/env python3
"""dream_reinforce.py — 做梦「高频加强记忆」（2026-09-29 用户：链整理继承低频清除，但高频使用部分要有加强机制）：低频修剪仍由 chain_store.prune 继承（不动），本模块反向加强——freq≥TH 的原子＝① 语义/因果边权 ×1.5（封顶 chain_edges.CAP，三维空间里更“亮”）② 非 memory/knowledge 者复制一条 `强化记忆·f<freq>·<链>：<原文>` 入 memory 链并 ref 回原原子，且把新原子 freq 置为源 freq（天然豁免下轮低频修剪）③ 记 <SMS_HOME>/chains/reinforced.json（id→freq）做幂等：freq 未涨则本轮不再重复沉淀，涨了才再加强。回 {candidates, promoted, weighted}。用法：python -B dream_reinforce.py [阈值freq]"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chain_store as cs, chain_edges as ce, resolve_home, atomic_io
def _p(sms): return os.path.join(sms, "chains", "reinforced.json")
def reinforce(sms=None, th=8, cap=12):
    sms = sms or resolve_home.ensure(); st = cs.Store(sms)
    fs = [f for f in st.all_frags() if not f.get("dead") and f.get("freq", 1) >= th]
    prev = atomic_io.rjson(_p(sms), default={}) or {}; have = {f["text"] for f in st.all_frags("memory")}
    out = dict(prev); n = w = 0
    for f in sorted(fs, key=lambda x: -x.get("freq", 1))[:cap]:
        w += ce.weight(st, f["id"], "semantic", 1.5) + ce.weight(st, f["id"], "causal", 1.5)
        if prev.get(f["id"]) == f["freq"]: out[f["id"]] = f["freq"]; continue
        out[f["id"]] = f["freq"]
        t = "强化记忆·f%d·%s：%s" % (f["freq"], f["chain"], (f.get("text") or "")[:180])
        if f["chain"] != "memory" and t not in have:
            fid = st.add("memory", t, [[f["id"], "ref", 1.0]])
            if fid and not str(fid).startswith("ERR"):
                c = st._cof(fid); d = cs._ld(st._p(c, fid)); d["freq"] = f["freq"]; cs._wj(st._p(c, fid), d); n += 1
    atomic_io.wjson(_p(sms), out)
    return {"candidates": len(fs), "promoted": n, "weighted": w, "threshold": th}
if __name__ == "__main__":
    print(json.dumps(reinforce(th=int(sys.argv[1]) if len(sys.argv) > 1 else 8), ensure_ascii=False))
