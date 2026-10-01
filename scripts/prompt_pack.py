#!/usr/bin/env python3
"""prompt_pack.py — 提示词四操作：split 拆分（按句碎片化）/ simplify 简化（打分取要）/ merge 合并（近义去重并频）/ pack 压缩检索（向量余弦＋频次＋一跳语义邻域，语句化输出 ≤max_chars 的发送大模型记忆块）。pack() 供 agent_stream 每次输入前置注入；命中碎片自动加频次。"""
import os, sys, re
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
def _hits(store, qv, sess=None):
    frags = [f for f in store.all_frags() if not f.get("dead") and (not sess or f["chain"] not in ISO
            or not any(e[1] == "member" for e in f["edges"]) or any(e[0] == sess for e in f["edges"]))]
    byid = {f["id"]: f for f in frags}
    sc = [[cs.cos(f["vec"], qv) + 0.1 * min(f["freq"], 10), f["id"], f["freq"], f["text"]] for f in frags if cs.cos(f["vec"], qv) > 0]
    for q in list(sc):
        for e in byid[q[1]]["edges"]:
            if e[1] in ("semantic", "causal") and byid.get(e[0]): sc.append([q[0] * 0.6, e[0], byid[e[0]]["freq"], byid[e[0]]["text"]])
    return sc
def pack(text, max_chars=1200, sms=None, sess=None):
    try:
        r = chain_dfs.expand(text, max_chars, 3, sms, sess)
        if r and r != "（暂无压缩记忆）": return r
    except Exception as e:
        import debug; debug.error("prompt_pack DFS fallback: " + str(e)[:200], sms)
    store = cs.Store(sms or resolve_home.ensure())
    out, used, seen = [], 0, set()
    for sc, fid, fr, t in sorted(_hits(store, cs.vec(text), sess), reverse=True):
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
