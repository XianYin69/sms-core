#!/usr/bin/env python3
"""chain_edges.py — 原子间双向联系（2026-09-29 用户「不同的原子之间双向联系」）：碎片 edges 原为单向（a→b），本模块补对称——bidir(store,a,b,rel,w)＝a→b 与 b→a 同写（已有同向边只加权不重复，边权封顶 CAP）；symmetrize(sms)＝全库扫一遍为所有单向边补反向（做梦每轮首步跑，回补写条数）；rev_index(frags)＝入边反向索引（id→[(邻居,rel,权)]），与出边合并即邻接表 adj()，深度优先读取 chain_dfs 与三维近邻漫游共用（避免每次全库扫）；weight(store,fid,rel,mult)＝加强记忆时按关系批量调边权。关系集沿用 semantic/temporal/causal/ref/member。用法：python -B chain_edges.py symmetrize | adj <id>"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chain_store as cs, resolve_home
CAP = 3.0
SYM = ("semantic", "causal", "temporal")  # 仅语义类边补反向；ref/member 为结构边，反向炸扇出
def _has(f, tgt, rel): return any(e[0] == tgt and e[1] == rel for e in f.get("edges", []))
def bidir(store, a, b, rel="semantic", w=1.0):
    ca, cb = store._cof(a), store._cof(b)
    if not ca or not cb: return "缺原子：" + (a if not ca else b)
    for c, x, y in ((ca, a, b), (cb, b, a)):
        d = cs._ld(store._p(c, x))
        if _has(d, y, rel): d["edges"] = [[e[0], e[1], min(CAP, round(e[2] + w * 0.1, 3))] for e in d["edges"]]
        else: d["edges"].append([y, rel, round(w, 3)])
        cs._wj(store._p(c, x), d)
    return "双向已建 %s<->%s(%s)" % (a, b, rel)
def symmetrize(sms=None):
    store = cs.Store(sms or resolve_home.ensure()); fs = store.all_frags(); byid = {f["id"]: f for f in fs}; n = 0
    for f in fs:
        for e in list(f.get("edges", [])):
            t = byid.get(e[0])
            if t is None or e[1] not in SYM or _has(t, f["id"], e[1]): continue
            t["edges"].append([f["id"], e[1], e[2]]); cs._wj(store._p(t["chain"], t["id"]), t); n += 1
    return n
def rev_index(frags):
    r = {}
    for f in frags:
        for e in f.get("edges", []): r.setdefault(e[0], []).append((f["id"], e[1], e[2]))
    return r
def adj(f, rev=None):
    out = [(e[0], e[1], e[2]) for e in f.get("edges", [])]
    return out + list((rev or {}).get(f["id"], []))
def weight(store, fid, rel, mult=1.5):
    c = store._cof(fid)
    if not c: return 0
    d = cs._ld(store._p(c, fid)); k = 0
    for e in d["edges"]:
        if e[1] == rel: e[2] = min(CAP, round(e[2] * mult, 3)); k += 1
    cs._wj(store._p(c, fid), d); return k
if __name__ == "__main__":
    a = sys.argv[1:] or ["symmetrize"]; store = cs.Store(resolve_home.ensure())
    if a[0] == "symmetrize": print("补反向边 %d 条" % symmetrize())
    elif a[0] == "adj":
        fs = {f["id"]: f for f in store.all_frags()}; print(json.dumps(adj(fs.get(a[1], {"id": a[1], "edges": []}), rev_index(list(fs.values()))), ensure_ascii=False)[:600])
    elif a[0] == "bidir" and len(a) > 2: print(bidir(store, a[1], a[2], a[3] if len(a) > 3 else "semantic"))
    else: print(__doc__.strip().splitlines()[-1])