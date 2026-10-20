#!/usr/bin/env python3
"""ctx_compress.py — 实时上下文压缩（轻量并行版，前台零阻塞）：
基于搜索引用设计：以 chain_dfs 泛洪命中集作为引用集，命中＝保留（无损局部去重），
未命中＝不进入上下文文本（语义上抛弃无用信息，不物理删除避免全量 IO）。
不全量 all_frags，不全库 merge_near，不滑动窗口；后台线程运行，60s 内节流避免重复触发。
"""
import os, sys, time, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, chain_store as cs, chain_dfs, chain_error

_THROTTLE_S = 60
_KEEP_TOP = 40
_last = {}

def _throttled(sms):
    now = time.time()
    if now - _last.get(sms, 0) < _THROTTLE_S:
        return True
    _last[sms] = now
    return False

def compress(sms, ref_text, cap=4000):
    if _throttled(sms):
        return {"merged": 0, "dropped": 0, "kept": 0, "ref_ids": 0, "text": "", "throttled": True}
    store = cs.Store(sms)
    ref_ids = set()
    hits = []
    try:
        sd = chain_dfs.seeds_for(ref_text, k=5, sms=sms)
        hits = chain_dfs.dfs(store, sd, depth=2, cap=cap, sms=sms)
        for d, f in hits:
            ref_ids.add(f["id"])
    except Exception as e:
        chain_error.hook("ctx_compress", "dfs", str(e)[:160])
        hits = []
    # 无损：命中集内按文本去重（内存级，不落盘，不全库 merge_near）
    seen_text = set()
    merged = 0
    uniq = []
    for d, f in hits:
        t = f.get("text", "")
        if t in seen_text:
            merged += 1
            continue
        seen_text.add(t)
        uniq.append(f)
    # 有损：未被引用的不进入上下文文本（语义抛弃，不物理删除避免全量 IO）
    kept = [f for f in uniq if not f.get("dead")]
    kept.sort(key=lambda f: -f.get("freq", 1))
    ctx = "\n".join("[%s·f%d] %s" % (f["id"], f.get("freq", 1), f["text"][:160]) for f in kept[:_KEEP_TOP])
    return {"merged": merged, "dropped": len(hits) - len(kept), "kept": len(kept), "ref_ids": len(ref_ids), "text": ctx}

def maybe(sms, ref_text, on_line=None, bg=True):
    def _run():
        try:
            r = compress(sms, ref_text)
            if r.get("throttled"):
                return
            if on_line:
                on_line("[ctx_compress] 去重%d·保留%d/引用%d·上下文%d条" % (r["merged"], r["kept"], r["ref_ids"], len(r["text"]) and r["text"].count("\n") + 1 or 0))
        except Exception as e:
            chain_error.hook("ctx_compress", "maybe", str(e)[:200])
    if bg:
        th = threading.Thread(target=_run, daemon=True, name="ctx-compress")
        th.start()
        return th
    _run(); return None

if __name__ == "__main__":
    import resolve_home as _rh
    sms = _rh.ensure(); ref = " ".join(sys.argv[1:]) or "任务"
    print(compress(sms, ref))
