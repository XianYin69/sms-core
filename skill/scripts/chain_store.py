#!/usr/bin/env python3
"""chain_store.py — 十一链（用户/记忆/逻辑/时间/事件/会话/调用skill/调用工具/subsession
派发对话（批23 对等·非子级）/对话/钉选knowledge）碎片存储层：每条链为 JSON 碎片（语句化/
最小化），含向量（64 维哈希投影，语句指向）、频次（使用计数）、边（语义/时间/因果/引用/
成员member，树形·神经网络型；ts＝ISO 字符串秒级）。数据 <SMS_HOME>/chains/<链>/<id>.json；
纯标准库、零依赖。
性能（2026-10-02 治 sms_shell 卡顿·规格 perf_spec.md·对外行为与中文文案零回归）：
- all_frags 枚举链目录时跳过以 "." 开头的目录（.git/.kilo/.cache 不再被当链扫）；
- FC 增量缓存升级为跨进程持久 <SMS_HOME>/chains/.cache/<链>.fcz（pickle·原子写·带版本号
  ＋链名校验），载入后按 scandir+stat 的 (size,mtime) 比对只重解析变化项，缺失/版本不符/
  损坏一律回退全量扫描并重建——SMS 每个工具调用新起 python 进程，进程内缓存等于每次冷读；
- 写路径 _wj 即时刷新 FC 并标脏，脏链在 all_frags 收口与进程退出时批量回写 .fcz；
- purge_dead 真删 dead 墓碑（merge_near/prune 只标不删→七成碎片是死档纯 IO 浪费），
  prune() 末尾串接，CLI `python -B chain_store.py purge`；
- merge_near 先按 text 精确分桶合并（O(N)）、再对代表元算 cos，跳过 dead，chain 为空时
  逐链限域（去全库两两 O(N²)）；
- _cof 的链名清单按 root mtime 缓存，不再每次 sorted(os.listdir)。
"""
import os, sys, json, re, time, math, pickle, atexit, hashlib, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chains_git, resolve_home, atomic_io

FC = {}      # path -> (size, mtime, frag)：增量缓存内存侧，由 .fcz 持久化（见 docstring）
WRITES = [0]  # 本进程写碎片计数：chain_dfs 三维索引据此即时失效（跨进程写由 TTL＋(size,mtime) 兜住）
DIRS = {}    # root -> (root mtime, [链名])：链目录清单缓存（跳过点目录）
DIRTY = {}   # root -> set(链名)：待回写 .fcz 的链
LOADED = set()  # (root, 链名)：本进程已载入过 .fcz，之后只信 FC＋(size,mtime)
CACHE_VER = 3   # .fcz 格式版本，不符即回退全量扫描并重建
DIRS_TTL = 1.0  # 链目录清单缓存上限（秒）：mtime 延迟兜底，跨进程新建链最迟 1s 可见


def _toks(s):
    s = s.lower()
    bg = [a + b for a, b in zip(s, s[1:])
          if "\u4e00" <= a <= "\u9fff" and "\u4e00" <= b <= "\u9fff"]
    return re.findall(r"[a-z0-9]+", s) + bg


def vec(t):
    ks = [int(hashlib.md5(x.encode()).hexdigest()[:8], 16) % 64 for x in set(_toks(t))]
    v = [float(ks.count(i)) for i in range(64)]
    n = math.sqrt(sum(q * q for q in v)) or 1.0
    return [round(q / n, 4) for q in v]


def cos(a, b): return sum(x * y for x, y in zip(a, b))


def _ld(p): return atomic_io.rjson(p, encoding="utf-8")


def _atomic_bin(path, obj):
    """pickle 原子写：与 atomic_io.wjson 同套（进程内锁＋同目录临时文件＋os.replace 重试）。"""
    d = os.path.dirname(os.path.abspath(path)); os.makedirs(d, exist_ok=True)
    t = path + ".tmp%d" % (threading.get_ident() % 100000)
    with atomic_io.LK:
        with open(t, "wb") as f: pickle.dump(obj, f, protocol=4)
        for a in range(8):
            try: os.replace(t, path); return
            except PermissionError:
                if a == 7: raise
                time.sleep(0.03)


def _cp(root, chain): return os.path.join(root, ".cache", chain + ".fcz")


def _ensure_ignore(root):
    """链目录由 chains_git 以 `git add -A` 归档，故 .cache/ 必须 ignore（幂等·缺失才补）。"""
    p = os.path.join(root, ".gitignore")
    t = None
    try:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f: t = f.read()
    except Exception: t = None
    if t is None: body = ".cache/\n"
    elif ".cache/" in t: return
    else: body = ("" if t.endswith("\n") else "\n") + ".cache/\n"
    try:
        with open(p, "a" if t else "w", encoding="utf-8") as f: f.write(body)
    except Exception: pass

def _cache_load(root, chain):
    """读 .fcz：缺失/损坏/版本不符/链名不符 → None（调用方回退全量扫描并重建）。"""
    try:
        with open(_cp(root, chain), "rb") as f: doc = pickle.load(f)
    except Exception: return None
    if not isinstance(doc, dict): return None
    if doc.get("ver") != CACHE_VER or doc.get("chain") != chain: return None
    ent = doc.get("entries")
    return ent if isinstance(ent, dict) else None


def _cache_save(root, chain):
    _ensure_ignore(root)
    pre = os.path.join(root, chain) + os.sep
    ent = {p: v for p, v in FC.items() if p.startswith(pre)}
    try: _atomic_bin(_cp(root, chain), {"ver": CACHE_VER, "chain": chain, "entries": ent})
    except Exception: pass


def _mark(root, chain): DIRTY.setdefault(root, set()).add(chain)


def _cache_flush(root):
    for c in sorted(DIRTY.pop(root, set()) or []): _cache_save(root, c)


def _flush_at_exit():
    for root in list(DIRTY): _cache_flush(root)

atexit.register(_flush_at_exit)


def _wj(p, d):
    """写碎片：落盘＋即时刷新 FC（本进程读侧零重解析）＋标脏该链 .fcz（收口/退出时批量回写）。"""
    atomic_io.wjson(p, d); st = os.stat(p); FC[p] = (st.st_size, st.st_mtime, d)
    _mark(os.path.dirname(os.path.dirname(p)), os.path.basename(os.path.dirname(p)))
    chains_git.touch()
    # 2026-10-15：写碎片后作废 prompt_pack._hits_cache（5s TTL 内的 32K cos 结果）。
    # 读写同进程时（bump/merge/prune/对话收口）不作废＝写后立刻读到过期召回。
    # 惰性 import：避免 chain_store 与 prompt_pack 循环导入（prompt_pack import chain_store）。
    try:
        import prompt_pack; prompt_pack._hits_invalidate()
    except Exception: pass


def _frag(e):
    st = e.stat(); c = FC.get(e.path)
    if c and c[0] == st.st_size and c[1] == st.st_mtime: return c[2]
    try: d = _ld(e.path)
    except Exception: d = None
    if d is not None: FC[e.path] = (st.st_size, st.st_mtime, d)
    return d


class Store:
    def __init__(self, sms):
        self.root = os.path.join(sms, "chains"); chains_git.ensure(self.root)
        self.cc = (resolve_home.conf(sms).get("chains") or {})

    def _p(self, c, fid): return os.path.join(self.root, c, fid + ".json")

    def _chain_dirs(self):
        """链目录清单：跳过以 "." 开头的目录（.git/.kilo/.cache），按 root mtime 缓存。

        NTFS 上父目录 mtime 更新有延迟（新建链目录后可能瞬时未变），故 mtime 之外再加 TTL
        兜底；本进程 add() 建目录后显式作废（_dirs_invalidate），避免新链被漏扫。
        """
        try: rk = os.stat(self.root).st_mtime
        except OSError: return []
        e = DIRS.get(self.root)
        if e and e[0] == rk and time.time() - e[2] < DIRS_TTL: return e[1]
        ls = sorted(d for d in os.listdir(self.root)
                    if not d.startswith(".") and os.path.isdir(os.path.join(self.root, d)))
        DIRS[self.root] = (rk, ls, time.time()); return ls

    def _dirs_invalidate(self): DIRS.pop(self.root, None)

    def _cof(self, fid):
        return next((c for c in self._chain_dirs() if os.path.exists(self._p(c, fid))), None)


    def _sync(self, c):
        """增量刷新该链 FC，返回 scandir 顺序 [(path, frag)]：只重解析 (size,mtime) 变化项。"""
        d = os.path.join(self.root, c); key = (self.root, c)
        if key in LOADED: ent = {}
        else:
            ent = _cache_load(self.root, c) or {}
            LOADED.add(key)
            if not ent: _mark(self.root, c)
        seen = set(); out = []
        try: it = list(os.scandir(d))
        except OSError: it = []
        for e in it:
            if not e.name.endswith(".json"): continue
            p = e.path; seen.add(p)
            try: st = e.stat()
            except OSError: continue
            v = FC.get(p) or ent.get(p)
            if v and v[0] == st.st_size and v[1] == st.st_mtime:
                FC[p] = v; out.append((p, v[2])); continue
            try: f = _ld(p)
            except Exception: f = None
            if f is not None:
                FC[p] = (st.st_size, st.st_mtime, f); out.append((p, f)); _mark(self.root, c)
        for p in [k for k in list(ent) if k not in seen]: ent.pop(p)
        gone = [k for k in list(FC) if k.startswith(d + os.sep) and k not in seen]
        for p in gone: FC.pop(p, None)
        if gone: _mark(self.root, c)
        return out


    def all_frags(self, chain=None):
        out = []
        for c in ([chain] if chain else self._chain_dirs()):
            if not os.path.isdir(os.path.join(self.root, c)): continue
            out += [f for p, f in self._sync(c) if f]
        _cache_flush(self.root)
        return out

    def add(self, chain, text, edges=None):
        if self.cc.get(chain, {}).get("enabled") is False:
            return "ERR 链已停用：" + chain + "（:config set chains." + chain + ".enabled true 恢复）"
        fid = hashlib.md5((chain + text + str(time.time())).encode()).hexdigest()[:10]
        os.makedirs(os.path.join(self.root, chain), exist_ok=True); self._dirs_invalidate()
        _wj(self._p(chain, fid), {"id": fid, "chain": chain,
                                  "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                  "text": text.strip(), "vec": vec(text), "freq": 1,
                                  "edges": [[e[0], e[1], e[2] if len(e) > 2 else 1.0]
                                            for e in edges or []]})
        return fid


    def bump(self, fid):
        if c := self._cof(fid):
            d = _ld(self._p(c, fid)); d["freq"] += 1; _wj(self._p(c, fid), d)
        return bool(c)

    def remove(self, fid):
        c = self._cof(fid)
        if not c: return None
        p = self._p(c, fid); os.remove(p); FC.pop(p, None); _mark(self.root, c)
        chains_git.touch(); return True

    def link(self, a, b, rel="semantic", w=1.0):
        if c := self._cof(a):
            d = _ld(self._p(c, a))
            d["edges"].append([b, rel if self._cof(b) else "ref", round(w, 3)])
            _wj(self._p(c, a), d)


    def _merge_chain(self, c, thr):
        """单链去重：先按 text 精确分桶合并（O(N)），再对代表元算 cos（R≪N）；跳过 dead。"""
        fs = [f for p, f in self._sync(c) if f and not f.get("dead")]
        buckets = {}; reps = []; n = 0
        for f in fs: buckets.setdefault(str(f.get("text", "")), []).append(f)
        for g in buckets.values():
            a = g[0]
            for b in g[1:]:
                a["freq"] = a.get("freq", 1) + b.get("freq", 1)
                a["edges"] = a.get("edges", []) + b.get("edges", [])
                b["dead"] = True; _wj(self._p(b["chain"], b["id"]), b); n += 1
            if len(g) > 1: _wj(self._p(a["chain"], a["id"]), a)
            reps.append(a)
        live = []
        for a in reps:
            if a.get("dead"): continue
            lim = self.cc.get(a["chain"], {}).get("merge_thr", thr)
            for b in live:
                if cos(a["vec"], b["vec"]) < lim: continue
                b["freq"] = b.get("freq", 1) + a.get("freq", 1)
                b["edges"] = b.get("edges", []) + a.get("edges", [])
                a["dead"] = True; _wj(self._p(a["chain"], a["id"]), a); n += 1; break
            if not a.get("dead"): live.append(a)
        _cache_flush(self.root)
        return n

    def merge_near(self, chain=None, thr=0.92):
        """近义合并：chain 指定则单链；为空则逐链调用（禁止全库两两 O(N²)）。"""
        if chain: return self._merge_chain(chain, thr)
        return sum(self._merge_chain(c, thr) for c in self._chain_dirs())


    def purge_dead(self, min_age_s=60):
        """真删 dead 墓碑文件（默认只删 min_age_s 前的，避开在途读者）并失效 FC/.cache。"""
        now = time.time(); n = 0; touched = set()
        for c in self._chain_dirs():
            for p, f in self._sync(c):
                if not f or not f.get("dead"): continue
                try:
                    if now - os.stat(p).st_mtime < min_age_s: continue
                    os.remove(p)
                except OSError: continue
                FC.pop(p, None); touched.add(c); n += 1
        for c in touched: _mark(self.root, c)
        _cache_flush(self.root)
        if n: chains_git.touch()
        return n

    def prune(self, days=14, min_freq=1):
        def cut(o):
            return time.strftime("%Y-%m-%d",
                                 time.localtime(time.time() - o.get("prune_days", days) * 86400))
        dead = []
        for f in self.all_frags():
            if f["chain"] == "knowledge": continue
            ch = self.cc.get(f["chain"], {})
            if f["ts"][:10] >= cut(ch): continue
            if f.get("freq", 1) > ch.get("min_freq", min_freq): continue
            _wj(self._p(f["chain"], f["id"]), dict(f, dead=True, pruned=cut(ch)))
            dead.append(1)
        self.purge_dead()
        return len(dead)


if __name__ == "__main__":
    a = sys.argv[1:] or ["help"]; st = Store(resolve_home.ensure())
    if a[0] == "purge": print("PURGED %d" % st.purge_dead(int(a[1]) if len(a) > 1 else 60))
    elif a[0] == "merge": print("MERGED %d" % st.merge_near(a[1] if len(a) > 1 else None))
    elif a[0] == "prune": print("PRUNED %d" % st.prune())
    else: print("用法：python -B chain_store.py purge [min_age_s]|merge [链]|prune")
