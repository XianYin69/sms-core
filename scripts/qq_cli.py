#!/usr/bin/env python3
"""qq_cli.py — QQ 推送的命令行入口与绑定编排（2026-09-29）：bind [source]＝qq_bindflow 发起扫码（task 约 2 分钟过期→默认 180s×3 轮自动换新码·弱网退避重试），成功后写 <SMS_HOME>/config/qq.json（旧值 .bak·chmod 600）；resume＝读 bind_pending.json 对上次扫码续握手（免重扫·手机页面卡「连接中」时用）；check＝只取 getAppAccessToken 的链路自检（不发消息·不占日配额·报耗时，用来分清「凭据错」还是「网卡」）；手工录入 --appid/--secret/--openid（开放平台管理端可见，绕过扫码）；status＝配置/凭据/今日已推/outbox 积压一览（密钥打码）；test "<文本>"＝真发一条（可 --img <路径> 附带截图）；on/off＝开关；conf k=v＝改阈值（max_day/min_gap/max_len/dedup）；ack true/false＝入站即时回执开关（qq.json ack·回执走主动端点不占被动窗）；brief true/false＋brief_len=N＝QQ 简洁模式与收口限长；flush＝补发 outbox（对话收口自动调，也可手跑）；report＝打印当前任务表快照（＝回传 QQ 里那张表）；progress＝按最新未完成表立刻推一次进度（受 task_gap 节流）；stall [status|check|tick]＝任务表卡住看门狗（qq_stall：src==qq 且仍有未完成行的表，mtime 距今 >stall_after 即推「⚠任务表卡住 …」，同签名 stall_repeat 内不重发；status 看阈值与去重状态、check 立刻扫一遍并真推、tick 走节流窗口；开关与阈值走 conf stall/stall_after/stall_repeat/stall_tick）；open [create]＝webbrowser 打开开放平台机器人列表/快捷创建登录页（零新依赖，登录后管理端可见 appId/clientSecret，配合手工录入）。bind/resume/check 的编排在 qq_bindflow.py（慢网加固：task 约 2 分钟即过期→默认 180s×3 轮自动换新码；resume 读 bind_pending.json 免重扫续握手；check 只取 token 自检·不占日配额）。用法：python -B qq_cli.py bind|resume|check|status|test|img|on|off|conf|flush|open|listen|unlisten|lstatus|linbox|report|progress|stall [参数]；img <图片路径> [tag]＝发一张本地截图（走 qq_push.send_image·POST /v2/users/{openid}/files base64·受 min_gap/max_day/同文件哈希 60s 去重/img_max_kb 上限，失败静默入 outbox 不阻塞）；test 可加 --img <路径> 文图同发。"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, qq_push as qp, qq_bindflow as qf
def mask(v): return (str(v)[:4] + "****" + str(v)[-3:]) if v and len(str(v)) > 8 else ("未设置" if not v else "****")
def status():
    c = qp.conf(); s = qp._st(c); ob = qp._ld(qp._f(c["sms"], "outbox.json"), []) or []
    return {"已绑定": bool(c.get("appId") and c.get("openid")), "开关": "on" if c.get("enabled") else "off",
            "appId": c.get("appId") or "-", "clientSecret": mask(c.get("clientSecret")), "openid": c.get("openid") or "-",
            "今日已推": s.get("n", 0), "日上限": c["max_day"], "outbox积压": len(ob), "阈值": {k: c[k] for k in ("min_gap", "max_len", "dedup")}, "回执": c.get("ack"), "简洁模式": c.get("brief"), "简洁限长": c.get("brief_len")}
def toggle(on):
    p = os.path.join(resolve_home.ensure(), "config", "qq.json"); d = qp._ld(p, {}) or {}
    d["enabled"] = bool(on); json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1); return "QQ 推送：" + ("开" if on else "关")
def conf_set(kv):
    p = os.path.join(resolve_home.ensure(), "config", "qq.json"); d = qp._ld(p, {}) or {}
    k, _, v = str(kv).partition("="); v = v.strip().strip('"')
    d[k] = {"true": True, "false": False}.get(v.lower(), int(v) if v.isdigit() else (float(v) if v.replace(".", "").isdigit() else v))
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1); return {k: d[k]}
if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]; opt = lambda k, d="": sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
    if a[0] in ("bind", "resume"): p, m = (qf.bind((a[1] if len(a) > 1 and not a[1].startswith("--") else "") or "SMS", int(opt("--timeout", 180)), int(opt("--rounds", 3))) if a[0] == "bind" else qf.resume(int(opt("--timeout", 180)))); print(m + ("·" + p if p else ""))
    elif a[0] == "check": print(json.dumps(qf.check(), ensure_ascii=False, indent=1))
    elif a[0] == "test": im = opt("--img"); print(qp.push(" ".join(x for x in a[1:] if x != "--img" and x != im) or "SMS 测试推送：链路可用", "测试", image=im))
    elif a[0] == "img": print(qp.push("", "QQ·图" + (("·" + a[2]) if len(a) > 2 else ""), image=a[1]) or "未推送（未绑定/文件不存在或超 img_max_kb/60s 内同图/配额间隔·详见 qq/outbox.json）")
    elif a[0] == "flush": print(qp.flush() or "outbox 无积压或未绑定")
    elif a[0] == "report": import qq_report; print(qq_report.snapshot() or "无活动任务表（tasks 空或全部 done）")
    elif a[0] == "progress": import qq_report, task_table as tt; print(qq_report.progress(tt._load(tt._latest())) or "未推送（开关关/未绑定/进度未变/间隔内已合并）")
    elif a[0] == "listen": import qq_boot; qq_boot.set_flag(True); print(__import__("qq_listen").spawn())
    elif a[0] == "unlisten": import qq_boot; qq_boot.set_flag(False); print(__import__("qq_listen").stop())
    elif a[0] == "lstatus": print(json.dumps(__import__("qq_watch").status(), ensure_ascii=False, indent=1))
    elif a[0] == "linbox": print(json.dumps(__import__("qq_policy").inbox()[-8:], ensure_ascii=False, indent=1))
    elif a[0] == "stall":
        import qq_stall as KS; print(json.dumps(KS.status(), ensure_ascii=False, indent=1) if (a[1] if len(a) > 1 else "status") == "status" else json.dumps(KS.check(), ensure_ascii=False) if a[1] == "check" else str(KS.tick()))
    elif a[0] == "conf" and len(a) > 1: print(json.dumps(conf_set(a[1]), ensure_ascii=False))
    elif a[0] in ("ack", "brief", "brief_len") and len(a) > 1: print(json.dumps(conf_set("%s=%s" % (a[0], a[1])), ensure_ascii=False))
    elif a[0] in ("on", "off"): print(toggle(a[0] == "on"))
    elif a[0] == "open": import webbrowser; u = {"create": "https://q.qq.com/qqbot/openclaw/login.html"}.get(a[1] if len(a) > 1 else "", "https://q.qq.com/qqbot/openclaw/index.html"); webbrowser.open(u); print("已调用系统浏览器打开：" + u + ("（登录后到「机器人管理」复制 AppID/AppSecret 回填 :qq --appid/--secret/--openid）" if u.endswith("login.html") else ""))
    elif opt("--appid"): print("已手工录入：" + qf.save(opt("--appid"), opt("--secret"), opt("--openid")))
    else: print(json.dumps(status(), ensure_ascii=False, indent=1))
