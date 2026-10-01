#!/usr/bin/env python3
"""commands.py — 命令系统：汇总内置命令、各 skill 暴露接口与个性化指令（user_commands）→ registry/commands.json；help/intent/show/use 查看调用，alias/unalias 定义个性化指令格式（如 skill-update→迭代 skill），hud/deploy/shell/temp/sandbox/privacy 入口路由；批16 LLM 主导：问答可直答，动手必真执行。"""
import os, sys, json, time, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
BUILTIN = {"help": "列出所有命令（内置/skill 接口/个性化）", "intent": "按一句话意图匹配候选命令 <utterance>",
  "show": "查看某命令详情 <name>", "use": "调用命令 <name> [args...]（个性化=展开步骤并执行；其余转 dispatch/skill_executor，SMS 不作答）",
  "alias": "定义个性化指令 <name> --desc= --args=a,b --step='script:|delegate:|say:..' [--write]", "unalias": "删除个性化指令 <name> [--write]",
  "temp": "子 skill 未指定路径的新建目录 → <SMS_HOME>/tmp", "sandbox": "SMS 沙盒 create/list/deliver/clean",
  "privacy": "背景隐私采集 notice/collect/open（须 grant privacy，每笔告知）", "dep": "依赖原始链接：list <技能>/check [技能…]/probe <技能> [依赖]/fetch <技能> <依赖>（deps.json 每条须 source_url；取回需 :grant network）", "plan": "计划任务：ls/validate/add \"标题\" \"时间\" \"诉求\" [技能] /show <id>/pause/resume/run/due/tick/serve（时间＝ISO 时刻｜+分钟｜5 段 cron；到点自动建任务表并挂 session 链执行）", "hud": "界面顶面 HUD session/step/alert/hide（置顶·穿透·不抢焦点，任务进行时提示）", "session": "会话层：new [名]＝新建会话（session·批23 多对话容器·非 conv——conv 每输入/派发自动开收）｜list｜use <id>｜current｜overview＝会话拓扑（按创建先后＋各 session 未完成行数）｜conflicts＝跨会话未完成/同技能并行冲突（对等对话监视·指导·训诫线索）",
    "grant": "权限授予：:grant <键|角色> [分钟] [--id <openid/会话名>]（--id＝只给该 id·TTL 到期自动失效·danger 不随批量）；:grant ids 看已绑定 id；:grant unbind <id> 收回；远程高危＝:grant remote --id <id> 或 qq.json remote_admin", "solo": "SOLO 模式 on|off|status|banner|review <键>（批27：阻塞/错误先分析再决定修复或重试·重试无限但有条件·solo.analyze_retry/max_same_error）（权限免用户确认·缺权限由大模型自审授予·solo.never 键与 danger 默认不自审·:grant revoke <键> 即时收回（<键> 0＝永久授予非收回））", "shell": "sms-shell：任意话语经数据流交已装 agent CLI（默认 skill_manage_system 指令）；TUI/GUI 双前端；:agents/:use/:skill 治理", "resume": "接续前次对话 on|off|status（重启壳后续上轮上下文·默认开）", "stop": "任务进行中请求停止当前任务（TUI/GUI 输 stop/停止/:stop·检查点收口；readline Ctrl+C；stop_channel.py）", "deploy": "部署＝仅把 bin 启动文件复制到指定路径（默认预览，--write 且 grant write 执行；bin/locate.py 回源定位，sms-shell 目标处直接可用）", "task_table": "任务拆分与任务表制表器 plan/new/show/next/eta/status/add/remove/skill（脚本粗分自动建种子表·模型判复杂可 op=plan 自建〔批22〕·简单输入免表直送·顶栏进度与剩余时间预测）", "manual": "三平台命令手册查询 manual [pwsh|powershell|cmd|bash|zsh|all]·register-manual 登记（shell_commands 子技能）"}
ROUTE = {"plan": "planned_tasks.py", "dep": "dep_fetch.py", "alias": "user_commands.py", "unalias": "user_commands.py", "temp": "resolve_home.py", "sandbox": "sandbox.py", "privacy": "privacy.py", "hud": "hud.py", "deploy": "deploy.py", "shell": "shell.py", "resume": "shell_resume.py", "solo": "solo.py", "task_table": "task_table.py", "manual": "sys_shells.py"}
def _load(sms, rel): return json.load(open(os.path.join(sms, rel), encoding="utf-8")) if os.path.exists(os.path.join(sms, rel)) else {}
def collect(sms):
    import user_commands
    cmds = [{"name": k, "description": v, "args": "", "source": "sms"} for k, v in BUILTIN.items()]
    for s in _load(sms, "registry/interfaces.json").get("skills", []):
        for it in s.get("interfaces", []):
            nm = it.get("name")
            if nm and all(c["name"] != nm for c in cmds): cmds.append({"name": nm, "description": it.get("description", ""), "args": "", "skill_id": s["skill_id"], "source": "skill"})
    for c in user_commands.load(sms)["commands"]:
        if all(x["name"] != c["name"] for x in cmds): cmds.append({"name": c["name"], "description": c.get("description", ""), "args": " ".join(c.get("arg_names", [])), "source": "user"})
    return {"schema": "skill_commands", "version": "1.1.0", "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"), "commands": cmds}
def match(doc, utter):
    u = (utter or "").lower()
    hits = [c["name"] for c in doc["commands"] if c["name"].lower() in u or any(t and t in u for t in c["name"].lower().replace("-", "_").split("_"))]
    return {"utterance": utter, "candidates": hits or [c["name"] for c in doc["commands"][:3]]}
def route(cmd, raw):
    name = ROUTE[cmd]; pre = {"alias": ["add"], "unalias": ["rm"]}.get(cmd, [])
    argvx = [sys.executable, "-B", os.path.join(HERE, name)] + pre + (raw if cmd == "temp" else raw[1:])
    if cmd == "shell": os.execv(sys.executable, argvx)
    p = subprocess.run(argvx, capture_output=True, text=True)
    return {"route": name, "out": (p.stdout or p.stderr).strip()[:2000]}
if __name__ == "__main__":
    sys.path.insert(0, HERE)
    import resolve_home, emit, user_commands
    sms = resolve_home.ensure()
    raw = sys.argv[1:]; argv = [x for x in raw if x != "--write"]; w = "--write" in raw
    cmd = argv[0] if argv else "help"; arg = argv[1] if len(argv) > 1 else ""
    if cmd in ROUTE: print(json.dumps(route(cmd, raw), ensure_ascii=False, indent=2)); sys.exit(0)
    doc = collect(sms)
    if w: print(emit.write_json(os.path.join(sms, "registry", "commands.json"), doc, sms, False))
    names = [c["name"] for c in doc["commands"]]
    if cmd == "help": r = {"commands": names, "detail": doc["commands"]}
    elif cmd == "intent": r = match(doc, arg)
    elif cmd == "show": r = next((c for c in doc["commands"] if c["name"] == arg), {"error": "用法: show <name>"})
    elif cmd == "use":
        uc = user_commands.load(sms)
        r = user_commands.run(sms, arg, argv[2:]) if user_commands.find(uc, arg) else {"invoked": arg or None, "args": argv[2:], "next": "转 dispatch.py / skill_executor 执行并回到 SMS"}
    else: r = {"error": "用法: help | intent <utterance> | show <name> | use <name> [args] | alias|unalias <name> [opts] | temp|sandbox|privacy|hud|deploy|shell [args]"}
    print(json.dumps(r, ensure_ascii=False, indent=2))
