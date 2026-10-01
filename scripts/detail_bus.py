#!/usr/bin/env python3
"""detail_bus.py — 跨会话「详细细节」总线（批27·用户「其他会话任务的详细信息（推导·工具使用·命令行输出）也应写进主 shell 详细细节」）：
一条追加式 jsonl＝所有会话明细的唯一真源 <SMS_HOME>/runtime/details.jsonl。任何会话（client 壳·web·remote/QQ·cron·bg·子脚本进程）
把「非正文」信封行（reasoning 推导·tool 工具·sh 命令行输出·edit·step·task·skill·err·notice）经 publish() 投进来；
主壳 TUI 按字节偏移 tail() 增量消费合并进 app.details（右栏摘要＋F9 全屏），每条前缀〔sess·kind〕标来源——
旧版 F9 只见本进程本会话的行，别的会话在跑什么完全看不见。
写＝行级 append＋线程锁＋单行 ≤2000 字＋超 CAP(512KB) 截尾保 KEEP(256KB)，publish 全静默绝不阻断主流程。
读＝只 seek 消费方自己的偏移读新字节，O(新增字节) 不整档扫；文件被截尾变小自动回退文件头重取末 N 条。
各消费方自持偏移互不干扰；只依赖 resolve_home，不 import shell_*（core→shell 反向依赖红线）。
用法：python -B detail_bus.py tail [n] | status | clear"""
import os, sys, json, time, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import resolve_home
CAP = 512_000; KEEP = 256_000; MAXLEN = 2000
_LK = threading.Lock()
def path(sms=None): return os.path.join(sms or resolve_home.ensure(), "runtime", "details.jsonl")
def _touch(p):
    d = os.path.dirname(p)
    if not os.path.isdir(d): os.makedirs(d, exist_ok=True)
def publish(sess, conv, kind, text, sms=None):
    """一条明细入总线（任何会话任何进程可调·失败静默＝绝不因记日志拖垮主流程）。"""
    try:
        t = str(text or "").replace("\n", " ⏎ ").strip()
        if not t: return False
        p = path(sms); _touch(p)
        rec = {"ts": time.strftime("%H:%M:%S"), "sess": str(sess or ""), "conv": str(conv or ""), "kind": str(kind or ""), "text": t[:MAXLEN]}
        line = json.dumps(rec, ensure_ascii=False) + "\n"
        with _LK:
            try:
                if os.path.getsize(p) > CAP: _rot(p)
            except Exception: pass
            with open(p, "a", encoding="utf-8") as f: f.write(line)
        return True
    except Exception: return False
def _rot(p):
    """截尾保 KEEP：只留末段里完整的行，临时文件＋os.replace 原子换入。"""
    try:
        sz = os.path.getsize(p)
        if sz <= KEEP: return
        with open(p, "rb") as f:
            f.seek(max(0, sz - KEEP)); tail = f.read()
        nl = tail.find(b"\n")
        if nl >= 0: tail = tail[nl + 1:]
        tmp = p + ".tmp"
        with open(tmp, "wb") as f: f.write(tail)
        os.replace(tmp, p)
    except Exception: pass
def size(sms=None):
    try: return os.path.getsize(path(sms))
    except Exception: return 0
def tail(off=0, limit=400, sms=None):
    """增量消费：从消费方自己的字节偏移读到文件末，返回 (新偏移, [条目])——O(新增字节)；
    偏移越界（被截尾/清空）自动回退 0 重取末段；末行不完整（别的进程还在写）则不消费该行。"""
    p = path(sms)
    try:
        sz = os.path.getsize(p)
    except Exception:
        return max(0, int(off or 0)), []
    off = int(off or 0)
    if off > sz: off = 0
    try:
        with open(p, "rb") as f:
            f.seek(off); data = f.read(max(0, min(sz - off, CAP)))
    except Exception:
        return off, []
    new = sz; out = []
    if data and not data.endswith(b"\n"):
        cut = data.rfind(b"\n")
        if cut < 0: return off, []
        new = off + cut + 1; data = data[:cut + 1]
    for ln in data.decode("utf-8", "replace").splitlines():
        try: e = json.loads(ln)
        except Exception: continue
        if isinstance(e, dict) and e.get("text"): out.append(e)
    return new, out[-limit:]
def recent(n=30, sms=None):
    """首消费方取历史末 n 条（不等偏移，直接读尾段）。"""
    p = path(sms)
    try:
        sz = os.path.getsize(p)
        with open(p, "rb") as f:
            f.seek(max(0, sz - 128_000)); data = f.read()
    except Exception: return []
    lines = data.decode("utf-8", "replace").splitlines()
    out = []
    for ln in lines[-max(0, int(n)):] if n else []:
        try: e = json.loads(ln)
        except Exception: continue
        if isinstance(e, dict) and e.get("text"): out.append(e)
    return out
def label(e, width=10):
    """来源短标：〔sess 尾段·kind〕——主壳 F9/右栏据此分辨是哪条会话送来的。"""
    s = str(e.get("sess") or "?"); short = s[-width:] if s.startswith("sess-") else s[:width]
    return "〔%s·%s〕" % (short, e.get("kind") or "-")
def count(sms=None):
    try:
        with open(path(sms), encoding="utf-8", errors="replace") as f: return sum(1 for _ in f)
    except Exception: return 0
def clear(sms=None):
    try:
        with _LK: open(path(sms), "w", encoding="utf-8").close(); return "总线已清空 " + path(sms)
    except Exception as e: return "清空失败：" + str(e)[:80]
if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]
    if a[0] == "tail":
        n = int(a[1]) if len(a) > 1 and a[1].isdigit() else 30
        for e in recent(n): print("%s %s %s" % (e.get("ts"), label(e), e.get("text"))[:600])
        if not recent(n): print("（总线空——各会话的推导/工具/命令行输出将自动汇入此处·主壳 F9 同口径显示）")
    elif a[0] == "clear": print(clear())
    else: print("detail_bus: %s · %d 条 · %d 字节 · 上限 %dKB（截尾保 %dKB）" % (path(), count(), size(), CAP // 1024, KEEP // 1024))
