#!/usr/bin/env python3
"""msg_flow.py — 用户↔大模型↔客户端 JSON 传输信封（v1.1）：一笔输入/输出＝ {v,kind,ts,conv,sess,skill,tool,chain,ok,text,meta}——kind＝user_in/llm_out/tool/skill/task/step/notice/err/edit/sh/tts/reasoning；ts 恒 ISO 本地时间；conv/sess 对话与会话归属（隔离审计）；skill/tool/chain 记录技能名与工具链路径；meta 装进度（task done/total、edit 路径、sh 退出码…）。分类（2026-09-26 用户「按类型判断是否隐藏长信息」）——CLASS 把 kind 归入 body 正文（llm_out·永不折叠）/echo 回显（user_in）/alert 告警（err·不折叠）/status 状态（step/task·常显短行）/detail 明细（tool/skill/edit/sh·超长折叠进「详细细节」；reasoning＝模型思考过程恒进明细不出主输出）/quiet 静默（tts），FOLD 集合＋foldable() 供前端与 ps1 壳同口径分流。make() 产 dict、dumps() 产行、parse() 判信封（非信封返回 None，前端按原文渲染）、brief() 产人读一行（TUI/ps1 显示用，信封原样经 ev 回调交上层做进度/审计）。批7 共享判定 kindof()/visible()/blank()＝信封解析＋⧉技能▸ 派发对话剥前缀＋前缀反推三合一·剥前缀后空行不上屏不入库，HIDE 隐藏类（tool/edit/sh/step/task/reasoning）与派发对话过程行恒不进主输出——Textual split 与 readline/单发/GUI 门控同一口径。本模块零第三方依赖零链写（批27 增明细总线投递＝只 import detail_bus·失败静默）。"""
import json, time, re, os
KINDS = ("user_in", "llm_out", "tool", "skill", "task", "step", "notice", "err", "edit", "sh", "tts", "reasoning")
CLASS = {"llm_out": "body", "user_in": "echo", "err": "alert", "step": "status", "task": "status", "tts": "quiet",
         "tool": "detail", "skill": "detail", "edit": "detail", "sh": "detail", "notice": "body", "reasoning": "detail"}
FOLD = frozenset(k for k, c in CLASS.items() if c == "detail")
def cls(kind): return CLASS.get(kind, "detail")
def foldable(kind): return kind in FOLD
SUB = re.compile(r"^(?:⧉[^\s▸]*▸\s*)+")
PRE = (("$ ", "tool"), ("▸ ", "step"), ("⧉", "skill"), ("! ", "sh"), ("≡", "task"), ("✎ ", "edit"), ("♪ ", "tts"), ("✗ ", "err"), ("• ", "notice"), ("◌ ", "reasoning"))
HIDE = frozenset(("tool", "edit", "sh", "step", "task", "reasoning"))
def kindof(t):
    t = str(t)
    if (e := parse(t)): return e.get("kind"), False
    m = SUB.match(t); base = t[m.end():] if m else t
    return next((k for p, k in PRE if base.startswith(p)), "llm_out"), bool(m)
def blank(t):
    t = str(t); m = SUB.match(t); return not (t[m.end():] if m else t).strip()
def fmt(s): s = max(0, int(s or 0)); return ("约剩 %dm%02ds" % divmod(s, 60)) if s >= 60 else ("约剩 %ds" % s)
def visible(t):
    if blank(t): return False
    k, sub = kindof(t); return not (k in HIDE or (k == "skill" and not sub))
BUS = frozenset(("tool", "skill", "edit", "sh", "step", "task", "reasoning", "err"))
_ON = [None]
def _bus_on():
    """shell.detail_bus 开关（默认开）：关掉＝各会话只记自己的明细，主壳 F9 不再合并他会话行。""" 
    if _ON[0] is None:
        try:
            import settings; _ON[0] = bool(settings.get("shell.detail_bus", True))
        except Exception: _ON[0] = True
    return _ON[0]
def publish(e):
    """明细行投跨会话总线（批27·env SMS_DETAIL_BUS=0 可关）：任何会话的推导/工具/命令行输出都汇进主壳 F9。"""
    try:
        if e.get("kind") in BUS and os.environ.get("SMS_DETAIL_BUS", "1") != "0" and _bus_on():
            import detail_bus; detail_bus.publish(e.get("sess") or "", e.get("conv") or "", e.get("kind"), e.get("text"))
    except Exception: pass
    return e
def _own(k):
    """缺 conv/sess 时按当前线程归属补齐（批27）：gateway 的过程行不经 agent_tools.emit 直接 make()，
    留空会让主壳把**本会话**的行误当「其他会话」重复并入 F9——故回落 chains（线程本地）＋env 真值；
    只读不建（绝不调 cur_sess()，避免脚本侧顺手新建 session 的副作用）。"""
    try:
        import chains
        v = chains.ACTIVE.get(k) or ""
        return v or (os.environ.get("SMS_SESSION") if k == "sess" else "") or ""
    except Exception:
        return ""
def make(kind, text, conv="", sess="", skill="", tool="", chain=(), ok=None, meta=None):
    return publish({"v": 1, "kind": kind if kind in KINDS else "notice", "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "conv": conv or _own("conv"), "sess": sess or _own("sess"), "skill": skill, "tool": tool, "chain": list(chain),
            "ok": ok, "text": str(text), "meta": dict(meta or {})})
def dumps(e): return json.dumps(e, ensure_ascii=False, default=str)
def parse(s):
    s = str(s).strip()
    if not (s.startswith("{") and '"v": 1' in s[:24]): return None
    try: e = json.loads(s)
    except Exception: return None
    return e if isinstance(e, dict) and e.get("v") == 1 and e.get("kind") in KINDS else None
def brief(e, jsonline=False):
    if jsonline: return dumps(e)
    m = e.get("meta") or {}; tag = {"task": "≡ %s %s/%s%s" % (e.get("skill") or e.get("tool"), m.get("done", 0), m.get("total", 0), (" ▸" + fmt(m["eta_s"])) if m.get("eta_s") else "")}.get(e["kind"])
    if not tag:
        head = {"user_in": "✎ ", "llm_out": "", "tool": "$ ", "skill": "⧉ ", "step": "▸ ", "notice": "• ", "err": "✗ ", "edit": "✎ ", "sh": "! ", "tts": "♪ ", "reasoning": "◌ "}.get(e["kind"], "")
        bits = [x for x in ((("技能:" + e["skill"]) if e.get("skill") else ""), (("工具:" + e["tool"]) if e.get("tool") else "")) if x]
        tag = head + (("〔" + "→".join(bits) + "〕") if bits else "") + str(e.get("text") or "")
    pre = "" if e.get("ok") is not False else "失败 "
    return tag if not (e.get("ts") and jsonline) else tag
