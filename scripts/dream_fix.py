#!/usr/bin/env python3
"""dream_fix.py — 做梦错误自修登记（红线 17·批8）：skill_errors entries（count≥3·status=open·未 escalated）→ 逐条直调 Skill_Generator 的 self_update.py `report`（自更新运行在 Skill_Generator 侧·其修改路径负责纠正 skill 与脚本），错误现场＝debug.py error 通道（skill_errors 每笔直调）尾部随 repro 附带；登记成功才标 escalated（失败下轮做梦重试）·记 event 链。未检出 Skill_Generator 则不标、提示先 bootstrap。用法：python -B dream_fix.py pending|fix"""
import os, sys, json, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, atomic_io, chains, debug
def _p(sms): return os.path.join(sms, "errors", "skill_errors.json")
def _doc(sms): return atomic_io.rjson(_p(sms), default={"entries": []})
def _pend(doc): return [e for e in doc.get("entries", []) if e.get("count", 0) >= 3 and e.get("status") == "open" and not e.get("escalated")]
def pending(sms): return _pend(_doc(sms))
def _sg_script(sms):
    import bootstrap
    d = bootstrap.in_folders() or (bootstrap.in_config(sms) or {}).get("path") or ""
    su = os.path.join(d, "scripts", "self_update.py")
    return su if d and os.path.isfile(su) else None
def report(sms, skill, err, repro=""):
    su = _sg_script(sms)
    if not su: return False, "未检出 Skill_Generator（先 bootstrap.py 拉取后重试）"
    cwd = os.path.join(sms, "tmp", "dream_fix"); os.makedirs(cwd, exist_ok=True)
    p = subprocess.run([sys.executable, "-B", su, "report", "--skill", str(skill), "--error", str(err)[:400], "--repro", str(repro)[:300]],
                       cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode == 0, (p.stdout or p.stderr or "").strip()[:200]
def fix(sms, r=None):
    r = {} if r is None else r; doc = _doc(sms); es = _pend(doc); r["escalated"] = 0; r["reported"] = 0
    if not es: return r
    su = _sg_script(sms)
    if not su:
        chains.record("event", "做梦自修：未检出 Skill_Generator（bootstrap.py 拉取后重试），待登记 %d 条" % len(es)); return r
    cwd = os.path.join(sms, "tmp", "dream_fix"); os.makedirs(cwd, exist_ok=True)
    tail = debug.tail(4, sms).replace("\n", " ⏎ ")[-260:]
    for e in es:
        err = "SMS 做梦自动修复：%s@%s ×%d（%s…%s）%s" % (e.get("skill"), e.get("where"), e.get("count"), e.get("first"), e.get("last"), str(e.get("msg", ""))[:180])
        p = subprocess.run([sys.executable, "-B", su, "report", "--skill", str(e.get("skill")), "--error", err[:400], "--repro", ("debug_err_tail=" + tail)[:300]], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        ok = p.returncode == 0; r["reported"] += 1 if ok else 0
        if ok: e["escalated"] = time.strftime("%Y-%m-%dT%H:%M:%S"); r["escalated"] += 1
        chains.record("event", "做梦自修：%s → Skill_Generator self_update report %s（rc=%d）" % (e.get("skill"), "已登记" if ok else "失败", p.returncode))
    if r["escalated"]: atomic_io.wjson(_p(sms), doc)
    return r
if __name__ == "__main__":
    sms = resolve_home.ensure(); cmd = sys.argv[1] if len(sys.argv) > 1 else "pending"
    print(json.dumps(pending(sms), ensure_ascii=False, indent=2) if cmd == "pending" else json.dumps({k: v for k, v in fix(sms).items() if k != "violations"}, ensure_ascii=False))
