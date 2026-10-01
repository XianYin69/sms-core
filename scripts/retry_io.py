#!/usr/bin/env python3
"""retry_io.py - 统一「有限次重试」器（2026-09-29 用户「QQ监听失败的时候需要重试一定次数·提供商访问失败需要重试一定次数」）：call(fn, times, base, cap, on_try, retry_on) = 首次 + 最多 times 次重试，指数退避 base*2^n 封顶 cap，times<=0 即只跑一次；次数一律由配置给（提供商=settings llm_gateway.retries · QQ 出站=qq.json push_retries · QQ 监听=qq.json listen_retries），代码不写死。retry_on(e) 判可否重试，默认 transient()：HTTP 4xx 不重试（408/425/429 与 5xx 除外）、超时/断连/DNS/OSError/坏 JSON/Retryable 重试；Stopped/KeyboardInterrupt/SystemExit 永不重试（stop 即时中断）。耗尽时抛 Retryable("重试耗尽(N次) ...")，上层据此知道「已经重试过了」不再整轮重发（防重试次数相乘）。用法：python -B retry_io.py selftest。"""
import sys, time
class Retryable(RuntimeError): pass
FATAL = ("Stopped", "KeyboardInterrupt", "SystemExit")
def transient(e):
    if isinstance(e, Retryable): return True
    if type(e).__name__ in FATAL: return False
    try:
        import urllib.error, http.client
        if isinstance(e, urllib.error.HTTPError): return e.code in (408, 425, 429) or e.code >= 500
        return isinstance(e, (urllib.error.URLError, TimeoutError, ConnectionError, OSError, http.client.HTTPException, ValueError))
    except Exception: return True
def call(fn, times=3, base=1.0, cap=8.0, on_try=None, retry_on=None, args=(), kw=None):
    kw = kw or {}; n = max(0, int(times or 0))
    for i in range(n + 1):
        try: return fn(*args, **kw)
        except Exception as e:
            if type(e).__name__ in FATAL or not (retry_on or transient)(e): raise
            if i >= n: raise Retryable("重试耗尽(%d次) %s: %s" % (n, type(e).__name__, str(e)[:120])) from e
            d = min(float(cap), float(base) * (2 ** i))
            try: on_try and on_try(i + 1, n, e, d)
            except Exception: pass
            time.sleep(d)
if __name__ == "__main__":
    box = {"n": 0}
    def flaky():
        box["n"] += 1
        if box["n"] < 3: raise Retryable("boom %d" % box["n"])
        return "ok"
    tries = []
    r = call(flaky, 3, base=0.01, on_try=lambda i, n, e, d: tries.append("%d/%d" % (i, n)))
    try:
        call(lambda: (_ for _ in ()).throw(Retryable("dead")), 2, base=0.01)
        out = "NO_RAISE"
    except Retryable as e: out = str(e)[:40]
    print('{"result": "%s", "attempts": %d, "reported": %s, "exhausted": "%s", "zero_retry": %s}' % (
        r, box["n"], tries, out, call(lambda: 1, 0) == 1))
