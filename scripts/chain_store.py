#!/usr/bin/env python3
"""chain_store.py — 十一链（用户/记忆/逻辑/时间/事件/会话/调用skill/调用工具/subsession 派发对话（批23 对等·非子级）/对话/钉选knowledge）碎片存储层：每条链为 JSON 碎片（语句化/最小化），含向量（64 维哈希投影，语句指向）、频次（使用计数）、边（语义/时间/因果/引用/成员member，树形·神经网络型；ts＝ISO 字符串秒级）。数据 <SMS_HOME>/chains/<链>/<id>.json；纯标准库、零依赖。性能（2026-09-26 治「每句全量读盘 1-2s」）：all_frags 经 FC 按 (size,mtime) 增量缓存——scandir 目录遍历仅 stat 比对，改动文件才重新解析 JSON，未变文件复用缓存对象；写路径 _wj 同步刷新缓存，跨进程改动由 mtime 失效自动兜住。"""
import os, sys, json, re, time, math, hashlib; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import chains_git, resolve_home, atomic_io
FC = {}  # path -> (size, mtime, frag)：all_frags 增量缓存，见 docstring
WRITES = [0]  # 本进程写碎片计数：chain_dfs 三维索引据此即时失效（跨进程写由 TTL＋(size,mtime) 兜住）
def _toks(s):
    s = s.lower(); return re.findall(r"[a-z0-9]+", s) + [a + b for a, b in zip(s, s[1:]) if "\u4e00" <= a <= "\u9fff" and "\u4e00" <= b <= "\u9fff"]
def vec(t):
    ks = [int(hashlib.md5(x.encode()).hexdigest()[:8], 16) % 64 for x in set(_toks(t))]
    v = [float(ks.count(i)) for i in range(64)]; n = math.sqrt(sum(q * q for q in v)) or 1.0; return [round(q / n, 4) for q in v]
def cos(a, b): return sum(x * y for x, y in zip(a, b))
def _ld(p): return atomic_io.rjson(p, encoding="utf-8")
def _wj(p, d):
    atomic_io.wjson(p, d); st = os.stat(p); FC[p] = (st.st_size, st.st_mtime, d); chains_git.touch()
def _frag(e):
    st = e.stat(); c = FC.get(e.path)
    if c and c[0] == st.st_size and c[1] == st.st_mtime: return c[2]
    try: d = _ld(e.path)
    except Exception: d = None
    if d is not None: FC[e.path] = (st.st_size, st.st_mtime, d)
    return d
class Store:
    def __init__(self, sms): self.root = os.path.join(sms, "chains"); chains_git.ensure(self.root); self.cc = (resolve_home.conf(sms).get("chains") or {})
    def _p(self, c, fid): return os.path.join(self.root, c, fid + ".json")
    def _cof(self, fid): return next((c for c in (sorted(os.listdir(self.root)) if os.path.isdir(self.root) else []) if os.path.exists(self._p(c, fid))), None)
    def add(self, chain, text, edges=None):
        if self.cc.get(chain, {}).get("enabled") is False: return "ERR 链已停用：" + chain + "（:config set chains." + chain + ".enabled true 恢复）"
        fid = hashlib.md5((chain + text + str(time.time())).encode()).hexdigest()[:10]; os.makedirs(os.path.join(self.root, chain), exist_ok=True)
        _wj(self._p(chain, fid), {"id": fid, "chain": chain, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "text": text.strip(), "vec": vec(text), "freq": 1, "edges": [[e[0], e[1], e[2] if len(e) > 2 else 1.0] for e in edges or []]})
        return fid
    def all_frags(self, chain=None):
        return [f for c in ([chain] if chain else (sorted(os.listdir(self.root)) if os.path.isdir(self.root) else [])) for d in (os.path.join(self.root, c),) if os.path.isdir(d) for e in os.scandir(d) if e.name.endswith(".json") and (f := _frag(e))]
    def bump(self, fid):
        if c := self._cof(fid): d = _ld(self._p(c, fid)); d["freq"] += 1; _wj(self._p(c, fid), d)
        return bool(c)
    def remove(self, fid):
        return next((os.remove(self._p(c, fid)) or FC.pop(self._p(c, fid), None) or chains_git.touch() or True for c in (self._cof(fid),) if c), None)
    def link(self, a, b, rel="semantic", w=1.0):
        if c := self._cof(a): d = _ld(self._p(c, a)); d["edges"].append([b, rel if self._cof(b) else "ref", round(w, 3)]); _wj(self._p(c, a), d)
    def merge_near(self, chain=None, thr=0.92):
        fs = self.all_frags(chain); n = 0
        for i, a in enumerate(fs):
            for b in fs[i + 1:]:
                if (a.get("dead") or b.get("dead")) or not (a["text"] == b["text"] or cos(a["vec"], b["vec"]) >= self.cc.get(a["chain"], {}).get("merge_thr", thr)): continue
                a["freq"] += b.get("freq", 1); a["edges"] += b.get("edges", []); b["dead"] = True; _wj(self._p(a["chain"], a["id"]), a); _wj(self._p(b["chain"], b["id"]), b); n += 1
        return n
    def prune(self, days=14, min_freq=1):
        cut = lambda o: time.strftime("%Y-%m-%d", time.localtime(time.time() - o.get("prune_days", days) * 86400))
        dead = [(self._wj(self._p(f["chain"], f["id"]), dict(f, dead=True, pruned=cut(self.cc.get(f["chain"], {})))) or 1) for f in self.all_frags() if f["chain"] != "knowledge" and f["ts"][:10] < cut(self.cc.get(f["chain"], {})) and f.get("freq", 1) <= self.cc.get(f["chain"], {}).get("min_freq", min_freq)]
        return len(dead)
