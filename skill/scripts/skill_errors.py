#!/usr/bin/env python3
"""skill_errors.py — 记录 skill 出错位置与日志：SMS/errors/skill_errors.json；
〔批40 A1〕同一 (skill, where, 归一化签名) 合并计数——不再要求 status==open 才合并：
同因错误此前一天落 9 条独立条目（mine_canary 版本解析 ValueError ×9），台账信噪比被吃掉。
签名归一复用 chain_error.sig（时间戳/hex/盘符路径/数字 → 占位符），导入失败退回本地归一。
resolved 签名再现＝重新打开（status→open + reopened 日期），回归不丢可见性。
OPEN 且判为非缺陷（超时收口/用户停止）自动转 not_defect 并留 verdict。
〔批40 A3〕写盘与 debug.log 落盘全程兜底：open(w)+json.dump（未关句柄＝共享读必 Errno 22）
改 atomic_io.rjson/wjson；错误消息剥换行＋NUL＋不可编码字符；debug.error 失败降级到
errors/skill_error_fallback.log，再失败则静默——登记动作自身绝不抛穿（此前 Errno 22
把 record 炸穿，被 agent_stream/agent_tools 上层 except 当成本轮异常＝二次故障，
且 debug.log 只剩干瘪的 "[Errno 22] Invalid argument"（str(OSError) 丢 filename），
真因（print 到 stdout 句柄非法 [Errno 22] Invalid argument: '<stdout>'）无处可查。
用法：python -B skill_errors.py list|due|migrate|sweep [--write]；
      python -B skill_errors.py record <skill> --where W --msg M [--write]；
      python -B skill_errors.py resolve <skill> [--write]"""
import os, sys, json, re, time
TH = 3; DATE = time.strftime("%Y-%m-%d")
def _p(sms): return os.path.join(sms, "errors", "skill_errors.json")
def _fb(sms): return os.path.join(sms, "errors", "skill_error_fallback.log")

CLEAN = ((re.compile(r"[\r\n\t]+"), " ⏎ "), (re.compile(r"[\ud800-\udfff\x00-\x08\x0b\x0c\x0e-\x1f]"), "?"))
def clean(msg, n=400):
    """落盘文本先过一遍：剥换行/NUL/未配对代理项（WinError 123/Errno 22 与 print '<stdout>' 炸源）。"""
    s = str(msg if msg is not None else "")
    for rx, ph in CLEAN: s = rx.sub(ph, s)
    return " ".join(s.split())[:n]
PATHY = re.compile(r"(?i)\s*(?:at\s+)?(?:[a-z]:)?[\\/][^\\s'\"]*")
TAIL = re.compile(r"\s@\S*?:?\d*\s+\S*\s*$")
RUN = re.compile(r"<(?:n|hex|ts|path|num)>(?:[\s.,;:=\-/]+<(?:n|hex|ts|path|num)>)+")
PH = "<n>"  # 版本串/行列号收敛为一个占位：'v1.2.3' 与 'v9' 同因（批40 A1）
def _sig2(m):
    """〔批40 A1〕登记侧签名：先过 chain_error 占位归一，再剥掉全部路径样 token＋尾部
    `@file:line fn` 现场——同因不同次（v1.2.3 vs v9、x.py:12 vs y.py:3）必落同一键。"""
    s = " ".join(str(m or "").split()).lower()
    try:
        import chain_error
        s = chain_error.sig(s)
    except Exception:
        pass
    s = PATHY.sub(" ", s)
    s = TAIL.sub(" ", s)
    s = RUN.sub(PH, s)
    return " ".join(s.split())[:72]
try:
    import chain_error as _ce
    _sig = _sig2
except Exception:
    _VOL = ((re.compile(r"\d{4}-\d{2}-\d{2}[ T]?[\d:]*"), "<ts>"), (re.compile(r"\b[0-9a-fA-F]{8,}\b"), "<hex>"),
            (re.compile(r"[A-Za-z]:[\\/][^\s,;)\]]+"), "<path>"), (re.compile(r"\d+", re.A), "<n>"))
    def _sig(m):
        s = " ".join(str(m or "").split()).lower()
        for rx, ph in _VOL: s = rx.sub(ph, s)
        s = PATHY.sub(" ", s); s = TAIL.sub(" ", s); s = RUN.sub(PH, s)
        return " ".join(s.split())[:72]
    _ce = None
def key(skill, where, msg): return (str(skill or "?"), str(where or "unknown"), _sig(msg))
def same(a, skill, where, msg):
    """台账条目匹配：优先批40 sig 字段；旧条目（无 sig）退回按 msg 签名现算。"""
    sk = a.get("sig") or _sig(a.get("msg", ""))
    return (str(a.get("skill")), str(a.get("where")), sk) == key(skill, where, msg)

def _doc(sms):
    try:
        import atomic_io
        d = atomic_io.rjson(_p(sms), default=None)
    except Exception:
        d = None
    if not isinstance(d, dict): return {"updated": DATE, "entries": []}
    d.setdefault("entries", []); d.setdefault("updated", DATE)
    return d
def _save(sms, doc, write):
    doc["updated"] = DATE
    if not write: return {"preview": True, "entries": len(doc["entries"])}
    try:
        import permissions
        if not permissions.allow(sms, "write"): return {"denied": "会话未授予 write 权限（permissions.json），拒绝写盘"}
    except Exception: pass  # permissions 不可用＝非会话语境（计划任务/守护），照写
    try:
        import atomic_io
        atomic_io.wjson(_p(sms), doc); return {"ok": _p(sms)}
    except Exception as e:
        return _degrade(sms, doc, e)
def _degrade(sms, doc, err):
    """台账写不进（锁/坏盘/权限）→ 追加降级日志保登记不丢，rc 非零也不抛穿。"""
    try:
        os.makedirs(os.path.dirname(_fb(sms)), exist_ok=True)
        with open(_fb(sms), "a", encoding="utf-8", errors="replace") as f:
            f.write("%s 台账写失败 %s；条目%d\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), clean(err, 160), len(doc.get("entries", []))))
        with open(_p(sms), "w", encoding="utf-8", errors="replace") as f:  # 最后再赌一次直写
            json.dump(doc, f, ensure_ascii=False, indent=1)
        return {"ok": _p(sms), "note": "atomic 失败已直写"}
    except Exception as e2:
        return {"error": "台账落盘失败：" + clean(e, 120) + " / 降级亦失败：" + clean(e2, 120)}
def _log(sms, line):
    """debug.log 落盘兜底：失败转 fallback，绝不抛穿登记主流程。"""
    try:
        import debug; debug.error(line, sms)
    except Exception as e:
        try:
            os.makedirs(os.path.dirname(_fb(sms)), exist_ok=True)
            with open(_fb(sms), "a", encoding="utf-8", errors="replace") as f:
                f.write(time.strftime("[%m-%d %H:%M:%S] ") + clean(line, 300) + "｜debug.error 失败 " + clean(e, 80) + "\n")
        except Exception: pass

def describe(e, n=240):
    """〔批40 A3〕异常→可诊断文本：str(OSError) 丢 filename/filename2/winerror——
    `[Errno 22] Invalid argument` 之所以查不出根因就在这。标签（errno/winerror/文件基名/栈帧）
    一律置于尾部并优先保留：主体过长只截主体，绝不把根因挤没。"""
    head = "%s: %s" % (type(e).__name__, e)
    tags = []
    if getattr(e, "errno", None) is not None: tags.append("errno=%s" % e.errno)
    if getattr(e, "winerror", None) is not None: tags.append("winerror=%s" % e.winerror)
    for a in ("filename", "filename2"):
        v = getattr(e, a, None)
        if v is not None: tags.append("%s=%r" % (a, os.path.basename(str(v).strip(chr(92) + "/")) or str(v)[:60]))
    try:
        tb = getattr(e, "__traceback__", None)
        if tb is not None:
            import traceback
            fr = traceback.extract_tb(tb)[-1]
            tags.append("@%s:%d %s" % (os.path.basename(fr.filename), fr.lineno, (fr.line or "").strip()[:60]))
    except Exception: pass
    t = clean(" ".join(tags), 140)
    keep = max(60, n - len(t) - 4)
    return clean(head[:keep] + " ｜" + t, n)

NOT_DEFECT = ("run_watch 超时收口", "超时收口", "底栏停止", "用户主动", "用户停止", "stop_channel",
              "空转自愈")  # 〔批40 A1〕spin-guard 自愈＝非缺陷（N4 五例长期挂 open 的真因是漏了这类）
def not_defect(msg):
    """批29 P3-09：超时收口与用户主动停止＝非缺陷，不记 open。"""
    m = str(msg or "")
    return next((k for k in NOT_DEFECT if k in m), "")
PREC = ("open", "not_defect", "resolved")
def record(sms, skill, where, msg, write):
    doc = _doc(sms); msg = clean(msg); nd = not_defect(msg)
    e = next((x for x in doc["entries"] if same(x, skill, where, msg)), None)
    if e:
        e["count"] = int(e.get("count", 0)) + 1; e["last"] = DATE
        e.setdefault("sig", _sig(msg))
        if not nd and e.get("status") == "resolved":  # 修后又现＝回归，重新打开
            e["status"] = "open"; e["reopened"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        elif nd and e.get("status") == "open": e["status"] = "not_defect"; e["verdict"] = "非缺陷：" + nd
    elif nd:
        doc["entries"].append({"skill": skill, "where": where, "msg": msg, "sig": _sig(msg), "count": 1,
                               "first": DATE, "last": DATE, "status": "not_defect", "verdict": "非缺陷：" + nd})
    else:
        doc["entries"].append({"skill": skill, "where": where, "msg": msg, "sig": _sig(msg), "count": 1,
                               "first": DATE, "last": DATE, "status": "open"})
    cur = e or doc["entries"][-1]
    if _ce:
        try: _ce.hook("skill", str(skill) + "@" + str(where), msg)
        except Exception: pass
    _log(sms, "skill_error %s@%s ×%d %s" % (skill, where, cur["count"], msg))
    r = _save(sms, doc, write); r["merged"] = bool(e); r["status"] = cur.get("status")
    return r
def resolve(sms, skill, write):
    doc = _doc(sms); n = 0
    for x in doc["entries"]:
        if x["skill"] == skill and x["status"] == "open":
            x["status"] = "resolved"; x["last"] = DATE; x["resolved_at"] = time.strftime("%Y-%m-%dT%H:%M:%S"); n += 1
    if not n: return {"error": "无 %s 未解决记录" % skill}
    return _save(sms, doc, write)
def migrate(sms, write=True):
    """〔批40 A1〕历史台账按 (skill,where,sig) 收敛：count 累加、first 取早、last 取晚，
    status 取最活跃（open>not_defect>resolved）；只读预演不带 --write。"""
    doc = _doc(sms); out = {}; order = []
    for x in doc["entries"]:
        k = (str(x.get("skill")), str(x.get("where")), x.get("sig") or _sig(x.get("msg", "")))
        if k not in out:
            y = dict(x); y["sig"] = k[2]; y["count"] = int(x.get("count", 0) or 0)
            out[k] = y; order.append(k)
        else:
            y = out[k]; y["count"] += int(x.get("count", 0) or 0)
            y["first"] = min(str(y.get("first", "")), str(x.get("first", ""))) or DATE
            y["last"] = max(str(y.get("last", "")), str(x.get("last", ""))) or DATE
            if PREC.index(x.get("status", "open")) < PREC.index(y.get("status", "open")):
                y["status"] = x.get("status"); y["msg"] = x.get("msg", y.get("msg"))
    before, after = len(doc["entries"]), len(order)
    doc["entries"] = [out[k] for k in order]
    r = {"before": before, "after": after, "merged": before - after}
    r.update(_save(sms, doc, write))
    return r
def sweep(sms, write=True):
    """〔批40 A1〕存量收敛：open 条目命中非缺陷关键词（超时收口/用户停止/空转自愈）→ 转
    not_defect 并留 verdict，让催办面只剩真缺陷（N4 的 5 例自愈条目此前无人判、一直挂 open）。
    幂等·只改 status/verdict 不动 count；只读预演不带 --write。"""
    doc = _doc(sms); hits = []
    for x in doc["entries"]:
        if x.get("status") != "open": continue
        nd = not_defect(str(x.get("msg", "")) + " " + str(x.get("verdict", "")))
        if nd:
            x["status"] = "not_defect"; x["verdict"] = "非缺陷：" + nd
            x["swept_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            hits.append("%s@%s×%s←%s" % (x.get("skill"), x.get("where"), x.get("count"), nd))
    r = {"changed": len(hits), "items": hits}
    r.update(_save(sms, doc, write))
    return r
def due(sms):
    agg = {}
    for x in _doc(sms)["entries"]:  # not_defect 不计入修复催办
        if x["status"] == "open": agg[x["skill"]] = agg.get(x["skill"], 0) + x["count"]
    hits = {k: v for k, v in agg.items() if v >= TH}
    return {"due": hits, "suggest": ["启用 Skill_Generator self_update 修复 %s（未解决错误 %d 处）" % (k, v) for k, v in hits.items()]}

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home
    sms = resolve_home.ensure(); a = [x for x in sys.argv[1:] if not x.startswith("--")]; w = "--write" in sys.argv
    opt = lambda k, d="": sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
    cmd = a[0] if a else "list"
    if cmd == "record": r = record(sms, a[1], opt("--where", "unknown"), opt("--msg", ""), w)
    elif cmd == "resolve": r = resolve(sms, a[1], w)
    elif cmd == "migrate": r = migrate(sms, w)
    elif cmd == "due": r = due(sms)
    elif cmd == "sweep": r = sweep(sms, w)
    else:
        d = _doc(sms); r = {"entries": d["entries"], "signatures": len({key(x["skill"], x["where"], x.get("sig") or x["msg"]) for x in d["entries"]})}
    print(json.dumps(r, ensure_ascii=False, indent=2))
