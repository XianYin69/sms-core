#!/usr/bin/env python3
"""qq_chunk.py — QQ 出站分段器（2026-09-29 用户「修吞字：push 折叠换行＋[:max_len] 一刀切是根因」）：split(text,cap) **保留换行**按行装箱，仅单行超 cap 才硬切，绝不静默丢字；cap_for(c,tag)＝max_len 扣掉〔tag〕信封位，防标签把正文挤出上限；send(c,text,tag,ep,mk) 逐段 POST——多段时 tag 自动加 ·i/n、段间守 min_gap（官方 5qps·30qpm 护栏），任一段 code≠0 即回 None 交调用方回落（qq_reply 被动失败→qq_push 主动推送）；qq_push.send 与 qq_reply.try_send 共用本模块，出站再无一刀切。用法：python -B qq_chunk.py split "<文本>" [cap] | selftest。"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
def cap_for(c, tag="SMS"): return max(40, int(c.get("max_len") or 500) - len(str(tag)) - 12)
def split(text, cap):
    cap = max(40, int(cap)); out = []
    for ln in str(text or "").splitlines() or [""]:
        while len(ln) > cap: out.append(ln[:cap]); ln = ln[cap:]
        if out and len(out[-1]) + len(ln) + 1 > cap: out.append(ln)
        elif out: out[-1] = out[-1] + "\n" + ln
        else: out.append(ln)
    return [x for x in out if x.strip()] or [str(text or "").strip()[:cap]]
def send(c, text, tag, ep, mk=None):
    import qq_push as qp
    segs = split(text, cap_for(c, tag)) or [str(text or "")[:cap_for(c, tag)]]
    mk = mk or (lambda t: {"msg_type": 0, "content": t}); n = len(segs); res = None
    for i, sg in enumerate(segs, 1):
        if i > 1: time.sleep(float(c.get("min_gap") or 2.0))
        res = qp._post(ep, mk(("〔%s·%d/%d〕%s" % (tag, i, n, sg)) if n > 1 else ("〔%s〕%s" % (tag, sg))), qp.token(c), c)
        if isinstance(res, dict) and int(res.get("code") or 0): return None
    return res
if __name__ == "__main__":
    a = sys.argv[1:] or ["help"]
    if a[0] == "split":
        g = split(" ".join(a[1:2]) or "行1\n行2", int(a[2]) if len(a) > 2 else 500)
        print("\n".join("%d/%d·%d字|%s" % (i, len(g), len(x), x[:36].replace("\n", "\\n")) for i, x in enumerate(g, 1)))
    elif a[0] == "selftest":
        long = "\n".join("第%d行：" % i + "内容" * 30 for i in range(1, 12))
        g = split(long, 200); back = "\n".join(g)
        print(json.dumps({"原字数": len(long), "行数": len(long.splitlines()), "段数": len(g), "还原等长": len(back) == len(long), "无丢字": back == long, "单行硬切": len(split("x" * 650, 200))}, ensure_ascii=False))
    else: print(__doc__.strip()[:300])
