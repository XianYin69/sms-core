#!/usr/bin/env python3
"""qq_reply.py — 入站消息「回到原聊天线程」的被动回复（2026-09-29 用户「我要发消息给你」）：官方文档实测——同一 messages 接口多带 msg_id 即**被动回复**（msg_id 取自 C2C_MESSAGE_CREATE/GROUP_AT_MESSAGE_CREATE 的 d.id、**5 分钟内有效**、不占主动消息 1000 条/天配额），故入站对话的答案走被动、显示在原会话；本模块只存一次性上下文 CTX＝{msg_id,openid,kind,exp}，端点按 kind 选：user→/v2/users/{openid}/messages、group→/v2/groups/{group_openid}/messages；ttl 默认 280s 留 20s 余量防边界过期。qq_push.send 先问 try_send：命中就发被动，失败（过期/频控/无权限）自动清上下文回 None，qq_push 随即回落主动推送——两条都失败才由 qq_push 吞异常记 error 链，绝不影响数据流。与 qq_push 互为延迟 import（qq_push.send 内 import 本模块·本模块函数内 import qq_push）避免循环依赖。2026-09-29 修吞字接线：try_send(c,text,tag) 与 qq_push._rp 的三参调用对齐（此前签名不合→TypeError 被 except 吞→被动回复从未真正生效），超长交 qq_chunk 按行装箱分段（首段被动、余段逐段主动补发并守 min_gap），取消 [:max_len] 一刀切静默截断。用法：python -B qq_reply.py state|set <msg_id> [openid] [user|group]|send "<文本>"|clear。"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
API = "https://api.bot.qq.com"
CTX = {}
def set_reply(msg_id="", openid="", kind="user", ttl=280):
    CTX.clear(); CTX.update({"msg_id": str(msg_id or ""), "openid": str(openid or ""), "kind": kind or "user", "exp": time.time() + float(ttl)}); return dict(CTX)
def clear(): CTX.clear()
def live(): return bool(CTX.get("msg_id")) and time.time() < float(CTX.get("exp") or 0)
def _ep(kind, oid): return API + "/v2/%s/%s/messages" % ("groups" if str(kind) == "group" else "users", oid)
def _body(tag, t, i=0, n=1): return ("〔%s·%d/%d〕%s" % (tag, i, n, t)) if n > 1 else ("〔%s〕%s" % (tag, t))
def try_send(c, text, tag="SMS"):
    """有未过期 msg_id 就被动回复首段；余段走主动推送补发（不截断·守 min_gap）；全失败清上下文回 None 交 qq_push 回落。"""
    if not live(): return None
    import qq_chunk as KC, qq_push as qp
    mid, kind = CTX["msg_id"], CTX.get("kind") or "user"
    segs = KC.split(text, KC.cap_for(c, tag)) or [str(text or "")]; n = len(segs); res = None
    for oid in list(dict.fromkeys([x for x in (CTX.get("openid"), c.get("openid")) if x])):
        try:
            d = qp._post(_ep(kind, oid), {"msg_type": 0, "content": _body(tag, segs[0], 1, n), "msg_id": mid}, qp.token(c))
            if int(d.get("code") or 0): continue
            res = d; break
        except Exception: continue
    if res is None: clear(); return None
    for i, sg in enumerate(segs[1:], 2):
        try:
            time.sleep(float(c.get("min_gap") or 2.0))
            qp._post(API + "/v2/users/%s/messages" % c["openid"], {"msg_type": 0, "content": _body(tag, sg, i, n)}, qp.token(c))
        except Exception: break
    return res
if __name__ == "__main__":
    import qq_push as qp, qq_chunk as KC
    a = sys.argv[1:] or ["state"]; c = qp.conf()
    if a[0] == "segtest":
        set_reply("selftest-mid", c.get("openid") or "", "user")
        segs = KC.split("行1\n行2\n" + "长" * 1200, KC.cap_for(c, "QQ\u00b7\u6d4b\u8bd5"))
        print(json.dumps({"cap_for": KC.cap_for(c, "QQ"), "max_len": c["max_len"], "分段数": len(segs),
                          "三参签名": "tag" in try_send.__code__.co_varnames, "无静默截断": sum(len(x) for x in segs) >= 1200}, ensure_ascii=False))
        clear()
    else:
        print(json.dumps({"ctx": dict(CTX), "live": live(), "ready": qp.ready(c)}, ensure_ascii=False) if a[0] == "state"
              else str(set_reply(a[1], a[2] if len(a) > 2 else "", a[3] if len(a) > 3 else "user")) if a[0] == "set"
              else str(try_send(c, " ".join(a[1:]) or "SMS 被动回复自测") or "无上下文或被动失效（回落主动）") if a[0] == "send"
              else str(clear()) if a[0] == "clear" else __doc__.strip()[:300])
