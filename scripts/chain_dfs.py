#!/usr/bin/env python3
"""chain_dfs.py — 深度优先读取三维链记忆（2026-09-29 用户「大模型读取这个3维链式记忆需要使用深度优先算法」）：种子＝向量命中碎片；沿两类邻接做迭代式 DFS——① 双向语义边（chain_edges.adj＝出边＋rev 入边）② 三维空间同格/邻格原子（chain_space3d 坐标按 (X链域, int(Y时间·次数), int(Z长度)) 建网格，同格＝记忆邻近）；每层按「三维距离－边权－频次」定序取前 BR 分支，深度上限 depth、字符预算 cap 内顺序产出；命中碎片自动 bump（读到＝强化）。byid/rev/pos/grid 走 TTL 缓存（网关常驻进程二次调用近零成本）。block() 缩进渲染（缩进＝DFS 深度·模型可见路径结构）。用法：python -B chain_dfs.py search "<查询>" [cap] | seed <id> [depth]"""
import os, sys, json, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chain_store as cs, chain_edges as ce, chain_space3d as sp, resolve_home
BR, TTL = 8, 30.0; IDX = {"t": 0.0, "w": -1, "byid": {}, "rev": {}, "pos": {}, "grid": {}}
def _cell(p): return (int(p[0]), int(p[1]), int(p[2])) if p and len(p) == 3 else None
def _cells(c):
    x, y, z = c; return [(x, y + a, z + b) for a in (0, 1, -1) for b in (0, 1, -1)]
def index(sms=None, force=False):
    if force or cs.WRITES[0] != IDX["w"] or time.time() - IDX["t"] > TTL:
        frags = [f for f in cs.Store(sms or resolve_home.ensure()).all_frags() if not f.get("dead")]
        pos = sp.load(sms); g = {}
        for f in frags: g.setdefault(_cell(pos.get(f["id"])), []).append(f["id"])
        IDX.update(t=time.time(), w=cs.WRITES[0], byid={f["id"]: f for f in frags}, rev=ce.rev_index(frags), pos=pos, grid=g)
    return IDX
def nbrs(fid, ix):
    f = ix["byid"][fid]
    o = [(n, w) for n, rel, w in ce.adj(f, ix["rev"]) if n in ix["byid"]]
    c = _cell(ix["pos"].get(fid))
    for cc in (_cells(c) if c else []): o += [(n, 0.5) for n in ix["grid"].get(cc, [])]
    return o
def dfs(store, seeds, depth=3, cap=1200, sms=None):
    ix = index(sms); byid, pos = ix["byid"], ix["pos"]; out, seen, used = [], set(), 0
    for s in [x for x in seeds if x in byid]:
        stack = [(0, s)]
        while stack and used < cap:
            d, fid = stack.pop()
            if fid in seen: continue
            f = byid[fid]; seen.add(fid); out.append((d, f)); used += len(f.get("text") or "") + 1
            if d >= depth: continue
            nb = sorted([(math.dist(pos.get(fid, [9, 9, 9]), pos.get(n, [9, 9, 9])) - w - 0.15 * min(byid[n].get("freq", 1), 10), n) for n, w in nbrs(fid, ix) if n not in seen])
            for _, n in nb[:BR]: stack.append((d + 1, n))
    return out
def seeds_for(text, k=3, sess=None, sms=None):
    ix = index(sms); qv = cs.vec(text); ISO = ("session", "skill_call", "tool_call", "subsession", "dialogue")
    fs = [f for f in ix["byid"].values() if not sess or f["chain"] not in ISO or not any(e[1] == "member" for e in f["edges"]) or any(e[0] == sess for e in f["edges"])]
    sc = sorted(((cs.cos(f["vec"], qv), f["id"]) for f in fs), reverse=True)
    return [i for s, i in sc[:k] if s > 0]
def block(res, store=None):
    o = ["%s[%s·%s·f%d·d%d] %s" % ("  " * d, f["id"], f["chain"], f.get("freq", 1), d, (f.get("text") or "")[:160]) for d, f in res]
    if store: [store.bump(f["id"]) for _, f in res]
    return "\n".join(o)
def expand(text, cap=1200, depth=3, sms=None, sess=None):
    store = cs.Store(sms or resolve_home.ensure()); sd = seeds_for(text, sess=sess, sms=sms); return block(dfs(store, sd, depth, cap, sms), store) if sd else "（暂无压缩记忆）"
if __name__ == "__main__":
    a = sys.argv[1:] or ["help"]; st = cs.Store(resolve_home.ensure())
    print(expand(" ".join(a[1:]), int(a[2]) if len(a) > 2 else 1200) if a[0] == "search" and len(a) > 1
          else block(dfs(st, [a[1]], int(a[2]) if len(a) > 2 else 3)) if a[0] == "seed" and len(a) > 1
          else __doc__.strip().splitlines()[-1])