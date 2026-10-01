#!/usr/bin/env python3
"""skill_route.py — 数据流 SMS 技能路由〔仅参考·非裁决〕（批16 LLM 主导）：读 registry/register.json 活跃技能（quarantine/pending_review 信任级跳过）＋ interfaces.json 接口词，与输入打分匹配（阈值 4：技能id 子串命中或分词＋接口词双证据）；命中→chains.log("skill") 记 skill_call 链并返回命中 id 与〔参考〕句——是否真派发由模型在网关工具循环内自主决定（旧「命中即自动开子会话」脚本扇出已废除）；未命中注入技能全表＋批22 指引：动手类无相近技能且属新领域/需复用→模型先派 Skill_Generator 创建再执行；match/listtext 供壳内 :skills 与 ps1 清单。批6：skills()/_terms() 共用 (mtime,size) 内存缓存 _reg（冷读 213ms→暖 ~5ms·task 扇出多调免重解析）；route 计时入 latency。用法：python -B skill_route.py match \"<话语>\" | list"""
import os, sys, json, re, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import resolve_home, chains, latency
def _load(sms, rel):
    try: return json.load(open(os.path.join(sms, rel), encoding="utf-8"))
    except Exception: return {}
STOP = {"系统", "问题", "使用", "功能", "支持", "提供", "进行", "可以", "需要", "一个", "这个", "那个", "用户", "管理", "相关", "通过", "以及", "如果", "默认", "显示", "输出", "输入", "操作", "文件", "设置", "配置"}
def _dterms(d):
    t = re.sub(r"\s+", "", str(d or "")); ws = [x for x in re.findall(r"[a-z][a-z0-9_\-]{3,}", t.lower()) if x not in STOP] + [t[i:i + 2] for i in range(len(t) - 1) if "\u4e00" <= t[i] <= "\u9fff" and "\u4e00" <= t[i + 1] <= "\u9fff" and t[i:i + 2] not in STOP]
    return list(dict.fromkeys(ws))[:80]
_RC = {}
def _reg(sms):
    r = os.path.join(sms, "registry", "register.json"); i = os.path.join(sms, "registry", "interfaces.json")
    try: k = (os.path.getmtime(r), os.path.getsize(r), os.path.getmtime(i), os.path.getsize(i))
    except Exception: k = None
    if (c := _RC.get("v")) and c[0] == k: return c[1]
    ss = [s for s in _load(sms, "registry/register.json").get("skills", []) if s.get("status", "active") == "active" and s.get("trust") not in ("quarantine", "pending_review")]
    tm = {}
    for it in _load(sms, "registry/interfaces.json").get("skills", []):
        ws = [str(n.get("name", "")) for n in it.get("interfaces", [])] + [str(x) for x in (it.get("capabilities") or [])]
        tm.setdefault(it.get("skill_id") or "", []).extend(w for w in ws if 1 < len(w) <= 12)
    for s in ss: tm.setdefault(str(s.get("id") or ""), []).extend(_dterms(s.get("description")))
    _RC["v"] = (k, (ss, tm)); return ss, tm
def skills(sms=None): return _reg(sms or resolve_home.ensure())[0]
def _terms(sms): return _reg(sms)[1]
def _score(s, u, terms):
    sid = str(s.get("id", "")).lower()
    return (4 if sid and sid in u else 0) + 2 * sum(1 for x in re.split(r"[-_.]+", sid) if len(x) >= 4 and x in u) + min(4, sum(1 for w in terms.get(s.get("id"), []) if w.lower() in u))
def match(text, sms=None):
    sms = sms or resolve_home.ensure(); ss, terms = _reg(sms); u = text.lower()
    return [ss[i] for sc, i in sorted(((_score(s, u, terms), i) for i, s in enumerate(ss)), key=lambda x: -x[0])[:2] if sc >= 4]
def catalog(sms=None):
    return ("技能全表：" + "；".join("%s（%s）" % (s.get("id"), re.sub(r"\s+", "", str(s.get("description") or ""))[:26]) for s in skills(sms)))[:620]
def listtext(sms=None):
    ss = skills(sms); return ("技能注册表为空：先运行 register.py 扫描安装根（config.scan_roots），或经 Skill_Generator 创建后重装。" if not ss else "可调用托管技能 %d 个（说法即打分给〔参考〕·采纳与否由模型定，Ctrl+K 可显式选填）：" % len(ss) + "；".join("%s（%s）" % (s.get("id"), re.sub(r"\s+", "", str(s.get("description") or ""))[:26]) for s in ss) + "。执行类诉求经 skill 工具派发对等对话真派发执行（批23 每派发自开独立 conv），结果整合作答；需本机真跑脚本/调设备时以 :use 切 agent CLI 承接。")[:1400]
def route(text, sms=None):
    t0 = time.perf_counter(); sms = sms or resolve_home.ensure(); ss, terms = _reg(sms); u = text.lower()
    ranked = sorted(((_score(s, u, terms), i) for i, s in enumerate(ss)), key=lambda x: -x[0]); hs = [ss[i] for sc, i in ranked[:2] if sc >= 4]
    for s in hs: chains.log("skill", "路由命中:" + str(s.get("id")))
    latency.rec("route", ",".join(str(s.get("id")) for s in hs) or "-", (time.perf_counter() - t0) * 1000)
    if hs:
        g = "；".join("%s→%s" % (s.get("id"), os.path.join(str(s.get("install_path", "")), str(s.get("entry", "SKILL.md")))) for s in hs)
        return ",".join(str(s.get("id")) for s in hs), "[SMS 路由·参考] 关键词打分命中（" + g + "·产物目标＝工作区 tmp：" + resolve_home.wtmp() + "）——本行仅供参考，是否派 skill 工具开对等对话真执行（按其 SKILL.md）由你结合话语自主决定；纯问答/解释可直接作答不必派发；确不采纳时简要说明理由即可。"
    return None, "[SMS 路由·参考] 关键词未命中。你可直答（简短·用户语言·内部英语处理）或对照下表/索引择最相关技能用 skill 工具真执行。**判复杂且无现成技能可做的动手诉求（要读写/调设备/跑脚本）：先经 skill 工具派发 Skill_Generator（create 路径）按需新建技能，再回来派发执行——不要因「没找到技能」就空口声称已做或拒绝。** 下表为已装技能，命中与否、直答还是派发或新建，均由你结合意图自主决定，禁止空口声称已执行。" + catalog(sms)
if __name__ == "__main__":
    a = sys.argv[1:] or ["list"]
    if a[0] == "list": print(listtext())
    elif a[0] == "match" and len(a) > 1: sid, inj = route(" ".join(a[1:])); print(json.dumps({"hit": sid, "inject": inj[:220]}, ensure_ascii=False))
    else: print(__doc__.strip().splitlines()[1]); sys.exit(1)
