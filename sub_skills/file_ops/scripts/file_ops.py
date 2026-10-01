#!/usr/bin/env python3
"""file_ops.py — file_ops 子技能引擎：文件 读/写/追加/复制/移动/删除/列举/信息。读只读开放；写盘统一经 emit 门控（默认预览，--write 且会话 grant write 才落盘）；复制/移动/覆盖/删除＝高危，先预览并经用户当轮同意（--yes）且 grant danger（红线16）。禁止写入 skill 本体目录（一律落 <SMS_HOME>/）。每次动作记 tool_call 链。用法：python -B file_ops.py read <path> [--max n] | write <path> (--text ".."|--from f) [--append] | copy <src> <dst> | move <src> <dst> | delete <path> | list <dir> [--glob pat] [--write] | stat <path>；高危动作加 --yes --write。"""
import os, sys, json, glob as _g, shutil
PS = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts")); sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), PS]
import resolve_home, permissions, chains
SMS = resolve_home.ensure(); SK = os.path.abspath(os.path.join(PS, ".."))
def _guard(p): a = os.path.abspath(p); return a == SK or a.startswith(SK + os.sep) or a == SMS or a.startswith(SMS + os.sep)
def read(p, mx=20000):
    if not os.path.isfile(p): return "文件不存在：" + p
    d = open(p, encoding="utf-8", errors="replace").read(int(mx))
    return d + ("\n…[截断 %dB]" % os.path.getsize(p) if os.path.getsize(p) > int(mx) else "")
def _write(p, content, append, dry, sms):
    if _guard(p): return "拒绝：不得写入 skill 本体目录（落 <SMS_HOME>/）：" + p
    if dry: return "预览写入 %s（%d 字%s）——--write 且 grant write 才落盘" % (p, len(content), "·追加" if append else "")
    if not permissions.allow(sms, "write"): return "DENIED：会话未授予 write，拒绝落盘"
    os.makedirs(os.path.dirname(os.path.abspath(p)) or ".", exist_ok=True)
    open(p, "a" if append else "w", encoding="utf-8").write(content); chains.log("tool", "file_ops:write")
    return "已写入 " + p
def move_copy(src, dst, mv, yes, dry, sms):
    if _guard(dst) or (mv and _guard(src)): return "拒绝：涉 skill 本体目录"
    if os.path.exists(dst): return "拒绝覆盖已存在目标（高危，须先删或换名）：" + dst
    if dry: return "预览%s %s→%s——--write 且 grant danger 才执行" % ("移动" if mv else "复制", src, dst)
    if not (permissions.allow(sms, "write") and permissions.allow(sms, "danger") and yes): return "DENIED：复制/移动为高危，须 --yes + grant danger + write"
    (shutil.move if mv else shutil.copy2)(src, dst); chains.log("tool", "file_ops:" + ("move" if mv else "copy")); return ("已移动 " if mv else "已复制 ") + src + "→" + dst
def delete(p, yes, sms):
    if _guard(p): return "拒绝：不得删除受保护 skill 本体"
    if not os.path.exists(p): return "路径不存在：" + p
    if not (permissions.allow(sms, "danger") and yes): return "DENIED：删除为高危（无 --yes 或未 grant danger），未执行 " + p
    shutil.rmtree(p) if os.path.isdir(p) else os.remove(p); chains.log("tool", "file_ops:delete"); return "已删除 " + p
def ls(d, pat="*"):
    if not os.path.isdir(d): return "目录不存在：" + d
    return "\n".join(sorted(x.replace("\\", "/") for x in _g.glob(os.path.join(d, pat)))[:400]) or "（空）"
def _content(a, argv):
    if "--text" in a:
        rest = a[a.index("--text") + 1:]; return " ".join(x for x in rest if not x.startswith("--"))
    if "--from" in argv: return open(argv[argv.index("--from") + 1], encoding="utf-8", errors="replace").read()
    return ""
if __name__ == "__main__":
    a = sys.argv[1:] or ["__doc__"]; c = a[0]; W = "--write" in a; Y = "--yes" in a
    argv = [x for x in a[1:] if not x.startswith("--")]
    if c == "read": print(read(argv[0], a[a.index("--max") + 1] if "--max" in a else 20000)); chains.log("tool", "file_ops:read")
    elif c == "stat": print(json.dumps({os.path.abspath(argv[0]): os.path.getsize(argv[0])}, ensure_ascii=False) if os.path.isfile(argv[0]) else ls(argv[0])); chains.log("tool", "file_ops:stat")
    elif c == "write": print(_write(argv[0], _content(a, argv), "--append" in a, not W, SMS))
    elif c == "list": print(ls(argv[0], argv[1] if len(argv) > 1 else "*")); chains.log("tool", "file_ops:list")
    elif c == "copy": print(move_copy(argv[0], argv[1], False, Y, not W, SMS))
    elif c == "move": print(move_copy(argv[0], argv[1], True, Y, not W, SMS))
    elif c == "delete": print(delete(argv[0], Y, SMS))
    else: print(__doc__.strip()); sys.exit(1)
