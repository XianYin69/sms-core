#!/usr/bin/env python3
"""flow_guard.py — 主流程空口守卫＋token 预算（批20·2026-09-28 用户反馈「仍然会在莫名奇妙的地方停止」；批21·用户「构建时算 token·超限拆分交给 AI」）：批18 任务表门控只约束有表的复杂任务，单步执行类诉求免表——模型宣告「现在开始写/Writing the animation now/Let me check」后以纯文本收口、零执行调用、磁盘无产物，用户被迫反复「继续」。promises(txt)＝中英「动手宣告」最小特征识别（gateway.run 在 depth==0、〔任务表〕无未完成行且本轮从未调 write/skill/task 时据此注入续推提示，共用 task.max_continue 熔断）；jargs(raw)＋TRUNC＝finish=length 截断致工具参数不完整时 gateway 不执行、回分段 write append 指引；CONT＝finish=length 截断正文（无工具调用）时注入续推、模型自行分段续写；est/msgs_est/budget/add_note＝发送前估算消息 tokens（CJK≈1/字·其余≈1/4字），大于 max_tokens 时给首条用户消息追加〔Token 预算〕块——脚本只测量与告知，是否拆分/怎么拆由模型自决（相信大模型）。仅特征识别与文案、不做路由裁决（裁决权在模型）。用法：python -B flow_guard.py test"""
import re, json
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef]")
PROMISE = re.compile(r"(?:现在|马上|这就|立刻|正要|我将|我会|开始|正在|准备|接下来我|下面我|我先|我们先)[^。\n]{0,16}(?:写|创建|生成|制作|实现|构建|建立|修复|执行|动手|落盘|查看|检查|确认|做一|建一)|(?:now|next|i\s+wil[lm]|i'?m\s+going|let\s+me|first\s+i)[^.\n]{0,30}(?:writ|creat|generat|build|mak|implement|fix|check|look|see|list|insp|exam|exec|run|test)|(?:writ|creat|generat|build|implement|fix|check|insp)[a-z]+[^.\n]{0,30}(?:now|shortly|immediately|next)", re.I)
TRUNC = "⚠ 本轮输出达 max_tokens 被截断（finish=length）：工具调用参数不完整·未执行——大文件请分多段 write(append=true) 写入（每段≤600字），或精简单次输出后重试。"
CONT = "[SMS 主流程守卫] 你上一轮正文在 max_tokens 处被截断（finish=length）——从截断处自行分段续写（文件用 write append=true 续、长答复拆多轮），禁止从头重来或就此收口。"
def promises(txt): return bool(txt and PROMISE.search(str(txt)))
def jargs(raw):
    try: json.loads(raw or "{}"); return True
    except Exception: return False
def est(s): s = str(s or ""); return len(CJK.findall(s)) + (len(s) - len(CJK.findall(s))) // 4
def _c(m): c = m.get("content") or ""; return c if isinstance(c, str) else " ".join(str(p.get("text", "")) for p in c if isinstance(p, dict))
def msgs_est(msgs): return sum(est(_c(m)) + sum(est(str((t.get("function") or {}).get("name", "")) + str((t.get("function") or {}).get("arguments", ""))) for t in m.get("tool_calls") or []) for m in msgs)
def budget(msgs, mt):
    x = msgs_est(msgs); return "" if x <= mt else "\n\n〔Token 预算·脚本测量·拆分由你〕本次输入≈%d tokens＞单轮 max_tokens=%d（输入超输出上限本身正常·上下文才是硬限制）——凡预计单轮输出（含工具参数/正文）会超 %d：长文件分多段 write(append=true)·长答复拆多轮续写；预计不超则正常作答，勿为此浪费篇幅。" % (x, mt, mt)
def add_note(msg, note):
    if not note: return msg
    m = dict(msg); c = m.get("content")
    m["content"] = (c if isinstance(c, str) else " ".join(str(p.get("text", "")) for p in c if isinstance(p, dict))) + note if c is not None else note
    return m
def notice(kind, idle): return "• 主流程守卫：" + {"pend": "〔任务表〕仍有未完成行·自动续推中（第", "cut": "正文被 max_tokens 截断·自动续推分段续写（第"}.get(kind, "检测到空口宣告（说要动手·本轮零执行调用）·自动续推中（第") + str(idle) + "次·对话不结束）"
def inject(kind, pend=""): return {"pend": "[SMS 主流程守卫] 主任务未完成·不得收口结束：\n" + pend + "\n据实改表并继续推进未完成行（无依赖用 task 工具并发·有依赖 parallel=false 或依序逐 skill·完成即 task_plan status done）·全部行 done 后才一句 ≤40 字收口——禁止重复宣告完成而不推进。", "cut": CONT}.get(kind) or "[SMS 主流程守卫] 你刚宣告要动手，但本轮未调用任何 write/skill/task 执行工具、产物未落盘——禁止空口收口：立即用 write/exec/skill 真执行（长内容分多段 write append=true·每段≤600字·防 max_tokens 截断）；若确无需动手或已完成，给一句 ≤40 字事实结论。"
if __name__ == "__main__":
    ok = all(map(promises, ["现在开始写动画。", "Writing the animation now.", "Let me check the contents of tmp too.", "接下来我将创建文件", "我马上生成页面"])) and not any(map(promises, ["已完成，文件在 tmp\\a.html。", "链机制是省 token 的记忆介质。", "这段代码的含义是：先写头再写体。", ""])) and jargs('{"a":1}') and not jargs('{"a":1') and "主任务未完成" in inject("pend", "x") and "空口" in inject("prom") and "截断" in inject("cut") and est("你好") == 2 and est("abcd") == 1 and budget([{"role": "user", "content": "短"}], 4096) == "" and "Token 预算" in budget([{"role": "user", "content": "汉" * 100}], 50) and "预算" in add_note({"role": "user", "content": "hi"}, "〔Token 预算〕")["content"] and add_note({"role": "user", "content": "hi"}, "")["content"] == "hi"
    print("flow_guard selftest: " + ("OK" if ok else "FAIL")); raise SystemExit(0 if ok else 1)
