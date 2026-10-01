#!/usr/bin/env python3
"""debug.py — SMS 调试模式（错误分析）：开＝启动器 `--debug` / env `SMS_DEBUG=1` / 壳内 `:debug on`（持久 flag 文件 <SMS_HOME>/shell/debug·关即删）/ 配置 debug.enabled=true（F4 图形配置「调试·启用」T/F 选择器即时生效）；日志路径默认 <SMS_HOME>/logs/debug.log，可经配置 debug.path 自定义输出路径（F4「调试·输出路径」·绝对路径）；开启后 shell_core 记录每条元指令与话语派发、run_script 记录 命令+rc+stderr，agent_tools/gateway 的 msg_flow 工具/技能/任务信封随 ev 上报，Textual _work 异常输出完整 traceback——全部追加落日志（>512KB 自动截尾 256KB·运行时数据不进工具目录），顶栏出现 DEB 标识；:debug tail [n] 查看尾部；error＝错误记录通道——skill_errors.py 每笔直调、不受 enabled 门控（做梦自修 dream_fix 取错误现场）。用法：python -B debug.py on|off|status|path|tail [n]"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import resolve_home
def _sget(k):
    try: import settings; return settings.get(k)
    except Exception: return None
def flag(sms=None): return os.path.join(sms or resolve_home.resolve(), "shell", "debug")
def path(sms=None): return str(_sget("debug.path") or "").strip() or os.path.join(sms or resolve_home.resolve(), "logs", "debug.log")
def enabled(sms=None): return os.environ.get("SMS_DEBUG") == "1" or os.path.isfile(flag(sms)) or bool(_sget("debug.enabled"))
def on(sms=None):
    p = flag(sms); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w").close(); os.environ["SMS_DEBUG"] = "1"
    return "调试模式：开 · 日志=" + path(sms)
def off(sms=None):
    os.environ["SMS_DEBUG"] = "0"
    try: os.remove(flag(sms))
    except OSError: pass
    return "调试模式：关（日志保留于 " + path(sms) + "）"
def _w(s, sms, tag=""):
    p = path(sms); os.makedirs(os.path.dirname(p), exist_ok=True)
    if os.path.exists(p) and os.path.getsize(p) > 524288:
        open(p, "wb").write(open(p, "rb").read()[-262144:])
    open(p, "a", encoding="utf-8").write(time.strftime("[%m-%d %H:%M:%S] ") + tag + str(s).replace("\n", " ⏎ ")[:2000] + "\n")
def log(s, sms=None): return _w(s, sms) if enabled(sms) else None
def error(s, sms=None): return _w(s, sms, "[ERR] ")  # 错误记录通道：恒落 debug.log（skill_errors 每笔直调，做梦自修取错误现场）
def tb():
    import traceback; return traceback.format_exc()
def tail(n=20, sms=None):
    try: return "\n".join(open(path(sms), encoding="utf-8").read().splitlines()[-n:]) or "(空)"
    except FileNotFoundError: return "(无日志——尚未产生调试记录)"
if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]; cmd = a[0]
    if cmd == "on": print(on())
    elif cmd == "off": print(off())
    elif cmd == "status": print("on · " + path() if enabled() else "off（--debug 启动 / env SMS_DEBUG=1 / :debug on）")
    elif cmd == "path": print(path())
    elif cmd == "tail": print(tail(int(a[1]) if len(a) > 1 and a[1].isdigit() else 20))
    else: print(__doc__.strip().splitlines()[-1])
