#!/usr/bin/env python3
"""qq_boot.py — QQ 入站监听的自启与自愈（2026-09-29 用户「我要发消息给你」：监听进程不能只活在本次开机，SMS 重启／监听被杀／网络崩掉都要能自己回来，否则 QQ 端又变「该机器人未连接灵魂」）：开关＝<SMS_HOME>/config/qq.json 的 listen 布尔（:qq listen 置真并立即拉起、:qq unlisten 置假并停止，语义与 qq_listen 一致）；autostart() 由数据流每轮开头（agent_stream.ask）调用——listen=true 且 qq_watch.alive() 为假（含僵尸：pid 在但心跳过期）才 qq_listen.spawn() 重新拉起分离子进程，已在跑则零成本返回 None，异常吞掉记 error 链绝不断数据流。判活口径与顶栏徽标同源（qq_watch：真 pid OpenProcess＋心跳 180s 窗口）。用法：python -B qq_boot.py status|on|off。"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, qq_push as qp, qq_watch as W
def _p(sms=None): return os.path.join(sms or resolve_home.ensure(), "config", "qq.json")
def set_flag(on, sms=None):
    p = _p(sms); d = qp._ld(p, {}) or {}; d["listen"] = bool(on)
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1); return bool(on)
def flag(sms=None): return bool((qp._ld(_p(sms), {}) or {}).get("listen"))
def autostart(sms=None):
    if not flag(sms) or W.alive(sms): return None
    try:
        import qq_listen as L
        r = L.spawn(sms); W.log("autostart: " + str(r), sms); return r
    except Exception as e:
        try:
            import chain_error; chain_error.hook("gate", "qq_boot.autostart", str(e)[:200])
        except Exception: pass
        return None
if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]
    print(json.dumps({"listen": flag(), "watch": W.status()}, ensure_ascii=False, indent=1) if a[0] == "status"
          else "自启开关：" + ("开（" + str(autostart() or "已在跑") + "）" if set_flag(True) else "-") if a[0] == "on"
          else "自启开关：关（" + str(__import__("qq_listen").stop()) + "）" if a[0] == "off" else __doc__.strip()[:240])
