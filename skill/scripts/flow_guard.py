#!/usr/bin/env python3
"""flow_guard.py — 主流程空口守卫＋token 预算（批20·2026-09-28 用户反馈「仍然会在莫名奇妙的地方停止」；批21·用户「构建时算 token·超限拆分交给 AI」）：批18 任务总览门控只约束有表的复杂任务，单步执行类诉求免表——模型宣告「现在开始写/Writing the animation now/Let me check」后以纯文本收口、零执行调用、磁盘无产物，用户被迫反复「继续」。promises(txt)＝中英「动手宣告」最小特征识别（gateway.run 在 depth==0、〔任务总览〕无未完成行且本轮从未调 write/skill/task 时据此注入续推提示，共用 task.max_continue 熔断）；jargs(raw)＋TRUNC＝finish=length 截断致工具参数不完整时 gateway 不执行、回分段 write append 指引；CONT＝finish=length 截断正文（无工具调用）时注入续推、模型自行分段续写；est/msgs_est/budget/add_note＝发送前估算消息 tokens（CJK≈1/字·其余≈1/4字），大于 max_tokens 时给首条用户消息追加〔Token 预算〕块——脚本只测量与告知，是否拆分/怎么拆由模型自决（相信大模型）。批28 历史净化：fixargs/clean_tool_calls/bad_args——写回历史前把 finish=length 的半截 arguments 补全或降级 "{}"、空 tool_call_id 补稳定 id，杜绝毒消息常驻历史致后续每轮网关 400。仅特征识别与文案、不做路由裁决（裁决权在模型）。用法：python -B flow_guard.py test"""
import re, json, hashlib
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef]")
PROMISE = re.compile(r"(?:现在|马上|这就|立刻|正要|我将|我会|开始|正在|准备|接下来我|下面我|我先|我们先)[^。\n]{0,16}(?:写|创建|生成|制作|实现|构建|建立|修复|执行|动手|落盘|查看|检查|确认|做一|建一)|(?:now|next|i\s+wil[lm]|i'?m\s+going|let\s+me|first\s+i)[^.\n]{0,30}(?:writ|creat|generat|build|mak|implement|fix|check|look|see|list|insp|exam|exec|run|test)|(?:writ|creat|generat|build|implement|fix|check|insp)[a-z]+[^.\n]{0,30}(?:now|shortly|immediately|next)", re.I)
TRUNC = "⚠ 本轮输出达 max_tokens 被截断（finish=length）：工具调用参数不完整·未执行——大文件请分多段 write(append=true) 写入（每段≤600字），或精简单次输出后重试。"
CONT = "[SMS 主流程守卫] 你上一轮正文在 max_tokens 处被截断（finish=length）——从截断处自行分段续写（文件用 write append=true 续、长答复拆多轮），禁止从头重来或就此收口。"
def promises(txt): return bool(txt and PROMISE.search(str(txt)))
def jargs(raw):
    try: json.loads(raw or "{}"); return True
    except Exception: return False
def _ok(s):
    """arguments 是否已是合法 JSON 对象/数组（网关只接受这两种形态）。"""
    try: return isinstance(json.loads(s), (dict, list))
    except Exception: return False


def _scan(s):
    """扫一遍残缺 JSON：返回（是否停在字符串字面量内，未闭合括号栈），补全候选据此生成。"""
    st = []; q = False; esc = False
    for ch in s:
        if q:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': q = False
            continue
        if ch == '"': q = True
        elif ch in "{[": st.append(ch)
        elif ch in "}]":
            if st and ((st[-1] == "{") == (ch == "}")): st.pop()
    return q, st


def _cands(s):
    """最小改动候选：补引号＋补闭合括号 → 再试补 null → 再回退到上一个成员/引号边界后补全。"""
    out = []
    for cut in (0, s.rfind(","), s.rfind('"'), s.rfind(":")):
        t = s if cut <= 0 else s[:cut]
        if not t.strip(): continue
        q, st = _scan(t)
        tail = "".join("}" if c == "{" else "]" for c in reversed(st))
        base = t + ('"' if q else "")
        for v in (base + tail, base + "null" + tail, base.rstrip(", :") + tail):
            if v.strip() and v not in out: out.append(v)
    return out


def fixargs(raw):
    """半截工具参数补全（finish=length 常见）：能补成合法对象/数组即返回补全串，否则回 ""（调用方降级 "{}"）。"""
    s = str(raw or "").strip()
    if not s: return ""
    if _ok(s): return s
    for v in _cands(s):
        if _ok(v): return v
    return ""


def clean_tool_calls(m):
    """净化写回历史的工具调用（治「历史投毒→网关 400」·gateway 在 msgs.append(m) 前调用）：
    ① arguments 非合法 JSON 对象/数组（finish=length 半截 JSON）→ 尽量补全，补不成降级 "{}"；
    ② id 缺失/空白 → 生成稳定 id（内容哈希＋序号，无随机数，重复调用幂等）。
    原地修改并返回同一 m（调用方以 bad_args() 先留快照，净化项不再执行工具）。"""
    tcs = m.get("tool_calls") if isinstance(m, dict) else None
    if not isinstance(tcs, list): return m
    seed = hashlib.sha1(str(m.get("content") or "").encode("utf-8")).hexdigest()[:8]
    for i, tc in enumerate(tcs):
        if not isinstance(tc, dict): continue
        f = tc.get("function")
        if isinstance(f, dict):
            s = f.get("arguments")
            if isinstance(s, (dict, list, type(None))): s = json.dumps(s or {}, ensure_ascii=False)
            if not _ok(s): f["arguments"] = fixargs(s) or "{}"
        if not str(tc.get("id") or "").strip():
            nm = str((tc.get("function") or {}).get("name") or "")
            h = hashlib.sha1(("%s:%d:%s" % (seed, i, nm)).encode("utf-8")).hexdigest()
            tc["id"] = "call_" + h[:12]
    return m


def bad_args(tcs):
    """净化前快照：逐项标记 arguments 是否非法（净化后参数已改写，不能再据 jargs 判定）。"""
    return [not jargs(str(((t.get("function") or {}).get("arguments")) or "{}")) for t in tcs or []]


def est(s): s = str(s or ""); return len(CJK.findall(s)) + (len(s) - len(CJK.findall(s))) // 4
def _c(m): c = m.get("content") or ""; return c if isinstance(c, str) else " ".join(str(p.get("text", "")) for p in c if isinstance(p, dict))
def msgs_est(msgs): return sum(est(_c(m)) + sum(est(str((t.get("function") or {}).get("name", "")) + str((t.get("function") or {}).get("arguments", ""))) for t in m.get("tool_calls") or []) for m in msgs)
NOTE = "\n\n〔Token 预算·脚本测量·拆分由你〕本次输入≈%d tokens＞单轮 max_tokens=%d（输入超输出上限本身正常·上下文才是硬限制）——凡预计单轮输出（含工具参数/正文）会超 %d：长文件分多段 write(append=true)·长答复拆多轮续写；预计不超则正常作答，勿为此浪费篇幅。"
def budget(msgs, mt, ctx=None):
    """批29：拿到真实上下文（上游标注或越界实测）就按占窗比例判——每轮 6k 输入不再误报；ctx 缺＝旧口径零回归。"""
    x = msgs_est(msgs)
    if not ctx: return "" if x <= mt else NOTE % (x, mt, mt)
    if x >= int(ctx * 0.75): return "\n\n〔Token 预算·脚本测量·拆分由你〕本次输入≈%d tokens 已占真实上下文 %d 的 75%% 以上——立即分段：长答复拆多轮续写、长文件分多段 write(append=true)。" % (x, ctx)
    if x > mt and x >= int(ctx * 0.35): return NOTE % (x, mt, mt)
    return ""
def add_note(msg, note):
    if not note: return msg
    m = dict(msg); c = m.get("content")
    m["content"] = (c if isinstance(c, str) else " ".join(str(p.get("text", "")) for p in c if isinstance(p, dict))) + note if c is not None else note
    return m
def notice(kind, idle): return "• 主流程守卫：" + {"pend": "〔任务总览〕仍有未完成行·自动续推中（第", "cut": "正文被 max_tokens 截断·自动续推分段续写（第"}.get(kind, "检测到空口宣告（说要动手·本轮零执行调用）·自动续推中（第") + str(idle) + "次·对话不结束）"
def inject(kind, pend=""): return {"pend": "[SMS 主流程守卫] 主任务未完成·不得收口结束：\n" + pend + "\n据实改表并继续推进未完成行（无依赖用 task 工具并发·有依赖 parallel=false 或依序逐 skill·完成即 task_plan status done）·全部行 done 后才一句 ≤40 字收口——禁止重复宣告完成而不推进。", "cut": CONT}.get(kind) or "[SMS 主流程守卫] 你刚宣告要动手，但本轮未调用任何 write/skill/task 执行工具、产物未落盘——禁止空口收口：立即用 write/exec/skill 真执行（长内容分多段 write append=true·每段≤600字·防 max_tokens 截断）；若确无需动手或已完成，给一句 ≤40 字事实结论。"
if __name__ == "__main__":
    ok = all(map(promises, ["现在开始写动画。", "Writing the animation now.", "Let me check the contents of tmp too.", "接下来我将创建文件", "我马上生成页面"])) and not any(map(promises, ["已完成，文件在 tmp\\a.html。", "链机制是省 token 的记忆介质。", "这段代码的含义是：先写头再写体。", ""])) and jargs('{"a":1}') and not jargs('{"a":1') and "主任务未完成" in inject("pend", "x") and "空口" in inject("prom") and "截断" in inject("cut") and est("你好") == 2 and est("abcd") == 1 and budget([{"role": "user", "content": "短"}], 4096) == "" and "Token 预算" in budget([{"role": "user", "content": "汉" * 100}], 50) and budget([{"role": "user", "content": "汉" * 100}], 50, 983616) == "" and "Token 预算" in budget([{"role": "user", "content": "汉" * 100}], 50, 150) and "75%" in budget([{"role": "user", "content": "汉" * 1000}], 50, 1000) and "预算" in add_note({"role": "user", "content": "hi"}, "〔Token 预算〕")["content"] and add_note({"role": "user", "content": "hi"}, "")["content"] == "hi"
    print("flow_guard selftest: " + ("OK" if ok else "FAIL")); raise SystemExit(0 if ok else 1)
