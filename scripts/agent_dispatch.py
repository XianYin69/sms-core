#!/usr/bin/env python3
"""agent_dispatch.py — agent 工具 schema 与派发（gateway 工具循环与 CLI 共用·单一真源）：SCHEMA＝OpenAI function 清单 exec·read·write·skill·ask·task·task_detail·user_send·thinking_chain·chain·debate·glob·grep·ls·webfetch（read 一族与联网取文 2026-09-26 集成见 agent_tools2.py；批17 链直读写 chain 与双链辩论 debate 见 agent_tools3.py）；execute(name, raw_args)→agent_tools/agent_task 对应实现，参数按形参名过滤、异常回错误文本给模型（不中断工具循环）。工具权限——settings agent_tools.<name>（默认 true）门控：tools_schema() 供 gateway 只暴露启用工具、execute() 拒调禁用工具，菜单 F1→大模型工具权限 或 `:tools`/`:config set agent_tools.read false` 增删。用法：python -B agent_dispatch.py call <工具> '<json>' | skill <id> <诉求> | task <诉求> | detail [task-id] | tools [enable|disable <name>]"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import runtime_rec as rr, agent_tools as at, agent_tools2 as a2, agent_tools3 as a3, agent_task as atk, task_table as tt, settings, chain_error
P = lambda t, d: {"type": t, "description": d}; F = lambda n, d, p, r: {"type": "function", "function": {"name": n, "description": d, "parameters": {"type": "object", "properties": p, "required": r}}}
SCHEMA = [F("exec", "执行 shell 命令（cwd＝工作区·生成文件入 tmp）——范式：一次到位勿反复试探，找文件用 glob/ls、查内容用 grep、读文件用 read（本工具经 sys_shells 统一入口·PowerShell 下 &&/2>nul/dir /b 会被自动改写并说明）", {"cmd": P("string", "命令")}, ["cmd"]),
 F("read", "读文本文件（流式窗口读·不整读大文件）：path[, max_lines, offset]——先 grep 定位再按 offset 续读，截断会回下一个 offset", {"path": P("string", "路径"), "max_lines": P("integer", "最多行数"), "offset": P("integer", "起始行（0 基）")}, ["path"]),
 F("write", "写文本文件（工作区/SMS 默认可写，越界需授权）：长内容分多段 append=true（每段≤600字）防 max_tokens 截断", {"path": P("string", "路径"), "content": P("string", "内容"), "append": P("boolean", "是否追加")}, ["path", "content"]),
 F("skill", "把诉求派发给托管技能——批23 对等对话：每次派发自开一个独立 conv 独立链归属（与你的对话无主次，互任监视者/指导者/训诫者），技能在其对话内按其 SKILL.md 全文执行；收口＝形式停止返回你的对话续推任务表（执行类诉求用真派发；纯问答可直答不强制；无匹配技能且属新领域/动手需求→先 name=Skill_Generator input=需求 走 create 路径新建技能再派发，不得空手拒绝）", {"name": P("string", "技能id"), "input": P("string", "用户诉求")}, ["name", "input"]),
 F("ask", "子问答：需要独立小答案时用（≤300字·不面向用户复述）", {"question": P("string", "问题")}, ["question"]),
 F("task", "把复合诉求拆分为子任务执行并整合（进度实时上顶栏·批18：parallel=true 子任务无依赖/无冲突时并发派发〔默认〕·parallel=false 有先后依赖则依序串行——并发前提是你判定子任务互不冲突）", {"intent": P("string", "诉求"), "parallel": P("boolean", "true＝无依赖并发（默认）·false＝有依赖依序"), "lane": P("string", "fg＝前台（默认·本对话等结果）｜bg＝后台（立即拿句柄继续干别的，表内行与前台同地位、不阻前台收口）")}, ["intent"]),
 F("task_detail", "查询任务进度（id 空＝最近清单）", {"id": P("string", "任务id")}, []),
 F("task_plan", "任务表制表器 task_table 的建表与改表口：op=plan 由你判复杂即自建表（value＝你拆的各步骤，逗号分隔——不必等用户列步骤或输「制表」，复杂与否你定）、按〔任务表〕行推进——status 置行 done/running、add 补漏步（自动路由技能）、remove 删不合理行、skill 改指定技能、show/next/eta 查询、lane 把某行转后台(bg)/前台(fg)（批26 并行：后台行不阻前台收口·表内地位相同）；每次建表改表顶栏进度与剩余时间同步刷新", {"op": P("string", "plan|show|next|eta|add|remove|status|skill|lane"), "tid": P("string", "任务表id（plan 免填）"), "row": P("string", "行id（t1/t2…）"), "value": P("string", "plan＝各步骤逗号分隔；add＝新步骤目标；status＝状态；skill＝技能id")}, ["op"]),
 F("user_send", "向用户客户端发送一条提示/结果文本", {"text": P("string", "文本")}, ["text"]),
 F("thinking_chain", "把一步决策记入逻辑链（frm→to：why）", {"frm": P("string", "从"), "to": P("string", "到"), "why": P("string", "理由")}, ["frm", "to", "why"]),
 F("glob", "按文件名模式找文件（支持 ** 递归·默认工作区·生成器早停）", {"pattern": P("string", "glob 模式"), "path": P("string", "基目录，默认工作区"), "limit": P("integer", "最多返回项，默认 200")}, ["pattern"]),
 F("grep", "文件内容正则检索（剪枝 .git/__pycache__/node_modules·跳二进制与 >8MB·逐行流式·命中即止）", {"pattern": P("string", "正则"), "path": P("string", "基目录"), "include": P("string", "文件名过滤如 *.py"), "max": P("integer", "最多命中")}, ["pattern"]),
 F("ls", "目录清单（默认工作区）", {"path": P("string", "目录")}, []),
 F("webfetch", "网页取文（仅 http(s)·须先 :grant network）：gzip/deflate 与响应头 charset 自适应，HTML 默认抽正文（as_text=false 取原文），2MB 上限＋瞬时错重试", {"url": P("string", "http(s) URL"), "chars": P("integer", "最多字符"), "as_text": P("boolean", "HTML 抽正文，默认 true")}, ["url"]),
 F("chain", "十二链直接读写（链＝省 token 的三维空间记忆·批17·链域×时间/次数域×长度域，注入按深度优先遍历）：op=recall 按查询检索链经验（可限单链·链名或 all）、op=append 把一条结论/经验写入链（memory/knowledge/logic/user…·收口链对话收口时落盘）、op=stats 各链计数——涉及既往经验先 recall 再答，得出有价值结论即 append", {"op": P("string", "recall|append|stats"), "chain": P("string", "链名（含 error 错误记录链）或 all"), "query": P("string", "检索词（recall）"), "text": P("string", "语句（append）"), "to": P("string", "可选：挂边目标碎片 id"), "rel": P("string", "边关系 semantic|causal|ref")}, ["op"]),
 F("debate", "正反双辩论（Skill_Generator 辩论链思想）：对论断铺 pro/con 论据清单生成双链＋verdict 记逻辑链——决策岔路先自辩修正路径（人多在回路旁），裁决仅供参考、最终在你", {"claim": P("string", "论断"), "pro": {"type": "array", "items": {"type": "string"}, "description": "正方论据清单"}, "con": {"type": "array", "items": {"type": "string"}, "description": "反方论据清单"}}, ["claim"]),
 F("ask_user", "任务进行中向用户提问并阻塞等待其屏幕应答（一次一问·简短；无交互壳会立即返回说明）", {"question": P("string", "要问用户的问题")}, ["question"])]
REG = {"read": at.read, "write": at.write, "command": at.command, "skill": at.run_skill, "ask": at.ask, "task": atk.task, "task_detail": atk.task_detail, "task_plan": tt.revise, "user_send": at.user_send, "thinking_chain": at.thinking_chain, "chain": a3.chain, "debate": a3.debate, "glob": a2.glob, "grep": a2.grep, "ls": a2.ls, "webfetch": a2.webfetch, "ask_user": lambda question: __import__("ask_channel").ask(question)}
NAMES = [f["function"]["name"] for f in SCHEMA]
REQ = {f["function"]["name"]: f["function"]["parameters"].get("required") or [] for f in SCHEMA}
def _bad(nm, msg, sig=""): at.emit("tool", msg, tool=nm, ok=False); chain_error.hook("tool", nm, (sig or msg)[:200]); return msg
TYPES = {f["function"]["name"]: {k: (v or {}).get("type", "") for k, v in (f["function"]["parameters"].get("properties") or {}).items()} for f in SCHEMA}
_FILL = {"string": "...", "integer": 0, "number": 0, "boolean": True, "array": ["..."], "object": {}}
def _tbad(t, v):
    if not t: return False
    if t == "string": return not isinstance(v, str)
    if t == "integer": return isinstance(v, bool) or not isinstance(v, int)
    if t == "number": return isinstance(v, bool) or not isinstance(v, (int, float))
    if t == "boolean": return not isinstance(v, bool)
    if t == "array": return not isinstance(v, (list, tuple))
    if t == "object": return not isinstance(v, dict)
    return False
def _miss(n, a):
    tp = TYPES.get(n, {}); out = []
    for k in REQ.get(n, []):
        v = a.get(k)
        if v is None: out.append(k + "＝未传"); continue
        if isinstance(v, str) and not v.strip(): out.append(k + "＝空白（strip 后为空）"); continue
        if _tbad(tp.get(k, ""), v): out.append("%s＝类型不符（应 %s·实 %s）" % (k, tp.get(k), type(v).__name__))
    for k, v in a.items():
        if v is None or k in REQ.get(n, []) or k not in tp: continue
        if _tbad(tp[k], v): out.append("%s＝类型不符（应 %s·实 %s）" % (k, tp[k], type(v).__name__))
    return out
def _ex(n): return json.dumps({k: _FILL.get(TYPES.get(n, {}).get(k, "string"), "...") for k in REQ.get(n, [])}, ensure_ascii=False)
def _psig(n): return "参数缺失：" + n + " 需要 " + " 与 ".join(REQ.get(n, []))
def _pmsg(n, m): return "参数缺失/类型不符：" + n + " 需要 " + " 与 ".join(REQ.get(n, [])) + "（本次 " + "、".join(m) + "）——请照此最小示例一次改对：" + n + " " + _ex(n)
def tool_on(n): return bool(settings.get("agent_tools." + n, True))
def tools_schema(): return [f for f in SCHEMA if tool_on(f["function"]["name"])]
def tools_status(): return {n: tool_on(n) for n in NAMES}
def tools_toggle(n, v): settings.set("agent_tools." + n, bool(v)); return "工具 " + n + " → " + ("启用" if v else "禁用（对大模型隐藏并拒绝调用；F1→工具权限 或 :config set agent_tools." + n + " true 恢复）")
def bind(on_line=None, ev=False): return at.bind(on_line, ev)
def execute(name, raw):
    tname = {"command": "exec"}.get(name, name)
    if tname in NAMES and not tool_on(tname): return "工具已禁用：" + tname + "（菜单 F1→大模型工具权限 或 :tools enable " + tname + "）"
    try: a = json.loads(raw or "{}")
    except Exception: a = {"cmd": str(raw)}
    if not isinstance(a, dict): a = {"cmd": str(a)}
    if name in ("exec", "command"):
        if m := _miss("exec", a): return _bad(tname, _pmsg("exec", m), sig=_psig("exec"))
        rr.rec("exec"); 
        try: return at.command(a.get("cmd", ""))
        finally: rr.rec("idle")
    if name == "skill":
        mm = []
        if not str(a.get("name", "") or "").strip(): mm.append("name＝未传或空白")
        if not (a.get("input") or a.get("inp")): mm.append("input＝未传或空白")
        if mm: return _bad("skill", _pmsg("skill", mm), sig=_psig("skill"))
        rr.rec("exec"); 
        try: return chain_error.fail("skill", a.get("name", ""), at.run_skill(a.get("name", ""), a.get("input") or a.get("inp") or ""))
        finally: rr.rec("idle")
    fn = REG.get(name)
    if not fn: return "未知工具：" + name
    if m := _miss(tname, a): return _bad(tname, _pmsg(tname, m), sig=_psig(tname))
    kw = {k: v for k, v in a.items() if k in fn.__code__.co_varnames[:fn.__code__.co_argcount] and not (v is None and k not in REQ.get(tname, []))}
    try: return chain_error.fail("tool", name, fn(**kw))
    except TypeError as e: return _bad(tname, "参数不匹配：" + tname + "（" + str(e)[:120] + "）——请照此最小示例改对：" + tname + " " + _ex(tname), sig=_psig(tname))
    except Exception as e: return _bad(name, "工具失败：" + str(e)[:200])
if __name__ == "__main__":
    a = sys.argv[1:] or ["help"]
    if a[0] == "call" and len(a) > 1: print(execute(a[1], a[2] if len(a) > 2 else "{}"))
    elif a[0] == "skill" and len(a) > 2: r = at.run_skill(a[1], " ".join(a[2:])); print(("派发对话 " + a[1] + " 已形式收口·控制权回调用方（正文如上·⧉ 前缀·任务表未完行请继续推进或重派）") if r.startswith(at.WRAP) else r)
    elif a[0] == "task" and len(a) > 1: print(atk.task(" ".join(a[1:])))
    elif a[0] == "detail": print(atk.task_detail(a[1] if len(a) > 1 else ""))
    else: print(__doc__.strip().splitlines()[1][:400])
