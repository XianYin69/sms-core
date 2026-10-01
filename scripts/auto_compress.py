#!/usr/bin/env python3
"""auto_compress.py — 自动触发智能体上下文压缩：会话日目录（不计归档）超阈值时，把 dialogue.md 旧记录折叠为打分提纲，原文无损归档 context_archive.md（sha1 可回溯）。"""
import os, sys, re, time, hashlib

MAX_BYTES = 20000
KEEP_TAIL = 30
STOP = re.compile(r"[。！？；;.\n]")

def _digest(head):
    sents = [s.strip() for s in STOP.split(head) if len(s.strip()) > 4]
    scored = [(2 if re.search(r"\d|意图|决定|结论|红线|钉选", s) else 1, i, s) for i, s in enumerate(sents)]
    top = sorted(sorted(scored, reverse=True)[:max(1, int(len(scored) * 0.3))], key=lambda x: x[1])
    return "\n".join("- " + x[2] for x in top)

def compress_day(sms, day, write):
    d = os.path.join(sms, "sessions", day); p = os.path.join(d, "dialogue.md")
    if not os.path.isdir(d) or not os.path.exists(p): return None
    total = sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d) if f != "context_archive.md")
    if total <= MAX_BYTES: return None
    lines = open(p, encoding="utf-8").read().splitlines()
    if "## 记录" not in lines or len(lines) - lines.index("## 记录") - 1 <= KEEP_TAIL: return None
    i = lines.index("## 记录")
    head = "\n".join(lines[i + 1:-KEEP_TAIL]); tail = lines[-KEEP_TAIL:]
    sha = hashlib.sha1(head.encode("utf-8")).hexdigest()[:10]
    out = lines[:i + 1] + ["", "> 压缩 %s（原文归档 context_archive.md，sha1=%s）" % (time.strftime("%F %T"), sha), _digest(head), ""] + tail
    if not write: return {"preview": p, "context_bytes": total, "head_lines": len(head.splitlines())}
    import permissions
    try:  # 后台/非交互：SOLO 自审不入此路（无人应答·防阻塞与成本失控）
        import permissions; permissions.set_noninteractive(True)
    except Exception: pass
    if not permissions.allow(sms, "write"): return {"denied": "会话未授予 write 权限（permissions.json），拒绝压缩"}
    with open(os.path.join(d, "context_archive.md"), "a", encoding="utf-8") as h:
        h.write("\n\n## 归档 %s sha1=%s\n\n%s\n" % (time.strftime("%F %T"), sha, head))
    open(p, "w", encoding="utf-8").write("\n".join(out) + "\n")
    return {"compressed": p, "sha1": sha, "context_bytes_before": total}

def maybe(sms):
    """emit 会话写盘后自动触发：已授予 write 才压缩，否则静默。"""
    import permissions
    if permissions.allow(sms, "write"):
        r = compress_day(sms, time.strftime("%Y-%m-%d"), True)
        if r:
            print("[auto_compress] " + str(r))

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home
    sms = resolve_home.ensure()
    day = next((a for a in sys.argv[1:] if not a.startswith("--")), time.strftime("%Y-%m-%d"))
    r = compress_day(sms, day, "--write" in sys.argv)
    print("无需压缩（低于阈值或无旧记录）" if r is None else r)
