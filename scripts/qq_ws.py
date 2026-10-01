#!/usr/bin/env python3
"""qq_ws.py — 纯标准库 WebSocket 客户端（RFC6455·为 QQ 机器人入站而生：不装 websocket-client、不引 Node，SMS 零新依赖）：connect(url, headers) 走 TCP＋TLS（wss）＋HTTP Upgrade 握手，校验状态行 101 与 Sec-WebSocket-Accept（SHA1(key+GUID) base64），握手后残留字节移交 Conn.buf 防丢首帧 HELLO；send(text) 出文本帧——客户端→服务端**必须掩码**（4B 随机 key＋逐字节 XOR）；recv(timeout) 就地消化控制帧：ping(9)→原载荷回 pong(10)、pong(10) 忽略、close(8)→返回 None 交上层重连、fin=0 分片累积后一次返回；_r(n) 带缓冲读避免半包死锁。recv 的 timeout 同时充当心跳到期信号；**2026-09-29 修静默卡死**：op=9/10 控制帧走 continue 永不退出循环，故加墙钟 deadline＝timeout*4，超时抛 socket.timeout 交上层（qq_session）判僵尸重连（抛 socket.timeout/TimeoutError 由上层发 op=1 心跳）。实测接入点由 GET /gateway 返回 wss://api.sgroup.qq.com/websocket（与文档示例域名不同，故 URL 一律取接口返回值不硬编码）。"""
import os, time, socket, ssl, struct, base64, hashlib
from urllib.parse import urlparse
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
def _mask(p): k = os.urandom(4); return k + bytes(c ^ k[i % 4] for i, c in enumerate(p))
def _frame(op, data=b"", fin=True):
    b = bytearray([(0x80 if fin else 0) | op]); n = len(data)
    e = b"" if n < 126 else (struct.pack(">H", n) if n < 65536 else struct.pack(">Q", n))
    b.append(0x80 | (n if n < 126 else (126 if n < 65536 else 127))); return bytes(b) + e + _mask(data)
class Conn:
    def __init__(self, s, buf=b""): self.s, self.buf = s, buf
    def _r(self, n):
        while len(self.buf) < n:
            if not (c := self.s.recv(65536)): raise ConnectionError("ws 对端关闭")
            self.buf += c
        o, self.buf = self.buf[:n], self.buf[n:]; return o
    def send(self, text): self.s.sendall(_frame(1, str(text).encode()))
    def recv(self, timeout=90):
        self.s.settimeout(timeout); f = b""; dl = time.time() + float(timeout) * 4
        while True:
            if time.time() > dl: raise socket.timeout("recv 墙钟看门狗超时（op=9/10 控制帧空转不出循环）")
            h = self._r(2); op = h[0] & 15; ln = h[1] & 127
            if ln > 125: ln = struct.unpack(">H" if ln == 126 else ">Q", self._r(2 if ln == 126 else 8))[0]
            k = self._r(4) if h[1] & 0x80 else b""; d = self._r(ln)
            if k: d = bytes(c ^ k[i % 4] for i, c in enumerate(d))
            if op == 8: return None
            if op == 9: self.s.sendall(_frame(10, d)); continue
            if op == 10: continue
            f += d
            if h[0] & 0x80: return f.decode("utf-8", "replace")
    def close(self):
        try: self.s.sendall(_frame(8)); self.s.close()
        except Exception: pass
def connect(url, headers=None, timeout=20):
    u = urlparse(url); host = u.hostname; port = u.port or (443 if u.scheme == "wss" else 80)
    s = socket.create_connection((host, port), timeout=timeout)
    if u.scheme == "wss": s = ssl.create_default_context().wrap_socket(s, server_hostname=host)
    key = base64.b64encode(os.urandom(16)).decode(); path = (u.path or "/") + (("?" + u.query) if u.query else ""); buf = b""
    hd = {"Host": host, "Upgrade": "websocket", "Connection": "Upgrade", "Sec-WebSocket-Key": key, "Sec-WebSocket-Version": "13", **(headers or {})}
    s.sendall((("GET %s HTTP/1.1\r\n" % path) + "".join("%s: %s\r\n" % kv for kv in hd.items()) + "\r\n").encode())
    while b"\r\n\r\n" not in buf:
        if not (c := s.recv(4096)): raise ConnectionError("握手被拒：" + buf[:120].decode("utf-8", "replace"))
        buf += c
    head, rest = buf.split(b"\r\n\r\n", 1)
    if b" 101 " not in head: raise ConnectionError("握手非 101：" + head.split(b"\r\n")[0].decode("utf-8", "replace"))
    exp = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
    if ("sec-websocket-accept: " + exp).lower() not in head.decode("utf-8", "replace").lower(): raise ConnectionError("Accept 校验失败")
    return Conn(s, rest)
