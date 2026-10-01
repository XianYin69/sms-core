#!/usr/bin/env python3
"""dream_roam.py — 做梦网络漫游（批17：漫游拓扑十一链上的经验）：跑在后台做梦子进程内，不占对话前台——话题取 settings dream.roam_topics（空则从 user/dialogue 链高频近期语句提取）→ ff_lite 内核搜索 → 取未访问页经 learn.from_url 蒸馏入 knowledge/logic 链（与既有碎片经做梦合并连通）；须 :grant network（无授权跳过，绝不在做梦中途向用户要权限）；开关 dream.roam（默认开）、量控 dream.roam_pages（每轮取页上限·默认2）/dream.roam_keep（每页条数·默认4）；已访问 URL 累积 chains/roam_seen.json 防重游。用法：python -B dream_roam.py topics|roam"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, settings, permissions, chains, chain_store as cs, atomic_io
def topics(sms, k=2):
    t = settings.get("dream.roam_topics", [], sms=sms) or []
    if isinstance(t, str): t = [x for x in t.replace("，", ",").split(",") if x.strip()]
    if t: return [str(x)[:80] for x in t][:k]
    st = cs.Store(sms); seen, out = set(), []
    for f in sorted([f for f in st.all_frags("user") + st.all_frags("dialogue") if len(f["text"]) > 8], key=lambda f: -f.get("freq", 1)):
        w = f["text"].split(" ", 1)[-1].strip()[:80]
        if w and w not in seen: seen.add(w); out.append(w)
        if len(out) >= k: break
    return out
def _sp(sms): return os.path.join(sms, "chains", "roam_seen.json")
def _seen(sms):
    try: return set(atomic_io.rjson(_sp(sms), default=[]) or [])
    except Exception: return set()
def roam(sms, r=None):
    if not settings.get("dream.roam", True, sms=sms): return "off"
    if not permissions.allow(sms, "network"): return "no-network"
    import ff_lite, learn, dream_bg
    pages = max(1, int(settings.get("dream.roam_pages", 2, sms=sms))); keep = max(1, int(settings.get("dream.roam_keep", 4, sms=sms)))
    seen = _seen(sms); hit = 0
    for q in topics(sms, pages):
        dream_bg.stamp(sms)
        try: rows = json.loads(ff_lite.search(q, 5) or "[]")
        except Exception: continue
        u = next((str(x.get("url", "")) for x in rows if str(x.get("url", "")).startswith("http") and x["url"] not in seen), None)
        if not u: continue
        res = learn.from_url(u, keep=keep); hit += 1 if str(res).startswith("已学习") else 0
        if hit: seen.add(u)
    if hit:
        try: atomic_io.wjson(_sp(sms), sorted(seen)[-400:])
        except Exception: pass
        chains.record("event", "做梦漫游：取页%d 入链" % hit)
    return "roamed:%d" % hit
if __name__ == "__main__":
    sms = resolve_home.ensure()
    print(json.dumps(topics(sms), ensure_ascii=False) if len(sys.argv) > 1 and sys.argv[1] == "topics" else roam(sms))
