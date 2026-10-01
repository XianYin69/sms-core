#!/usr/bin/env python3
"""chain_space3d.py — 链→三维空间映射（2026-09-29 用户「把链映射到3维空间：链域、时间/次数域、长度域，每个链上的节点是这个空间里一个具体位置的原子，不同原子之间双向联系」）：每条链的碎片＝空间中一个原子，坐标＝
  X 链域＝链名在 chains.CHAINS 的序号（离散 12 槽，error 为第 12 槽）
  Y 时间/次数域＝log2(1+freq) ＋ 2·exp(-age_days/14)（近期高频者上移）
  Z 长度域＝log1p(len(text))（语句体量）
rebuild(sms) 全量重算并落 <SMS_HOME>/chains/space3d.json（id→[x,y,z]·带 ts/count）；pos(frag) 单原子坐标；
load(sms) 带 (size,mtime) 缓存读；near(fid,k) 三维欧氏近邻（做梦加强记忆与 DFS 取邻用）；
axes() 供顶栏/报告说明。双向边见 chain_edges.py，DFS 读取见 chain_dfs.py。
用法：python -B chain_space3d.py rebuild | pos <id> | near <id> [k] | axes"""

import os, sys, json, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chains, chain_store as cs, resolve_home, atomic_io
AX = ("链域X", "时间/次数域Y", "长度域Z")
def _slot(c):
    try: return float(chains.CHAINS.index(c))
    except Exception: return float(len(chains.CHAINS))
def _age_d(ts):
    try: return max(0.0, (time.time() - time.mktime(time.strptime(str(ts)[:19], "%Y-%m-%dT%H:%M:%S"))) / 86400.0)
    except Exception: return 365.0
def pos(f):
    return [_slot(f.get("chain", "")), round(math.log2(1 + (f.get("freq", 1) or 1)) + 2 * math.exp(-_age_d(f.get("ts", "")) / 14), 4),
            round(math.log1p(len(f.get("text") or "")), 4)]
def _p(sms): return os.path.join(sms, "chains", "space3d.json")
def rebuild(sms=None):
    sms = sms or resolve_home.ensure(); d = {f["id"]: pos(f) for f in cs.Store(sms).all_frags() if not f.get("dead")}
    atomic_io.wjson(_p(sms), {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "axes": list(AX), "n": len(d), "pos": d}); return d
def load(sms=None):
    d = atomic_io.rjson(_p(sms or resolve_home.ensure()), default=None) or {}
    return d.get("pos") or rebuild(sms)
def near(fid, k=6, sms=None):
    m = load(sms)
    if fid not in m: return []
    a = m[fid]; return sorted([(round(math.dist(a, b), 3), i) for i, b in m.items() if i != fid])[:k]
def axes(): return {"axes": list(AX), "slots": len(chains.CHAINS), "chains": list(chains.CHAINS)}
if __name__ == "__main__":
    a = sys.argv[1:] or ["axes"]; st = cs.Store(resolve_home.ensure())
    print(json.dumps(axes(), ensure_ascii=False) if a[0] == "axes" else json.dumps(rebuild(), ensure_ascii=False)[:300] if a[0] == "rebuild"
          else json.dumps(near(a[1], int(a[2]) if len(a) > 2 else 6), ensure_ascii=False) if a[0] == "near"
          else json.dumps(pos(next((f for f in st.all_frags() if f["id"] == a[1]), {"chain": "?", "text": ""})), ensure_ascii=False))