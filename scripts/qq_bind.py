#!/usr/bin/env python3
"""qq_bind.py — QQ 机器人扫码绑定（纯 Python 复刻 @tencent-connect/qqbot-connector 1.2.0 协议·无 Node 运行时）：POST https://q.qq.com/lite/create_bind_task {key:base64(32B)} → data.task_id；扫码页 https://q.qq.com/qqbot/openclaw/connect.html?task_id=..&source=..&_wv=2（手机 QQ 扫码或浏览器打开）；POST /lite/poll_bind_result {task_id} → data{status 0NONE/1PENDING/2COMPLETED/3EXPIRED, bot_appid, bot_encrypt_secret, user_openid}；appSecret＝AES-256-GCM(key=base64decode(key), iv=前12字节, tag=后16字节, ct=中间) 解 bot_encrypt_secret——Python 侧必须 decrypt(iv, ct‖tag 合并, None)：cryptography 的 data 参数须含尾随 tag，把 tag 当 aad 传必抛 InvalidTag（Node SDK createDecipheriv 分传 iv/ct/tag 的写法不可照抄）；关键红利＝绑定回执自带 user_openid，故无需用户先给机器人发消息即可主动推送。凭据落 <SMS_HOME>/config/qq.json（旧值备份 .bak）。二维码＝装 segno/qrcode 打印 ASCII，否则打印链接。慢网加固＝_post 超时 20s×3 退避重试；save_pending/load_pending/clear_pending 把 task_id+key 落 <SMS_HOME>/qq/bind_pending.json，供 qq_bindflow.resume 免重扫续握手（connect.html 的「连接中」须本机 poll 成功才收口）。用法：python -B qq_bind.py [source] [--timeout 300] [--appid A --secret S --openid O 手工录入]"""
import os, sys, json, time, base64, secrets, urllib.request as U
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home
HOST = "https://q.qq.com"
def _post(path, body, tries=3, to=20):
    for i in range(tries):
        try:
            req = U.Request(HOST + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "Accept": "application/json"})
            with U.urlopen(req, timeout=to) as r: return json.loads(r.read().decode("utf-8", "replace") or "{}")
        except Exception:
            if i >= tries - 1: raise
            time.sleep(2 * (i + 1))
def genkey(): return base64.b64encode(secrets.token_bytes(32)).decode()
def create(key):
    d = _post("/lite/create_bind_task", {"key": key})
    if d.get("retcode") != 0 or not (d.get("data") or {}).get("task_id"): raise RuntimeError(d.get("msg") or json.dumps(d, ensure_ascii=False)[:160])
    return d["data"]["task_id"]
def poll(tid):
    d = _post("/lite/poll_bind_result", {"task_id": tid})
    if d.get("retcode") != 0: raise RuntimeError(d.get("msg") or "poll_bind_result failed")
    x = d.get("data") or {}
    return int(x.get("status") or 0), str(x.get("bot_appid") or ""), x.get("bot_encrypt_secret") or "", x.get("user_openid") or ""
def decrypt(sec_b64, key_b64):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    n, k = base64.b64decode(sec_b64), base64.b64decode(key_b64)
    return AESGCM(k).decrypt(n[:12], n[12:], None).decode("utf-8")
def save_raw(tid, key, sec, appid, oid, err, sms=None):
    """解密失败兜底：task_id/key/bot_encrypt_secret 原文落 <SMS_HOME>/qq/bind_raw.json 供事后重解（凭据不丢）。"""
    sms = sms or resolve_home.ensure(); p = os.path.join(sms, "qq", "bind_raw.json"); os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump({"task_id": tid, "key": key, "bot_encrypt_secret": sec, "appId": appid, "openid": oid,
               "error": type(err).__name__ + ": " + str(err)[:200], "at": time.strftime("%Y-%m-%dT%H:%M:%S")}, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("原始 bot_encrypt_secret 前缀=" + str(sec)[:48] + "…（完整原文已存 " + p + "·修好后可重解）"); return p
def _pf(sms=None): return os.path.join(sms or resolve_home.ensure(), "qq", "bind_pending.json")
_ld = lambda p, d=None: json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else d
def save_pending(tid, key, source="", sms=None):
    p = _pf(sms); os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump({"task_id": tid, "key": key, "source": source, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1); return p
def load_pending(sms=None): return _ld(_pf(sms), {}) or {}
def clear_pending(sms=None):
    try: os.remove(_pf(sms))
    except OSError: pass
def qurl(tid, source=""): return "%s/qqbot/openclaw/connect.html?task_id=%s&source=%s&_wv=2" % (HOST, tid, source)
def show(u):
    for mod, fn in (("segno", lambda m: print(m.make(u, error="M").terminal())), ("qrcode", lambda m: m.make(u).print_ascii())):
        try:
            import importlib; fn(importlib.import_module(mod)); return "请用手机 QQ 扫上方二维码"
        except Exception: pass
    return "未装 segno/qrcode——请用手机 QQ 或浏览器打开下方链接完成绑定"
