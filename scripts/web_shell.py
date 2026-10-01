#!/usr/bin/env python3
"""web_shell.py — 本地加密网页壳：HTTPS 绑 web_shell.host:port（默认 127.0.0.1:8737），自签指纹证书＋配对 token（常时比较·Host 防重绑定）；页面＝对话（等同 sms-shell 含 : 元指令）、配置系统（llm_gateway/chains/dream/模型参数，api_key 掩码只写不读）、上游模型元数据刷新、链设置与对外端口状态（对外开关属高危面须 confirm=yes，服务本体在 external.py＋PQ 验签）。批23 TUI 对齐：只读端点 commands/sessions/tasks/plans/chains/perms/hud/qq/tts/skills/files/file/detail/token(reveal)/ask ＋ 动作端点 plan/add·pause·run、task/status、stop、resume、file/save、grant、tts/say、qq/test·img——每端点 try/except 兜底 {"err":…}（前端据此打「卡纸 JAM」条，绝不 500 断流）；token 显影仅本机回环＋有效 token。用法：python -B web_shell.py start|serve|stop|status|token [--rotate]|fingerprint。"""
import os, sys, json, time, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import net_util, settings, model_meta, web_certs, resolve_home, atomic_io
import session_reg as _sreg
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
NAME = "web_shell"; S = os.path.dirname(os.path.abspath(__file__)); SMS = resolve_home.ensure
KC = os.path.realpath(os.path.dirname(os.path.dirname(os.path.dirname(S))))
def _err(e): return {"err": "%s: %s" % (type(e).__name__, str(e)[:180])}
def _m(n):
    import importlib; return importlib.import_module(n)
def _roots(w=False):
    ws = _m("workspace"); out = []
    for p in [ws.current(), ws.vroot()] + list(ws.list_ws() or []) + (
            [os.path.join(SMS(), "tmp")] if w else [SMS(), S]):
        try: out.append(os.path.realpath(str(p)))
        except Exception: pass
    return [x for x in out if x]
def _under(p, w=False):
    q = os.path.realpath(os.path.abspath(os.path.expanduser(str(p or ""))))
    if not any(q == r or q.startswith(r + os.sep) for r in _roots(w)): return ""
    if w and q.startswith(os.path.realpath(KC) + os.sep) and not _m("permissions").allow(SMS(), "danger"): return ""
    return q
def _meta():
    try:
        ln = next((l for l in open(os.path.join(S, "shell_tui.py"), encoding="utf-8", errors="replace") if l.startswith("META =")), "")
        return [":" + x for x in __import__("re").findall(r'"([a-z_]+)"', ln)]
    except Exception:
        return []
def g_commands(q=None):
    c = _m("commands").collect(SMS())
    return {"commands": c.get("commands") or [], "meta": _meta(), "schema": c.get("schema"),
            "version": c.get("version"), "generated_at": c.get("generated_at"),
            "count": len(c.get("commands") or [])}
def g_sessions(q=None):
    sr = _m("session_reg"); tt = _m("task_table"); reg = sr.list_(); cur = sr.current(); un = {}
    for tid in tt._all():
        d = tt._load(tid) or {}; s = str(d.get("sess") or "")
        n = len([x for x in (d.get("subtasks") or []) if str(x.get("status")) not in ("done", "error", "stopped")])
        if n: un[s] = un.get(s, 0) + n
    out = [{"id": k, "session": k, "created": v.get("created"), "at": v.get("created"), "name": v.get("name"),
            "kind": v.get("kind"), "state": v.get("state"), "conv": v.get("conv"),
            "last_active": v.get("last_active"), "unfinished": un.get(k, 0),
            "convs": v.get("convs") or ([v["conv"]] if v.get("conv") else []), "conv_count": len(v.get("convs") or []),
            "current": bool(cur) and k == cur} for k, v in reg.items()]
    out.sort(key=lambda x: str(x["created"] or ""))
    return {"sessions": out, "current": cur, "count": len(out),
            "conflicts": [x["id"] for x in out if x["unfinished"]]}
def g_tasks(q=None):
    tt = _m("task_table"); q = q or {}; ids = tt._all(); un = tt.unfinished() or []
    tid = str(q.get("tid") or "") or (un[-1][0] if un else (ids[-1] if ids else ""))
    doc = (tt._load(tid) if tid else {}) or {}; subs = doc.get("subtasks") or []
    rows = [{"id": x.get("id"), "row": x.get("id"), "title": x.get("goal"), "goal": x.get("goal"),
             "step": x.get("goal"), "status": x.get("status"), "lane": x.get("lane") or "fg",
             "skill": x.get("skill"), "inst": x.get("inst")} for x in subs]
    dn = len([r for r in rows if r["status"] == "done"])
    try: eta = _m("msg_flow").fmt(tt.eta(doc)) if doc else "-"
    except Exception: eta = "-"
    return {"tid": doc.get("id") or tid, "id": doc.get("id") or tid, "intent": doc.get("intent"),
            "conv": doc.get("conv"), "sess": doc.get("sess"), "created": doc.get("created"),
            "rows": rows, "tasks": rows, "done": dn, "total": len(rows), "unfinished": len(rows) - dn,
            "eta": eta, "tables": ids[-12:], "pending": [list(x) for x in un]}
def g_plans(q=None):
    pt = _m("planned_tasks"); out = []
    for e in pt.scan():
        d = e.get("doc")
        if not isinstance(d, dict) or pt.is_template(e.get("path"), d): continue
        sc = d.get("schedule") or {}
        out.append({"id": d.get("id"), "title": d.get("title"),
                    "at": d.get("next_run") or sc.get("at") or sc.get("cron") or sc.get("every_min"),
                    "spec": str(sc.get("mode") or "") + " " + str(sc.get("at") or sc.get("cron") or sc.get("every_min") or ""),
                    "cmd": d.get("input"), "text": d.get("input"), "status": d.get("status"),
                    "skill": d.get("skill"), "runs": d.get("runs"), "last_run": d.get("last_run"),
                    "errors": e.get("errors") or [], "dir": e.get("skill_dir"), "path": e.get("path")})
    return {"plans": out, "items": out, "count": len(out)}
def g_chains(q=None):
    ch = _m("chains"); st = ch.store(); per = {}
    for f in st.all_frags() or []:
        if not isinstance(f, dict): continue
        c = str(f.get("chain") or "?"); e = per.setdefault(c, {"frags": 0, "freq": 0, "last": ""})
        e["frags"] += 1; e["freq"] += int(f.get("freq") or 1)
        if str(f.get("ts") or "") > e["last"]: e["last"] = str(f.get("ts") or "")
    cfg = (settings.status(SMS()) or {}).get("chains") or {}
    rows = [{"chain": k, "name": k, "frags": v["frags"], "count": v["frags"], "freq": v["freq"], "last": v["last"],
             "enabled": (cfg.get(k) or {}).get("enabled") if isinstance(cfg.get(k), dict) else None}
            for k, v in sorted(per.items())]
    return {"chains": rows, "stats": {k: v["frags"] for k, v in per.items()},
            "total": sum(v["frags"] for v in per.values()), "config": cfg, "names": list(ch.CHAINS),
            "sess": ch.cur_sess(), "sessions": [x for x in str(ch.list_sess() or "").split("\n") if x][-10:]}
def _solo_state():
    """SOLO 状态（web 主输出窗口提示与风险告知用）：惰性 import，取不到一律 {"enabled": false}，绝不让 /api/perms 500。"""
    try:
        return _m("solo").status(SMS()) or {"enabled": False}
    except Exception:
        return {"enabled": False}
def g_perms(q=None):
    pm = _m("permissions"); eff = pm._eff(SMS()); e = eff.get("effective") or {}; src = eff.get("source") or {}
    DESC = {"read": "读文件·读链", "write": "写工作区文件", "execute": "本机命令执行", "network": "外网检索",
            "privacy": "背景隐私采集", "vault": "密钥库", "verify": "签名校验",
            "danger": "写 skill 目录／收编（红线16·当日单独 grant）"}
    perms = [{"name": k, "key": k, "on": bool(v), "status": "on" if v else "off", "desc": DESC.get(k, k),
              "note": DESC.get(k, k), "source": src.get(k, ""), "grant": (eff.get("grants") or {}).get(k)}
             for k, v in e.items()]
    tools = [{"name": k, "tool": k, "enabled": bool(v), "on": bool(v), "desc": "大模型工具开关"}
             for k, v in ((settings.status(SMS()) or {}).get("agent_tools") or {}).items()]
    return {"perms": perms, "items": perms, "grants": perms, "tools": tools, "roles": list(pm.ROLES),
            "count": len(perms), "tool_count": len(tools), "solo": _solo_state()}
def g_hud(q=None):
    d = atomic_io.rjson(os.path.join(SMS(), "hud", "state.json"), encoding="utf-8", default=None) or {}
    now = time.time(); live = {}
    for k in ("session", "step", "alert"):
        if d.get(k) and float(d.get(k + "_expires") or 0) > now: live[k] = d.get(k)
    return {"hud": live, "session": live.get("session", ""), "step": live.get("step", ""),
            "alert": live.get("alert", ""), "raw": d, "ttl": {k: round(float(d.get(k + "_expires") or 0) - now) for k in ("session", "step", "alert")}}
def g_qq(q=None):
    qc = _m("qq_cli"); st = qc.status() or {}
    try: w = _m("qq_watch").status()
    except Exception: w = {}
    on = str(st.get("开关") or "").lower() == "on"
    return {"enabled": on, "on": on, "bound": bool(st.get("已绑定")), "has_creds": bool(st.get("已绑定")),
            "sent_today": st.get("今日已推"), "daily_limit": st.get("日上限"), "outbox": st.get("outbox积压"),
            "appId": st.get("appId"), "clientSecret": st.get("clientSecret"), "openid": st.get("openid"),
            "listening": (w.get("pid") or None) if w.get("running") else None,
            "alive": "%s·%s" % (w.get("state"), w.get("beat_age")) if w else "-", "watch": w, "status": st}
def g_tts(q=None):
    t = _m("tts"); d = t.status()
    if isinstance(d, str):
        try: d = json.loads(d)
        except Exception: d = {"raw": d}
    try: vs = t.voices()
    except Exception: vs = []
    return {"enabled": bool(d.get("on")), "on": bool(d.get("on")), "voice": d.get("voice"),
            "profile": d.get("profile"), "engine": d.get("engine"), "status": d, "voices": vs}
def g_skills(q=None):
    out = []
    for s in _m("skill_route").skills(SMS()) or []:
        ip = str(s.get("install_path") or ""); en = str(s.get("entry") or "SKILL.md")
        out.append({"id": s.get("id"), "skill_id": s.get("id"), "name": s.get("name"),
                    "desc": s.get("description"), "description": s.get("description"),
                    "path": os.path.join(ip, en), "skill_md": os.path.join(ip, en), "dir": ip,
                    "kind": s.get("kind"), "status": s.get("status"), "tools": s.get("tools"),
                    "trust": s.get("trust"), "updated_at": s.get("updated_at")})
    return {"skills": out, "items": out, "count": len(out)}
def g_files(q=None):
    ws = _m("workspace"); cur = (q or {}).get("ws") or ws.current(); root = _under(cur)
    if not root or not os.path.isdir(root): return {"err": "目录不存在或未登记：" + str(cur)[:120]}
    try: it = sorted(os.scandir(root), key=lambda x: (not x.is_dir(), x.name.lower()))
    except Exception as e: return _err(e)
    out = []
    for x in it[:400]:
        if x.name in (".git", "__pycache__", "node_modules"): continue
        try: out.append({"name": x.name, "path": x.path, "size": x.stat().st_size,
                         "type": "dir" if x.is_dir() else "file"})
        except Exception: out.append({"name": x.name, "path": x.path, "size": None})
    return {"ws": root, "current": ws.current(), "files": out, "items": out, "count": len(out),
            "workspaces": ws.list_ws()}
def g_file(q=None):
    q = q or {}; p = _under(q.get("path") or "")
    if not p: return {"err": "路径越界或未登记工作区：" + str(q.get("path"))[:120]}
    if not os.path.isfile(p): return {"err": "不是文件：" + p[:160]}
    sz = os.path.getsize(p)
    if sz > 2_000_000: return {"err": "文件过大（>2MB）不预览：" + p[:160]}
    try: t = open(p, encoding="utf-8").read()
    except Exception: return {"path": p, "content": "", "text": "", "size": sz, "err": "二进制或编码不可辨，无法预览"}
    return {"path": p, "content": t, "text": t, "size": sz, "ws": _m("workspace").current()}
def g_detail(q=None):
    p = os.path.join(SMS(), "shell", "detail.json")
    d = atomic_io.rjson(p, encoding="utf-8", default=None)
    if d is None: return {"text": "", "lines": [], "hint": "尚无长输出留档（超阈值输出或 :detail 落此）", "path": p}
    t = "\n".join(str(x) for x in d) if isinstance(d, list) else json.dumps(d, ensure_ascii=False, indent=1)
    return {"text": t, "detail": t, "lines": t.count("\n") + 1, "path": p, "size": len(t)}
def g_ask(q=None):
    ac = _m("ask_channel"); out = []
    try:
        while len(out) < 8:
            x = ac.poll()
            if x is None: break
            out.append({"id": hashlib.sha1(str(x).encode()).hexdigest()[:8], "text": str(x), "q": str(x)})
    except Exception as e:
        return {"err": str(e)[:180], "questions": out}
    return {"questions": out, "items": out, "armed": bool((getattr(ac, "UI", None) or {}).get("armed")),
            "pending": ac.ASK_Q.qsize(), "answered": (getattr(ac, "UI", None) or {}).get("answered")}
def p_plan_add(b):
    pt = _m("planned_tasks"); spec = str(b.get("spec") or b.get("text") or "").strip()
    if not spec: return {"err": "spec 为空（例：5m :dream run）"}
    parts = spec.split(None, 1)
    when, text = (parts[0], parts[1]) if len(parts) > 1 else (str(b.get("when") or ""), spec)
    if not text.strip(): return {"err": "缺要执行的指令文本"}
    r = pt.add(text.strip()[:24], when, text.strip(), str(b.get("skill") or "sms"))
    return {"ok": str(r)[:300], "spec": spec}
def p_plan(op, b):
    pt = _m("planned_tasks"); tid = str(b.get("id") or b.get("tid") or "").strip()
    if not tid: return {"err": "缺计划任务 id"}
    st = {"pause": "paused", "run": "pending", "resume": "pending", "done": "done", "cancel": "paused"}.get(op, "pending")
    r = pt.setstatus(tid, st)
    return {"ok": str(r)[:300], "id": tid, "status": st} if r else {"err": "无此计划任务：" + tid[:80]}
def p_task_status(b):
    tt = _m("task_table"); row = str(b.get("row") or b.get("id") or "").strip()
    if not row: return {"err": "缺行 id（t1/t2…）"}
    un = tt.unfinished() or []; tid = str(b.get("tid") or "") or (un[-1][0] if un else "")
    if b.get("lane"):
        lv = "bg" if str(b.get("lane")).lower() in ("bg", "后台", "back", "background") else "fg"
        r = tt.revise("lane", tid, row, lv)
        return {"ok": str(r)[:200], "row": row, "lane": lv} if not str(r).startswith("无") else {"err": str(r)[:200]}
    st = str(b.get("status") or "done").strip()
    if st not in ("pending", "running", "done", "error", "stopped"): return {"err": "非法状态：" + st[:40]}
    r = tt.revise("status", tid, row, st)
    return {"ok": str(r)[:200], "row": row, "status": st, "tid": tid} if not str(r).startswith("无") else {"err": str(r)[:200]}
def p_stop(b):
    sc = _m("stop_channel"); sc.request(str(b.get("why") or "网页壳 STOP 键"))
    return {"ok": True, "status": sc.status(), "stopped": sc.stopped()}
def p_resume(b):
    tt = _m("task_table"); sc = _m("stop_channel"); sc.clear()
    un = tt.unfinished() or []; tid = str(b.get("tid") or "") or (un[-1][0] if un else "")
    nxt = tt.revise("next", tid) if tid else "无未完成计划表"
    return {"ok": True, "tid": tid, "next": str(nxt)[:200], "status": sc.status()}
def p_file_save(b):
    p = _under(b.get("path") or "", w=True); c = b.get("content")
    if not p: return {"err": "路径越界／未登记工作区（写 skill 目录须 :grant danger）：" + str(b.get("path"))[:120]}
    if not isinstance(c, str): return {"err": "content 须为字符串"}
    if len(c) > 4_000_000: return {"err": "内容过大（>4MB）拒写"}
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True); tmp = p + ".writetmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f: f.write(c)
        os.replace(tmp, p)
    except Exception as e: return _err(e)
    return {"ok": p, "bytes": len(c.encode("utf-8"))}
def p_grant(b):
    pm = _m("permissions"); sms = SMS()
    if b.get("tool"):
        nm = str(b.get("tool")); at = (settings.status(sms).get("agent_tools") or {})
        if nm not in at: return {"err": "无此工具开关：" + nm[:40]}
        v = bool(b.get("on")); return {"ok": settings.set("agent_tools." + nm, v), "tool": nm, "on": v}
    key = str(b.get("key") or b.get("perm") or "").strip()
    if not key: return {"err": "缺权限键或角色（如 network / danger / worker）"}
    if key.split(".")[0] == "external": return {"err": "对外端口属高危面：走 /api/config 带 confirm=yes（红线16/18）"}
    try: ttl = max(0, min(int(b.get("ttl") or 0), 1440))
    except Exception: ttl = 0
    return {"ok": pm.apply(sms, "grant", key, bool(b.get("dry")), ttl), "key": key, "ttl": ttl}
def p_tts_say(b):
    t = _m("tts"); txt = str(b.get("text") or "").strip()[:1000]
    if not txt: return {"err": "空文本"}
    try: r = t.speak(txt, bool(b.get("wait")))
    except Exception as e: return _err(e)
    return {"ok": True, "queued": len(txt), "ret": str(r)[:120]}
def p_qq_test(b):
    qp = _m("qq_push"); c = qp.conf()
    if not qp.ready(c): return {"err": "QQ 未就绪（缺 appId/clientSecret/openid 或开关已关·:qq bind / :qq on）"}
    r = qp.push(str(b.get("text") or "SMS 网页壳自检：QQ 出站链路 OK"), "QQ·test", c)
    return {"ok": bool(r), "ret": str(r)[:160]}
def p_qq_img(b):
    qp = _m("qq_push"); p = _under(b.get("path") or "")
    if not p or not os.path.isfile(p): return {"err": "图片不存在或路径越界：" + str(b.get("path"))[:120]}
    c = qp.conf()
    if not qp.ready(c): return {"err": "QQ 未就绪（:qq bind / :qq on）"}
    r = qp.push(str(b.get("text") or "SMS 截图"), "QQ·img", c, p)
    return {"ok": bool(r), "path": p, "ret": str(r)[:160]}
GETS = {"/api/commands": g_commands, "/api/sessions": g_sessions, "/api/tasks": g_tasks,
        "/api/plans": g_plans, "/api/chains": g_chains, "/api/perms": g_perms, "/api/hud": g_hud,
        "/api/qq": g_qq, "/api/tts": g_tts, "/api/skills": g_skills, "/api/files": g_files,
        "/api/file": g_file, "/api/detail": g_detail, "/api/ask": g_ask}
def _post(self, fn, b):
    try: return net_util.send(self, 200, fn(b))
    except Exception as e: return net_util.send(self, 200, _err(e))
class H(BaseHTTPRequestHandler):
    server_version = "sms-web"; protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def _wk(self): return hashlib.sha1((self.headers.get("X-SMS-Token") or "").encode()).hexdigest()[:8] + "@" + (self.client_address[0] if self.client_address else "?")
    def _auth(self): return net_util.check_token(self.headers.get("X-SMS-Token") or self.headers.get("Authorization", "").removeprefix("Bearer ").strip()) and net_util.host_ok(self.headers.get("Host"))
    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/index.html"): return net_util.send(self, 200, net_util.page(), "text/html; charset=utf-8")
        if not self._auth(): return net_util.send(self, 401, {"err": "需要配对 token（python -B web_shell.py token / :web token）"})
        try: _sreg.bind("web", self._wk(), "Web·GET " + p[:16])
        except Exception: pass
        q = net_util.qs(self)
        if p == "/api/info":
            st = settings.status(); st["fingerprint"] = web_certs.fpr(); st["token_prefix"] = net_util.token()[:6] + "…"
            st["model_meta"]["models"] = model_meta.load().get("models") or {}; return net_util.send(self, 200, st)
        if p == "/api/token":
            if not net_util.local_peer(self.client_address[0]) or str(q.get("reveal") or "") not in ("1", "true", "yes"):
                return net_util.send(self, 403, {"err": "令牌显影仅限本机回环＋reveal=1（其余一律 403）"})
            try: _m("chains").log("session", "web token reveal")
            except Exception: pass
            return net_util.send(self, 200, {"token": net_util.token(), "hint": "明文仅本机回环可见·审计已记链"})
        fn = GETS.get(p)
        if fn:
            try: return net_util.send(self, 200, fn(q))
            except Exception as e: return net_util.send(self, 200, _err(e))
        return net_util.send(self, 404, {"err": "404"})
    def do_POST(self):
        p = self.path.split("?")[0]; b = net_util.body(self)
        if not self._auth(): return net_util.send(self, 401, {"err": "需要配对 token"})
        try: _sreg.bind("web", self._wk(), "Web·POST " + p[:16])
        except Exception: pass
        if p == "/api/chat": return net_util.send(self, 200, net_util.chat(b.get("text")))
        if p == "/api/config":
            path = str(b.get("path", ""))
            if not path or path.split(".")[0] in ("comment", ""): return net_util.send(self, 400, {"err": "无效路径"})
            if path.startswith("external") and b.get("confirm") != "yes": return net_util.send(self, 428, {"err": "对外端口属高危面：须 confirm=yes（resistance #16/#18）"})
            return net_util.send(self, 200, {"ok": settings.set(path, b.get("value"))})
        if p == "/api/models/refresh": return net_util.send(self, 200, model_meta.refresh())
        if p == "/api/token/rotate": return net_util.send(self, 200, {"token": net_util.token(True), "hint": "新 token 已写 shell/web.token 并输出到本地终端；旧 token 即刻失效"})
        if p == "/api/plan/add": return _post(self, p_plan_add, b)
        if p.startswith("/api/plan/"):
            op = p.rsplit("/", 1)[-1]
            return _post(self, lambda x, o=op: p_plan(o, x), b)
        if p == "/api/task/status": return _post(self, p_task_status, b)
        if p == "/api/stop": return _post(self, p_stop, b)
        if p == "/api/resume": return _post(self, p_resume, b)
        if p == "/api/file/save": return _post(self, p_file_save, b)
        if p == "/api/grant": return _post(self, p_grant, b)
        if p == "/api/tts/say": return _post(self, p_tts_say, b)
        if p == "/api/qq/test": return _post(self, p_qq_test, b)
        if p == "/api/qq/img": return _post(self, p_qq_img, b)
        return net_util.send(self, 404, {"err": "404"})
def serve(host=None, port=None):
    c = settings.eff()[NAME]
    if not c.get("enabled", True): return "web_shell.enabled=false——拒绝启动（:config set web_shell.enabled true）"
    host = host or c.get("host", "127.0.0.1"); port = int(port or c.get("port", 8737))
    srv = ThreadingHTTPServer((host, port), H); srv.socket = net_util.ctx().wrap_socket(srv.socket, server_side=True)
    net_util.write_run(NAME, port); model_meta.maybe()
    print("网页壳 https://%s:%d · 证书指纹 %s · token %s" % (host, port, web_certs.fpr()[:16], net_util.token()))
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
    finally: net_util.clear(NAME)
if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]; cmd = a[0]
    if cmd == "status":
        pid = net_util.running(NAME); port = net_util.port_of(NAME) or settings.get(NAME + ".port", 8737)
        print(json.dumps({"running": pid, "port": port, "url": "https://127.0.0.1:%s/" % port, "fingerprint": web_certs.fpr()[:16]}, ensure_ascii=False))
    elif cmd == "start": print("网页端已禁用：先 :config set web_shell.enabled true" if not settings.get(NAME + ".enabled", True) else ("已在运行 pid=" + str(net_util.running(NAME)) if net_util.running(NAME) else net_util.spawn(NAME)))
    elif cmd == "serve": print(serve())
    elif cmd in ("stop", "token", "fingerprint"): print(net_util.stop(NAME) if cmd == "stop" else net_util.token("--rotate" in a) if cmd == "token" else web_certs.fpr())
    else: print(__doc__.strip().splitlines()[-1])
