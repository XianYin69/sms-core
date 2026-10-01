#!/usr/bin/env python3
"""chain_error.py — 错误记录链（第 12 链 error）：运行期错误语句化为原子 `err:<kind>:<src> <msg>`；kind＝tool（agent_dispatch 工具异常）/script（shell_core rc≠0·超时）/skill（skill_errors 每笔）/dream（做梦后台失败）/shell（壳生命周期）/gate（其余）。同 (kind,src,msg 前 60 字) 命中既有未修原子只 bump freq，并挂 ref/member 边到当前 conv/session；error 属在谈链（chain_timing.LIVE）即时落盘。做梦 dream_repair 以本链＋skill_errors 台账为修复依据，修好 resolve() 打 [已修]。用法：python -B chain_error.py record <kind> <src> "<msg>" | list [kind] | stats | resolve <id>"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chains, chain_store as cs
KINDS = ("tool", "script", "skill", "dream", "shell", "gate")
def _st(): return cs.Store(chains.resolve_home.ensure())
def find(kind, src, msg):
    pre = "err:%s:%s" % (kind, src); m = " ".join(str(msg).split())[:60]
    for f in _st().all_frags("error"):
        t = f.get("text") or ""
        if t.startswith(pre) and "[已修]" not in t and m and m in t[len(pre):][:len(m) + 5]: return f
    return None
def record(kind, src, msg, edges=None):
    kind = kind if kind in KINDS else "gate"; src = (str(src) or "unknown").replace(" ", "_")[:60]
    if not str(msg).strip(): return None
    if f := find(kind, src, msg): _st().bump(f["id"]); return f["id"]
    e = [[chains.ACTIVE["conv"] or chains.cur_sess(), "ref", 1.0], [chains.cur_sess(), "member", 1.0]] + list(edges or [])
    return _st().add("error", "err:%s:%s %s" % (kind, src, " ".join(str(msg).split())[:400]), e)
SELFFIX = ("参数缺失", "参数不匹配")
def selffix(text): return any(w in str(text)[:80] for w in SELFFIX)
def hook(kind, src, msg):
    try: record(kind, src, msg)
    except Exception: pass
    return None
FAILK = ("失败", "未知工具", "ERR ", "无托管技能", "已禁用")
def fail(kind, src, r):
    if isinstance(r, str) and any(k in r[:24] for k in FAILK): hook(kind, src, r[:200])
    return r
def open_frags(kind=None):
    fs = [f for f in _st().all_frags("error") if "[已修]" not in (f.get("text") or "")]
    return [f for f in fs if f["text"].count(":") > 1 and f["text"].split(":")[1] == kind] if kind else fs
def tally():
    d = {}
    for f in open_frags():
        k = f["text"].split(":")[1] if f["text"].count(":") > 1 else "?"; d[k] = d.get(k, 0) + f.get("freq", 1)
    return d
def resolve(fid):
    st = _st(); c = st._cof(fid)
    if not c: return "无此错误原子：" + str(fid)
    d = cs._ld(st._p(c, fid)); d["text"] += " [已修]"; cs._wj(st._p(c, fid), d); return "已标记修复 " + fid
def line(f): return "%s f%d %s" % (f["id"], f.get("freq", 1), f["text"][:150])
if __name__ == "__main__":
    a = sys.argv[1:] or ["stats"]
    print(json.dumps(tally(), ensure_ascii=False) if a[0] == "stats" else resolve(a[1]) if a[0] == "resolve" and len(a) > 1
          else record(a[1], a[2], " ".join(a[3:])) if a[0] == "record" and len(a) > 2
          else "\n".join(line(f) for f in open_frags(a[1] if len(a) > 1 else None)) or "（无未修错误原子）")