#!/usr/bin/env python3
"""learn.py — 学习脚本（联动十一链与做梦，resistance #17）：把网页（经 firefox lite 内核）或交互蒸馏成语句化知识碎片写入 knowledge/logic 链（含向量·频次·边），惰性触发做梦合并·修剪·重建检索·钉选。数据只入 <SMS_HOME>/chains/，禁止写 skill 目录。用法：python -B learn.py from-url <url> [--keep n] | note "<语句>" [--chain knowledge|logic] [--to id --rel 关系] | from-session [日期] | recall "<查询>" [--n] | distill [--sync] | stats。每次动作记 tool_call 链。"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, chain_store as cs, chains, prompt_pack, dream, ff_lite
SMS = resolve_home.ensure()
def note(text, chain="knowledge", to="", rel="semantic"):
    text = " ".join(str(text).split())
    if len(text) < 4: return "语句过短，未记录"
    fid = chains.record(chain, text, [[to, rel, 1.0]] if to else None)
    chains.log("tool", "learn:note:" + chain); dream.maybe(SMS); return fid
def _absorb(sents, tag):
    prev, n = None, 0
    for s in sents:
        fid = chains.record("knowledge", "%s %s" % (tag, s.strip()[:200]), [[prev, "causal", 0.8]] if prev else None)
        if fid and not str(fid).startswith("ERR"):
            prev = fid; n += 1
    chains.log("tool", "learn:absorb:%d" % n); dream.maybe(SMS); return n
def from_url(url, keep=6):
    body = ff_lite.fetch(url)
    if body.startswith("ERR") or body.startswith("DENIED"): return body
    scored = sorted(prompt_pack.split(body), key=lambda s: (len(prompt_pack.KEY.findall(s)), min(len(s), 40)), reverse=True)
    return "已学习 %d 条：%s → knowledge/logic 链" % (_absorb(scored[:keep], "网·%s" % url[:60]), url[:60])
def from_session(day=""):
    p = os.path.join(SMS, "sessions", day or time.strftime("%Y-%m-%d"), "dialogue.md")
    if not os.path.isfile(p): return "无会话对话文件：" + p
    n = _absorb(prompt_pack.split(prompt_pack.simplify(open(p, encoding="utf-8").read()))[:8], "会话")
    return "已从会话学习 %d 条" % n
def recall(q, n=6):
    st = cs.Store(SMS); qv = cs.vec(q); out = []
    for f in st.all_frags("knowledge") + st.all_frags("logic"):
        c = cs.cos(f.get("vec", []), qv)
        if c > 0.05: out.append((c + 0.1 * min(f.get("freq", 1), 10), f))
    out.sort(reverse=True, key=lambda x: x[0]); r = []
    for sc, f in out[:n]: st.bump(f["id"]); r.append("[%s·f%d·%.2f] %s" % (f["chain"], f.get("freq", 1) + 1, sc, f["text"][:160]))
    chains.log("tool", "learn:recall"); return "\n".join(r) or "（暂无可学习记忆）"
def stats():
    st = cs.Store(SMS); c = {}
    for f in st.all_frags(): c[f["chain"]] = c.get(f["chain"], 0) + 1
    return "链碎片：" + "、".join("%s=%d" % (k, v) for k, v in sorted(c.items())) + "　做梦到期：" + str(dream.due(SMS))
if __name__ == "__main__":
    a = sys.argv[1:] or ["stats"]; c = a[0]
    if c == "from-url" and len(a) > 1: print(from_url(a[1], int(a[3]) if len(a) > 3 and a[3].isdigit() else 6))
    elif c == "note" and len(a) > 1: print(note(" ".join(a[1:]).split("--chain")[0].split("--to")[0].split("--rel")[0], a[a.index("--chain") + 1] if "--chain" in a else "knowledge", a[a.index("--to") + 1] if "--to" in a else ""))
    elif c == "from-session": print(from_session(a[1] if len(a) > 1 and not a[1].startswith("--") else ""))
    elif c == "recall" and len(a) > 1: print(recall(" ".join(a[1:]).split("--n")[0], int(a[a.index("--n") + 1]) if "--n" in a else 6))
    elif c == "distill": print("做梦完成：" + str(dream.run(SMS)) if "--sync" in a else str(dream.maybe(SMS) and "spawned" or "未到期（--sync 立即做梦）"))
    else: print(stats())
