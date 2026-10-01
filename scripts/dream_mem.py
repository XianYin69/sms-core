#!/usr/bin/env python3
"""dream_mem.py — 做梦记忆沉淀（红线 17·批8）：高频有用碎片（knowledge/logic/user·freq≥3）整理写入 SMS_HOME 记忆链（memory·按既有文本去重）；其中命中私人信息（手机/邮箱/证件/卡号/住址/生日/密码/账号等）的，走既有处理路径——privacy.py 混淆+掩码+矩阵变换后落 <SMS_HOME>/privacy/records.json 并刷新 NOTICE.md（须 grant privacy·未授权只记 event 不写），记忆链只存 privacy 引用号不存明文，个性化对话经 privacy open（必要理由）取用。用法：python -B dream_mem.py test <语句>"""
import os, sys, re, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, chains, permissions, privacy, atomic_io
PRIV = re.compile(r"1[3-9]\d{9}|\d{17}[\dXx]|[\w.+-]+@[\w-]+\.[\w.]+|身份证|银行卡|信用卡|口令|密码|住址|户籍|生日|账号|微信号|手机号")
def _priv(t): return bool(PRIV.search(t or ""))
def _rec(sms, t, cat="dream_auto"):
    d = os.path.join(sms, "privacy"); os.makedirs(d, exist_ok=True); rp = os.path.join(d, "records.json")
    doc = atomic_io.rjson(rp, default={"records": [], "audit": []})
    x = privacy.xor(t); rec = {"id": "p%03d" % (len(doc["records"]) + 1), "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "category": cat, "masked": privacy.mask(t), "obfuscated": x, "matrix": privacy.matrix(x)}
    doc["records"].append(rec); atomic_io.wjson(rp, doc); privacy.notice(d, doc); return rec["id"]
def absorb(sms, top, r=None):
    r = {} if r is None else r
    have = [f["text"] for f in chains.store().all_frags("memory")]; added = priv = denied = 0
    for f in [x for x in top if x["chain"] in ("knowledge", "logic", "user") and x.get("freq", 1) >= 3][:12]:
        t = (f.get("text") or "").strip()[:160]
        if not t or any(t in h for h in have): continue
        if _priv(t):
            if not permissions.allow(sms, "privacy"): denied += 1; continue
            rid = _rec(sms, t); chains.record("memory", "做梦私存｜%s｜经privacy变换待授权取用" % rid); have.append(t); priv += 1
        else:
            chains.record("memory", "做梦记忆｜" + t); have.append(t); added += 1
    if denied: chains.record("event", "做梦记忆沉淀：%d 条私人信息未写（须 :grant privacy 授权）" % denied)
    r["memorized"] = added; r["privatized"] = priv; r["privacy_denied"] = denied; return r
if __name__ == "__main__":
    sms = resolve_home.ensure()
    if len(sys.argv) > 2 and sys.argv[1] == "test": print(json.dumps({"private": _priv(sys.argv[2])}, ensure_ascii=False))
    else: print(json.dumps(absorb(sms, sorted(chains.store().all_frags(), key=lambda f: -f.get("freq", 1))[:40]), ensure_ascii=False))
