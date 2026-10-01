#!/usr/bin/env python3
"""tts.py — 朗读引擎「阿林娜（alina）」开关与挂钩（合成后端 tts_say.py）：开关单一真源＝settings tts.enabled（:tts on|off 直接写配置）。模型输出经 agent_stream 调 hook() 逐句读出：批7③——朗读门控与主输出显示同一真源 msg_flow.visible（思考◌/$ 工具/⧉技能过程/▸步骤/≡任务/空行一律不读·⧉技能 剥前缀后其正文照读·JSON 信封只读 text 字段）；markdown 符号/URL/文件路径剥净（tts_say.clean）；批6：标点符号与文件路径不朗读（strip_punct 去标点·clean 去路径·按句切仍保留断句）。批25 新输出抢读：每次输入先调 preempt()——轮次号＋1 并掐断在读·清旧轮积压，worker 只读最新轮（免两段/多段输出叠读）；语速封顶 138%≈6 字每秒（tts_say._params）。用法：python -B tts.py say "<文本>" | test | on | off | toggle | status | voices。"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, settings, chains, msg_flow, tts_say
SMS = resolve_home.ensure()
NAME = lambda: settings.get("tts.profile_name", "阿林娜")
CAP = lambda: max(60, min(500, int(settings.get("tts.max_chars", 400))))  # 上限 500 字＝封顶语速下 ≤90s 看门狗内读完
def on(): return bool(settings.get("tts.enabled", False))
def set_on(v):
    settings.set("tts.enabled", bool(v)); v or tts_say.stop()
    return NAME() + "：" + ("开" if v else "关") + "（写配置 tts.enabled·即时生效·关即清队列）"
def speak(text, wait=False): return tts_say.speak(tts_say.strip_punct(tts_say.clean(text)), wait, max(1, _T[0]))
def voices(): return tts_say.voices()
_T = [0]
def preempt():
    """批25 轮次抢读：新一轮输出开始＝轮次＋1·掐断在读并清旧积压（agent_stream.ask 每输入首调）。"""
    if not on(): return "关（未启用·无在读）"
    _T[0] += 1; return "轮次 %d·%s" % (_T[0], tts_say.interrupt(_T[0]))
def hook(on_line):
    if not on(): return on_line
    def w(ln):
        on_line(ln); s = str(ln).strip()
        if not s or not msg_flow.visible(s) or s.startswith(("注意：", "拒绝：", "网关错误", "!", "•")): return
        if (m := msg_flow.SUB.match(s)): s = s[m.end():]
        e = msg_flow.parse(s)
        if e: s = str(e.get("text") or "")
        t = tts_say.clean(s)
        if t and not t.startswith(("sms>", "◌")):
            for ch in tts_say.chunks(t, CAP()): tts_say.speak(tts_say.strip_punct(ch), n=_T[0])
    return w
def status():
    return json.dumps({"profile": NAME() + "（alina）", "engine": "SAPI5", "on": on(),
                       "voice": settings.get("tts.voice", ""), "rate_pct": tts_say._params()["r"], "pitch": settings.get("tts.pitch", "+0st"), "volume_pct": int(settings.get("tts.volume", 100)), "max_chars": CAP(), "turn": _T[0], "gender": "female-mechanical", "platform": "windows"}, ensure_ascii=False)
if __name__ == "__main__":
    try: __import__("session_reg").bind("bg", "tts", "朗读")
    except Exception: pass
    a = sys.argv[1:] or ["status"]; c = a[0]
    if c == "say" and len(a) > 1: print(speak(" ".join(a[1:]), True))
    elif c == "test": print(speak("你好，我是" + NAME() + "，很高兴为你朗读。", True))
    elif c == "voices": print(voices())
    elif c == "on": print(set_on(True))
    elif c == "off": print(set_on(False))
    elif c == "toggle": print(set_on(not on()))
    else: chains.log("tool", "tts:status"); print(status())
