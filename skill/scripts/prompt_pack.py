#!/usr/bin/env python3
"""prompt_pack.py — 提示词四操作：split 拆分（按句碎片化）/ simplify 简化（打分取要）/ merge 合并（近义去重并频）/ pack 压缩检索（向量余弦＋频次＋一跳语义邻域，语句化输出 ≤max_chars 的发送大模型记忆块）。pack() 供 agent_stream 每次输入前置注入；命中碎片自动加频次。"""
import os, sys, re, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chain_store as cs, resolve_home, chain_dfs
STOP = re.compile(r"[。！？；;.\n]")
KEY = re.compile(r"\d|意图|决定|结论|红线|钉选|偏好|待办")
def split(text): return [s.strip() for s in STOP.split(text) if len(s.strip()) > 4]
def simplify(text, keep=0.4):
    s = split(text)
    idx = sorted(range(len(s)), key=lambda i: (0 if KEY.search(s[i]) else 1, -len(s[i])))
    return "\n".join(s[i] for i in sorted(idx[:max(1, int(len(s) * keep))])) if s else ""
def merge(sms, chain): return cs.Store(sms).merge_near(chain)
ISO = ("session", "skill_call", "tool_call", "subsession", "dialogue")
_hits_cache = {"t": 0.0, "key": None, "val": []}
_HITS_TTL = 5.0  # 秒：召回结果缓存（文本+session 双键·写碎片后由 _wj 侧作废——见下方 _invalidate）
def _hits_invalidate():
    """写碎片（chain_store._wj）后调用：本进程下一次 pack 不再重算 32K 条 cos（写入频率远低于读）。
    由 chain_store._wj 在 _mark 时经此钩子通知——不额外扫 mtime（与 chain_dfs.IDX 同口径）。"""
    _hits_cache["t"] = 0.0
def _hits(store, qv, sess=None):
    """召回（向量余弦＋频次＋一跳语义邻域）。性能（2026-10-15 治 1.3s/轮卡顿）：
    ① 不再每轮 all_frags()——优先取 chain_dfs.index() 已缓存的 byid（同一份 frags·TTL 30s），
       只有在 IDX 未建时才回落 Store（首调用／force 后）；
    ② cos 只算一次（旧版在 filter 与 scoring 两处各算一遍＝32K×64×2 浮点·纯 Python≈1.3s）；
    ③ 结果按 (text, sess) 缓存 5s——同一轮内 chains.conversation 只调一次 pack，跨轮同文本复用。"""
    import chain_dfs
    key = (qv, sess)
    now = time.time()
    if _hits_cache["key"] == key and now - _hits_cache["t"] < _HITS_TTL:
        return _hits_cache["val"]
    # 优先复用 chain_dfs.index() 的缓存（同一份 frags，TTL 30s）
    ix = chain_dfs.index()
    if ix.get("byid"):
        frags = list(ix["byid"].values())
    else:
        frags = [f for f in store.all_frags() if not f.get("dead")]
    byid = {f["id"]: f for f in frags}
    # 单次 cos：filter 与 scoring 合并
    sc = []
    for f in frags:
        if f.get("dead"): continue
        if sess and f["chain"] in ISO and not any(e[1] == "member" for e in f["edges"]): continue
        if sess and f["chain"] in ISO and not any(e[0] == sess for e in f["edges"]): continue
        c = cs.cos(f["vec"], qv)
        if c <= 0: continue
        sc.append([c + 0.1 * min(f.get("freq", 1), 10), f["id"], f.get("freq", 1), f["text"]])
    # 一跳语义/因果邻接展开（同旧口径）
    for q in list(sc):
        f = byid.get(q[1])
        if not f: continue
        for e in f.get("edges") or []:
            if e[1] in ("semantic", "causal") and byid.get(e[0]):
                nb = byid[e[0]]
                sc.append([q[0] * 0.6, e[0], nb.get("freq", 1), nb["text"]])
    _hits_cache["key"] = key; _hits_cache["t"] = now; _hits_cache["val"] = sc
    return sc
def pack(text, max_chars=1200, sms=None, sess=None, keywords=None):
    try:
        # 关键词泛洪种子：用操作关键词做向量种子，命中相关记忆碎片，沿语义/因果边＋3D空间邻格做 BFS 深扩展
        q = keywords or text
        r = chain_dfs.expand(q, max_chars, 3, sms, sess)
        if r and r != "（暂无压缩记忆）": return r
    except Exception as e:
        import debug; debug.error("prompt_pack DFS fallback: " + str(e)[:200], sms)
    store = cs.Store(sms or resolve_home.ensure())
    qv = cs.vec(keywords or text)
    out, used, seen = [], 0, set()
    for sc, fid, fr, t in sorted(_hits(store, qv, sess), reverse=True):
        if fid in seen: continue
        seen.add(fid); store.bump(fid)
        if used + len(t) > max_chars: break
        out.append("[%s·f%d] %s" % (fid, fr, t)); used += len(t) + 1
    return "\n".join(out) or "（暂无压缩记忆）"
if __name__ == "__main__":
    a = sys.argv[1:]
    op = a[0] if a else ""
    print("\n".join(split(" ".join(a[1:]))) if op == "split" else simplify(" ".join(a[1:])) if op == "simplify"
          else "合并 %d 对近义碎片" % merge(resolve_home.ensure(), a[1] if len(a) > 1 else "memory") if op == "merge"
          else pack(" ".join(a[1:])) if op == "pack" else (print(__doc__.strip()), sys.exit(1))[0])
