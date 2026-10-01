#!/usr/bin/env python3
"""qq_brief.py — QQ 简洁模式开关（2026-09-29 用户「QQ 上别刷屏·简洁模式」）：状态借 agent_stream 的 state 机制落 <SMS_HOME>/shell/qq_brief（"1"＝开）——qq_inbound.deliver 在调 agent_stream.ask 前置位、结束/异常清掉；prompt_builder.build 读到即在提示追加「回复≤200字·要点直给·勿刷屏」；qq_flow.close 在 brief 生效时把收口正文限长 brief_len、超出以「…（余下见 SMS 壳）」收尾。本模块直接读写状态文件而不 import agent_stream（后者 import prompt_builder/qq_flow/qq_push·回环），凭据开关＝qq.json 的 brief/brief_len（qq_push.DEF 默认 true/260）。用法：python -B qq_brief.py on|off|state|cap "<文本>"。"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qq_push as qp
KEY = "qq_brief"
def _p(sms=None): return os.path.join(sms or qp.conf()["sms"], "shell", KEY)
def on(v, sms=None):
    try:
        os.makedirs(os.path.dirname(_p(sms)), exist_ok=True); open(_p(sms), "w", encoding="utf-8").write("1" if v else ""); return bool(v)
    except Exception: return None
def state(sms=None):
    try: return open(_p(sms), encoding="utf-8").read().strip()
    except Exception: return ""
def sess_kind(sms=None):
    """当前 session 通道 kind（只读不 ensure·不 import prompt_builder 以免回环）。"""
    try:
        import session_reg as R
        sid = os.environ.get("SMS_SESSION") or R._rd(R._c(sms))
        return str((R.get_(sid, sms) or {}).get("kind") or "") if sid else ""
    except Exception: return ""
def live(c=None):
    """简洁模式是否真在生效＝凭据开＋标志位 1＋当前 session 确为 qq 通道
    （2026-09-30 残留修复：标志位曾跨通道残留，TUI/网页/cron 正文被无端限长）。"""
    c = c or qp.conf()
    k = sess_kind(c.get("sms"))
    if k and k != "qq": return False
    return bool(c.get("brief")) and state(c["sms"]) == "1"
def cap(text, c=None):
    c = c or qp.conf(); t = str(text or ""); n = int(c.get("brief_len") or 260)
    return t if not live(c) or len(t) <= n else t[:n] + "…（余下见 SMS 壳）"
if __name__ == "__main__":
    a = sys.argv[1:] or ["state"]
    print(str(on(a[0] == "on")) if a[0] in ("on", "off")
          else json.dumps({"qq_brief": state(), "live": live()}, ensure_ascii=False) if a[0] == "state"
          else cap(" ".join(a[1:])) if a[0] == "cap" else __doc__.strip()[:300])
