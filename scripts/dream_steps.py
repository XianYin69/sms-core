#!/usr/bin/env python3
"""dream_steps.py — 做梦流程的扩展步（2026-09-29 用户三维链空间＋错误链＋加强记忆＋修复闭环）：core(sms)＝① 原子双向边补对称（chain_edges.symmetrize）② 合并近义 ③ 低频修剪（继承 chain_store.prune·knowledge 钉选豁免）④ 高频加强记忆（dream_reinforce）⑤ 重建三维坐标索引（chain_space3d.rebuild），每步写心跳（dream_watch.beat）供顶栏与判活；repair(sms,r)＝按错误记录链做 skill/程序修复（dream_repair.fix），需权限或高危无法后台的自动转 dream_pending（空闲时顶栏「⚠修复待批N」前台提醒，用户 :repair go 后续跑）；close(sms,r)＝收尾状态落 chains/dream.state＋僵尸锁（锁在但进程死/心跳超时）落 error 链。用法：python -B dream_steps.py core|repair|close"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, chain_store as cs, chain_edges as ce, chain_space3d as sp
import dream_reinforce, dream_repair, dream_pending, dream_watch, chain_error
def core(sms=None):
    sms = sms or resolve_home.ensure(); st = cs.Store(sms); r = {}
    dream_watch.beat("补双向边"); r["symmetrized"] = ce.symmetrize(sms)
    dream_watch.beat("合并近义"); r["merged"] = st.merge_near()
    dream_watch.beat("低频修剪"); r["pruned"] = st.prune()
    dream_watch.beat("高频加强"); r["reinforced"] = dream_reinforce.reinforce(sms)
    dream_watch.beat("三维索引"); r["atoms"] = len(sp.rebuild(sms)); dream_watch.beat("整理完成")
    return r
def top(sms=None, n=40):
    return sorted(cs.Store(sms or resolve_home.ensure()).all_frags(), key=lambda f: -f.get("freq", 1))[:n]
def repair(sms=None, r=None):
    sms = sms or resolve_home.ensure(); r = {} if r is None else r
    dream_watch.beat("错误链修复")
    try: r.update(dream_repair.fix(sms, r))
    except Exception as e:
        chain_error.hook("dream", "dream_steps.repair", str(e)); r["repair"] = 0; r["repair_err"] = str(e)[:120]
    r["pending"] = len(dream_pending.open_rows(sms)); return r
def close(sms=None, r=None):
    sms = sms or resolve_home.ensure(); s = dream_watch.state(sms)
    if s["zombie"]: chain_error.hook("dream", "dream_watch", "锁在但后台进程已死/心跳超时（pid=%s beat_age=%s）" % (s["pid"], s["beat_age"]))
    dream_watch.beat("收尾")
    try:
        json.dump({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "summary": {k: v for k, v in (r or {}).items() if k != "violations"}},
                  open(os.path.join(sms, "chains", "dream.state"), "w", encoding="utf-8"), ensure_ascii=False)
    except Exception: pass
    return s
if __name__ == "__main__":
    a = sys.argv[1:] or ["core"]; sms = resolve_home.ensure()
    print(json.dumps(core(sms) if a[0] == "core" else repair(sms) if a[0] == "repair" else close(sms), ensure_ascii=False, indent=1))
