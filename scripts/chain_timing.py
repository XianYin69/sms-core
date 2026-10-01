#!/usr/bin/env python3
"""chain_timing.py — 十一链读写时序分层（批17·链＝省 token 的介质）：在谈链（user/logic/dialogue/session/skill_call/tool_call/subsession）会话中即读即写；收口链（memory/knowledge/time/event）会话中攒着——沉淀与拓扑类语句不中途落盘（省写盘/git 提交/检索噪音），对话收口统一 flush；缓冲假 id（buf-*）在 flush 时换真碎片 id，指向假 id 的边随迁。队列镜像 <SMS_HOME>/shell/deferred.json，壳进程崩溃后下轮对话开头自动重放。用法：python -B chain_timing.py status|flush"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, atomic_io
LIVE = ("user", "logic", "dialogue", "session", "skill_call", "tool_call", "subsession", "error")
CLOSING = ("memory", "knowledge", "time", "event")
Q = []
def _sp(): return os.path.join(resolve_home.ensure(), "shell", "deferred.json")
def in_conv():
    import chains; return bool(chains.ACTIVE["conv"])
def deferred(chain): return chain in CLOSING and in_conv()
def _save():
    try: os.makedirs(os.path.dirname(_sp()), exist_ok=True); atomic_io.wjson(_sp(), Q)
    except Exception: pass
def _load():
    global Q
    if not Q:
        try: Q = list(atomic_io.rjson(_sp(), default=[]) or [])
        except Exception: Q = []
    return Q
def buffer(chain, text, edges=None):
    _load(); fid = "buf-%d-%d" % (len(Q), int(time.time() * 1000) % 1000000)
    Q.append({"id": fid, "chain": chain, "text": " ".join(str(text).split()), "edges": [list(e) for e in edges or []]})
    _save(); return fid
def pending(): _load(); return len(Q)
def flush(store=None):
    _load(); n = 0
    if not Q: return 0
    if store is None: import chains; store = chains.store()
    while Q:
        op = Q.pop(0)
        edges = [[_REAL.get(e[0], e[0]), e[1], e[2] if len(e) > 2 else 1.0] for e in op["edges"] if not str(e[0]).startswith("buf-") or str(e[0]) in _REAL]
        fid = store.add(op["chain"], op["text"], edges)
        if fid and not str(fid).startswith("ERR"): _REAL[op["id"]] = str(fid); n += 1
    _REAL.clear(); _save(); return n
_REAL = {}
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "flush":
        import chains; print("已收口写入 %d 条缓冲碎片" % flush(chains.store()))
    else:
        _load(); print("在谈链＝" + "、".join(LIVE) + "\n收口链＝" + "、".join(CLOSING) + "\n缓冲待写＝%d 条（%s）" % (len(Q), _sp() if Q else "无"))
