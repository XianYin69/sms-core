#!/usr/bin/env python3
"""smsocket_boot.py — SMSocket（本机模型路由网关）的自启·判活·接入 SMS（2026-10-06 用户「测试 smsocket 是否可以连接上大模型，如果可以就在 sms 的菜单里添加：在打开 SMS-core 时打开 smsocket，然后把 SMS 接入 smsocket」）。
连通实测（同日，本机 8011 实例）：/v1/chat/completions 非流 1.0s 出「收到」、流式 27 帧、tool_calls 正常、/healthz ok=true → 「能连上」为真，本模块据此落地。
开关＝settings smsocket{enabled,auto_start,attach_gateway,root,config,host,port,boot_timeout}（F4 图形化 / :config set smsocket.<k> <json>）。
判活＝GET http://host:port/healthz 且 ok=true（菜单、顶栏、自愈同一口径；pid 文件只作「谁拉起」的辅助，用户自己用 start.ps1 拉起的实例照样认）。
拉起＝分离子进程 `python -B run.py --config <config>`（cwd=root·日志 <SMS_HOME>/shell/smsocket.log·pid 写 shell/smsocket.pid——该文件已登记进 shell_lifecycle.SVC，故关壳/重启必回收，绝不留成无人认领的常驻进程）。
壳启动与每轮数据流都走 autostart(wait=False)：内核没起就后台拉起，SMS-core 开面绝不因等网关而卡住（实测冷启到 /healthz 就绪约 2–3s）。
接入＝把 llm_gateway.base_url/api_key 指向 SMSocket，原直连参数备份在 llm_gateway.direct；:smsocket detach 或「网关半路死」即刻回退直连——SMS 不能因为代理而断网。attach/detach 幂等，重复调用不覆盖备份。写配置走 atomic_io 直写＋失效 settings 缓存，绝不用 settings.set 整段写 llm_gateway（那会把 api_key 明文记进 event 链）。
用法：python -B smsocket_boot.py status|start|stop|attach|detach|doctor|autostart。"""
import os, sys, json, time, threading, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import no_window, resolve_home, settings, net_util as nu, atomic_io, chains

NAME = "smsocket"
DEF = {"host": "127.0.0.1", "port": 8011, "config": "config.yaml", "boot_timeout": 12}
_T = {"t": 0.0, "ok": None, "busy": False, "fail": 0.0}   # fail＝上次拉起失败时刻：30s 冷却，防每轮数据流反复拉一个起不来的内核   # ok＝判活节流（0.6s）；busy＝同进程防并发起双内核


def cfg(sms=None):
    return dict(DEF, **(settings.get("smsocket", {}, sms) or {}))


def url(path="/", sms=None):
    c = cfg(sms)
    return "http://%s:%s%s" % (c.get("host") or DEF["host"], int(c.get("port") or DEF["port"]), path)


def base(sms=None):
    return url("/v1", sms)


def key(sms=None):
    """客户端主密钥：root 下 smsocket.key（改名前的 router.key 兼容）；都没有＝对端以 --no-key 起法。"""
    root = cfg(sms).get("root") or ""
    for f in ("smsocket.key", "router.key"):
        p = os.path.join(root, f)
        if os.path.isfile(p):
            return (open(p, encoding="utf-8").read() or "").strip() or None
    return None


def health(timeout=0.6, sms=None):
    """就绪判据：/healthz 且 ok=true（回 dict，不通回 None）——providers/models/egc 一并带出供状态行用。"""
    import urllib.request
    try:
        with urllib.request.urlopen(url("/healthz", sms), timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        return d if isinstance(d, dict) and d.get("ok") else None
    except Exception:
        return None


def alive(sms=None, force=False):
    now = time.time()
    if not force and now - _T["t"] < 0.6:
        return _T["ok"]
    _T.update(t=now, ok=health(sms=sms) is not None)
    return _T["ok"]


def _ps(q, timeout=8):
    try:
        o = no_window.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", q],
                          capture_output=True, text=True, timeout=timeout, errors="replace")
        return (o.stdout or "").strip()
    except Exception:
        return ""


def pid(sms=None, deep=True):
    """在跑的 SMSocket pid。deep=False＝只读 pid 文件（壳启动/顶栏高频路径，零 PowerShell·实测差 2s）；
    deep=True＝再按监听端口反查（用户用 start.ps1 手拉、本机没写过 pid 文件时也认）。"""
    p = nu.running(NAME)
    if p:
        return p if not deep or "run.py" in _ps("(Get-CimInstance Win32_Process -Filter 'ProcessId=%d').CommandLine" % p) else None
    if not deep:
        return None
    s = _ps("(Get-NetTCPConnection -LocalPort %d -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess"
            % int(cfg(sms).get("port") or DEF["port"]))
    return int(s) if s.isdigit() else None


def _gw_write(mut, sms=None):
    """改 llm_gateway 的唯一写口：直读直写 config.json（atomic_io）＋失效 settings 缓存。
    不用 settings.set("llm_gateway", dict)——它把整段值明文记进 event 链，api_key 会泄进记忆。"""
    sms = sms or resolve_home.ensure()
    p = os.path.join(sms, "config", "config.json")
    doc = atomic_io.rjson(p, default={}) or {}
    g = dict(doc.get("llm_gateway") or {})
    out = mut(g)
    if out is False:
        return False
    doc["llm_gateway"] = g
    atomic_io.wjson(p, doc)
    settings._G.update(t=0.0, d=None)
    return True


def spawn(sms=None, wait=None):
    """分离拉起 SMSocket 内核（已在跑＝零成本）。wait=None 跟随参数·False＝后台拉不等（壳启动用）。"""
    c = cfg(sms)
    if alive(sms, force=True):
        return "已在跑：" + url(sms=sms)
    if _T["busy"]:
        return "拉起中（另一线程已在拉起）"
    root = c.get("root") or ""
    if not os.path.isfile(os.path.join(root, "run.py")):
        _T["fail"] = time.time(); return "失败：smsocket.root 未配置或无 run.py（:config set smsocket.root \"C:\\...\\smsocket\"）"
    sms = sms or resolve_home.ensure()
    argv = [sys.executable, "-B", os.path.join(root, "run.py"),
            "--config", os.path.join(root, c.get("config") or DEF["config"])]

    def _go():
        _T["busy"] = True
        try:
            log = open(os.path.join(sms, "shell", NAME + ".log"), "a")
            pr = no_window.Popen(argv, cwd=root, stdin=subprocess.DEVNULL, stdout=log, stderr=log, sms_detach=True)
            open(nu.pidfile(NAME), "w").write(str(pr.pid))
            end = time.time() + float(c.get("boot_timeout") or DEF["boot_timeout"])
            while time.time() < end:
                if health(sms=sms) is not None:
                    _T.update(t=0.0, ok=True)
                    chains.record("event", "SMSocket 自启成功 pid=%s %s" % (pr.pid, url(sms=sms)))
                    if cfg(sms).get("attach_gateway", True) and not attached(sms):
                        attach(sms)   # 后台拉起成功即接入，不等下一轮数据流（否则「打开 SMS-core 就接入」要慢一轮）
                    return
                if pr.poll() is not None:
                    try: os.remove(nu.pidfile(NAME))
                    except Exception: pass
                    _T["fail"] = time.time()
                    chains.record("event", "SMSocket 内核退出 rc=%s" % pr.returncode)
                    return
                time.sleep(0.3)
        except Exception as e:
            _T["fail"] = time.time()
            chains.record("event", "SMSocket 拉起异常：" + str(e)[:120])
        finally:
            _T["busy"] = False
            if not alive(sms, force=True):
                _T["fail"] = time.time()
            _T["t"] = 0.0
    if wait is False:
        threading.Thread(target=_go, daemon=True).start()
        return "后台拉起中（不阻塞·就绪后自动接入）"
    _go()
    return "已启动 " + url(sms=sms) if alive(sms, force=True) else "启动失败（日志 shell/%s.log）" % NAME


def stop(sms=None):
    p = pid(sms)
    if not p:
        nu.clear(NAME)
        return "未运行"
    try:
        no_window.run(["taskkill", "/PID", str(p), "/T", "/F"], capture_output=True, timeout=15)
    except Exception as e:
        return "失败：taskkill " + str(e)[:100]
    nu.clear(NAME)
    _T.update(t=0.0, ok=None)
    return "已停止 pid=%s" % p


def attached(sms=None):
    """SMS 当前 llm_gateway 是否指向 SMSocket。"""
    g = settings.get("llm_gateway", {}, sms) or {}
    return str(g.get("base_url") or "").rstrip("/") == base(sms).rstrip("/")


def attach(sms=None):
    """接入：base_url/api_key 指向 SMSocket，原直连参数备份进 llm_gateway.direct（幂等·不覆盖已有备份）。"""
    if not alive(sms, force=True):
        return "拒绝接入：SMSocket 未就绪（:smsocket start）"
    if attached(sms):
        return "已接入：" + base(sms)
    def mut(g):
        if not g.get("direct"):
            g["direct"] = {"base_url": g.get("base_url"), "api_key": g.get("api_key"),
                           "api_key_env": g.get("api_key_env")}
        g["base_url"] = base(sms)
        g["api_key"] = key(sms) or ""
        g["api_key_env"] = None
        g["enabled"] = True
        return True
    _gw_write(mut, sms)
    chains.record("event", "SMS 接入 SMSocket：%s（原直连备份 llm_gateway.direct）" % base(sms))
    return "已接入：" + base(sms) + "（原直连已备份，:smsocket detach 回退）"


def detach(sms=None):
    """回退直连：还原 llm_gateway.direct 备份。"""
    g = settings.get("llm_gateway", {}, sms) or {}
    if not attached(sms):
        return "未接入（当前 base_url=%s）" % g.get("base_url")
    d = g.get("direct") or {}
    if not d.get("base_url"):
        return "无法回退：llm_gateway.direct 备份缺失，请手改 :config set llm_gateway.base_url <上游地址>"
    def mut(gg):
        gg["base_url"], gg["api_key"] = d["base_url"], d.get("api_key") or ""
        gg["api_key_env"] = d.get("api_key_env")
        gg.pop("direct", None)
        return True
    _gw_write(mut, sms)
    chains.record("event", "SMS 退出 SMSocket，回退直连 %s" % d.get("base_url"))
    return "已回退直连：" + str(d.get("base_url"))


def autostart(sms=None, wait=False):
    """壳启动（shell_core.startup_block）与每轮数据流（agent_stream.ask）同径调用。
    默认 wait=False：内核没起＝后台线程拉起，本轮照旧直连，下轮自动接入——SMS-core 开面绝不因等代理而卡。
    网关死了而 SMS 还指着它＝立刻回退直连（绝不让 SMS 因代理断网）。异常吞掉记 error 链。"""
    c = cfg(sms)
    try:
        if not c.get("enabled", True):        # 停用＝不许再把 SMS 挂在网关上（回退直连后才交还）
            if attached(sms):
                detach(sms)
                return "smsocket.enabled=false，已回退直连"
            return None
        msg = None
        up = alive(sms)
        if not up and c.get("auto_start", True) and time.time() - _T["fail"] > 30:
            msg = spawn(sms, wait=wait)      # 自启关＝不拉，但下面的失联回退照跑（安全网不随自启关而关）
            up = alive(sms, force=True)
        if up:
            if c.get("attach_gateway", True) and not attached(sms):
                a = attach(sms)
                if "拒绝" not in a:
                    msg = (msg + " · " if msg else "") + a
        elif attached(sms):
            detach(sms)
            msg = (msg + " · " if msg else "") + "网关失联，已回退直连"
        return msg
    except Exception as e:
        try:
            import chain_error
            chain_error.hook("gate", "smsocket_boot.autostart", str(e)[:200])
        except Exception:
            pass
        return None


def status(sms=None, cheap=False):
    """cheap=True＝壳启动/顶栏用：判活走 0.6s 节流缓存、pid 只读 pid 文件（不跑 PowerShell）。"""
    c = cfg(sms)
    h = health(sms=sms) if not cheap else ({"ok": True} if alive(sms) else None)
    g = settings.get("llm_gateway", {}, sms) or {}
    return {"enabled": bool(c.get("enabled", True)), "auto_start": bool(c.get("auto_start", True)),
            "attach_gateway": bool(c.get("attach_gateway", True)), "url": url(sms=sms),
            "root": c.get("root") or "", "pid": pid(sms, deep=not cheap) if h else None, "up": bool(h),
            "providers": (h or {}).get("providers"), "models": (h or {}).get("models"),
            "egc": bool(((h or {}).get("egc") or {}).get("enabled")),
            "attached": attached(sms), "gateway_base_url": g.get("base_url"),
            "direct": (g.get("direct") or {}).get("base_url") or None}


def doctor(sms=None):
    """端到端实测：SMSocket 在不在 → 经它向上游问一句话（真出字才算通，不看自报状态）。"""
    st = status(sms)
    if not st["up"]:
        return dict(st, probe="网关未就绪（:smsocket start）")
    import urllib.request
    body = json.dumps({"model": settings.get("llm_gateway.model", "", sms) or "auto",
                       "max_tokens": 32, "messages": [{"role": "user", "content": "只回答一个字：通"}]}).encode()
    hd = {"Content-Type": "application/json"}
    if key(sms):
        hd["Authorization"] = "Bearer " + key(sms)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(urllib.request.Request(base(sms) + "/chat/completions", data=body, headers=hd), timeout=60) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        msg = ((d.get("choices") or [{}])[0].get("message") or {}).get("content")
        return dict(st, probe="ok %.0fms 上游回=%r" % ((time.perf_counter() - t0) * 1000, (msg or "")[:20]))
    except Exception as e:
        return dict(st, probe="fail " + str(e)[:160])


if __name__ == "__main__":
    a = (sys.argv[1:] or ["status"])[0]
    sms = resolve_home.ensure()
    if a == "start":
        print(spawn(sms, wait=True))
    elif a == "stop":
        print(stop(sms))
    elif a == "attach":
        print(attach(sms))
    elif a == "detach":
        print(detach(sms))
    elif a == "doctor":
        print(json.dumps(doctor(sms), ensure_ascii=False, indent=1))
    elif a == "autostart":
        print(autostart(sms, wait=True) or "ok（已在跑/已接入）")
    else:
        print(json.dumps(status(sms), ensure_ascii=False, indent=1))
