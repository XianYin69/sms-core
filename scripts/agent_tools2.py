#!/usr/bin/env python3
"""agent_tools2.py — 常规 agent 工具补齐（集成 codex/kilocode 等 read 一族·与 agent_tools 同信封上报）：glob(pattern,path) 递归找文件（默认工作区）·grep(pattern,path,include,max) 内容检索（跳过 .git/__pycache__/node_modules）·ls(path) 目录清单·webfetch(url,chars) 网页取文（默认拒绝——须 :grant network，urllib 直取失败回原因不抛异常）；全部输出截 ≤4000 字，经 agent_dispatch 注册后仍受 settings agent_tools.<name> 逐项门控。用法：python -B agent_tools2.py glob|grep|ls|webfetch <参数…>"""
import os, sys, re, fnmatch, glob as _g, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import resolve_home, permissions, solo, settings, agent_tools as at, tool_kit as tk
SMS = resolve_home.ensure()
def _base(path): return at._r(path or resolve_home.workspace())
def glob(pattern="**/*", path="", limit=200):
    """生成器早停匹配（批27）：不再整树展开后再截断。"""
    hs, tr = tk.glob_fast(str(pattern), _base(path), limit)
    at.emit("tool", "glob " + str(pattern) + " → " + str(len(hs)) + ("+（还有更多）" if tr else "") + " 项", tool="glob", ok=True)
    return "\n".join(hs) or "（无匹配）"
def grep(pattern, path="", include="*", max=60):
    """剪枝＋流式＋命中即止（批27）：跳 .git/__pycache__/node_modules 等与二进制/超 8MB 文件，逐行扫不整读。"""
    b = _base(path)
    try: rx = re.compile(str(pattern))
    except re.error as e: return "正则错误：" + str(e)[:120]
    out, tr = tk.grep_walk(b, rx, include, max)
    at.emit("tool", "grep " + str(pattern) + " 命中 " + str(len(out)) + ("（截断）" if tr else ""), tool="grep", ok=bool(out))
    return "\n".join(out) or "（无命中）"
def ls(path="", limit=200):
    b = _base(path)
    try: rows = sorted(os.listdir(b))[:limit]
    except Exception as e: return "ls 失败：" + str(e)[:120]
    at.emit("tool", "ls " + b + "（" + str(len(rows)) + " 项）", tool="ls", ok=True)
    return "\n".join(x + (os.sep if os.path.isdir(os.path.join(b, x)) else "") for x in rows) or "（空目录）"
def ask_sub(question, rounds=None):
    import gateway, agent_dispatch as ad, stop_channel as stop; cap = int(rounds if rounds is not None else settings.get("caps.ask_rounds", 0)); n = 0  # 0＝无限（默认·防任务断裂）·F4 caps.ask_rounds
    msgs = [{"role": "system", "content": "你是 SMS 数据流的子问答：只据所问简明作答（内部英语处理·≤300字·输出随用户语言），不确定就说不确定；需要本机事实就调工具取到再答（finish=tool_calls 时须回填结果续答，不得把工具轮当失败）。"}, {"role": "user", "content": str(question)[:4000]}]
    while True:
        if (n := n + 1) and cap and n > cap: at.emit("tool", "子问答达 %d 轮上限" % cap, tool="ask", ok=False); return "子问答：工具轮次用尽，未得结论（caps.ask_rounds＝0 即无限）"
        stop.check(); m, err = gateway.chat(msgs)  # 无限轮须留 :stop 手动收口出口（批10 通道·Stopped 上抛 gateway 轮首兜住）
        if not m: at.emit("tool", "子问答失败", tool="ask", ok=False); return "子问答失败：" + err
        if not (tcs := m.get("tool_calls") or []): at.emit("tool", "子问答完成", tool="ask", ok=True); return (m.get("content") or m.get("reasoning_content") or "") or "（子问答空响应）"
        msgs.append(m)
        for tc in tcs:
            f = tc.get("function") or {}; msgs.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": str(ad.execute(str(f.get("name", "")), str(f.get("arguments") or "{}")))[:2000] or "(无输出)"})
def webfetch(url, chars=4000, as_text=True):
    """网页取文（批27 精准高速）：Accept-Encoding gzip/deflate＋charset 优先响应头＋2MB 字节上限＋
    HTML 自动抽正文（省 token 主因）＋瞬时错有限重试（agent_tools.webfetch_retries）；超时仍走 run_watch T1 分级防误杀。"""
    if not re.match(r"(?i)^https?://", str(url)): return "拒绝：仅允许 http(s) 地址"
    ok, note = solo.gate(SMS, "network", ctx={"tool": "webfetch", "url": str(url), "intent": "网页取文"})
    if not ok: return "拒绝：webfetch 需 :grant network（默认拒绝·敏感键不随角色批量）" + solo.tail(note)
    import run_watch as rw
    call = lambda rq: rw.net_call(urllib.request.urlopen, rq, timeout=rw.tiers.t1("net"), kind="net")
    t, info = tk.fetch(str(url), chars, as_text, call, int(settings.get("agent.webfetch_retries", 2)))
    if t is None: at.emit("tool", "webfetch 失败 " + str(url)[:80], tool="webfetch", ok=False); return "取页失败：" + str(info)[:180]
    at.emit("tool", "webfetch " + str(url)[:80] + "（" + info + "）", tool="webfetch", ok=True)
    return t[:int(chars)]
if __name__ == "__main__":
    a = sys.argv[1:] or ["help"]
    print(glob(*(a[1:] or ["**/*"])) if a[0] == "glob" else grep(*(a[1:2] + a[2:3])) if a[0] == "grep" else ls(a[1] if len(a) > 1 else "") if a[0] == "ls" else webfetch(a[1]) if a[0] == "webfetch" and len(a) > 1 else __doc__.strip().splitlines()[1][:300])
