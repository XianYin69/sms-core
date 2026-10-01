#!/usr/bin/env python3
"""prompt_builder.py — 引导增强型提示词构建器与对话初始化（批24：分段引导·语句精简·处理协议）：init＝①技能名＋②模型身份（配置参数）＋③工作区＋④SKILL.md 索引；build＝①处理协议＋②治理红线＋③SKILL.md 索引＋④用户输入（唯一指令）＋⑤QQ 简洁模式提示（qq_inbound 经 qq_brief 写 <SMS_HOME>/shell/qq_brief=1 时追加「回复≤200字·要点直给·勿刷屏」，直读状态文件不 import qq_brief/agent_stream 防回环）；PROTOCOL＝内部处理一律英语精简语句、最终输出译回用户语言；index＝register.json 活跃技能「id → SKILL.md 绝对路径」紧凑清单（供模型按需 exec 读全文，非全文注入）。用法：python -B prompt_builder.py init | build "<用户输入>" | index。"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, settings
SKILL = "skill_manage_system"
PROTOCOL = "〔处理协议·批24〕内部处理（思考·工具参数·链写入·任务表步骤·草稿）一律用英语、语句精简；给用户的最终输出先以英语处理完成、再译回用户话语所用语言，简短直给。"
PROMPT = "你是 skill_manage_system（SMS）数据流中的主导决策者（LLM 主导·脚本辅助）：问答可直答（简短·用户语言）；本机事实先 read/grep/glob/ls/exec 查证、禁编造；动手才用工具——命中托管技能用 skill 派发对等对话（独立 conv·独立链·无主次·互任监视/指导/训诫）按注入 SKILL.md 真执行，收口＝形式停止、由你整合续推；本机脚本 exec 一次运行、禁反复试探、禁空口声称已执行；[SMS 路由·参考] 仅供裁量；既往先 chain recall、有价值即 chain append、岔路用 debate 自辩（仅高危回人确认）；确无可用技能则建议经 Skill_Generator 创建。生成文件只入工作区 tmp\\（env SMS_TMP·壳已自动建）；tmp 产物收编先 ws_release.py diff 预览、当轮同意后 release --yes（须 :grant danger）；模型/技能配置直读 <SMS_HOME>/config、禁复制重建入工作区；SMS 设置/命令据 settings/commands 查证作答。"
def _reg(sms): return json.load(open(os.path.join(sms, "registry", "register.json"), encoding="utf-8")).get("skills", [])
def model_block(sms=None):
    sms = sms or resolve_home.ensure(); g = settings.eff(sms)["llm_gateway"]; mm = settings.eff(sms).get("model_meta", {}).get("defaults", {})
    ctx = (mm or {}).get("context_length")
    return "模型身份：" + str(g.get("model") or "auto") + "（" + str(g.get("base_url") or "未配置网关") + "）· temperature=" + str(g.get("temperature")) + " top_p=" + str(g.get("top_p")) + " max_tokens=" + str(g.get("max_tokens")) + (" 上下文≤" + str(ctx) if ctx else "")
def index(sms=None):
    sms = sms or resolve_home.ensure()
    try: rows = [s for s in _reg(sms) if s.get("status", "active") == "active" and s.get("trust") not in ("quarantine", "pending_review")]
    except Exception: rows = []
    if not rows: return "SKILL.md 索引：（注册表为空，先跑 register.py）"
    return "SKILL.md 索引（id → SKILL.md 路径，命中可 exec 读全文按其流程）：\n" + "\n".join("%s → %s" % (s.get("id"), os.path.join(str(s.get("install_path", "")), str(s.get("entry", "SKILL.md")))) for s in rows)[:2400]
def init(sms=None):
    sms = sms or resolve_home.ensure(); t = resolve_home.wtmp()
    return "[SMS 对话初始化·引导结构]\n① 技能名：" + SKILL + "\n② " + model_block(sms) + "\n③ 工作区：" + t[: -len(os.sep + "tmp")] + "（生成文件只入 tmp\\＝" + t + "·模型/技能配置直读 " + os.path.join(sms, "config") + "·待审产物可 ws_release diff/release 收编）\n④ " + index(sms)
PLAN = ("\n⑤ 计划任务（批26）：真源＝各技能目录 planned_tasks 文件夹内 *.json（Skill_Generator 初始化即建该文件夹）＋<SMS_HOME>\\planned_tasks；"
  "用户提出定时/每天/到点/计划任务＝先 ask_user 问清细节（何时·做什么·产物·通知渠道），再 exec 跑 planned_tasks.py add 标题 时间 诉求 [技能] 登记"
  "（时间＝ISO 时刻｜+分钟｜5 段 cron）；到点由壳内 plan_tick 自动触发：建任务表→挂该任务绑定的 session 链→执行；:plan ls 查看、:plan pause <id> 暂停。")
BRIEF = "\n⑥ QQ 简洁模式（用户此刻在 QQ 通道看消息）：回复≤200字·要点直给·勿刷屏。"
def _bp(sms=None): return os.path.join(sms or resolve_home.ensure(), "shell", "qq_brief")
def sess_kind(sms=None):
    """当前 session 通道 kind（只读·绝不 ensure，免得为此新建会话）。"""
    try:
        import session_reg as R
        sid = os.environ.get("SMS_SESSION") or R._rd(R._c(sms))
        return str((R.get_(sid, sms) or {}).get("kind") or "") if sid else ""
    except Exception: return ""
def brief_on(sms=None):
    """QQ 简洁模式判定（2026-09-30 残留修复）：qq_brief 是全局状态文件，一条 QQ ask 被看门狗杀掉时 finally 跑不到、
    标志残留，于是 TUI/网页/计划任务对话也被告知「用户此刻在 QQ·回复≤200字」（实测本条由 cron 会话触发却挂着 QQ 口径）。
    现＝仅当当前 session kind=qq 才生效；非 QQ 通道读到残留标志顺手清掉；kind 取不到＝按旧口径（宁保守不误关）。"""
    try:
        k = sess_kind(sms)
        if k and k != "qq":
            try:
                if open(_bp(sms), encoding="utf-8").read().strip() == "1":
                    open(_bp(sms), "w", encoding="utf-8").write("")
            except Exception: pass
            return False
        return open(_bp(sms), encoding="utf-8").read().strip() == "1"
    except Exception: return False
def build(user_input, sms=None):
    return "[SMS 逐轮构建·引导结构]\n① 处理协议：" + PROTOCOL + "\n② 治理红线：" + PROMPT + "\n③ " + index(sms) + "\n④ 用户输入（唯一指令）：\n" + user_input + PLAN + (BRIEF if brief_on(sms) else "")
if __name__ == "__main__":
    a = sys.argv[1:] or ["init"]; cmd = a[0]
    if cmd == "init": print(init())
    elif cmd == "index": print(index())
    elif cmd == "protocol": print(PROTOCOL)
    elif cmd == "build": print(build(" ".join(a[1:]) or "你好"))
    else: print(__doc__.strip().splitlines()[-1])
