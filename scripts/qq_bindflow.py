#!/usr/bin/env python3
"""qq_bindflow.py — QQ 扫码绑定的编排层（2026-09-29 慢网加固·从 qq_cli 拆出保 ≤50 行）：bind＝建任务→出码→轮询握手，因 task 实测仅约 2 分钟有效（不打开页面 18s 即 status=3），故默认 180s×3 轮自动换新码重试，过期/超时不必手输命令；resume＝读 <SMS_HOME>/qq/bind_pending.json 里存的 task_id/key 对同一次扫码续握手（轮询进程被中断、手机页面一直卡「连接中」时免重扫——该页要等本机 poll_bind_result 成功才收口）；check＝只调 getAppAccessToken 的链路自检（不发消息·不占日配额·报耗时），用来区分「凭据错」还是「网太卡」；成功才写 config/qq.json（旧值 .bak·chmod 600），任何失败绝不动原凭据。用法：python -B qq_bindflow.py bind|resume|check"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, qq_bind as qb, qq_push as qp, chain_error
def save(appid, secret, openid, sms=None):
    sms = sms or resolve_home.ensure(); p = os.path.join(sms, "config", "qq.json")
    try: open(p + ".bak", "w", encoding="utf-8").write(open(p, encoding="utf-8").read())
    except Exception: pass
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump({"appId": appid, "clientSecret": secret, "openid": openid, "enabled": True, "bound": time.strftime("%Y-%m-%dT%H:%M:%S")}, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    try: os.chmod(p, 0o600)
    except Exception: pass
    return p
def _wait(tid, key, timeout):
    t0, last = time.time(), 0.0
    while time.time() - t0 < timeout:
        try: st, appid, sec, oid = qb.poll(tid)
        except Exception as e: print("轮询异常（网络慢·退避重试）：" + str(e)[:70]); time.sleep(4); continue
        if st == 2 and appid and sec:
            qb.clear_pending()
            try: return save(appid, qb.decrypt(sec, key), oid), "绑定成功 openid=" + (oid or "-")
            except Exception as e: chain_error.hook("script", "qq_bind", "decrypt task=" + tid + " " + type(e).__name__ + " " + str(e)[:160]); return qb.save_raw(tid, key, sec, appid, oid, e), "appSecret 解密失败（" + type(e).__name__ + "）——原文已落 bind_raw.json 可事后重解"
        if st == 3: qb.clear_pending(); return None, "EXPIRED"
        if time.time() - last > 12: last = time.time(); print("等待手机 QQ 扫码确认…已 %d/%ds（页面停在「连接中」＝在等本机轮询握手，请保持本窗口开着；task 约 2 分钟过期）" % (time.time() - t0, timeout))
        time.sleep(3)
    return None, "TIMEOUT"
def bind(source="", timeout=180, rounds=3):
    if qp.conf().get("appId"): print("提示：已有有效凭据（appId=%s）——只有本次绑定成功才覆盖（旧值备份 qq.json.bak），失败不动原凭据" % qp.conf().get("appId"))
    for i in range(1, rounds + 1):
        key = qb.genkey()
        try: tid = qb.create(key)
        except Exception as e: print("建任务失败（网络卡）：" + str(e)[:70]); time.sleep(2); continue
        u = qb.qurl(tid, source); print("—— 第 %d/%d 轮 ——%s" % (i, rounds, qb.show(u))); print("扫码链接：" + u); qb.save_pending(tid, key, source)
        p, m = _wait(tid, key, timeout)
        if p or m not in ("EXPIRED", "TIMEOUT"): return p, m
        print("本轮未完成（%s）%s" % (m, "——自动换新码重试，请立刻用手机 QQ 扫码" if i < rounds else "——可 :qq resume 续握手 / :qq bind 重扫 / 手工录入凭据"))
    return None, "绑定未完成：task 约 2 分钟即过期＋弱网易错过握手——先 :qq check 判网络，再 :qq bind 重扫，或 :qq --appid/--secret/--openid 手工录入"
def resume(timeout=180):
    d = qb.load_pending()
    if not d.get("task_id"): return None, "没有待完成的绑定任务（:qq bind 发起后才会记录 task_id/key）"
    print("续绑 task=%s（建于 %s·免重扫，手机页面若仍「连接中」这次握手即收口）" % (d["task_id"], d.get("at")))
    p, m = _wait(d["task_id"], d["key"], timeout)
    return p, (m if m not in ("EXPIRED", "TIMEOUT") else ("task 已过期——:qq bind 重扫" if m == "EXPIRED" else "本机 %ds 内未完成握手（弱网常见）——task 可能仍有效：再 :qq resume，或 :qq bind 重扫" % timeout))
def check():
    c = qp.conf(); t0 = time.time()
    if not qp.ready(c): return {"绑定": False, "说明": "未绑定或开关关闭——:qq bind 重扫，或 :qq --appid/--secret/--openid 手工录入"}
    try: qp.token(c); return {"绑定": True, "token": "OK", "耗时ms": int((time.time() - t0) * 1000), "今日已推": qp._st(c).get("n", 0), "待完成绑定": bool(qb.load_pending().get("task_id")), "说明": "token 可取＝appId/secret 与网络均正常（自检不发消息·不占日配额）"}
    except Exception as e: return {"绑定": True, "token": "FAIL", "错误": str(e)[:200], "耗时ms": int((time.time() - t0) * 1000), "说明": "取 token 失败＝网络卡或凭据失效：换网重试，仍失败则 :qq bind 重绑"}
