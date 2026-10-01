#!/usr/bin/env python3
"""external.py — 对外端口（默认关闭，高危面）：HTTPS（web_certs 指纹证书）绑 external.interface:port；外部请求必须先经 PQ 非对称验签——/api/pair 提交公钥（须本地 enroll 批准的指纹，否则 403）→ 挑战 nonce → /api/verify 以私钥签 nonce → 通过后发 TTL 会话 token；/api/chat 仅 Bearer 可用（不开配置写·密钥面）；失败限速超限封 10 分钟；pq_mode strict 无 PQ 拒启；跨网推荐 SSH 隧道＋指纹钉选。用法：python -B external.py status|enable [--yes]|disable|start|serve|stop|tunnel|enroll <pub_b64> [note] [ttl]|revoke <fpr>|list。"""
import os, sys, json, time, secrets
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import net_util, settings, ext_net, web_certs, chains
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
NAME = "external"; TOK = {}; FAIL = {}; BLOCK = {}
def _rate(ip):
    FAIL[ip] = [t for t in FAIL.get(ip, []) if time.time() - t < 60]
    if len(FAIL[ip]) >= int(settings.get(NAME + ".max_fail_per_min", 5)): BLOCK[ip] = time.time() + 600; chains.record("event", "对外端口限速封禁 " + ip + " 600s")
    return BLOCK.get(ip, 0) > time.time()
class H(BaseHTTPRequestHandler):
    server_version = "sms-ext"; protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def _reject(self, code, msg): FAIL.setdefault(self.client_address[0], []).append(time.time()); chains.record("event", "对外端口拒绝 " + self.client_address[0] + "：" + msg[:60]); return net_util.send(self, code, {"err": msg})
    def _bearer(self): e = TOK.get(self.headers.get("Authorization", "").removeprefix("Bearer ").strip()); return e if e and e["exp"] > time.time() else None
    def do_GET(self): p = self.path.split("?")[0]; return net_util.send(self, 200, {"service": "sms_shell/external", "backend": ext_net.backend(), "pq": ext_net.is_pq(), "cert_fpr": web_certs.fpr()[:32], "pair": "本地先 enroll 公钥，再 POST /api/pair {pub_b64} → /api/verify {fpr,nonce,sig_b64} → Bearer 调 /api/chat"}) if p == "/api/info" else self._reject(404, "404")
    def do_POST(self):
        ip = self.client_address[0]; p = self.path.split("?")[0]; b = net_util.body(self)
        if _rate(ip): return self._reject(429, "失败过多，已限速")
        if p == "/api/pair": f = ext_net.fpr(b["pub_b64"]) if b.get("pub_b64") else ""; return self._reject(403, "指纹未注册：本机执行 external.py enroll <pub_b64> [note] [ttl]") if not ext_net.trusted(f) else net_util.send(self, 200, {"fpr": f, "nonce": ext_net.challenge(f)})
        if p == "/api/verify": f = str(b.get("fpr", "")); ok = ext_net.answer(f, str(b.get("nonce", "")), str(b.get("sig_b64", "")))
        if p == "/api/verify" and ok: t = secrets.token_urlsafe(24); TOK[t] = {"fpr": f, "exp": time.time() + settings.get(NAME + ".session_ttl_min", 240) * 60}; chains.record("event", "对外端口会话签发 fpr=" + f[:16]); return net_util.send(self, 200, {"token": t})
        if p == "/api/verify": return self._reject(401, "PQ 验签失败或挑战过期")
        if p == "/api/chat":
            e = self._bearer()
            if not e: return self._reject(401, "需要 Bearer 会话 token（/api/pair→/api/verify）")
            try: __import__("session_reg").bind("remote", "ext:" + str(e.get("fpr") or "")[:16], "远程·" + str(e.get("fpr") or "")[:8])
            except Exception: pass
            return net_util.send(self, 200, net_util.chat(b.get("text")))
        return self._reject(404, "404")
def serve(host=None, port=None):
    c = settings.eff()[NAME]
    if not c.get("enabled"): return "拒绝：对外端口未启用——需 `python -B external.py enable --yes`（用户当轮确认，resistance #16/#18）"
    if not ext_net.is_pq() and c.get("pq_mode", "auto") == "strict": return "拒绝：pq_mode=strict 且本机无 ML-DSA 后端"; (not ext_net.is_pq() and print("警告：无 PQ 后端，降级 ed25519——对外安全性下降"))
    host = host or c.get("interface", "0.0.0.0"); port = int(port or c.get("port", 8738))
    srv = ThreadingHTTPServer((host, port), H); srv.socket = net_util.ctx().wrap_socket(srv.socket, server_side=True)
    net_util.write_run(NAME, port); chains.record("event", "对外端口启动 %s:%s backend=%s" % (host, port, ext_net.backend())); print("对外 https://%s:%d 指纹=%s backend=%s（验签配对接听中）" % (host, port, web_certs.fpr()[:16], ext_net.backend()))
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
    finally: chains.record("event", "对外端口停止"); net_util.clear(NAME)
def preview(): c = settings.eff()[NAME]; return "预览（默认不写盘）：开启对外端口 https://%s:%s＝向网络暴露 SMS 会话通道；仅 /api/chat、须本地 enroll 指纹＋PQ 验签、失败限速。确认：external.py enable --yes；更安全远程：external.py tunnel" % (c.get("interface"), c.get("port"))
if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]; cmd = a[0]
    if cmd == "status": print(json.dumps(settings.status()[NAME], ensure_ascii=False))
    elif cmd == "enable": print("已启用（未启动）：external.py start" if "--yes" in a and settings.set(NAME + ".enabled", True) is not None else preview())
    elif cmd in ("stop", "disable"): print((net_util.stop(NAME) + " · 配置已关闭") if cmd == "disable" and settings.set(NAME + ".enabled", False) is not None else net_util.stop(NAME))
    elif cmd == "start": print("已在运行 pid=" + str(net_util.running(NAME)) if net_util.running(NAME) else (net_util.spawn(NAME) if settings.get(NAME + ".enabled") else "未启用：先 external.py enable --yes"))
    elif cmd == "serve": print(serve() or "已退出")
    elif cmd == "tunnel": print("外网访问推荐隧道：远端 ssh -N -L <port>:127.0.0.1:<port> 用户@本机，并把 external.interface 设为 127.0.0.1（仅隧道入口可达）、按证书指纹钉选——非对称＋加密通道双重保障本机")
    elif cmd == "enroll" and a[1:]: print("已批准指纹：" + ext_net.enroll(a[1], *(a[2:3] or [""]), int(a[3]) if len(a) > 3 else 0))
    elif cmd in ("revoke", "list"): print(("吊销 " + str(ext_net.revoke(a[1])) + " 条") if cmd == "revoke" and a[1:] else json.dumps(ext_net.load(), ensure_ascii=False, indent=1))
    else: print(__doc__.strip().splitlines()[-1])
