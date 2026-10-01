#!/usr/bin/env python3
"""chains.py — 十一链＋error 错误记录链（第 12 链·在谈即时落盘）记录 API（用户/记忆/逻辑/时间/事件/会话/调用skill/调用工具/subsession 派发对话/对话/钉选knowledge）＋对话规则（红线 17·批23 对等对话：每次用户输入与每次技能派发＝各开一个独立 conv 独立链归属，对话间无主次、互任监视者·指导者·训诫者；输出停止＝形式收口非实质完成，dream 审计）＋会话层 sess（session＝多对话容器·新建会话＝新 session 非 conv，防跨会话污染：session/skill_call/tool_call/subsession/dialogue 碎片打 member→sess 边，prompt_pack 检索只收当前 sess；多壳并行以 env SMS_SESSION 各绑其 session；先后顺序与跨会话未完成冲突经 sessions_view 供对话监视；批29 session 提升为一等公民＝通道级容器（用户诉求「客户端/网页端/QQ 远程/计划任务/后台任务各占用一个 session；session 的查看/新建/切换不用通过大模型，直接通过脚本完成」）——kind∈client|web|qq|cron|bg|shell 各占一条，真源与读写＝session_reg.py，查看/新建/切换经 session_cli.py 零模型直达）；清单存 <SMS_HOME>/shell/sessions.json＋current_session；批17 读写时序分层——在谈链（user/logic/dialogue/session/skill_call/tool_call/subsession）会话中即写，收口链（memory/knowledge/time/event）对话中经 chain_timing 缓冲、收口统一落盘。用法：python -B chains.py <链> "<语句>" [--to <目标>] [--rel 关系] | session new [名]|list|use <id>|current|overview|conflicts | log <skill|tool|sub> "<名>" | list [链]"""
import os, sys, json, time, threading
_MT = threading.current_thread()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, chain_store, chain_timing
CHAINS = ("user", "memory", "logic", "time", "event", "session", "skill_call", "tool_call", "subsession", "dialogue", "knowledge", "error")
ISO = ("session", "skill_call", "tool_call", "subsession", "dialogue")
RULE = "对话规则（批23·对等对话）：本对话是独立对话——每次用户输入与每次技能派发各成一个独立 conv 与独立链归属，对话间无主次之分，只互相扮演监视者·指导者·训诫者；输出停止＝形式收口而非实质完成，任务完成只认〔任务表〕全部行 done 与用户诉求落地；本对话收口只结束自己：〔任务表〕仍有未完成行时由调度你的对话（或任何监视到它的对话）继续推进，禁止把单个派发完成当作整段任务结束；凡使用 agent 的 skill 必须另开对等对话执行并即时收口（红线17·防跨对话污染）；压缩记忆仅供背景引用；[当前输入·唯一指令] 只约束本对话；session＝多对话容器（新建会话＝新 session·conv 每输入/派发自动开收），话语带〔会话拓扑〕＝他 session 有未完成/冲突线索——负监视训诫之责：提示用户接续或收口，未经确认不越会话代改他人表；处理协议（批24）＝内部处理一律英语·语句精简，用户可见输出先英语成稿再译回用户语言。"
class _Active:
    """批27（用户「多个用户输入无需排队·全部并行处理」）＝conv/sess 归属由进程级单例改为**按线程隔离**：
    主线程读写基值（旧行为逐字不变），其他线程（并行 worker／task 子任务／QQ 与计划任务线程）首次访问时
    从基值 fork 出自己的副本，此后只动本线程——同进程并行跑多个输入时，A 的 conv 不再被 B 覆写
    （旧版 chains.ACTIVE["conv"]=... 是全局的，并行即串台：信封归属、任务表 pending、链 member 边全认错对话）。
    对外仍是 dict 口径：[]、get、update、clear、keys、items、in、dict(ACTIVE) 全支持（老调用点零改动）。"""
    __slots__ = ("_base", "_tl")
    def __init__(self):
        self._base = {"conv": "", "sess": ""}; self._tl = threading.local()
    def _d(self):
        if threading.current_thread() is _MT: return self._base
        d = getattr(self._tl, "d", None)
        if d is None: d = self._tl.d = dict(self._base)
        return d
    def __getitem__(self, k): return self._d()[k]
    def __setitem__(self, k, v): self._d()[k] = v
    def __delitem__(self, k): self._d().pop(k, None)
    def __contains__(self, k): return k in self._d()
    def __iter__(self): return iter(self._d())
    def __len__(self): return len(self._d())
    def __repr__(self): return repr(self._d())
    def get(self, k, default=None): return self._d().get(k, default)
    def update(self, m=(), **kw): self._d().update(dict(m), **kw)
    def clear(self): self._d().clear()
    def keys(self): return self._d().keys()
    def values(self): return self._d().values()
    def items(self): return self._d().items()
    def copy(self): return dict(self._d())
ACTIVE = _Active()
def store(): return chain_store.Store(resolve_home.ensure())
def record(chain, text, edges=None): return chain_timing.buffer(chain, text, edges) if chain in CHAINS and chain_timing.deferred(chain) else store().add(chain, text, edges) if chain in CHAINS else "ERR 未知链：" + chain + "（候选：" + "、".join(CHAINS) + "）"
_SEQ = [int.from_bytes(os.urandom(2), "big") & 0x3FF]  # 进程内随机起点：跨进程同毫秒也不易撞名
def session_id():
    """conv 全局唯一：秒＋毫秒＋进程内自增序号——同一秒连发多条消息各得独立 conv（session 下多 conv 的前提）。"""
    _SEQ[0] = (_SEQ[0] + 1) & 0xFFF
    return "conv-" + time.strftime("%Y%m%d-%H%M%S") + "-%03d%03d" % (time.time() * 1000 % 1000, _SEQ[0])
def _st(n): p = os.path.join(resolve_home.ensure(), "shell"); os.makedirs(p, exist_ok=True); return os.path.join(p, n)
def _smap():
    import atomic_io
    try: return atomic_io.rjson(_st("sessions.json"))
    except Exception: return {}
def cur_sess():
    if not ACTIVE["sess"]:
        try: ACTIVE["sess"] = os.environ.get("SMS_SESSION") or open(_st("current_session"), encoding="utf-8").read().strip()
        except Exception: ACTIVE["sess"] = ""
    if ACTIVE["sess"]: return ACTIVE["sess"]
    try:
        sid = __import__("session_reg").current()
        if sid: ACTIVE["sess"] = sid; return sid
    except Exception: pass
    return new_sess("默认会话")
def new_sess(name=""):
    sid = "sess-" + time.strftime("%Y%m%d-%H%M%S"); m = _smap(); m[sid] = {"created": time.strftime("%Y-%m-%d %H:%M:%S"), "name": (name or "").strip()[:40] or sid[5:], "kind": "shell", "key": sid, "pid": os.getpid(), "last_active": time.strftime("%Y-%m-%d %H:%M:%S"), "state": "active", "conv": ""}
    import atomic_io; atomic_io.wjson(_st("sessions.json"), m); open(_st("current_session"), "w", encoding="utf-8").write(sid)
    ACTIVE["sess"] = sid; record("session", "sess-new:" + sid + " " + m[sid]["name"]); return "已新建并切入会话（session）" + sid + "——新建会话＝新 session 非 conv·conv 每输入/派发自动开收（批23 对等对话）"
def use_sess(sid):
    if sid not in _smap(): return "无此会话：" + sid + "（session list 查看）"
    open(_st("current_session"), "w", encoding="utf-8").write(sid); ACTIVE["sess"] = sid; record("session", "sess-use:" + sid); return "已切换会话 " + sid
def list_sess():
    cur = cur_sess(); return "\n".join("%s %s｜%s%s" % (k, v.get("created", ""), v.get("name", ""), "（当前）" if k == cur else "") for k, v in sorted(_smap().items())) or "（暂无会话）"
def set_active(conv=None, sess=None): ACTIVE.update(({"conv": conv} if conv else {}) | ({"sess": sess} if sess else {}))
def conversation(text):
    import prompt_pack; h = __import__("sessions_view").hint(cur_sess())
    return "[压缩记忆]\n" + prompt_pack.pack(text, 1200, sess=cur_sess()) + "\n\n[" + RULE + "]" + ("\n\n〔会话拓扑〕" + h if h else "") + "\n\n[当前输入·唯一指令]\n" + text
def log(kind, name, conv=""):
    sid = conv or ACTIVE["conv"] or session_id()
    return record("skill_call" if kind == "skill" else "tool_call" if kind == "tool" else "subsession", name + "@" + sid, [[sid, "ref", 1], [cur_sess(), "member", 1]])
if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: print(__doc__.strip().splitlines()[1]); sys.exit(1)
    if a[0] == "session": import session_cli; print(session_cli.main(a[1:])); sys.exit(0)  # 单一口径＝session_cli（零模型脚本直达·旧子命令兼容）
    if a[0] == "log" and len(a) >= 3: print(log(a[1], a[2])); sys.exit(0)
    if a[0] == "list": print("\n".join("%s %s %s" % (f["id"], f["chain"], f["text"][:60]) for f in store().all_frags(a[1] if len(a) > 1 else None))); sys.exit(0)
    edges = [[a[a.index("--to") + 1], a[a.index("--rel") + 1] if "--rel" in a else "semantic"]] if "--to" in a else None
    fid = record(a[0], a[1]) if len(a) > 1 else None
    if fid and edges and not str(fid).startswith("ERR"): store().link(fid, edges[0][0], edges[0][1])
    print(fid if fid else "用法：chains.py <链> \"<语句>\" [--to t --rel r] | session new|list|use|current | list [链] | log <skill|tool|sub> <名>")
