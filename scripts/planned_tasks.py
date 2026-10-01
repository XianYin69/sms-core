#!/usr/bin/env python3
"""planned_tasks.py — 计划任务读取与调度（SMS 侧真源＝各技能目录 planned_tasks/*.json，由 Skill_Generator 初始化时写入）。
职责：①scan 扫描全部技能 planned_tasks 文件夹并校验 schema；②next_run 按 at/cron/interval 算下次触发；③due 取到点条目；④fire 到点自动执行＝为该计划任务绑定/复用 session（kind=cron）→ 建任务表（task_table.plan）→ 把任务表与执行记录挂到该 session 关联链（chains.record）→ 交 runner（默认 shell_core.handle，模型会先向用户询问细节再执行）→ 回写 status/last_run/next_run/runs；⑤tick 节流扫描并触发；⑥CLI：ls/validate/add/show/pause/resume/run/tick/serve。
约束（与 Skill_Generator README 一致）：一任务一文件、原子写、status 仅 pending/running/done/paused/failed、时间一律本地 ISO、技能自身不执行计划任务（只有本模块执行）。
用法：python -B planned_tasks.py ls | validate | add "<标题>" "<时间>" "<诉求>" [技能id] | show <id> | pause <id> | resume <id> | run <id> | tick | serve | selftest"""
import os, sys, json, time, glob, re, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, atomic_io, settings, chains, session_reg, task_table as tt
SMS = resolve_home.ensure()
DIRNAME = "planned_tasks"
ROOTS = [os.path.expanduser("~/.kilocode/skills"),
         os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sub_skills")]
STATUS = ("pending", "running", "done", "paused", "failed")
FIELDS = ("id", "title", "skill", "input", "schedule", "session", "status", "created", "next_run")
NOW = lambda: datetime.datetime.now()
ISO = lambda dt=None: (dt or NOW()).strftime("%Y-%m-%dT%H:%M:%S")

def _field(spec, val, lo, hi):
    spec = str(spec).strip()
    if spec in ("*", "?"): return True
    for part in spec.split(","):
        part = part.strip()
        step = 1
        if "/" in part:
            part, st = part.split("/", 1)
            try: step = max(1, int(st))
            except Exception: continue
        if part in ("*", ""): rng = range(lo, hi + 1)
        elif "-" in part:
            a, b = part.split("-", 1)
            try: rng = range(int(a), int(b) + 1)
            except Exception: continue
        else:
            try: rng = range(int(part), int(part) + 1)
            except Exception: continue
        if val in rng and (val - rng.start) % step == 0: return True
    return False

def _dow(spec, dow):
    """星期字段（标准 cron）：0 与 7 同为周日、1..6＝周一..周六；* 照常。"""
    return _field(spec, dow, 0, 7) or (dow == 0 and _field(spec, 7, 0, 7))

def cron_hit(expr, dt):
    f = str(expr or "").split()
    if len(f) != 5: return False
    dow = 0 if dt.weekday() == 6 else dt.weekday() + 1
    return (_field(f[0], dt.minute, 0, 59) and _field(f[1], dt.hour, 0, 23)
            and _field(f[2], dt.day, 1, 31) and _field(f[3], dt.month, 1, 12)
            and _dow(f[4], dow))

def cron_never(expr):
    """静态判「永不命中」并返回出错字段名（合法返回空串）——免跑全年逐分钟扫描。"""
    f = str(expr or "").split()
    if len(f) != 5: return "字段数≠5"
    if not any(_field(f[0], v, 0, 59) for v in range(60)): return "分钟"
    if not any(_field(f[1], v, 0, 23) for v in range(24)): return "小时"
    if not any(_field(f[2], v, 1, 31) for v in range(1, 32)): return "日"
    if not any(_field(f[3], v, 1, 12) for v in range(1, 13)): return "月"
    if not any(_dow(f[4], v) for v in range(7)): return "星期"
    return ""

def cron_next(expr, frm=None):
    if cron_never(expr): return None  # 判死即返，不再空跑一年
    t = (frm or NOW()).replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)
    for _ in range(0, 366 * 24 * 60):
        if cron_hit(expr, t): return t
        t += datetime.timedelta(minutes=1)
    return None

def parse_at(s):
    """本地 ISO/日期时间/裸时刻解析；裸时刻（HH:MM）取今日，已过则顺延明日。"""
    t = str(s or "").strip().replace("/", "-")
    if not t: return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try: return datetime.datetime.strptime(t, fmt)
        except Exception: pass
    if (m := re.match(r"^(\d{1,2}):(\d{2})(:(\d{2}))?$", t)):
        n = NOW()
        dt = n.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=int(m.group(4) or 0), microsecond=0)
        return dt if dt > n else dt + datetime.timedelta(days=1)
    return None
def roots():
    out = []
    for r in ROOTS:
        if os.path.isdir(r): out.append(r)
    return out

def extra_dirs():
    """SMS 级计划任务目录（不属于任何技能的全局定时项）。"""
    return [os.path.join(SMS, DIRNAME)]

def paths():
    p = [g for d in extra_dirs() for g in glob.glob(os.path.join(d, "*.json"))]
    for r in roots():
        p += glob.glob(os.path.join(r, "*", DIRNAME, "*.json"))
        p += glob.glob(os.path.join(r, "skill", "sub_skills", "*", DIRNAME, "*.json"))
    return sorted(set(p))

STATUS_ = STATUS
FIELDS_ = FIELDS

def bad(doc):
    e = [f"缺字段 {k}" for k in FIELDS if k not in doc]
    if str(doc.get("status", "")) not in STATUS: e.append("status 非法：" + str(doc.get("status")))
    if not isinstance(doc.get("schedule"), dict): e.append("schedule 必须是对象")
    elif str(doc["schedule"].get("mode", "")) not in ("at", "cron", "interval"): e.append("schedule.mode 非法（须 at|cron|interval）")
    elif str(doc["schedule"].get("mode", "")) == "cron":
        nf = cron_never(doc["schedule"].get("cron", ""))
        if nf: e.append("cron 永不命中（%s 字段无解），请检查星期字段：%s" % (nf, doc["schedule"].get("cron")))
    if not str(doc.get("input", "")).strip(): e.append("input 为空")
    return e

def load(path):
    try: doc = json.load(open(path, encoding="utf-8"))
    except Exception as ex: return None, ["JSON 解析失败：" + str(ex)[:120]]
    return doc, bad(doc)

def is_template(path, doc):
    """模板/示例文件（template.json 或 id 含占位符 <）不参与校验与调度。"""
    return os.path.basename(str(path)) == "template.json" or "<" in str(doc.get("id", ""))

def scan():
    out = []
    for p in paths():
        doc, err = load(p)
        if doc is not None and is_template(p, doc): err = []
        if doc is None: out.append({"path": p, "doc": {"id": os.path.basename(p)}, "errors": err}); continue
        out.append({"path": p, "doc": doc, "errors": err,
                    "skill_dir": os.path.basename(os.path.dirname(os.path.dirname(p)))})
    return out

def next_run(doc, frm=None):
    sc = doc.get("schedule") or {}; mode = str(sc.get("mode", ""))
    if mode == "at":
        dt = parse_at(sc.get("at") or doc.get("next_run") or "")
        if dt and dt > (frm or NOW()): return dt
        return dt if dt else None
    if mode == "interval":
        base = parse_at(doc.get("last_run") or "") or frm or NOW()
        return base + datetime.timedelta(minutes=max(1, int(sc.get("every_min") or 60)))
    if mode == "cron": return cron_next(sc.get("cron", ""), frm)
    return None

def brief(doc):
    return "%-22s %-8s %-10s %-19s %s" % (str(doc.get("id"))[-22:], doc.get("status"),
                                          str((doc.get("schedule") or {}).get("mode")),
                                          str(doc.get("next_run") or "-"), str(doc.get("title") or "")[:26])

def _save(path, doc): atomic_io.wjson(path, doc)

def utter(doc, sid=""):
    return ("计划任务到点自动执行〔%s〕《%s》：\n%s\n"
            "要求：①细节不足先用 ask_user 逐项询问用户（范围/产物/通知渠道）；"
            "②据回答用 task_plan op=plan 建计划任务表并按表推进到全部行 done；"
            "③本任务绑定 session=%s，执行过程与结论挂到该 session 关联链；"
            "④完成后 user_send 一句回报。") % (doc.get("id"), doc.get("title"), doc.get("input"), sid)

def _default_runner(text):
    import runtime_bind as rb
    buf = []
    r = rb.run(text, lambda s: buf.append(str(s)[:300]))
    if isinstance(r, str) and (r.startswith("未绑定壳") or r.startswith("壳执行异常")): buf.append(r)
    return "\n".join(buf[-40:])

def _lock(path):
    """跨进程互斥：同一任务文件同时只允许一个执行者（TUI 内 tick 与后台 serve 并存时防双触发）。"""
    lk = path + ".lock"
    try:
        if os.path.exists(lk) and time.time() - os.path.getmtime(lk) > 900: os.remove(lk)
        fd = os.open(lk, os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, str(os.getpid()).encode()); os.close(fd)
        return lk
    except FileExistsError:
        return None
    except Exception:
        return None

def _unlock(lk):
    try: lk and os.remove(lk)
    except Exception: pass

def fire(entry, runner=None):
    doc, path = entry["doc"], entry["path"]
    lk = _lock(path)
    if not lk: return "skipped", "已有执行者持锁（防双触发）"
    mode = str((doc.get("schedule") or {}).get("mode", ""))
    sid = session_reg.ensure("cron", "%s:%s" % (doc.get("skill"), doc.get("id")), name=str(doc.get("title") or "")[:40])
    prev = dict(chains.ACTIVE)  # 红线17 防跨对话污染：触发期临时改归属，收口必还原
    conv = chains.session_id(); chains.set_active(conv=conv, sess=sid); session_reg.attach(conv, sid)
    now = NOW()
    doc.update(status="running", last_run=ISO(now), runs=int(doc.get("runs") or 0) + 1)
    nxt = next_run(doc, frm=now) if mode in ("cron", "interval") else None
    doc["next_run"] = ISO(nxt) if nxt else ""
    _save(path, doc)
    chains.record("session", "计划任务触发 %s《%s》→ conv=%s sess=%s" % (doc.get("id"), doc.get("title"), conv, sid))
    try:
        out = (runner or _default_runner)(utter(doc, sid))
        doc["status"] = "failed" if "执行异常" in str(out) else ("done" if mode == "at" and not nxt else "pending")
    except Exception as ex:
        doc["status"] = "failed"; out = "执行异常：" + repr(ex)[:200]; _save(path, doc)
    _save(path, doc)
    chains.record("session", "计划任务收口 %s → %s" % (doc.get("id"), doc["status"]))
    _unlock(lk)
    chains.set_active(conv=prev.get("conv") or "", sess=prev.get("sess") or "")
    return doc["status"], str(out)[:400]

def start(sms=None):
    """拉起分离的调度进程（同 dream_bg/qq_listen 范式）：已有活着的 serve 就跳过。"""
    import subprocess
    sms = sms or SMS
    d = os.path.join(sms, "planned"); os.makedirs(d, exist_ok=True)
    pf = os.path.join(d, "serve.pid")
    try:
        if os.path.exists(pf):
            pid = int((open(pf, encoding="utf-8").read() or "0").strip() or 0)
            r = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid], capture_output=True, text=True, errors="replace")
            if str(pid) in (r.stdout or ""): return "调度进程已在运行（pid %d）" % pid
    except Exception: pass
    logf = open(os.path.join(d, "serve.log"), "a", encoding="utf-8")
    kw = {"creationflags": 0x8 | 0x08000000} if os.name == "nt" else {"start_new_session": True}
    pr = subprocess.Popen([sys.executable, "-B", os.path.abspath(__file__), "serve"], stdin=subprocess.DEVNULL, stdout=logf, stderr=logf, cwd=os.path.dirname(os.path.abspath(__file__)), **kw)
    open(pf, "w", encoding="utf-8").write(str(pr.pid))
    return "计划任务调度进程已拉起（pid %d·日志 planned/serve.log）" % pr.pid

def due(now=None):
    now = now or NOW(); out = []
    for e in scan():
        d = e["doc"]
        if e["errors"] or is_template(e["path"], d) or str(d.get("status")) not in ("pending", ""): continue
        if (nr := parse_at(d.get("next_run") or "")) and nr <= now: out.append(e)
    return out

_T = [0.0]
def tick(force=False, gap=30):
    if not force and time.time() - _T[0] < gap: return []
    _T[0] = time.time()
    if not settings.get("planned.enabled", True): return []
    res = []
    for e in due():
        try: res.append((e["doc"].get("id"),) + fire(e))
        except Exception as ex: res.append((e["doc"].get("id"), "failed", repr(ex)[:200]))
    return res

def serve():
    print("计划任务调度已启·扫描根：%s" % "、".join(roots()))
    while True:
        for r in tick(force=True): print("触发：", r)
        time.sleep(max(5, int(settings.get("planned.tick_sec", 30))))

def infer(when):
    w = str(when).strip()
    if len(w.split()) == 5: return {"mode": "cron", "cron": w}
    if w.startswith("+") and w[1:].isdigit(): return {"mode": "interval", "every_min": int(w[1:])}
    return {"mode": "at", "at": w}

def add(title, when, text, skill="sms"):
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(title))[:24].strip("-").lower() or "task"
    pid = "pt-%s-%s" % (skill, slug)
    doc = {"id": pid, "title": title, "skill": skill, "input": text, "schedule": infer(when),
           "session": {"kind": "cron", "key": skill + ":" + pid}, "status": "pending",
           "created": ISO(), "next_run": "", "last_run": None, "runs": 0, "notify": "shell", "depends": []}
    nr = next_run(doc)
    doc["next_run"] = ISO(nr) if nr else ""  # 永不命中＝留空，绝不写「现在」防立即触发
    base = os.path.join(roots()[0], skill) if os.path.isdir(os.path.join(roots()[0], skill)) else SMS
    d = os.path.join(base, DIRNAME); os.makedirs(d, exist_ok=True)
    p = os.path.join(d, pid + ".json"); _save(p, doc)
    errs = bad(doc)
    return "已登记计划任务 %s → %s（下次 %s）%s" % (pid, p, doc["next_run"] or "—",
            ("" if not errs else "  ⚠校验：" + "；".join(errs)))

def setstatus(tid, status):
    for e in scan():
        if str(e["doc"].get("id")) == str(tid) or str(e["path"]) == str(tid):
            e["doc"]["status"] = status
            if status == "pending" and not e["doc"].get("next_run"):
                _nr = next_run(e["doc"]); e["doc"]["next_run"] = ISO(_nr) if _nr else ""
            _save(e["path"], e["doc"]); return "已置 %s → %s" % (e["doc"].get("id"), status)
    return "未找到计划任务：" + str(tid)

def find(tid):
    return next((e for e in scan() if str(e["doc"].get("id")) == str(tid)), None)

def selftest():
    """快测（不依赖外部状态）：星期 0/7 双写周日、6＝周六、永不命中不写 now。"""
    import datetime as _d
    ok = [True]
    def chk(name, cond):
        ok[0] = ok[0] and bool(cond)
        print("  [%s] %s" % ("OK" if cond else "FAIL", name))
    sat = _d.datetime(2026, 10, 3, 20, 0); sun = _d.datetime(2026, 10, 4, 10, 0)
    chk("0 20 * * 6 命中周六20:00", cron_hit("0 20 * * 6", sat))
    chk("0 10 * * 0 命中周日10:00", cron_hit("0 10 * * 0", sun))
    chk("0 10 * * 7 命中周日10:00", cron_hit("0 10 * * 7", sun))
    chk("0 10 * * 7 不误命中周六", not cron_hit("0 10 * * 7", sat))
    chk("* * * * * 恒命中", cron_hit("* * * * *", sat))
    frm = _d.datetime(2026, 9, 30, 0, 0)
    chk("next(0 20 * * 6)=%s" % cron_next("0 20 * * 6", frm), cron_next("0 20 * * 6", frm) == sat)
    chk("next(0 10 * * 0)=%s" % cron_next("0 10 * * 0", frm), cron_next("0 10 * * 0", frm) == sun)
    chk("next(0 10 * * 7)=%s" % cron_next("0 10 * * 7", frm), cron_next("0 10 * * 7", frm) == sun)
    chk("0 0 * * 8 判永不命中", cron_never("0 0 * * 8") == "星期")
    doc = {"id": "x", "title": "t", "skill": "sms", "input": "i", "session": {},
           "schedule": {"mode": "cron", "cron": "0 0 * * 8"}, "status": "pending",
           "created": ISO(), "next_run": ""}
    chk("永不命中→next_run=None（不写 now）", next_run(doc) is None)
    chk("validate 报错含「永不命中」", any("永不命中" in x for x in bad(doc)))
    good = dict(doc); good["schedule"] = {"mode": "cron", "cron": "0 10 * * 7"}
    chk("合法周日无该报错", not any("永不命中" in x for x in bad(good)))
    print("planned_tasks selftest: " + ("OK" if ok[0] else "FAIL"))
    return 0 if ok[0] else 1

if __name__ == "__main__":
    a = sys.argv[1:] or ["ls"]; c = a[0]
    if c == "ls":
        es = scan(); print("计划任务 %d 条·根：%s" % (len(es), "、".join(roots())))
        for e in es:
            print("  " + brief(e["doc"]) + ("" if not e["errors"] else "  〔校验：" + "；".join(e["errors"]) + "〕"))
    elif c == "validate":
        es = scan(); ng = [e for e in es if e["errors"]]
        print("共 %d 条·不合格 %d 条" % (len(es), len(ng)))
        for e in ng: print("  %s：%s" % (e["path"], "；".join(e["errors"])))
        sys.exit(1 if ng else 0)
    elif c == "add" and len(a) >= 4: print(add(a[1], a[2], a[3], a[4] if len(a) > 4 else "sms"))
    elif c == "show" and len(a) > 1:
        e = find(a[1]); print(json.dumps(e and e["doc"], ensure_ascii=False, indent=1) or "无")
    elif c in ("pause", "resume", "done", "pending") and len(a) > 1: print(setstatus(a[1], "paused" if c == "pause" else "pending"))
    elif c == "run" and len(a) > 1:
        e = find(a[1]); print("触发结果：" + repr(e and fire(e)))
    elif c == "due": 
        for e in due(): print("到点：" + brief(e["doc"]))
    elif c == "tick": print("本轮触发：" + repr(tick(force=True)))
    elif c == "serve":
        try: __import__("session_reg").bind("cron", "planned", "计划任务调度")
        except Exception: pass
        serve()
    elif c == "start": print(start())
    elif c == "selftest": sys.exit(selftest())
    else: print(__doc__)
