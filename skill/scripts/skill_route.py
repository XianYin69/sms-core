#!/usr/bin/env python3
"""skill_route.py — 数据流 SMS 技能路由〔仅参考·非裁决〕（批16 LLM 主导）：读 registry/register.json 活跃技能（quarantine/pending_review 信任级跳过）＋ interfaces.json 接口词，与输入打分匹配（阈值 4：技能id 子串命中或分词＋接口词双证据）；命中→chains.log("skill") 记 skill_call 链并返回命中 id 与〔参考〕句——是否真派发由模型在网关工具循环内自主决定（旧「命中即自动开子会话」脚本扇出已废除）；未命中注入技能全表＋批22 指引：动手类无相近技能且属新领域/需复用→模型先派 Skill_Generator 创建再执行；match/listtext 供壳内 :skills 与 ps1 清单。批6：skills()/_terms() 共用 (mtime,size) 内存缓存 _reg（冷读 213ms→暖 ~5ms·task 扇出多调免重解析）；route 计时入 latency。用法：python -B skill_route.py match \"<话语>\" | list"""
import os, sys, json, re, time, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import resolve_home, chains, latency
def _load(sms, rel):
    try: return json.load(open(os.path.join(sms, rel), encoding="utf-8"))
    except Exception: return {}
STOP = {"系统", "问题", "使用", "功能", "支持", "提供", "进行", "可以", "需要", "一个", "这个", "那个", "用户", "管理", "相关", "通过", "以及", "如果", "默认", "显示", "输出", "输入", "操作", "文件", "设置", "配置",
          "今天", "明天", "昨天", "现在", "然后", "一下", "怎么", "什么", "如何", "多少", "为什", "我们", "你们", "他们", "这些", "那些", "帮我", "帮我", "直接", "不能", "完成"}  # 批39：疑问/时间/人称高频词不作技能证据（实测「今天的天气怎么样」误召 decision-council）
def _dterms(d):
    """批39 词表分桶：英文词元与中文二元组各留 60（合计 120）——旧版合并后统一截 80，
    描述加长后英文词把中文词挤出场（实测「压测 SMS」召不回 sms_stress_test），命中反而更差。"""
    t = re.sub(r"\s+", "", str(d or ""))
    en = [x for x in re.findall(r"[a-z][a-z0-9_\-]{3,}", t.lower()) if x not in STOP]
    cj = [t[i:i + 2] for i in range(len(t) - 1) if "\u4e00" <= t[i] <= "\u9fff" and "\u4e00" <= t[i + 1] <= "\u9fff" and t[i:i + 2] not in STOP]
    return list(dict.fromkeys(en[:60] + cj[:60]))
_RC = {}
def _rcfg():
    """批39 打分口径（settings route.* 可调·关掉 idf 即旧行为逐字零回归）：
    idf＝词证据按稀有度加权；thr＝命中阈值；rare_df＝稀有词判定比例（df≤此比例·至少一个稀有词才算证据）；cap＝词分封顶。"""
    try:
        import settings; r = settings.get("route") or {}
    except Exception:
        r = {}
    return (bool(r.get("idf", True)), float(r.get("thr", 4)), float(r.get("rare_df", 0.06)), float(r.get("cap", 6)), int(r.get("top", 2)))
def _reg(sms):
    r = os.path.join(sms, "registry", "register.json"); i = os.path.join(sms, "registry", "interfaces.json")
    try: k = (os.path.getmtime(r), os.path.getsize(r), os.path.getmtime(i), os.path.getsize(i))
    except Exception: k = None
    if (c := _RC.get("v")) and c[0] == k: return c[1]
    ss = [s for s in _load(sms, "registry/register.json").get("skills", []) if s.get("status", "active") == "active" and s.get("trust") not in ("quarantine", "pending_review")]
    tm = {}
    for it in _load(sms, "registry/interfaces.json").get("skills", []):
        ws = [str(n.get("name", "")) for n in it.get("interfaces", [])] + [str(x) for x in (it.get("capabilities") or [])]
        sid = it.get("skill_id") or ""
        tm.setdefault(sid, []).extend(w for w in ws if 1 < len(w) <= 12)
        tm.setdefault(sid, []).extend(_dterms(it.get("purpose")))  # 批39：技能意图整句进项集（旧版只用接口名/能力标题，中文意图全丢）
    for s in ss: tm.setdefault(str(s.get("id") or ""), []).extend(_dterms(s.get("description")))
    df = {}
    for sid, ws in tm.items():
        for w in set(ws): df[w] = df.get(w, 0) + 1
    _RC["v"] = (k, (ss, tm, df)); return ss, tm, df
def skills(sms=None): return _reg(sms or resolve_home.ensure())[0]
def _terms(sms): return _reg(sms)[1]
def _rank(text, sms=None, top=None):
    """批39 打分：id 子串＝4、id 词元＝2/个 不变；词证据按 df 稀有度加权（idf）并要求至少一个稀有词，
    压掉「检查/配置/文件」类人人高频词的误召；rare 判定与阈值走 _rcfg()。返回 (前 top 名 (分数, 技能), 阈值)。"""
    sms = sms or resolve_home.ensure(); ss, terms, df = _reg(sms); u = text.lower()
    use_idf, thr, rare_df, cap, top = _rcfg(); top = top or 2
    n = max(1, len(ss)); rare_max = max(2, int(rare_df * n))  # n＝技能数（idf 基准＝多少技能共享该词，不是词表规模）
    lg = math.log
    def sc(s):
        sid = str(s.get("id", "")).lower()
        base = (4 if sid and sid in u else 0) + 2 * sum(1 for x in re.split(r"[-_.]+", sid) if len(x) >= 4 and x in u)
        ws = [w for w in terms.get(s.get("id"), []) if w.lower() in u]
        if not ws: return base
        if not use_idf: return base + min(4, len(ws))
        if not any(df.get(w, n) <= rare_max for w in ws): return base  # 全是人人有的高频词＝不作证据
        # 对数 idf：只出现 1 次的词≈5.3 分（一个稀有词即可过默认阈 4），人人都有的词≈1 分
        return base + min(cap, sum(1.0 + lg(n / max(1, df.get(w, n))) for w in ws))
    return sorted(((sc(s), s) for s in ss), key=lambda x: -x[0])[:top], thr
def _score(s, u, terms, df=None):
    """旧签名兜底（外部单点调用兼容）：无 df 即等权旧口径。"""
    sid = str(s.get("id", "")).lower()
    base = (4 if sid and sid in u else 0) + 2 * sum(1 for x in re.split(r"[-_.]+", sid) if len(x) >= 4 and x in u)
    if df is None: return base + min(4, sum(1 for w in terms.get(s.get("id"), []) if w.lower() in u))
    n = max(1, len(df)); ws = [w for w in terms.get(s.get("id"), []) if w.lower() in u]
    if not ws: return base
    if not any(df.get(w, n) <= max(2, int(0.06 * n)) for w in ws): return base
    return base + min(6, sum(1.0 + 3.0 * max(0.0, 1.0 - df.get(w, n) / n) for w in ws))
def match(text, sms=None):
    ranked, thr = _rank(text, sms); return [s for sc, s in ranked if sc >= thr]
def catalog(sms=None):
    return ("技能全表：" + "；".join("%s（%s）" % (s.get("id"), re.sub(r"\s+", "", str(s.get("description") or ""))[:26]) for s in skills(sms)))[:620]
def listtext(sms=None):
    ss = skills(sms); return ("技能注册表为空：先运行 register.py 扫描安装根（config.scan_roots），或经 Skill_Generator 创建后重装。" if not ss else "可调用托管技能 %d 个（说法即打分给〔参考〕·采纳与否由模型定，Ctrl+K 可显式选填）：" % len(ss) + "；".join("%s（%s）" % (s.get("id"), re.sub(r"\s+", "", str(s.get("description") or ""))[:26]) for s in ss) + "。执行类诉求经 skill 工具派发对等对话真派发执行（批23 每派发自开独立 conv），结果整合作答；需本机真跑脚本/调设备时以 :use 切 agent CLI 承接。")[:1400]
def route(text, sms=None):
    t0 = time.perf_counter(); sms = sms or resolve_home.ensure()
    ranked, thr = _rank(text, sms); hs = [s for sc, s in ranked if sc >= thr]
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
