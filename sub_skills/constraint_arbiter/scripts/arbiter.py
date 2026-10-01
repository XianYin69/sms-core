#!/usr/bin/env python3
"""arbiter.py — 约束冲突仲裁子技能（constraint_arbiter）执行体（2026-09-26 批4 用户需求「多 skill 约束冲突时处理决策冲突」）：多技能同时命中/多 SKILL.md 约束互相打架时，SMS 先派本技能仲裁再执行。确定性优先级阶梯（不可逾越）：P0 用户当轮话语 ＞ P1 SMS 治理（AGENTS.md＋resistance 红线）＞ P2 目标技能 SKILL.md 红线节 ＞ P3 子技能/接口描述行。检测＝约束句抽 2-gram 主题词，同主题（交集≥2）且极性相反（禁/不得/勿 vs 必须/须/应/仅）判为冲突；裁决＝低序号方胜出，同级冲突不擅断→输出「请用户拍板」建议问句。结果记 logic 链（frm→to：why）供审计与做梦。用法：python -B arbiter.py judge <技能id[,id…]> [话语] | constraints <技能id> [--json]"""
import os, sys, json, re
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts"))]; import resolve_home, chains, skill_route
SMS = resolve_home.ensure(); NEG = re.compile("禁止|不得|勿|不要|拒|禁"); POS = re.compile("必须|须|应|仅|只|要"); CL = re.compile("禁止|不得|勿|不要|拒|禁|必须|须|应|仅|只|要")
def _big(s): t = re.sub(r"\s+", "", str(s)); return {t[i:i + 2] for i in range(len(t) - 1) if "\u4e00" <= t[i] <= "\u9fff"}
def _cons(text, rank, src):
    out, sec = [], "body"
    for ln in text.splitlines():
        if ln.strip().startswith(("#", "##")): sec = "红线" if "红线" in ln or "resistance" in ln.lower() else sec
        if CL.search(ln) and len(ln.strip()) > 6: out.append({"src": src, "rank": rank - (1 if sec == "红线" else 0), "text": ln.strip()[:220]})
    return out
def load(ids):
    cs = []
    ag = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "AGENTS.md"))
    if os.path.exists(ag): cs += _cons(open(ag, encoding="utf-8").read(), 1, "SMS治理")
    rs = open(os.path.join(os.path.dirname(ag), "resistance", "resistance.md"), encoding="utf-8").read() if os.path.exists(os.path.join(os.path.dirname(ag), "resistance", "resistance.md")) else ""
    if rs: cs += _cons(rs, 1, "SMS治理")
    for sid in ids:
        s = next((x for x in skill_route.skills(SMS) if str(x.get("id", "")).lower() == sid.lower()), None)
        if not s: cs.append({"src": sid, "rank": 9, "text": "（未注册技能：" + sid + "——先 register.py 扫描）"}); continue
        p = os.path.join(str(s.get("install_path")), str(s.get("entry", "SKILL.md")))
        try: cs += _cons(open(p, encoding="utf-8", errors="ignore").read(), 2, sid)
        except Exception as e: cs.append({"src": sid, "rank": 9, "text": "（读取失败 %s：%s）" % (p, str(e)[:60])})
    return sorted(cs, key=lambda c: c["rank"])
def conflicts(cs):
    out = []
    for i in range(len(cs)):
        for j in range(i + 1, len(cs)):
            a, b = cs[i], cs[j]
            if a["src"] == b["src"]: continue
            if (NEG.search(a["text"]) and POS.search(b["text"]) or NEG.search(b["text"]) and POS.search(a["text"])) and len(_big(a["text"]) & _big(b["text"])) >= 2:
                w = a if a["rank"] <= b["rank"] else b; l = b if w is a else a
                out.append({"topic": "、".join(sorted(_big(a["text"]) & _big(b["text"]))[:4]), "winner": w, "loser": l, "manual": w["rank"] == l["rank"]})
    return out
if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--json"]; js = "--json" in sys.argv
    if not a or a[0] not in ("judge", "constraints") or len(a) < 2: print(__doc__.strip().splitlines()[-1]); sys.exit(1)
    cs = load([x for x in a[1].split(",") if x])
    if a[0] == "constraints": print(json.dumps(cs, ensure_ascii=False, indent=1) if js else "\n".join("P%d [%s] %s" % (c["rank"], c["src"], c["text"]) for c in cs)); sys.exit(0)
    ut = a[2] if len(a) > 2 else ""; cf = conflicts(cs)
    for k in cf: chains.record("logic", "冲突仲裁|%s→%s胜" % (k["loser"]["src"] + "‖" + k["winner"]["src"], k["winner"]["src"]) + "：" + k["topic"], [[chains.ACTIVE["conv"] or "", "ref", 1], [chains.cur_sess(), "member", 1]])
    rep = {"intent": ut[:120], "ladder": "P0 用户话语＞P1 SMS治理＞P2 目标技能红线＞P3 描述行", "order": ["P%d %s｜%s" % (c["rank"], c["src"], c["text"][:90]) for c in cs], "conflicts": [{"topic": k["topic"], "winner": k["winner"]["src"] + "｜" + k["winner"]["text"][:80], "loser": k["loser"]["src"], "need_user": k["manual"]} for k in cf], "verdict": ("冲突 %d 处·其中 %d 处同级需用户拍板（ask_user）" % (len(cf), sum(1 for k in cf if k["manual"]))) if cf else "无冲突：按阶梯顺序合并执行"}
    print(json.dumps(rep, ensure_ascii=False, indent=1) if js else "仲裁（%s）：%s\n" % (a[1], rep["verdict"]) + "\n".join("  ⚔ %s｜胜=%s｜负=%s%s" % (k["topic"], k["winner"]["src"], k["loser"]["src"], "（同级→问用户）" if k["manual"] else "") for k in cf))
