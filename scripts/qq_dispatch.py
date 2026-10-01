#!/usr/bin/env python3
"""qq_dispatch.py — QQ 入站派发队列（2026-09-29 真根因修复：qq_listen 曾把 qq_inbound.handle 直接挂在 WS 循环线程上同步跑，deliver 里 agent_stream.ask 一阻塞就把续心跳、看门狗、退避重连全拖死——表现为 pid 假活、listen.heartbeat 停更、且无一条 down 日志。本模块＝纯 stdlib queue＋单工作线程的解耦层：submit(m) 只做非阻塞入队（绝不反压 WS 线程，也不做磁盘写），worker 线程串行跑 qq_inbound.handle（QQ 侧本就逐条到达，串行还顺带防被动回复上下文 CTX 被并发写串台），WS 循环从此永不被 ask 阻塞，心跳与自愈各自独立。depth()/stats() 供 qq_watch/qq_cli 观测积压，ensure() 幂等起线程（daemon·随进程亡），stop() 投毒枚领取消。用法：python -B qq_dispatch.py stats|test [每条耗时秒]。
2026-09-30 真根因修复（用户「QQ 发消息全被丢弃、零回复」实测：qq/listen.log 22:15:28 连续「派发 队列满丢弃 msg_id=o64…o73」，inbox.json 最后写 17:33＝根本没进 handle）：旧 submit 把每条 WS 事件（含 op=11 ACK/READY 等噪声，qq_policy.parse 对其返回 None）一律入队，maxsize 只有 64，单 worker 串行且一条 ask 可跑数分钟（qq.handle_timeout=900），队列被噪声灌满后「丢弃新消息」策略把真实用户消息全扔掉。
四处改：①submit 入队前廉价噪声过滤——import qq_policy as P，用 P.EV.get((m or {}).get("t")) 判定，非消息类直接 return "skip·噪声" 不入队（try/except 兜底，判定异常按原样入队·宁多勿漏）；②maxsize 64→256，且满时改为丢最旧保最新（put 前 full 就 get_nowait 挤掉队头并计入 ST["drop"]），绝不丢用户刚发的；③命中丢弃经 qq_push.push 主动告知一句「⚠ 上一条仍在处理，本条已排队」（异常吞掉；同一原因 60s 节流，模块级时间戳 NT）；④coalesce：worker 取一条后把队列中同 openid 的后续消息文本合并进同一次 handle（换行拼接、最多 8 条，以最新一条为事件壳保住被动回复 msg_id，异 openid/毒枚原样回队），审计日志记「合并N条」。stats() 加 noise、coalesce 计数。"""
import os, sys, json, time, queue, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try: import qq_policy as P
except Exception: P = None
K = queue.Queue(maxsize=256)
ST = {"in": 0, "drop": 0, "done": 0, "err": 0, "last": 0.0, "noise": 0, "coalesce": 0}
_T = [None]; LK = threading.Lock(); NT = {}
def _log(msg, chain=False):
    try: import qq_watch as W; W.log("派发 " + str(msg)[:160])
    except Exception: pass
    if chain:
        try: import chain_error; chain_error.hook("gate", "qq_dispatch", str(msg)[:200])
        except Exception: pass
def _mid(m): return str((((m or {}).get("d") or {}).get("id")) or "")[:24]
def _oid(m):
    try:
        d = (m or {}).get("d") or {}; a = d.get("author") or {}
        return str(a.get("user_openid") or a.get("member_openid") or d.get("group_openid") or "")
    except Exception: return ""
def _txt(m):
    try: return str(((m or {}).get("d") or {}).get("content") or "").strip()
    except Exception: return ""
def _noise(m):
    "廉价噪声判定：t 不在 qq_policy.EV＝非消息事件（op=11 ACK/READY/心跳…）；判定异常按原样入队"
    try: return bool(P) and not P.EV.get((m or {}).get("t"))
    except Exception: return False
def _notice(why, text):
    "丢弃告知：同一原因 60s 只发一条（模块级时间戳 NT·异常吞掉·绝不反压 WS 线程）"
    try:
        if time.time() - float(NT.get(why) or 0) < 60: return
        NT[why] = time.time()
        import qq_push as qp; qp.push(text, "QQ·排队")
    except Exception: pass
def _put(m):
    "入队：满则先挤掉队头（丢最旧保最新·计入 drop·主动告知），返回是否入队"
    try: K.put_nowait(m); return True
    except queue.Full:
        try: old = K.get_nowait(); ST["drop"] += 1; _log("队列满挤掉最旧 msg_id=%s" % _mid(old))
        except Exception: return False
        _notice("drop", "⚠ 上一条仍在处理，本条已排队")
        try: K.put_nowait(m); return True
        except Exception: return False
def _unget(m):
    "把刚取出的事件放回队头（保序·不重复计 unfinished：join 的账留给真正处理它的那一次·绝不回队尾插队）"
    try:
        with K.mutex: K.queue.appendleft(m); K.not_empty.notify()
    except Exception:
        try: K.put_nowait(m)
        except Exception: pass
def _coalesce(m, limit=8):
    "worker 取一条后把队中同 openid 的后续消息文本换行并进同一次 handle（最多 limit 条·以最新一条为壳保住被动回复 msg_id·遇异 openid/空文本/毒枚放回队头即停，绝不重排他人消息），返回 (事件, 合并条数)"
    try:
        oid = _oid(m); texts = [_txt(m)]; base = m
        while len(texts) < limit:
            try: n = K.get_nowait()
            except queue.Empty: break
            if n is None or not oid or _oid(n) != oid or not _txt(n):
                _unget(n); break
            try: K.task_done()
            except Exception: pass
            texts.append(_txt(n)); base = n
        if len(texts) > 1:
            try:
                d = dict(base.get('d') or {}); d['content'] = '\n'.join(texts)
                base = dict(base); base['d'] = d
            except Exception: pass
            ST['coalesce'] += len(texts) - 1; _log('合并%d条 openid=%s' % (len(texts), oid[:12]))
        return base, len(texts)
    except Exception as e:
        _log('coalesce 异常 ' + str(e)[:120], True); return m, 1
def _work():
    "单条消息挂墙钟上限（2026-09-30 用户「QQ 端我发不进去、你没回复」真根因＝一条 ask 永久卡死唯一 worker 线程）：超时＝投停止旗标＋杀在途子进程树＋放弃该线程，worker 立刻回队列取下一条，绝不把整条 QQ 通道拖死。取到一条先 _coalesce 合并同 openid 积压，一次 ask 处理完用户连发的多条。"
    while True:
        m = K.get()
        if m is None: return
        try:
            m, _ = _coalesce(m)
            import qq_inbound as I, run_watch as rw, settings as st
            secs = max(60, int(st.get("qq.handle_timeout", 900)))
            # 分级（2026-10-01 error 链 2ab90541b9）：T3＝secs 总预算；T2＝阶段静默——stall 只作「普通阶段」档，
            # handle 内部 set_stage("llm"/"skill") 的长等待阶段自动换宽档 qq.handle_stall_llm，不再平铺误杀
            ok, r = rw.run_with_timeout(I.handle, secs, "QQ入站", (m,),
                                        stall=max(30, int(st.get("qq.handle_stall", 240))), stage="inbound")
            ST["done"] += 1
            if not ok:
                ST["err"] += 1; _log("超时中止 " + str(r).replace("\n", " ")[:220], True)  # 反馈首行带级别名（T1/T2/T3）
                try: I.qp.push("⚠ 上一条消息被计时器中止：%s" % str(r).replace("\n", " ")[:200], "QQ·计时器")
                except Exception: pass
            elif r: _log("done " + str(r)[:100])
        except Exception as e:
            ST["err"] += 1; _log("worker 异常 " + str(e)[:160], True)
        finally:
            ST["last"] = time.time(); K.task_done()  # 停止旗标不在这里清：超时放弃的线程靠它自行收口，run_watch 已挂 60s 定时复位
def ensure():
    with LK:
        t = _T[0]
        if t and t.is_alive(): return t
        _T[0] = t = threading.Thread(target=_work, name="qq-dispatch", daemon=True); t.start(); return t
def submit(m, c=None):
    "WS 线程唯一入口：噪声事件（op=11 ACK/READY/心跳…）不入队，真实消息非阻塞入队（满则挤最旧保最新），永不反压、永不磁盘写。"
    if _noise(m):
        ST["noise"] += 1; return "skip·噪声"
    ensure()
    if not _put(m):
        ST["drop"] += 1; _log("队列满丢弃 msg_id=%s" % _mid(m)); return "drop·队列满"
    ST["in"] += 1; return "queued·depth=%d" % K.qsize()
def depth(): return K.qsize()
def stats(): return dict(ST, depth=K.qsize(), maxlen=K.maxsize, thread=bool(_T[0] and _T[0].is_alive()))
def stop():
    try: K.put_nowait(None)
    except queue.Full: pass
def _drain():
    while K.queue:
        try: K.get_nowait(); K.task_done()
        except Exception: break
if __name__ == "__main__":
    a = sys.argv[1:] or ["stats"]
    if a[0] == "test":
        import qq_inbound as I; old = I.handle; out = {}; LOG = []; NOTI = []
        _lg, _nt, _en = globals()["_log"], globals()["_notice"], globals()["ensure"]
        globals()["_log"] = lambda msg, chain=False: LOG.append(str(msg)[:70])
        def _n(why, text):
            if time.time() - float(NT.get(why) or 0) < 60: return
            NT[why] = time.time(); NOTI.append(text)
        globals()["_notice"] = _n
        msg = lambda i, oid="ou_A": {"t": "C2C_MESSAGE_CREATE", "d": {"id": "m%d" % i, "author": {"user_openid": oid}, "content": "c%d" % i}}
        nz = lambda i: {"op": 11, "s": i, "t": None, "d": None}
        n0, i0 = ST["noise"], ST["in"]
        r = [submit(nz(x)) for x in range(300)]
        out["a噪声"] = {"返回": r[-1], "noise增量": ST["noise"] - n0, "入队增量": ST["in"] - i0, "队列深度": depth()}
        globals()["ensure"] = lambda: None
        d0, t0 = ST["drop"], time.time(); [submit(msg(x)) for x in range(300)]; enq = time.time() - t0
        ids = [str(x["d"]["id"]) for x in list(K.queue)]
        out["b溢出"] = {"入队耗时秒": round(enq, 3), "不阻塞WS": enq < 0.5, "深度": depth(), "maxlen": K.maxsize,
                       "丢弃计数": ST["drop"] - d0, "队首剩最旧": ids[0], "最新必在队": ids[-1] == "m299",
                       "告知条数": len(NOTI), "告知文案": (NOTI or [""])[0]}
        _drain(); globals()["ensure"] = _en
        c0 = ST["coalesce"]; [K.put(msg(x)) for x in range(5)]; K.put(msg(9, "ou_B"))
        head = K.get(); merged, nn = _coalesce(head); K.task_done()
        out["c合并"] = {"条数": nn, "合并文本": _txt(merged), "壳msg_id取最新": merged["d"]["id"],
                       "异openid停扫回队头深度": depth(), "coalesce增量": ST["coalesce"] - c0,
                       "审计日志": [x for x in LOG if "合并" in x], "挤旧日志样例": [x for x in LOG if "挤掉最旧" in x][:1]}
        _drain()
        SEEN = []
        I.handle = lambda m, c=None: (SEEN.append(_txt(m)), time.sleep(float(a[1]) if len(a) > 1 else 0.05))
        ensure(); submit(msg(0)); time.sleep(0.02); [submit(msg(x)) for x in range(1, 5)]
        for _ in range(300):
            if depth() == 0 and ST["done"] >= 2: break
            time.sleep(0.02)
        stop(); out["c端到端"] = {"handle调用次数": len(SEEN), "最长合并行数": max([len(s.split("\n")) for s in SEEN] or [0])}
        I.handle = old; globals()["_log"], globals()["_notice"], globals()["ensure"] = _lg, _nt, _en
        print(json.dumps(out, ensure_ascii=False, indent=1))
    elif a[0] == "stats": print(json.dumps(stats(), ensure_ascii=False))
    else: print(__doc__.strip()[:300])
