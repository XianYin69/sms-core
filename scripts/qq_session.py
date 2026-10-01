#!/usr/bin/env python3
"""qq_session.py — QQ 开放平台网关会话（WebSocket 事件订阅·2026-09-29 用户「我要发消息给你」；「该机器人未连接灵魂」的真义＝本机须有常驻进程消费消息事件，QQ 才认定机器人接上了 Agent）：① GET https://api.bot.qq.com/gateway（头 Authorization: QQBot <access_token>·token 复用 qq_push.token 缓存）取 wss 接入点（文档实测 wss://api.bot.qq.com/websocket/）② qq_ws.connect ③ 首帧 op=10 HELLO·d.heartbeat_interval 毫秒（缺省 41000·钳 ≥5s）④ op=2 IDENTIFY {token,intents,shard:[0,1],properties{$os,$browser,$device}}——intents 位取官方 SDK botpy：public_messages=1<<25（C2C_MESSAGE_CREATE＋GROUP_AT_MESSAGE_CREATE 单聊/群聊消息）、interaction=1<<26；无权限位会 4013/4014 直接断连，故 qq_listen 侧降级只订 1<<25 重试 ⑤ op=0 t=READY 记 d.session_id，此后每条事件带 s=seq ⑥ 每 hb 秒发 op=1 d=seq（收 op=11 ACK；一周期无 ACK 判僵尸重连；服务端主动 op=1 亦即时回心跳）⑧′ 墙钟看门狗：每轮回循环顶记 self.top，超 3*hb 未回顶＝recv 卡死（旧版控制帧空转致静默），抛 ConnectionError 走既有 down＋指数退避重连（有 sid 即 op=6 RESUME 补发漏事件）；⑦ op=7 Reconnect→重连后 op=6 RESUME {token,session_id,seq}（网关短时间补发漏事件）⑧ op=9 Invalid Session→清 sid 重新 IDENTIFY；断线指数退避 2→60s，连上复位；连续失败上限＝qq.json listen_retries（默认 8），耗尽则 gaveup 告警并交 qq_boot 下轮重拉。协议在本模块、准入在 qq_policy、派发到 qq_inbound。用法：python -B qq_session.py [事件数]＝连上打印事件名（自测）。"""
import os, sys, json, time, socket, urllib.request as U
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import qq_ws, qq_push as qp; import retry_io as rio, runtime_rec as rr; API = "https://api.bot.qq.com"; I_MSG = 1 << 25; I_INT = 1 << 26
def url(c):
    """取 wss 接入点：网络层失败（超时/断连/5xx/429）自动重试 listen_retries 次（退避 1s→8s）；业务错误（无 url 字段）不重试直接抛。"""
    def _g():
        req = U.Request(API + "/gateway", headers={"Authorization": "QQBot " + qp.token(c), "Accept": "application/json"})
        with U.urlopen(req, timeout=15) as r: d = json.loads(r.read().decode("utf-8", "replace") or "{}")
        w = d.get("url") or (d.get("data") or {}).get("url")
        if not w: raise RuntimeError("gateway: " + json.dumps(d, ensure_ascii=False)[:160])
        return w
    nr = int(c.get("listen_retries", 8)); bx = {"i": 0}
    def _ot(i, k, e, d): bx["i"] = i; rr.rec("qq_ws", attempt=i, retries=max(0, k - i), err=e)
    try:
        w = rio.call(_g, nr, base=1.0, cap=8.0, on_try=_ot)
        rr.rec("qq_ws", attempt=bx["i"], retries=max(0, nr - bx["i"]), err=""); return w
    except Exception as e:
        rr.rec("qq_ws", attempt=bx["i"], retries=0, err=e); raise
class Session:
    """一条 QQ 网关长连接：loop() 自动 HELLO→IDENTIFY/RESUME→心跳→事件回调，断线指数退避重连。"""
    def __init__(self, on_event, c=None, intents=I_MSG | I_INT):
        self.cb, self.c, self.intents = on_event, c or qp.conf(), intents
        self.conn = None; self.seq = None; self.sid = ""; self.hb = 41.0; self.last = 0.0; self.ack = True; self.back = 2.0; self.top = time.time()
    def _send(self, op, d=None): self.conn.send(json.dumps({"op": op, "d": d}))
    def open(self):
        tk = {"token": "QQBot " + qp.token(self.c)}; self.conn = qq_ws.connect(url(self.c))
        m = json.loads(self.conn.recv(20) or "{}")
        if m.get("op") != 10: raise RuntimeError("首帧非 HELLO：" + str(m)[:120])
        self.hb = max(5.0, float((m.get("d") or {}).get("heartbeat_interval") or 41000) / 1000.0)
        if self.sid: self._send(6, dict(tk, session_id=self.sid, seq=self.seq))
        else: self._send(2, dict(tk, intents=self.intents, shard=[0, 1], properties={"$os": "windows", "$browser": "SMS", "$device": "SMS"}))
        self.last = time.time(); self.ack = True
        rr.rec("qq_ws", attempt=0, retries=int(self.c.get("listen_retries", 8)), err="")
    def feed(self, t):
        m = json.loads(t); op = m.get("op"); d = m.get("d"); ty = m.get("t")
        if m.get("s") is not None: self.seq = m["s"]
        if op == 11: self.ack = True
        elif op == 1: self._send(1, self.seq)
        elif op == 7: raise ConnectionError("网关要求重连 op=7")
        elif op == 9: self.sid = ""; raise ConnectionError("Invalid Session（identify/intents 无权限）：" + str(d)[:120])
        elif op == 0 and ty:
            if ty in ("READY", "RESUMED"): self.sid = (d or {}).get("session_id") or self.sid
            else: self.cb(m)
    def loop(self, alive=lambda: True, on_state=lambda s, x="": None, max_retries=None):
        """监听主循环：断线指数退遳重连（2→60s）。max_retries（qq.json listen_retries，默认 8）＝连续失败重试上限，连上（identified）即清零计数与退遳；耗尽则 on_state("gaveup") 并返回 False（交 qq_listen 告警、qq_boot 下轮自愈重拉）；None/0 等价无限重连。"""
        fails = 0
        while alive():
            try:
                if time.time() - self.top > 3 * self.hb: raise ConnectionError("墙钟看门狗超时（recv 未回循环顶）")
                self.top = time.time(); self.conn and on_state("live", "")
                if not self.conn: self.open(); on_state("identified", self.sid); fails = 0; self.back = 2.0
                if time.time() - self.last >= self.hb:
                    if not self.ack: raise ConnectionError("心跳无 ACK（僵尸连接）")
                    self._send(1, self.seq); self.last = time.time(); self.ack = False
                try: x = self.conn.recv(min(2.0, max(0.2, self.hb)))
                except (socket.timeout, TimeoutError): x = ""
                if x is None: raise ConnectionError("对端 close 帧")
                if x: self.feed(x)
            except Exception as e:
                rr.rec("qq_ws", attempt=fails + 1, retries=max(0, int(max_retries or 0) - fails - 1), err=e)
                on_state("down", str(e)[:160]); self.conn and self.conn.close()
                self.conn = None; self.top = time.time(); fails += 1
                if max_retries is not None and int(max_retries) >= 0 and fails > int(max_retries): rr.rec("qq_ws", attempt=fails, retries=0, err=e); on_state("gaveup", "\u8fde\u7eed %d \u6b21\u91cd\u8fde\u5931\u8d25" % fails); return False
                time.sleep(self.back); self.back = min(60.0, self.back * 2)
        return True
