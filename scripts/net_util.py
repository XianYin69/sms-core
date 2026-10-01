#!/usr/bin/env python3
"""net_util.py — 网络壳公共件（web_shell/external 共用）：TLS 服务上下文（web_certs 自签指纹证书）、配对 token（<SMS_HOME>/shell/web.token 自动生成）、Host 防重绑定与 loopback 判定、pid/port 文件＋后台 spawn/停止、JSON/页面响应、JSON 请求体读取、经 shell_core.handle 收集式执行话语（元指令与数据流同 TUI/GUI）。"""
import os, sys, json, hmac, signal, secrets, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, web_certs
S = os.path.dirname(os.path.abspath(__file__))
def ctx(): return web_certs.context()
def token(rotate=False):
    p = os.path.join(resolve_home.ensure(), "shell", "web.token")
    if rotate or not os.path.exists(p):
        os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w").write(secrets.token_urlsafe(24))
    return open(p, encoding="utf-8").read().strip()
def check_token(got): return bool(got) and hmac.compare_digest(str(got), token())
def host_ok(hdr): return ((hdr or "").split(":")[0].strip().lower().strip("[]")) in ("127.0.0.1", "localhost", "::1")
def local_peer(ip): return ip in ("127.0.0.1", "::1", "localhost")
def pidfile(name): return os.path.join(resolve_home.ensure(), "shell", name + ".pid")
def portfile(name): return os.path.join(resolve_home.ensure(), "shell", name + ".port")
def write_run(name, port): open(pidfile(name), "w").write(str(os.getpid())); open(portfile(name), "w").write(str(port))
def clear(name): [os.remove(p) for p in (pidfile(name), portfile(name)) if os.path.exists(p)]
def running(name):
    try: pid = int(open(pidfile(name)).read())
    except Exception: return None
    try:
        if os.name == "nt":
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h: return None
            ctypes.windll.kernel32.CloseHandle(h); return pid
        os.kill(pid, 0); return pid
    except Exception: return None
def port_of(name):
    try: return int(open(portfile(name)).read())
    except Exception: return None
def stop(name):
    pid = running(name)
    if not pid: return "未运行：" + name
    (subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True) if os.name == "nt" else os.kill(pid, signal.SIGTERM)); clear(name)
    return "已停止 pid=" + str(pid)
def spawn(name):
    lf = open(os.path.join(resolve_home.ensure(), "shell", name + ".log"), "a"); sp = [sys.executable, "-B", os.path.join(S, name + ".py"), "serve"]
    kw = {"stdout": lf, "stderr": lf, "stdin": subprocess.DEVNULL}
    (subprocess.Popen(sp, creationflags=0x8 | 0x08000000, **kw) if os.name == "nt" else subprocess.Popen(sp, start_new_session=True, **kw))
    return "已后台启动：" + name + "（日志 shell/" + name + ".log）"
def send(h, code, obj, ctype="application/json; charset=utf-8"):
    b = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
    h.send_response(code); h.send_header("Content-Type", ctype); h.send_header("Content-Length", str(len(b))); h.send_header("Cache-Control", "no-store"); h.end_headers()
    try: h.wfile.write(b)
    except Exception: pass
def body(h):
    try:
        n = int(h.headers.get("Content-Length", 0) or 0); return json.loads(h.rfile.read(min(n, 4_000_000)).decode("utf-8")) if n else {}
    except Exception: return {}
def page(): return open(os.path.join(S, "web_page.html"), "rb").read()
def chat(text):
    import runtime_bind as rb
    lines = []; r = rb.run(str(text or "")[:6000], lines.append)
    return {"lines": lines, "exit": r == "exit", "meta": None if r == "exit" else r}

def qs(h):
    """查询串 → dict（web_shell 只读端点取 ws/path/tid/reveal 等参数）。"""
    try:
        import urllib.parse as up
        return {k: v[-1] for k, v in up.parse_qs((h.path or "").split("?", 1)[1]).items()}
    except Exception:
        return {}
