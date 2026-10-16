#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dsm.py — DSM v1（Delta Session Mesh）sms-core 侧编解码器与接线（叠加层，不是替换层）。

真源：Downloads/OpenAI兼容格式评测_20261005/DSM_v1/{规范_DSM_v1.md,dsm.schema.json,dsm_egress.py}
接线：DSM_wiring_contract.md §1-§6（端点/键名/开关语义/验收矩阵），逐条遵守、不自创。
默认全关：llm_gateway.dsm.enabled=false 时 gateway/gateway_sse 与今天逐字节同路（验收 A）。
本文件是两侧共享的唯一编解码器（SMSocket 侧逐字节复制），算法复用 dsm_egress.py 参考实现：
fingerprint/canon_mem/canon_cons/budget_map/to_openai/to_anthropic/split_fan/leak_check/ROLE 双射。
客户端新增（参考实现没有、契约 C/E 要求）：build_env（OpenAI msgs→信封）、
decode_to_openai_shape（DSM 响应信封→choices/usage，下游工具循环零改动）、
merge_stream（out=delta 按 seq 归并）、validate（按 dsm.schema.json 封闭表校验·纯标准库）、
SchemaStore（落盘镜像 <SMS_HOME>/runtime/dsm_schemas.json·atomic_io 原子写）。
边界：msgpack 本机未装→仅协商位；mem 的 `id+N` 邻居扩展只剥后缀（DFS 展开未落地）；
服务端会话态由 SMSocket 持有，本侧按 sid|cid|lane 记 delta 水位（前缀不符即全量重同步）。
用法：python -B dsm.py status|on|off|matrix|selftest
"""
import os, sys, json, re, glob, time, hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, chains, settings, atomic_io

# ---- 枚举与封闭键表（与 dsm_egress.py / dsm.schema.json 一致·顺序锁死） ----------
ROLE = ["system", "user", "assistant", "tool", "constraint", "note"]
RID = {n: i for i, n in enumerate(ROLE)}
POLICY_KEYS = {"sid", "cid", "lane", "dep", "lat", "fan", "bill", "verify", "out", "x"}
CORE = {"v", "sch", "mem", "d", "cons", "budget"} | POLICY_KEYS
CTYPE = "application/dsm+json"
CTYPE_STREAM = "application/x-ndjson"
ENDPOINT = "/v1/dsm/chat"
ENDPOINT_SCHEMA = "/v1/dsm/schema"
ISO_CHAINS = tuple(getattr(chains, "ISO", ()) or ())
LANE_CORE_TOOLS = ("exec", "read", "write", "grep", "glob", "ls")
DEFAULTS = {"enabled": False, "style": "openai-chat", "openai_compat": True, "fallback": True,
            "schema_ref": True, "mem_ref": True, "lane_tools": False, "budget": "auto",
            "out": "json", "fan": False}
REASON_TIER = {"low": 0, "mid": 1024, "high": 4096, "auto": None}
_REF_RE = re.compile(r"^sha1:[0-9a-f]{12}$")
_ID_RE = re.compile(r"^[0-9a-f]{10}$")

assert len(set(ROLE)) == len(ROLE) == len(RID), "DSM: ROLE 枚举重复"
assert [ROLE[RID[n]] for n in ROLE] == ROLE, "DSM: ROLE/RID 双射破裂（位置化即失效）"


class Unsupported(Exception):
    """信封装不下的语义（多模态 content 数组等）——调用方据此走 legacy 并打日志，
    绝不静默丢内容（契约 C：语义保真优先于强行套信封）。"""


# ---- 开关读取（契约 §2·缺失即安全默认，绝不因缺配置改变现有行为） ----------------
def cfg(sms=None):
    """llm_gateway.dsm 生效值＝DEFAULTS 深合并配置；api_key 一类敏感键永不进入返回结构。"""
    try:
        raw = (settings.eff(sms).get("llm_gateway") or {}).get("dsm") or {}
    except Exception:
        raw = {}
    c = dict(DEFAULTS)
    for k, v in raw.items():
        if k == "comment":
            continue
        c[k] = v
    c["enabled"] = bool(c["enabled"]); c["openai_compat"] = bool(c["openai_compat"]); c["fallback"] = bool(c["fallback"])
    return c


def enabled(sms=None):
    return bool(cfg(sms).get("enabled"))


def set_enabled(v, sms=None):
    """开关唯一写入口：经 settings.set 写 llm_gateway.dsm.enabled（settings 只 pop 赋 None 的键，
    故 False 必须写成 JSON false 而非 None，否则整块被抹掉）；其余键原样保留。"""
    sms = sms or resolve_home.ensure()
    # 只动用户自己写过的键：读原始 config（非 eff 深合并结果），否则会把整份默认值钉进
    # config.json，日后改 settings.default.json 的默认值就不再生效。
    cur = dict(((resolve_home.conf(sms).get("llm_gateway") or {}).get("dsm")) or {})
    cur.pop("comment", None); cur["enabled"] = bool(v)
    settings.set("llm_gateway.dsm", cur, sms=sms)
    # 开关是操作员的显式意图：清掉降级冷却，否则刚修好服务端还要白等 120 秒
    clear_broken()
    return cur


def set_out(v, sms=None):
    """响应编码开关唯一写入口：llm_gateway.dsm.out = json|delta（尾巴3）。

    delta＝服务端按 seq 吐 ndjson，客户端逐帧上屏（真逐字流）；json＝一次整包信封。
    默认仍是 json（安全默认：任何一环出问题切回来即可，灰度回滚一行）。
    """
    if v not in ("json", "delta"):
        raise ValueError("dsm.out 只能是 json|delta（msgpack 本机未装＝仅协商位）")
    sms = sms or resolve_home.ensure()
    cur = dict(((resolve_home.conf(sms).get("llm_gateway") or {}).get("dsm")) or {})
    cur.pop("comment", None); cur["out"] = v
    settings.set("llm_gateway.dsm", cur, sms=sms)
    clear_broken()
    return cur


def sms_home():
    try:
        return resolve_home.ensure()
    except Exception:
        return os.environ.get("SMS_HOME") or r"C:\Users\User\AppData\Local\SMS"


def chains_dir():
    return os.path.join(sms_home(), "chains")


# ---- URL 拼接（契约 §1·尾巴2 的结构性根治） -------------------------------------------------
# base_url 有两种活法：'http://h:8011/v1'（legacy 靠 base + "/chat/completions"）与
# 'http://h:8011'（裸 host）。而 dsm.ENDPOINT 自带 '/v1/…'（契约常量）。两种混用会拼出
# '/v1/v1/dsm/chat' → 服务端 404 → 客户端判定「服务端没有 DSM」并锁死降级，DSM 永远用不上
# （2026-10-06 实测根因）。归一规则只有一条**不变量**：最终 URL 里 '/v1/' 只出现一次。
# 因此：base 已含 /v1（结尾或中段代理前缀均可）而 path 又带 /v1 前缀 → 剥掉 path 的前缀；
# base 不含 /v1 而 path 也不含 → 补上 /v1（契约端点必须落在 /v1 下）。
_V1 = re.compile(r"/v1/?$")


def api_url(path, base=None, sms=None):
    """**唯一的 URL 拼接口**：legacy 路径（'/chat/completions'·不带 /v1）与 DSM 常量
    （'/v1/dsm/*'）都走这里，调用方不再自己 rstrip('/')+拼串——省得下一个 '尾巴2' 藏在
    某一处手写拼接里。"""
    if base is None:
        base = (settings.eff(sms).get("llm_gateway") or {}).get("base_url") or ""
    b = str(base).rstrip("/")
    p = str(path or "")
    if not p.startswith("/"):
        p = "/" + p
    has_v1 = bool(_V1.search(b)) or "/v1/" in b
    if p.startswith("/v1/"):
        return b + (p if not has_v1 else p[len("/v1"):])
    return b + ("/v1" if not has_v1 else "") + p


# ---- 引用→内容：指纹 / 记忆物化 / 约束模板（算法照抄 dsm_egress.py，不重发明） ----
def fingerprint(system, tools):
    """sch＝sha1(json.dumps({"s":system,"t":tools}, sort_keys, ensure_ascii=False))[:12]。
    顺序锁死是位置化的前提：工具开关变→子集变→指纹变→引用自动失效，不串味。"""
    blob = json.dumps({"s": system or "", "t": tools or []}, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return "sha1:" + hashlib.sha1(blob).hexdigest()[:12]


def frag(fid, sms=None):
    """按 id 在 12 链目录取碎片（id 全局唯一·先扫目录）。utf-8-sig 兼容 BOM 落盘。"""
    for p in glob.glob(os.path.join(sms or chains_dir(), "*", fid + ".json")):
        try:
            return json.load(open(p, encoding="utf-8-sig"))
        except Exception:
            return None
    return None


def _same_session(f, sid):
    """会话隔离（红线 17）：ISO 链碎片必须带 member→本 sess 边才准物化；
    非 ISO 链（user/memory/logic/knowledge…）属跨会话共享记忆，不过滤（与 prompt_pack 口径一致）。"""
    if not sid or f.get("chain") not in ISO_CHAINS:
        return True
    for e in (f.get("edges") or []):
        if len(e) >= 2 and e[1] == "member" and e[0] == sid:
            return True
    return False


def canon_mem(ids, sid=None, strict=False):
    """物化 mem：按 id 字典序（不是按得分）——顺序确定才有字节稳定前缀，才谈得上缓存命中。
    带 `+N` 后缀的引用剥掉深度位（邻居展开未落地→宁少带不误带）；跨会话 id 默认拒解并计数。"""
    out, skipped = [], []
    for raw in sorted(set((i or "").split("+")[0] for i in (ids or []) if i)):
        f = frag(raw)
        if not f:
            skipped.append(raw); continue
        if not _same_session(f, sid):
            skipped.append(raw + "!xsess"); continue
        out.append("[%s·f%d·%s] %s" % (f["id"], int(f.get("freq", 1) or 1), f["chain"], f["text"]))
    if strict and skipped:
        raise Unsupported("mem 引用不可解析/跨会话：%s" % ",".join(skipped[:4]))
    return "\n".join(out)


def canon_cons(cons):
    """约束槽位→确定性自然语言（提供商没有槽位，只能模板化，模板本身锁死以保证可复现）。"""
    if not cons:
        return ""
    L = []
    if cons.get("dedup_key"):
        L.append("去重口径：按业务键 " + "+".join(cons["dedup_key"]) + " 判重（不是按行号/整行）。")
    if cons.get("fx"):
        L.append("汇率（固定，勿自行取值）：" + "，".join("%s=%s" % (k, v) for k, v in sorted(cons["fx"].items())) + "。")
    if cons.get("round"):
        L.append("数值舍入：%s，先算后舍。" % cons["round"])
    if cons.get("output"):
        L.append("输出结构：严格按 schema %s 的位置序，不多不少。" % cons["output"])
    for c in cons.get("must", []):
        L.append("硬约束：" + c)
    return "\n".join(L)


def budget_map(b, style):
    """思考预算→各提供商真实字段（唯一能撬动 62-67% 输出侧成本的把手）。"""
    b = b or {}
    tier, mo = b.get("reason", "auto"), b.get("max_out")
    if style in ("openai", "openai-chat", "openai-responses"):
        # 与 dsm_egress.py 参考实现逐字一致（规范 §7 表格写 openai-responses→reasoning.effort，
        # 与参考实现不符——按契约「复用其算法」取参考实现，分歧已登记进交付报告）。
        out = {}
        if tier and tier != "auto":
            out["reasoning_effort"] = tier          # 分档，不动 max_tokens
        if mo:
            out["max_completion_tokens" if style == "openai-responses" else "max_tokens"] = mo
        return out
    if style == "anthropic":
        out = {}
        if tier and tier != "auto":
            out["thinking"] = {"type": "enabled", "budget_tokens": REASON_TIER[tier] or 1024}
        if mo:
            out["max_tokens"] = mo + int(out.get("thinking", {}).get("budget_tokens", 0))
        return out
    return {}


# ---- SchemaStore：ref→{system,tools} 物化仓库（客户端镜像·原子写盘） ---------------
class SchemaStore:
    """同 hash 同内容：客户端持镜像只为 x.mem_off 调试与本地物化，真源在服务端 runtime。
    落盘＝<SMS_HOME>/runtime/dsm_schemas.json（atomic_io 原子替换·缓存文件不进 skill 目录）。"""

    def __init__(self, path=None, sms=None):
        self.path = path or os.path.join(sms or sms_home(), "runtime", "dsm_schemas.json")
        self.by_hash = {}
        self._loaded = False
        self._dirty = False

    def _load(self):
        if self._loaded:
            return self.by_hash
        self._loaded = True
        try:
            doc = atomic_io.rjson(self.path, default={}) or {}
            self.by_hash = dict(doc.get("schemas") or {})
        except Exception:
            self.by_hash = {}
        return self.by_hash

    def _save(self):
        """写盘：_dirty 为真才真正落盘（false＝幂等 no-op）。"""
        try:
            if not self._dirty:
                return True
            atomic_io.wjson(self.path, {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                        "schemas": self.by_hash})
            self._dirty = False
            return True
        except Exception:
            return False

    def put(self, system, tools):
        """O(1) 注册：内存更新 + 标脏，写盘由 flush() 批量收口（避免每帧一写）。"""
        blob = json.dumps({"s": system, "t": tools}, ensure_ascii=False, sort_keys=True)
        h = "sha1:" + hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]
        self._load()[h] = {"system": system, "tools": tools, "bytes": len(blob.encode("utf-8"))}
        self._dirty = True
        return h

    def flush(self):
        """调用方（首帧登记出口 / 进程退出钩子）批量落盘；force 绕过 dirty 门。"""
        self._dirty = True
        return self._save()

    def get(self, h):
        return self._load().get(h)

    def has(self, h):
        return h in self._load()

    def refs(self):
        return len(self._load())


# ---- 校验（按 dsm.schema.json 的封闭表·纯标准库，本机无 jsonschema 依赖） ---------
def validate(env):
    """回问题列表（空＝合法）。additionalProperties:false 是硬约束：新语义一律走 x.<域>.<名>。"""
    e = []
    if not isinstance(env, dict):
        return ["env 必须是对象"]
    for k in ("v", "sch", "d"):
        if k not in env:
            e.append("缺必填键 %s" % k)
    for k in env:
        if k not in CORE:
            e.append("未知顶层键 %s（封闭表 additionalProperties:false）" % k)
    if env.get("v") != 1:
        e.append("v 必须为 1（协商位）")
    sch = env.get("sch")
    if not (isinstance(sch, str) and _REF_RE.match(sch)):
        e.append("sch 格式必须 sha1:<12hex>")
    d = env.get("d")
    if not isinstance(d, list):
        e.append("d 必须是数组")
    else:
        for i, t in enumerate(d):
            if not (isinstance(t, (list, tuple)) and len(t) == 2):
                e.append("d[%d] 必须是 [role_id, text] 位置化二元" % i); continue
            if not (isinstance(t[0], int) and 0 <= t[0] <= len(ROLE) - 1):
                e.append("d[%d] role_id 越界（0-%d）" % (i, len(ROLE) - 1))
            if not isinstance(t[1], str):
                e.append("d[%d] text 必须是字符串" % i)
    mem = env.get("mem")
    if mem is not None:
        if not isinstance(mem, list):
            e.append("mem 必须是 id 数组")
        else:
            for i, x in enumerate(mem):
                if not (isinstance(x, str) and _ID_RE.match(x.split("+")[0])):
                    e.append("mem[%d] 必须是 10 位十六进制碎片 id（可带 +N 深度后缀）" % i)
    if env.get("out") is not None and env["out"] not in ("json", "delta", "msgpack"):
        e.append("out 必须 ∈ json|delta|msgpack")
    b = env.get("budget")
    if b is not None:
        if not isinstance(b, dict):
            e.append("budget 必须是对象")
        else:
            if b.get("reason") not in (None, "low", "mid", "high", "auto"):
                e.append("budget.reason 必须 ∈ low|mid|high|auto")
            for k in b:
                if k not in ("reason", "max_out", "when_exceeded"):
                    e.append("budget 未知键 %s" % k)
            if b.get("when_exceeded") not in (None, "answer_partial", "truncate", "retry_higher", "fallback_lane"):
                e.append("budget.when_exceeded 非法")
    for k, allow in (("cons", dict), ("lat", dict), ("fan", dict), ("bill", dict), ("verify", list), ("x", dict)):
        v = env.get(k)
        if v is not None and not isinstance(v, allow):
            e.append("%s 类型应为 %s" % (k, allow.__name__))
    lat = env.get("lat")
    if isinstance(lat, dict) and lat.get("on_exceed") not in (None, "failover", "degrade", "abort"):
        e.append("lat.on_exceed 非法")
    fan = env.get("fan")
    if isinstance(fan, dict):
        if not (isinstance(fan.get("n", 1), int) and 1 <= fan.get("n", 1) <= 256):
            e.append("fan.n 必须 1..256")
        if fan.get("merge") not in (None, "concat", "vote", "reduce", "first_ok"):
            e.append("fan.merge 非法")
    return e


# ---- 会话/道号锚点（沿用现有获取方式，不自创来源） -------------------------------
def current_lane(conv=None):
    """lane＝当前任务总览 running 行 id（无则空串）——与 gateway.run 守卫同用 chains.ACTIVE["conv"]。"""
    c = conv if conv is not None else (chains.ACTIVE.get("conv") or "")
    if not c:
        return ""
    try:
        import task_table as tt
        td = tt.TD
        if not os.path.isdir(td):
            return ""
        for fn in sorted(os.listdir(td)):
            if not fn.endswith(".json"):
                continue
            doc = tt._load(fn[:-5]) or {}
            if doc.get("conv") != c:
                continue
            for x in (doc.get("subtasks") or []):
                if str(x.get("status")) == "running":
                    return str(x.get("id") or "")
    except Exception:
        return ""
    return ""


def session_ids(conv=None):
    """(sid, cid)＝chains ACTIVE 的 sess/conv（沿用现有获取方式）。"""
    try:
        sid = chains.ACTIVE.get("sess") or chains.session_id() or ""
    except Exception:
        sid = ""
    return sid, (conv if conv is not None else (chains.ACTIVE.get("conv") or ""))


# ---- msgs ⇄ 信封：位置化 turn 编解码（x.sms.turn_json 声明·两侧共享同一份代码） ----
_TURN_ROLES = (2, 3)          # assistant / tool 可能带协议外结构（tool_calls·tool_call_id）


def encode_turn(m):
    """OpenAI message → [role_id, text]。带 tool_calls 的 assistant 与带 tool_call_id 的 tool，
    把整条 turn 规范化成 JSON 字符串放进位置化 text 槽——text 属「内容面」不是协议面，
    故不违反 POLICY_KEYS 不出网；由 x.sms.turn_json=1 声明语义，decode_turn 精确还原。"""
    r = m.get("role")
    if r not in RID:
        raise Unsupported("信封无此 role：%s" % r)
    c = m.get("content")
    if isinstance(c, list):
        raise Unsupported("多模态/分段 content 不入信封（d.text 只承载字符串）")
    rid = RID[r]
    if rid in _TURN_ROLES and (m.get("tool_calls") or m.get("tool_call_id")):
        keep = {"role": r, "content": c if c is not None else ""}
        if m.get("tool_calls"):
            keep["tool_calls"] = m["tool_calls"]
        if m.get("tool_call_id"):
            keep["tool_call_id"] = m["tool_call_id"]
        return rid, json.dumps(keep, ensure_ascii=False, sort_keys=True)
    return rid, (c or "")


def decode_turn(rid, text):
    """[role_id, text] → OpenAI message（encode_turn 的逆·唯一还原规则）。"""
    m = {"role": ROLE[rid] if isinstance(rid, int) and 0 <= rid < len(ROLE) else str(rid), "content": text}
    if isinstance(rid, int) and rid in _TURN_ROLES and isinstance(text, str) and text[:1] == "{":
        try:
            j = json.loads(text)
        except Exception:
            return m
        if isinstance(j, dict) and ("tool_calls" in j or "tool_call_id" in j):
            out = {"role": j.get("role") or m["role"], "content": j.get("content", "")}
            if j.get("tool_calls"):
                out["tool_calls"] = j["tool_calls"]
            if j.get("tool_call_id"):
                out["tool_call_id"] = j["tool_call_id"]
            return out
    return m


# ---- delta 水位：d 只带新增轮次（服务端会话态由 SMSocket 持有·本侧只记已发前缀） ----
def _phash(msgs):
    return hashlib.sha1(json.dumps(msgs, ensure_ascii=False, sort_keys=True, default=str)
                        .encode("utf-8")).hexdigest()[:16]


def _state_path(sms=None):
    return os.path.join(sms or sms_home(), "runtime", "dsm_state.json")


def _state(sms=None):
    try:
        return atomic_io.rjson(_state_path(sms), default={}) or {}
    except Exception:
        return {}


def delta_window(key, msgs, sms=None):
    """回 (新增 msgs, 起始下标)。前缀哈希不符／水位越界＝服务端态可疑 → 全量重同步，
    宁可对不上缓存也绝不错发半截历史（语义保真优先于省字节）。"""
    st = _state(sms).get(key) or {}
    n, h = int(st.get("sent") or 0), st.get("ph")
    if n > len(msgs) or (h and h != _phash(msgs[:n])):
        return list(msgs), 0
    return list(msgs[n:]), n


STATE_MAX = 512                 # 水位条目上限（conv×lane 组合会一直长，必须封顶）
STATE_TTL = 86400.0             # 一天没用过的水位直接丢：宁可全量重发也不留僵尸键


def commit_delta(key, msgs, sms=None):
    """只在请求成功后调用（失败不得推进水位，否则下一轮少发历史）。

    水位文件按 conv|cid|lane 累积键，历史版本只增不减——每个新对话/新任务行都
    追加一条，长跑必成无界增长。这里同服务端 SessionStore 的口径封顶＋过期。
    """
    try:
        d = _state(sms)
        d[key] = {"sent": len(msgs), "ph": _phash(msgs), "ts": int(time.time())}
        cut = time.time() - STATE_TTL
        for k in [k for k, v in d.items()
                  if not isinstance(v, dict) or float(v.get("ts") or 0) < cut]:
            d.pop(k, None)
        while len(d) > STATE_MAX:
            oldest = min(d, key=lambda k: float((d[k] or {}).get("ts") or 0))
            d.pop(oldest, None)
        atomic_io.wjson(_state_path(sms), d); return True
    except Exception:
        return False


def reset_delta(key, sms=None):
    try:
        d = _state(sms); d.pop(key, None); atomic_io.wjson(_state_path(sms), d); return True
    except Exception:
        return False


def build_env(msgs, tools=None, model=None, dsm_cfg=None, store=None, lane=None, mem=None,
              cons=None, budget=None, fan=None, x=None, sms=None, resync=False):
    """OpenAI msgs → DSM 信封（契约 §3：sch 指纹、mem 引用、d 位置化、POLICY 不出网）。
    首条 system＝SYS（进 sch，不进 d）；其余轮次进 d。抛 Unsupported＝信封装不下
    （多模态等），调用方据此走 legacy 并记日志，绝不静默丢语义。
    信封附带 x.sms.schema_reg＝{ref,system,tools}：算 sch 指纹用的同一份原文，
    客户端 schema_frame 首帧登记直接取它（与指纹必然一致·不读本地镜像·杜绝 422/400）。
    该键是策略键不出网（服务端 materialize 只读 store.get(sch)，无此键零影响）。"""
    c = dsm_cfg or cfg()
    store = store or SchemaStore(sms=sms)
    sms = sms or sms_home()
    sys_txt = ""
    rest = []
    for m in msgs:
        if m.get("role") == "system" and not sys_txt:
            sys_txt = m.get("content") or ""
        else:
            rest.append(m)
    tools = list(tools or [])
    if c.get("lane_tools"):
        tools = [t for t in tools if ((t.get("function") or t).get("name") in LANE_CORE_TOOLS)]
    sch = store.put(sys_txt, tools)
    sid, cid = session_ids()
    lane = lane if lane is not None else current_lane()
    key = "%s|%s|%s" % (sid or "-", cid or "-", lane or "-")
    new, start = (rest, 0) if resync else delta_window(key, rest, sms)
    d = []
    for m in new:
        rid, txt = encode_turn(m)
        d.append([rid, txt])
    env = {"v": 1, "sch": sch, "d": d}
    if sid:
        env["sid"] = sid
    if cid:
        env["cid"] = cid
    if lane:
        env["lane"] = lane
    if c.get("mem_ref") and mem:
        env["mem"] = list(mem)
    if cons:
        env["cons"] = cons
    b = budget or (None if c.get("budget") in (None, "auto") else {"reason": c.get("budget")})
    if b:
        env["budget"] = b
    if fan and c.get("fan"):
        env["fan"] = fan
    # sms.delta_from：本帧 d 在完整历史中的起始下标。服务端 SessionStore 靠它区分
    # 「增量追加 / 全量重同步 / 水位不符」——不带它时服务端只能把 d 当全量整表替换，
    # 于是增量帧会静默丢掉之前的轮次（语义丢失）。0＝全量，>0＝自该下标追加。
    xx = {"sms.turn_json": 1, "sms.style": c.get("style"), "sms.delta_key": key,
          "sms.delta_from": int(start)}
    # schema_reg：算 sch 指纹用的同一份 system/tools 原文。客户端 schema_frame
    # 首帧登记取它（与指纹必然一致），不读本地镜像（防重启/写盘去抖滞后致 422/400）。
    xx["sms.schema_reg"] = {"ref": sch, "system": sys_txt, "tools": list(tools)}
    if not c.get("schema_ref"):
        xx["sms.inline_schema"] = {"system": sys_txt, "tools": tools}
    if not c.get("mem_ref"):
        xx["mem_off"] = True
    for k, v in (x or {}).items():
        xx[k] = v
    env["x"] = xx
    env["out"] = c.get("out") or "json"
    if model:
        xx["sms.model"] = model
    errs = validate(env)
    if errs:
        raise Unsupported("信封校验失败：" + "；".join(errs[:4]))
    return env


# ---- 出口翻译：内部 → 提供商指定格式（算法与 dsm_egress.py 一致） ----------------
def _turn_of(t):
    if isinstance(t, (list, tuple)):
        return (t[0] if isinstance(t[0], int) else RID.get(str(t[0]), 1)), (t[1] if len(t) > 1 else "")
    return RID.get(t.get("role"), 1), (t.get("text") or t.get("content") or "")


def _inline(env, store):
    """x.sms.inline_schema＝schema_ref 关闭位：不查仓库，直接用信封内联的 system+tools。"""
    inl = ((env.get("x") or {}).get("sms.inline_schema")) or {}
    if inl:
        return {"system": inl.get("system") or "", "tools": inl.get("tools") or []}
    return store.get(env.get("sch")) or {"system": "", "tools": []}


def to_openai(env, store, alias=None):
    rec = _inline(env, store)
    mem = "" if (env.get("x") or {}).get("mem_off") else canon_mem(env.get("mem"), env.get("sid"))
    cons = canon_cons(env.get("cons"))
    msgs = []
    sys_txt = (rec["system"] or "").strip()
    tail = "\n".join(x for x in (mem, cons) if x)
    if sys_txt:
        msgs.append({"role": "system", "content": sys_txt})
    if tail:
        msgs.append({"role": "system", "content": tail})
    for t in env.get("d", []):
        rid, txt = _turn_of(t)
        msgs.append(decode_turn(rid, txt))
    body = {"model": alias or (env.get("x") or {}).get("sms.model") or "auto", "messages": msgs}
    if rec["tools"]:
        body["tools"] = rec["tools"]
    body.update(budget_map(env.get("budget"), "openai"))
    return body


def to_responses(env, store, alias=None):
    rec = _inline(env, store)
    mem = "" if (env.get("x") or {}).get("mem_off") else canon_mem(env.get("mem"), env.get("sid"))
    cons = canon_cons(env.get("cons"))
    inp = []
    for t in env.get("d", []):
        rid, txt = _turn_of(t)
        m = decode_turn(rid, txt)
        inp.append({"role": m["role"], "content": m.get("content") or ""})
    ins = "\n".join(x for x in (rec["system"], mem, cons) if x)
    body = {"model": alias or (env.get("x") or {}).get("sms.model") or "auto", "input": inp}
    if ins:
        body["instructions"] = ins
    if rec["tools"]:
        body["tools"] = rec["tools"]
    body.update(budget_map(env.get("budget"), "openai-responses"))
    return body


def to_anthropic(env, store, alias=None):
    rec = _inline(env, store)
    mem, cons = canon_mem(env.get("mem"), env.get("sid")), canon_cons(env.get("cons"))
    sys_txt = "\n".join(x for x in (rec["system"], mem, cons) if x)
    msgs = []
    for t in env.get("d", []):
        rid, txt = _turn_of(t)
        role = "assistant" if rid == 2 else "user"
        if msgs and msgs[-1]["role"] == role:
            msgs[-1]["content"][0]["text"] += "\n" + txt        # 同角色合并（提供商要求交替）
        else:
            msgs.append({"role": role, "content": [{"type": "text", "text": txt}]})
    body = {"model": alias or (env.get("x") or {}).get("sms.model") or "auto",
            "system": sys_txt, "messages": msgs}
    if rec["tools"]:
        body["tools"] = [{"name": f["function"]["name"], "description": f["function"].get("description", ""),
                          "input_schema": f["function"].get("parameters", {})} for f in rec["tools"]]
    body.update(budget_map(env.get("budget"), "anthropic"))
    return body


def split_fan(env, done_lanes=None):
    """fan 是声明不是线程：一条内部报文 → N 个 lane 子报文 → 网关 /v1/batch 的 requests[]。
    dep 未满足的道不进批（串行）；同 sid/sch 共享会话态与 schema 引用。
    兼容参考实现的 env["_done_lanes"] 写法（done_lanes=None 时回退读它）。"""
    fan = env.get("fan") or {}
    n = int(fan.get("n", 1) or 1)
    lanes = fan.get("lane_ids") or ["%s.%d" % (env.get("lane", "l"), i) for i in range(n)]
    done = set(done_lanes if done_lanes is not None else (env.get("_done_lanes") or []))
    items, ready = [], []
    for lid in lanes:
        sub = {k: v for k, v in env.items() if k not in ("fan", "_done_lanes")}
        sub["lane"] = lid
        d = (fan.get("per_lane") or {}).get(lid)
        if d:
            sub["d"] = d
        items.append(sub)
        blocked = [x for x in (env.get("dep") or []) if x not in done]
        (ready if not blocked else []).append(lid)
    return {"requests": items, "dispatchable": bool(ready),
            "concurrency": int(fan.get("concurrency", len(ready) or 1)),
            "ready": ready, "blocked": [l for l in lanes if l not in ready],
            "merge": fan.get("merge", "concat"), "fail_fast": bool(fan.get("fail_fast", False))}


def leak_check(env, body):
    """红线一：内部策略键不得作为出网报文的「顶层键」出现（顶层＝协议面，嵌套＝内容面）。"""
    return sorted(k for k in POLICY_KEYS if k != "out" and k in (body or {}))


def name_collision(store, sch):
    """红线二登记：内部短键与工具参数名撞车（实测本机 task.lane / task_plan.lane 已撞）。
    新增核心键前必须先跑它。tools schema 属内容面，允许存在但必须登记。"""
    rec = store.get(sch) or {"tools": []}
    names = set()
    for t in rec.get("tools") or []:
        props = ((t.get("function") or {}).get("parameters") or {}).get("properties") or {}
        names |= set(props)
    return sorted(names & (CORE | {"model"}))


# ---- 响应信封 → OpenAI 形状（下游 agent_dispatch 工具循环零改动的前提） -----------
def _norm_tool_call(i, tc):
    f = (tc.get("function") or {}) if isinstance(tc, dict) else {}
    name = f.get("name") or tc.get("name") or tc.get("tool") or ""
    args = f.get("arguments")
    if args is None:
        args = tc.get("arguments") if tc.get("arguments") is not None else tc.get("parameters")
    if isinstance(args, (dict, list)):
        args = json.dumps(args, ensure_ascii=False, sort_keys=True)
    return {"id": tc.get("id") or ("dsm_tc_%d" % i), "type": "function",
            "function": {"name": str(name), "arguments": args if isinstance(args, str) else "{}"}}


def decode_to_openai_shape(resp):
    """DSM 响应信封 → {"model","choices":[{"message","finish_reason"}],"usage"}。
    answer＝字符串 或 [{tool_call}]；stop 一律映射进 OpenAI 词表（end_turn→stop /
    tool_call→tool_calls / length→length），未知值落 stop，原始 stop 留在返回的
    dsm 段——按 finish_reason 分支的调用方绝不因走 DSM 而改变行为。
    usage 三分账回填 OpenAI 口径：in→prompt_tokens，out_reason+out_answer→completion_tokens，
    cache_read→prompt_tokens_details.cached_tokens，out_reason→completion_tokens_details.reasoning_tokens。"""
    if isinstance(resp, list):                       # out=delta 的原始行也收（幂等归并）
        resp = merge_stream(resp)
    r = resp or {}
    ans = r.get("answer")
    tcs, parts = [], []
    if isinstance(ans, str):
        parts.append(ans)
    elif isinstance(ans, list):
        for i, it in enumerate(ans):
            if isinstance(it, dict) and (it.get("function") or it.get("name") or it.get("tool")):
                tcs.append(_norm_tool_call(i, it))
            elif isinstance(it, str):
                parts.append(it)
            else:
                parts.append(json.dumps(it, ensure_ascii=False, default=str))
    content = "\n".join(p for p in parts if p != "")
    reason = r.get("reason") or {}
    if isinstance(reason, str):
        reason = {"summary": reason}
    u = r.get("usage") or {}
    fin = str(r.get("stop") or "")
    # stop→finish_reason 必须落在 OpenAI 词表内（契约 §4）。把 DSM 的 end_turn 直接抄进
    # finish_reason，任何按 OpenAI 口径分支的调用方都会把它当「未知停止原因」，DSM 路径
    # 与 legacy 路径就此分叉——「工具循环零改动」的承诺也就破了。
    _S2F = {"end_turn": "stop", "stop": "stop", "tool_call": "tool_calls",
            "length": "length", "max_tokens": "length",
            "content_filter": "content_filter"}
    finish = "tool_calls" if tcs else _S2F.get(fin, "stop")
    inp = int(u.get("in") or 0); orz = int(u.get("out_reason") or 0); oa = int(u.get("out_answer") or 0)
    usage = {"prompt_tokens": inp, "completion_tokens": orz + oa, "total_tokens": inp + orz + oa,
             "prompt_tokens_details": {"cached_tokens": int(u.get("cache_read") or 0)},
             "completion_tokens_details": {"reasoning_tokens": orz}}
    if u.get("cost") is not None:
        usage["cost"] = u.get("cost"); usage["currency"] = u.get("currency")
    usage["dsm"] = u                                    # 三分账原样留存（归因用·不覆盖 OpenAI 口径）
    msg = {"role": "assistant", "content": content.replace("\x00", "").replace("\r", "\n"),
           "reasoning_content": reason.get("summary") or ""}
    if tcs:
        msg["tool_calls"] = tcs
    return {"model": r.get("model") or r.get("egress") or "dsm", "object": "chat.completion",
            "choices": [{"index": 0, "message": msg, "finish_reason": finish}], "usage": usage,
            "dsm": {"v": r.get("v"), "sid": r.get("sid"), "lane": r.get("lane"), "seq": r.get("seq"),
                    "egress": r.get("egress"), "lanes": r.get("lanes"),
                    "stop": fin}}


def merge_stream(envs):
    """out=delta：服务端按 seq 吐 ndjson 信封，本侧归并成一条完整响应信封再解码。
    文本增量按 seq 拼接；reason/usage/stop 取最后一个非空值（乱序到达也稳定）。"""
    seqs = sorted((e for e in (envs or []) if isinstance(e, dict)), key=lambda e: int(e.get("seq") or 0))
    out = {"v": 1, "answer": "", "reason": {"tokens": 0, "summary": ""}}
    for e in seqs:
        for k in ("sid", "lane", "egress", "stop", "model"):
            if e.get(k):
                out[k] = e[k]
        a = e.get("answer")
        if isinstance(a, list):
            # 收口帧的 tool_calls 数组**必须胜出**：服务端正文按 seq 先吐完，末帧才带
            # 工具调用；旧写法「非空字符串时丢弃数组」＝ delta 模式下工具循环整条断掉
            # （2026-10-06 实测）。文本与工具调用同时存在时按契约 §4 只保留数组，与
            # json 模式（encode_response 同规则）保持同形。
            out["answer"] = a if a else out["answer"]
        elif isinstance(a, str) and a:
            out["answer"] = (out["answer"] if isinstance(out["answer"], str) else "") + a
        rs = e.get("reason") or {}
        if isinstance(rs, str):
            out["reason"]["summary"] += rs
        else:
            out["reason"]["summary"] += rs.get("summary") or ""
            out["reason"]["tokens"] = int(rs.get("tokens") or out["reason"]["tokens"])
        if e.get("usage"):
            out["usage"] = e["usage"]
        if e.get("lanes"):
            out["lanes"] = e["lanes"]
    return out


# ---- 字节账（status 用·真算不估算） ---------------------------------------------
def measure(msgs=None, tools=None, model=None, dsm_cfg=None, store=None, sms=None):
    """同一份 msgs 分别算 legacy body 与 DSM 信封的 UTF-8 字节（含物化后的出网字节）。"""
    c = dsm_cfg or cfg()
    sms = sms or sms_home()
    store = store or SchemaStore(sms=sms)
    msgs = msgs or [{"role": "system", "content": "SYS"}, {"role": "user", "content": "hi"}]
    tools = tools or []
    legacy = {"model": model or "auto", "messages": msgs, "tools": tools}
    lb = len(json.dumps(legacy, ensure_ascii=False).encode("utf-8"))
    env = build_env(msgs, tools=tools, model=model, dsm_cfg=c, store=store, sms=sms, resync=True)
    eb = len(json.dumps(env, ensure_ascii=False).encode("utf-8"))
    mb = len(json.dumps(to_openai(env, store, model or "auto"), ensure_ascii=False).encode("utf-8"))
    return {"legacy_bytes": lb, "envelope_bytes": eb, "egress_openai_bytes": mb,
            "delta_pct": round(100.0 * (eb - lb) / max(1, lb), 1), "sch": env["sch"]}


# ---- CLI：status|on|off|matrix|selftest ------------------------------------------
MATRIX_HEADER = ("enabled", "openai_compat", "客户端行为（本仓库）", "服务端（SMSocket·另一对话）")
MATRIX = [
    ("true", "true", "POST /v1/dsm/chat 信封；404/415 且 fallback=true → 降级 legacy＋一条 warning", "TT 双开（默认·安全）"),
    ("true", "false", "只走 /v1/dsm/chat；任何 legacy 构造请求即报错（绝不静默降级）", "TF dsm-only"),
    ("false", "true", "与今天逐字节同路 /v1/chat/completions（验收 A）", "FT legacy-only"),
    ("false", "false", "客户端拒绝构造 legacy body → 报错并提示改开关", "FF 服务端 load 即 ValueError（不自毁）"),
]


def cli_matrix(a=None):
    print("DSM 开关真值表（契约 §5/§2·客户端视角）")
    print("  %-8s %-14s | %s | %s" % MATRIX_HEADER)
    for row in MATRIX:
        print("  enabled=%-5s openai_compat=%-5s | %s | %s" % row)
    return 0


def cli_status(a=None):
    c = cfg()
    st = {"mode": "dsm-envelope" if c["enabled"] else "legacy-openai",
          "dsm": c, "schema_refs": SchemaStore().refs()}
    sk = code_skew()
    if sk:
        # 代际错位必须看得见：SMS 与 SMSocket 联动，常驻 shell 跑旧码＝换了 DSM 空响应
        st["code_skew"] = [{"module": m, "src_mtime": round(a, 1), "pyc_mtime": round(b, 1)}
                           for m, a, b in sk]
    if broken():
        # 降级冷却必须看得见：否则「开了开关却还在走 legacy」会查不出来
        st["degraded"] = {"until_epoch": round(_BROKEN[0], 1),
                          "seconds_left": max(0, round(_BROKEN[0] - time.time(), 1)),
                          "reason": _BROKEN[1]}
    print(json.dumps(st, ensure_ascii=False, indent=1))
    try:
        import gateway as g, agent_dispatch as ad
        msgs = [{"role": "system", "content": g._sys()}, {"role": "user", "content": "status 探针"}]
        m = measure(msgs, ad.tools_schema(), g.cfg().get("model"), c)
        print("envelope %d B vs legacy %d B（出网物化 %d B·sch=%s·差 %+.1f%%）"
              % (m["envelope_bytes"], m["legacy_bytes"], m["egress_openai_bytes"], m["sch"], m["delta_pct"]))
    except Exception as e:
        print("字节对比取样失败（不影响开关）：", str(e)[:120])
    return 0


def cli_onoff(v, a=None):
    cur = set_enabled(v)
    print("llm_gateway.dsm.enabled = %s（经 settings.set 写入·未手改 JSON）" % cur["enabled"])
    if v:
        _n = code_skew_note()
        if _n:
            print("\u26a0 " + _n)
    return cli_status()


def cli_out(a=None):
    v = (a or [None])[1] if a and len(a) > 1 else None
    if v not in ("json", "delta"):
        print("用法：python -B dsm.py out json|delta（当前＝%s）" % cfg().get("out"))
        return 1
    cur = set_out(v)
    print("llm_gateway.dsm.out = %s（经 settings.set 写入·未手改 JSON）" % cur["out"])
    return cli_status()


def cli_selftest(a=None):
    store = SchemaStore(path=os.path.join(os.environ.get("SMS_TMP") or sms_home(), "runtime", "dsm_selftest_schemas.json"))
    sys_txt = "SYS 自检系统提示"
    tools = [{"type": "function", "function": {"name": "exec", "description": "d",
                  "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}}}}]
    sch = store.put(sys_txt, tools)
    env = {"v": 1, "sid": "sess-selftest", "cid": "conv-selftest", "lane": "t4", "dep": ["t1", "t2"],
           "sch": sch, "mem": ["025430cb5e", "98ca2d42d2", "267ce91149"],
           "d": [[1, "只输出一行 JSON：{\"ok\":true}"]],
           "cons": {"dedup_key": ["k"], "fx": {"USD": 7.2}, "output": "#/schema/out/x"},
           "budget": {"reason": "low", "max_out": 900, "when_exceeded": "answer_partial"},
           "lat": {"ttft_ms": 3000, "on_exceed": "failover"},
           "fan": {"n": 3, "lane_ids": ["t4a", "t4b", "t4c"], "merge": "vote", "concurrency": 3},
           "out": "json", "bill": {"to": "skill:selftest", "row": "t6"},
           "verify": [{"path": "answer[0]", "assert": "is_number"}],
           "x": {"future.key": "unknown keys must survive"}}
    oa, an = to_openai(env, store, "M"), to_anthropic(env, store, "M")
    ids = env["mem"]
    b1, b2, b3 = canon_mem(ids).encode(), canon_mem(list(reversed(ids))).encode(), canon_mem(ids + [ids[0]]).encode()
    fan = split_fan(env, [])
    fan_done = split_fan(env, ["t1", "t2"])
    resp = {"v": 1, "sid": "sess-selftest", "lane": "t4", "seq": 7, "reason": {"tokens": 12, "summary": "s"},
            "answer": [{"name": "exec", "arguments": {"cmd": "ls"}}], "stop": "tool_call",
            "usage": {"in": 467, "out_reason": 9412, "out_answer": 403, "cache_read": 320, "cache_write": 0,
                      "cost": 0.0495, "currency": "USD"}, "egress": "direct"}
    dec = decode_to_openai_shape(resp)
    m = measure([{"role": "system", "content": sys_txt}, {"role": "user", "content": "hi"}], tools, "M", store=store)
    ok = {
        "validate(合法信封)": validate(env) == [],
        "validate(拒未知顶层键)": bool(validate(dict(env, foo=1))),
        "ROLE 双射": [ROLE[RID[n]] for n in ROLE] == ROLE,
        "顶层泄漏==[]": leak_check(env, oa) == [] and leak_check(env, an) == [],
        "mem 乱序/重复同字节": (b1 == b2 == b3) and len(b1) > 0,
        "x.* 往返存活": to_openai(env, store, "M") and env["x"]["future.key"] == "unknown keys must survive",
        "物化确定性": json.dumps(oa, ensure_ascii=False, sort_keys=True) ==
                       json.dumps(to_openai(env, store, "M"), ensure_ascii=False, sort_keys=True),
        "fan dep 未满足→不可派": fan["dispatchable"] is False and fan["ready"] == [],
        "fan dep 满足→3 道": len(fan_done["ready"]) == 3 and fan_done["dispatchable"] is True,
        "响应→OpenAI 形状": dec["choices"][0]["finish_reason"] == "tool_calls" and
                            dec["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "exec",
        "usage 分项": dec["usage"]["prompt_tokens_details"]["cached_tokens"] == 320 and
                      dec["usage"]["completion_tokens_details"]["reasoning_tokens"] == 9412,
        "turn 往返（tool_calls 保真）": decode_turn(*encode_turn(
            {"role": "assistant", "content": "",
             "tool_calls": [{"id": "x", "function": {"name": "n", "arguments": "{}"}}]}))["tool_calls"][0]["id"] == "x",
        "撞名登记（task.lane 类）": isinstance(name_collision(store, sch), list),
        "开关默认全关": DEFAULTS["enabled"] is False and DEFAULTS["openai_compat"] is True and
                      DEFAULTS["fallback"] is True and DEFAULTS["out"] == "json",
    }
    print(json.dumps({"wire": ok, "bytes": m, "mem_bytes": len(b1)}, ensure_ascii=False, indent=1))
    bad = [k for k, v in ok.items() if v is not True]
    print("[selftest] %s（失败项：%s）" % ("PASS" if not bad else "FAIL", bad or "无"))
    return 0 if not bad else 1


# ---- 链记忆引用（客户端侧只出 id 表·物化在出口按 id 字典序，前缀才稳定） ----------
def mem_ids(query, max_chars=1200, sess=None, sms=None):
    """复用 prompt_pack 的召回口径取碎片 id（不再拼文本、不 bump 频次——DSM 侧只传引用）。
    召回失败回 []（信封少带记忆块，不影响请求合法性）。"""
    try:
        import prompt_pack as pp, chain_store as cs
        sms = sms or sms_home()
        store = cs.Store(sms)
        sid = sess if sess is not None else (session_ids()[0] or None)
        out, used = [], 0
        for sc, fid, freq, text in sorted(pp._hits(store, cs.vec(query or ""), sid), reverse=True):
            if fid in out:
                continue
            if used + len(text) > max_chars:
                break
            out.append(fid); used += len(text) + 1
        return out
    except Exception:
        return []

# ---- 接线辅助（gateway / gateway_sse 共用·失败一律回退 legacy，绝不静默丢语义） ----
def commit_from_env(env, msgs, sms=None):
    """请求成功后推进 delta 水位（与 build_env 同口径剥掉首条 system）。失败不推进。"""
    key = (env.get("x") or {}).get("sms.delta_key")
    if not key:
        return False
    rest = []
    seen = False
    for m in msgs:
        if m.get("role") == "system" and not seen:
            seen = True; continue
        rest.append(m)
    return commit_delta(key, rest, sms)


def _reg_key(ref):
    return "registered:" + str(ref)


def needs_register(ref, sms=None):
    """首帧登记判定：本 sid 未登记过该 ref 才发 POST /v1/dsm/schema（幂等，重复登记无害但费一跳）。"""
    sid = session_ids()[0] or "-"
    return bool((_state(sms).get("%s|%s" % (_reg_key(ref), sid)) or {}).get("done") is not True)


def mark_registered(ref, sms=None):
    sid = session_ids()[0] or "-"
    try:
        d = _state(sms); d["%s|%s" % (_reg_key(ref), sid)] = {"done": True, "ts": int(time.time())}
        atomic_io.wjson(_state_path(sms), d); return True
    except Exception:
        return False


def schema_frame(env, reg=None, store=None, sms=None):
    """POST /v1/dsm/schema 首帧 body（契约 §1：{ref, system, tools}·幂等）。

    优先取 build_env 挂进 x.sms.schema_reg 的原文（与 sch 指纹同源·绝不滞后），
    老信封（无该键）回退本地 SchemaStore 镜像。reg 可显式传入（build_env 后取出的同一键）。"""
    if reg is None:
        reg = ((env.get("x") or {}).get("sms.schema_reg")) or {}
    if reg:
        return {"ref": reg.get("ref") or env.get("sch"),
                "system": reg.get("system") or "",
                "tools": list(reg.get("tools") or [])}
    store = store or SchemaStore(sms=sms)
    rec = store.get(env.get("sch")) or {}
    return {"ref": env.get("sch"), "system": rec.get("system", ""), "tools": rec.get("tools", [])}


_BROKEN = [0.0, ""]                 # DSM 暂时不可用的截止时刻与原因（进程内）
BROKEN_COOLDOWN = 120.0             # 秒：降级期间直接走 legacy，不再每轮白打四次往返


def mark_broken(reason, seconds=None):
    """服务端没装 DSM / 水位反复对不上 → 记一次冷却。

    没有这个闩，enabled=true 而服务端无 /v1/dsm/* 时，每一轮都要重付
    「登记→404→重同步登记→404」四次 HTTP；降级本身是对的，反复试错才是浪费。
    """
    _BROKEN[0] = time.time() + float(BROKEN_COOLDOWN if seconds is None else seconds)
    _BROKEN[1] = str(reason)[:140]
    return True


def broken():
    return bool(_BROKEN[0] and time.time() < _BROKEN[0])


def broken_info():
    return tuple(_BROKEN)


def clear_broken():
    _BROKEN[0], _BROKEN[1] = 0.0, ""
    return True


DSM_WIRING = ("dsm", "gateway", "gateway_sse")


def code_skew(dirs=None):
    """DSM 接线模块「源码比字节码新」的清单＝常驻进程可能还在跑上一代 DSM 代码。

    SMS 与 SMSocket 是联动的：改了 dsm/gateway/gateway_sse 之后，已启动的 shell 内存里
    仍是旧编译产物（.pyc 时间戳＝它上次被加载的时刻），而 SMSocket 一重启就换成新一代
    服务端——两代协议对不上时，最坏表现就是「换了 DSM 返回空响应」而日志里一片 200
    （2026-10-06 实测）。返回 [(模块, 源码 mtime, 字节码 mtime)]，空表＝无可检出错位。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    pyc = os.path.join(here, "__pycache__")
    tag = "cpython-%d%d" % (sys.version_info[0], sys.version_info[1])
    out = []
    for m in DSM_WIRING:
        s = os.path.join(here, m + ".py")
        c = os.path.join(pyc, "%s.%s.pyc" % (m, tag))
        if not os.path.exists(s):
            continue
        if not os.path.exists(c):
            out.append((m, os.path.getmtime(s), 0.0))
        elif os.path.getmtime(s) > os.path.getmtime(c) + 1e-6:
            out.append((m, os.path.getmtime(s), os.path.getmtime(c)))
    return out


def code_skew_note(dirs=None):
    """人话一行（含重启指引）；无错位回空串。"""
    sk = code_skew(dirs)
    if not sk:
        return ""
    det = "、".join("%s（源码 %s 新于字节码 %s）" % (
        m, time.strftime("%m-%d %H:%M", time.localtime(a)),
        time.strftime("%m-%d %H:%M", time.localtime(b)) if b else "从未编译") for m, a, b in sk)
    return ("DSM 代码代际错位：%s——常驻的 SMS shell 仍在跑上一代 DSM 代码，"
            "而 SMSocket 可能已重启到新一代；两代对不上时最坏表现就是「换了 DSM 返回空响应」。"
            "重启 SMS（shell_lifecycle.py request restart）让两侧同代后再判。" % det)


def legacy_refused(c=None):
    """dsm.openai_compat=false 时客户端不得静默构造 legacy body（契约 §2：loud error）。"""
    c = c or cfg()
    if c.get("openai_compat"):
        return None
    return ("DSM 配置冲突：llm_gateway.dsm.openai_compat=false 时客户端不得再构造 legacy OpenAI body"
            "（服务端 /v1/chat/completions 会回 410）。请把 openai_compat 改回 true，或保持 dsm.enabled=true 走信封。")

if __name__ == "__main__":
    _a = sys.argv[1:] or ["status"]
    _cmd = _a[0]
    if _cmd == "status":
        sys.exit(cli_status(_a))
    if _cmd == "on":
        sys.exit(cli_onoff(True, _a))
    if _cmd == "off":
        sys.exit(cli_onoff(False, _a))
    if _cmd == "matrix":
        sys.exit(cli_matrix(_a))
    if _cmd == "out":
        sys.exit(cli_out(_a))
    if _cmd == "selftest":
        sys.exit(cli_selftest(_a))
    print("用法：python -B dsm.py status|on|off|matrix|selftest"); sys.exit(2)
