#!/usr/bin/env python3
"""dream_repair.py — 做梦修复器（2026-09-29 用户「skill 修复以及程序修复，修复依据来源于错误记录链；做梦遇到需权限等无法后台操作时，空闲时前台提醒用户，征得同意后继续修复」）：依据＝chain_error 未修原子（err:<kind>:<src> <msg>）。plan() 按 kind 归动作——skill/tool→skill 修复、script/dream/shell→程序修复，两者统一经 Skill_Generator self_update report（dream_fix.report 复用·其修改路径负责纠正 skill 与脚本）。后台可行性先验 blocked()：permissions 缺 write/danger/network、或命中高危核心脚本（gateway/permissions/redlines/deploy）→ 不硬试，dream_pending.add() 登记，空闲时由顶栏「⚠修复待批N」提醒；可后台则当场修，成功即 chain_error.resolve 原子并记 event。resume(pid)＝用户当轮 :repair go 同意后前台续跑同一动作（权限此时已生效），成功标 fixed。用法：python -B dream_repair.py plan|fix|resume <待批id>"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, chain_error, dream_pending, dream_fix, chains
NEED = ("write", "danger", "network"); HIGH = ("gateway", "permissions", "redlines", "deploy", "dream")
def _sms(sms=None): return sms or resolve_home.ensure()
def _act(k): return "skill" if k in ("skill", "tool") else "program"
def plan(sms=None):
    out = []
    for f in chain_error.open_frags():
        p = (f.get("text") or "").split(":")
        if len(p) < 3: continue
        k = p[1]; src = p[2].split(" ", 1)[0].replace("_", "@", 1) if k == "skill" else p[2].split(" ", 1)[0]
        if f.get("freq", 1) < 2 and k not in ("skill", "script", "dream"): continue
        if chain_error.selffix(f.get("text") or ""): continue
        out.append({"fid": f["id"], "kind": k, "target": src, "action": _act(k), "msg": (f.get("text") or "")[:200], "freq": f.get("freq", 1)})
    return out
def blocked(sms, it, consent=False):
    import permissions
    for g in NEED:
        try:
            if not permissions.allow(sms, g): return "缺 %s 权限·后台不可自动修" % g
        except Exception: return "权限校验异常·需前台确认"
    if not consent and it["action"] == "program" and any(w in it["target"] for w in HIGH): return "高危核心脚本改动需用户拍板"
    return None
def _run(sms, it, repro=""):
    err = "SMS 做梦修复（%s·%s）：%s" % (it["action"], it["kind"], it["msg"])
    ok, out = dream_fix.report(sms, it["target"], err, repro or "freq=%s" % it.get("freq", 1))
    if ok:
        chain_error.resolve(it["fid"]); chains.record("event", "做梦修复：%s→%s 已登记 Skill_Generator（%s）" % (it["kind"], it["target"], out[:80]))
    return ok, out
def fix(sms=None, r=None):
    sms = _sms(sms); r = {} if r is None else r; r.update({"repair": 0, "pending": 0, "blocked": []})
    for it in plan(sms):
        why = blocked(sms, it)
        if why:
            dream_pending.add(it["action"], it["target"], why + "｜" + it["msg"][:80], {"fid": it["fid"], "it": it}, sms)
            r["pending"] += 1; r["blocked"].append({"target": it["target"], "why": why}); continue
        ok, _ = _run(sms, it); r["repair"] += 1 if ok else 0
        if not ok: dream_pending.add(it["action"], it["target"], "后台修复失败·转前台重试", {"fid": it["fid"], "it": it}, sms); r["pending"] += 1
    return r
def resume(pid, sms=None):
    sms = _sms(sms); it = dream_pending.take(pid, sms)
    if not isinstance(it, dict): return it
    payload = it.get("it") or {"fid": (it.get("how") or {}).get("fid"), "kind": it["kind"], "target": it["target"], "action": it["kind"], "msg": it["reason"], "freq": it.get("count", 1)}
    why = blocked(sms, payload, True)
    if why: return "仍未取得所需权限：" + why + "（当轮 :grant write|danger 后重试）"
    ok, out = _run(sms, payload, "前台续跑·用户同意（" + str(pid) + "）")
    dream_pending.drop(pid, "fixed" if ok else "failed", sms)
    return ("已续跑修复并登记 Skill_Generator：" + str(payload["target"]) + ("｜" + out[:80] if out else "")) if ok else ("续跑仍失败：" + out[:160])
