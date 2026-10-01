#!/usr/bin/env python3
"""qq_push.py — QQ 主动推送（2026-09-29 用户「QQ 第三方 Agent 接入 SMS·只发送主要信息到我的 QQ」）：凭据 <SMS_HOME>/config/qq.json＝{appId,clientSecret,openid,enabled}（qq_bind.py 扫码写入）；发送＝POST https://api.bot.qq.com/v2/users/{openid}/messages {msg_type:0,content}＋Authorization: QQBot <token>（token 走 /app/getAppAccessToken，缓存 <SMS_HOME>/qq/token.json，提前 60s 重取）；口径＝只推 msg_flow CLASS∈{body,alert}（llm_out 模型正文/notice user_send/err 告警）＋模型提问＋做梦待批，思考 reasoning/工具 tool/代码 sh·edit/步骤 step·task/技能过程 skill 一律不推；护栏＝同文 60s 去重、最小间隔、日配额（官方 5qps·30qpm·单好友 1000/天·分段按段计数），超限写 <SMS_HOME>/qq/outbox.json 不阻塞前台，对话收口 flush() 补发；异常一律静默并记 error 链，推送失败绝不影响数据流。2026-09-29 修吞字：不再折叠换行、不再 [:max_len] 一刀切，超长交 qq_chunk 按行装箱分段（tag 加 ·i/n、段间守 min_gap 防 5qps/30qpm）；DEF 新增 ack（入站即时回执开关）/brief/brief_len（QQ 简洁模式）；2026-09-29 再增任务表卡住看门狗四项默认值（供 qq_stall.py 读，config/qq.json 同名键可覆盖·qq_cli conf k=v 改）：stall＝开关（默认开）、stall_after＝180s（src==qq 的表 mtime 距今超此值即判「无进展」）、stall_repeat＝600s（同签名在该窗口内不重发，防刷屏）、stall_tick＝30s（看门狗轮询节流）。函数：conf/ready/push/hook/flush/token/send；CLI 见 qq_cli.py。2026-09-30 修补发丢图：outbox 条目文本形如「正文 [图]路径」，flush() 经 _split_out() 拆出图片路径走 push(text, tag, c, image=path)（旧版整串当文本发＝真截图永久丢失）；无图条目行为不变、图文件已不存在＝只发正文、解析异常退回原样发送不抛。
2026-09-29 增图片：send_image(c,path,tag)＝读本地文件→base64→POST /v2/users/{openid}/files {file_type:1,file_data:<base64>,srv_send_msg:true}＋QQBot token（复用 token(c)·2026-09-30 实测修正：base64 塞进 url 字段被判 HTTP 400 {code:40093010,上传URL错误}（url 须为可访问链接），base64 只能放 file_data；file_data 形态实测 HTTP 200 返 file_uuid/file_info/ttl=86400，188KB 真截图通过·code=40001 清 token 缓存重试一次·网络层沿用 push_retries 退避·上限 DEF img_max_kb=2048KB）；push(text,tag,c=None,image=None) 让 alert/body 推送可随文带截图（图计 1 段占 max_day·同文件哈希 60s 去重·文图之间守 min_gap·第 3 位传 str 视为 image 故旧位置调用 push(text,tag,c) 不变·失败静默入 outbox/error 链不阻塞数据流）；CLI 新增 img <路径> [tag]。"""
import os, sys, json, time, hashlib, base64, urllib.request as U
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, msg_flow
import retry_io as rio, runtime_rec as rr
API = "https://api.bot.qq.com"; DEF = {"enabled": True, "max_day": 400, "min_gap": 2.0, "max_len": 500, "dedup": 60, "task_push": True, "task_gap": 8.0, "ack": True, "brief": True, "brief_len": 260, "push_retries": 3, "listen_retries": 8, "img_max_kb": 2048, "stall": True, "stall_after": 180, "stall_repeat": 600, "stall_tick": 30, "nudge": 1, "busy_grace": 120, "rt_trust": 3600, "shell_alive_ttl": 180}
_f = lambda sms, n: os.path.join(sms, "qq", n); _ld = lambda p, d=None: json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else d
def conf(sms=None):
    sms = sms or resolve_home.ensure(); c = _ld(os.path.join(sms, "config", "qq.json"), {}) or {}
    return dict(DEF, **{k: v for k, v in c.items() if not k.startswith("_")}, sms=sms)
def ready(c=None): c = c or conf(); return bool(c.get("appId") and c.get("clientSecret") and c.get("openid") and c.get("enabled"))
def _st(c): return _ld(_f(c["sms"], "state.json"), None) or {"day": "", "n": 0, "last": 0.0, "seen": {}}
def _wj(p, o): os.makedirs(os.path.dirname(p), exist_ok=True); json.dump(o, open(p, "w", encoding="utf-8"))
def _ob(c, txt, why):
    _wj(_f(c["sms"], "outbox.json"), ((_ld(_f(c["sms"], "outbox.json"), []) or []) + [{"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "text": txt, "why": why}])[-80:])
def _http(req):
    with U.urlopen(req, timeout=8) as r: return json.loads(r.read().decode("utf-8", "replace") or "{}")
def _post(url, body, tok="", c=None):
    """QQ 开放平台 POST：网络层失败（超时/断连/5xx/429）自动重试 push_retries 次（默认 3·指数退避 1s 起封顶 8s·HTTP 4xx 不重试）；耗尽抛 retry_io.Retryable 交调用方。"""
    req = U.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **({"Authorization": "QQBot " + tok} if tok else {})})
    nr = int((c or DEF).get("push_retries", 3)); bx = {"i": 0}
    def _ot(i, k, e, d): bx["i"] = i; rr.rec("qq_push", attempt=i, retries=max(0, k - i), err=e)
    try:
        r = rio.call(_http, nr, base=1.0, cap=8.0, on_try=_ot, args=(req,))
        rr.rec("qq_push", attempt=bx["i"], retries=max(0, nr - bx["i"]), err=""); return r
    except Exception as e:
        rr.rec("qq_push", attempt=bx["i"], retries=0, err=e); raise
def token(c):
    p, now = _f(c["sms"], "token.json"), time.time(); t = _ld(p, {}) or {}
    if t.get("token") and int(t.get("exp", 0)) - 60 > now: return t["token"]
    d = _post(API + "/app/getAppAccessToken", {"appId": c["appId"], "clientSecret": c["clientSecret"]})
    tk = d.get("access_token") or (d.get("data") or {}).get("access_token")
    if not tk: raise RuntimeError("token: " + json.dumps(d, ensure_ascii=False)[:160])
    _wj(p, {"token": tk, "exp": now + int(d.get("expires_in") or 3600)}); return tk
def _rp(c, t, tag="SMS"):
    try: import qq_reply; return qq_reply.try_send(c, t, tag)
    except Exception: return None
def _ok(r): return isinstance(r, dict) and int(r.get("code") or 0) == 0
def send(c, text, tag="SMS"):
    """出站发送（被动回复优先·回落主动推送）：失败自动重试 push_retries 次（默认 3·指数退避 1s→8s）；业务 code=40001（token 失效）先清缓存重取再试；重试仍失败回最后一次响应（交 push 记 outbox/链，绝不影响数据流）。"""
    n = max(0, int(c.get("push_retries", 3))); r = None
    for i in range(n + 1):
        r = _rp(c, text, tag) or __import__("qq_chunk").send(c, text, tag, API + "/v2/users/%s/messages" % c["openid"]) or r
        if _ok(r): return r
        if i >= n: return r
        if isinstance(r, dict) and int(r.get("code") or 0) == 40001:
            try: os.remove(_f(c["sms"], "token.json"))
            except OSError: pass
        time.sleep(min(8.0, 1.0 * (2 ** i)))
    return r
def _img_b64(p, c):
    """读本地图片→(md5前16, base64, 错误)：不存在/不可读/超 img_max_kb 时错误非空（交 send_image 入 outbox·不抛）。"""
    if not p or not os.path.isfile(p): return "", None, "图片不存在"
    try: b = open(p, "rb").read()
    except Exception as e: return "", None, "图片读取失败 " + str(e)[:80]
    if len(b) > int(c.get("img_max_kb") or 2048) * 1024: return hashlib.md5(b).hexdigest()[:16], None, "图片超 %sKB" % c.get("img_max_kb")
    return hashlib.md5(b).hexdigest()[:16], base64.b64encode(b).decode(), None
def send_image(c, path, tag="SMS"):
    """图片发送（2026-09-29 临时脚本实测 HTTP 200 形态）：读本地文件→base64→POST https://api.bot.qq.com/v2/users/{openid}/files，body {file_type:1, file_data:<base64>, srv_send_msg:true}＋Authorization: QQBot <token>；40093010「上传URL错误」＝url 字段误用（url 只接收可访问 URL、不接 base64），base64 必须用 file_data（复用 token(c)·srv_send_msg=true 由服务端直接下发，无需二次 messages 调用）；业务 code=40001 清 token 缓存重取后再试一次；网络层失败复用 _post 的 push_retries 指数退避（1s→8s·4xx 不重试）；上限 conf.img_max_kb（默认 2048KB）；失败一律静默入 outbox/error 链，绝不阻塞数据流。护栏（min_gap·日配额计 1 段·文件哈希 60s 去重）由 push(image=) 统一把关。"""
    try:
        c = c or conf(); p = str(path or "").strip().strip('"')
        h, b64, err = _img_b64(p, c)
        if err: _ob(c, "[img]" + p, err); return None
        if not ready(c): return None
        ep, body = API + "/v2/users/%s/files" % c["openid"], {"file_type": 1, "file_data": b64, "srv_send_msg": True}
        # 防回归 40093010「上传URL错误」：base64 只能放 file_data，url 字段只接收可访问链接——上传体绝不含 url
        if "url" in body or "file_data" not in body or not body.get("file_data"):
            _ob(c, "[img]" + p, "组包防回归：上传体须含非空 file_data 且不含 url（40093010）"); return None
        r = _post(ep, body, token(c), c)
        if isinstance(r, dict) and int(r.get("code") or 0) == 40001:
            try: os.remove(_f(c["sms"], "token.json"))
            except OSError: pass
            r = _post(ep, body, token(c), c)
        if not _ok(r): _ob(c, "[img]" + p + "·" + str(tag), "图片失败 " + json.dumps(r, ensure_ascii=False)[:120]); return None
        return r
    except Exception as e:
        try: import chain_error; chain_error.hook("gate", "qq_push", "img " + str(e)[:180])
        except Exception: pass
        return None
def push(text, tag="SMS", c=None, image=None):
    """出站推送（文本＋可选截图）：image=本地图片路径时随文补发一张图（图计 1 段占日配额·同文件哈希 60s 去重·文图之间守 min_gap）；第 3 位实参兼容旧调用——传 dict 视为 c、传 str 视为 image，故 qq_flow/qq_inbound/qq_report 既有 push(text, tag, c) 位置调用不受影响。"""
    try:
        if isinstance(c, str) and image is None: image, c = c, None
        c = c or conf(); text = str(text or "").strip(); image = str(image or "").strip()
        if not ready(c) or (not text and not image): return None
        segs = [x for x in (__import__("qq_chunk").split(text, __import__("qq_chunk").cap_for(c, tag)) or []) if x.strip()] if text else []
        ih = _img_b64(image, c)[0] if image else ""
        s, now, day = _st(c), time.time(), time.strftime("%Y%m%d")
        s = {"day": day, "n": 0, "last": 0.0, "seen": {}} if s.get("day") != day else s
        s["seen"] = {a: b for a, b in s["seen"].items() if now - float(b) < 600}
        _k = hashlib.md5(text.encode()).hexdigest()[:16]
        if text and now - float(s["seen"].get(_k) or 0) < float(c["dedup"]): return "去重跳过"
        if ih and now - float(s["seen"].get("img" + ih) or 0) < float(c["dedup"]):
            if not text: return "去重跳过（同图60s内）"
            image = ""
        nseg = len(segs) + (1 if image else 0)
        if not nseg: return None
        if text: s["seen"][_k] = now
        if ih and image: s["seen"]["img" + ih] = now
        if int(s["n"]) + nseg > int(c["max_day"]) or now - float(s.get("last") or 0) < float(c["min_gap"]): _ob(c, text + (" [图]" + image if image else ""), "配额/间隔"); return "已入outbox待补发"
        if segs: send(c, text, tag)
        if image:
            if segs: time.sleep(float(c.get("min_gap") or 2.0))
            send_image(c, image, tag)
        s["last"], s["n"] = time.time(), int(s["n"]) + nseg; _wj(_f(c["sms"], "state.json"), s)
        return ("已推送QQ·图" if image else "已推送QQ") if nseg < 2 else "已推送QQ·%d段" % nseg
    except Exception as e:
        try: import chain_error; chain_error.hook("gate", "qq_push", str(e)[:200])
        except Exception: pass
        return "推送失败（不影响数据流）：" + str(e)[:120]
def hook(e, c=None): return push(e.get("text"), "QQ·" + str(e.get("kind")), c, e.get("image")) if msg_flow.cls(e.get("kind")) in ("body", "alert") else None
def _split_out(txt):
    """outbox 条目 → (正文, 图片路径或 "")：兼容 push 配额入队「正文 [图]路径」与 send_image 三条失败入队「[img]路径[·tag]」（含带正文的「正文 [img]路径」）；无标记＝(原文, None) 行为完全不变；命中标记但图文件不存在＝图置空（无正文时 flush 即判「已丢弃」），绝不把本地路径当文字发出；异常＝原样返回不抛。"""
    t = str(txt or "")
    try:
        i = t.rfind(" [图]")
        if i >= 0:
            p = t[i + 4:].strip().strip('"')
            return t[:i].strip(), (p if p and os.path.isfile(p) else "")
        s = t.strip(); j = s.find("[img]")
        if j < 0: return t, None
        body = s[:j].strip(); p = s[j + 5:].strip().strip('"')
        for cand in [x for x in (p, p.rsplit("·", 1)[0] if "·" in p else "") if x]:
            if os.path.isfile(cand): return body, cand
        return body, ""
    except Exception: return t, None
def flush(c=None):
    c = c or conf(); p = _f(c["sms"], "outbox.json"); rows = _ld(p, []) or []
    if not (ready(c) and rows): return None
    def _resend(r):
        t, img = _split_out(r.get("text"))
        if img: return push(t, "QQ·补发", c, image=img)
        if t: return push(t, "QQ·补发", c)
        return "已丢弃（图文件不存在）"
    left = [r for r in rows[-10:] if not str(_resend(r)).startswith(("已推送QQ", "已丢弃"))]
    _wj(p, left) if left else os.remove(p); return "outbox 补发 %d/%d 条" % (len(rows) - len(left), len(rows))
