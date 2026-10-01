#!/usr/bin/env python3
"""agent_tools3.py — 模型直读写链与辩论工具（批17·相信大模型：链＝省 token 的记忆介质，经验由模型经本模块直接读写，不经脚本裁决）：chain(op=recall|append|stats, chain=链名|all, query/text, to, rel)——recall＝向量余弦＋频次检索（与 prompt_pack 同口径，可限单链），append＝把一条结论/经验语句化写入链（收口链会话中经 chain_timing 缓冲、收口落盘），stats＝各链计数；debate(claim, pro[], con[])——正反双辩论链（Skill_Generator 辩论思想入 SMS）：铺 pro/con 双链＋verdict 落 <SMS_HOME>/sessions/<日期>/debate_log.jsonl 并记 logic 链，裁决参考归模型。每笔经 msg_flow 信封留账。用法：python -B agent_tools3.py chain recall <链> "<查询>" | chain append <链> "<语句>" | debate "<论断>" --pro A --pro B --con C"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chains, chain_store as cs, agent_tools as at
SMS = chains.resolve_home.ensure()
def chain(op="recall", chain="all", query="", text="", to="", rel="semantic"):
    if op == "append":
        if chain not in chains.CHAINS: return "未知链：" + chain + "（候选：" + "、".join(chains.CHAINS) + "）"
        fid = chains.record(chain, str(text), [[to, rel, 1.0]] if to else None)
        at.emit("step", "链已记 " + chain + " " + str(fid)[:14], tool="chain")
        if str(fid).startswith("buf-"): return "已缓冲 " + chain + " 链（收口链·对话收口时落盘换真 id，暂持 " + str(fid) + " 勿作持久引用）"
        return ("已写入 " + chain + " 链 " + str(fid)) if fid and not str(fid).startswith("ERR") else str(fid)
    st = cs.Store(SMS); qv = cs.vec(str(query))
    if op == "stats":
        c = {}
        for f in st.all_frags(): c[f["chain"]] = c.get(f["chain"], 0) + 1
        at.emit("step", "链统计 " + str(len(c)) + " 链", tool="chain"); return "链碎片：" + "、".join("%s=%d" % (k, v) for k, v in sorted(c.items()))
    frags = st.all_frags() if chain == "all" else (st.all_frags(chain) if chain in chains.CHAINS else None)
    if frags is None: return "未知链：" + chain + "（候选：" + "、".join(chains.CHAINS) + "）"
    out = sorted(((cs.cos(f["vec"], qv) + 0.1 * min(f.get("freq", 1), 10), f) for f in frags if not f.get("dead") and cs.cos(f["vec"], qv) > 0.02), reverse=True, key=lambda x: x[0])[:8]
    for sc, f in out: st.bump(f["id"])
    r = "\n".join("[%s·%s·f%d·%.2f] %s" % (f["chain"], f["id"], f.get("freq", 1) + 1, sc, f["text"][:160]) for _, f in out)
    at.emit("step", "链检索 " + chain + " 命中 " + str(len(out)), tool="chain"); return r or "（无相关链碎片——可 chain append 记录新经验）"
def debate(claim, pro=None, con=None):
    import debate as dv
    pro = list(pro or []); con = list(con or []); doc = dv.debate(str(claim), pro, con)
    d = os.path.join(SMS, "sessions", time.strftime("%Y-%m-%d")); os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "debate_log.jsonl"), "a", encoding="utf-8") as fh: fh.write(json.dumps(doc, ensure_ascii=False) + "\n")
    fid = chains.record("logic", "辩论:" + str(claim)[:80] + "→" + doc["verdict"] + "（正%d/反%d）" % (len(pro), len(con)))
    at.emit("step", "双链辩论 " + str(doc["verdict"]) + "（正%d反%d）" % (len(pro), len(con)), tool="debate")
    return "verdict=%s（正%d论据/反%d论据·仅供参考·裁决在你）已记逻辑链 %s → %s" % (doc["verdict"], len(pro), len(con), fid, "sessions/" + time.strftime("%Y-%m-%d") + "/debate_log.jsonl")
if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "debate": print(debate(a[1], [a[i + 1] for i, x in enumerate(a) if x == "--pro"], [a[i + 1] for i, x in enumerate(a) if x == "--con"]))
    elif a and a[0] == "chain": print(chain(*(a[1:3] + a[3:4] + a[4:5])))
    else: print(__doc__.strip().splitlines()[1][:300])
