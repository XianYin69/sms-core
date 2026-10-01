#!/usr/bin/env python3
"""ws_release.py — 工作区 tmp 产物审核与收编（用户 2026-09-26 指示：tmp 内修改的文件且目标是工作区内的文件，经审核后可释放到工作区）：list/review＝tmp 待审清单；diff <tmp内文件> --to <工作区相对目标>＝审核（目标已存在出 unified diff，不存在出新建预览）；release <tmp内文件> --to <工作区相对目标> [--yes]＝收编（移动 tmp 文件到工作区目标路径）。源必须位于当前工作区 tmp/ 内、目标必须位于工作区根内且不得逃出或指回 tmp（realpath  containment）；默认仅预览，--yes 且用户当轮明确同意并经 :grant danger 才真实移动（红线 2/16·向用户目录移动覆盖＝高危）；释放记 event 链。用法：python -B ws_release.py list | diff <rel> --to <dest> | release <rel> --to <dest> --yes。"""
import os, sys, shutil, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, chains, permissions
def ws_root(): return os.path.realpath(resolve_home.workspace())
def tmp_root(): return os.path.join(ws_root(), "tmp")
def _ins(base, p): r = os.path.realpath(os.path.join(base, str(p or "").replace("/", os.sep))); return (r == base or r.startswith(base + os.sep)), r
def pair(name, to):
    ok, src = _ins(tmp_root(), name)
    if not ok or not os.path.isfile(src): return None, "拒绝：源须为 tmp/ 内已存在文件（生成文件先只入 tmp 待审）：" + str(name)
    ok, dst = _ins(ws_root(), to)
    if not ok or dst == tmp_root() or dst.startswith(tmp_root() + os.sep): return None, "拒绝：目标必须位于工作区根内且不得逃出或指回 tmp/：" + str(to)
    if os.path.isdir(dst): return None, "拒绝：目标是已存在目录 " + dst
    return (src, dst), None
def ls():
    t = tmp_root(); rows = [os.path.relpath(os.path.join(dp, fn), t) + "  " + str(os.path.getsize(os.path.join(dp, fn))) + "B" for dp, _, ns in os.walk(t) for fn in ns]
    return "tmp 待审产物（" + t + "）：\n" + "\n".join(rows) if rows else "tmp 无待审产物：" + t
def diff(name, to):
    pr, err = pair(name, to)
    if err: return err
    src, dst = pr
    if not os.path.exists(dst):
        head = "\n".join(open(src, encoding="utf-8", errors="replace").read().splitlines()[:20])
        return "新文件 " + os.path.relpath(src, tmp_root()) + " → " + dst + "\n" + head
    a = open(dst, encoding="utf-8", errors="replace").read().splitlines(); b = open(src, encoding="utf-8", errors="replace").read().splitlines()
    d = list(difflib.unified_diff(a, b, "工作区现文件", "tmp 新文件", lineterm="", n=2))
    return "\n".join(d[:80]) or "与现文件完全一致（无需释放）：" + dst
def release(name, to, yes=False):
    pr, err = pair(name, to)
    if err: return err
    src, dst = pr; msg = "释放 " + os.path.relpath(src, tmp_root()) + " → " + dst + ("（覆盖现有文件）" if os.path.exists(dst) else "（新文件）")
    if not yes: return msg + "\n预览·未执行：审核同意后须用户当轮明确确认并加 --yes 释放（目标仅限工作区内·须先 :grant danger）"
    if not permissions.allow(resolve_home.ensure(), "danger"): return msg + "\n拒绝执行：向用户工作区移动/覆盖＝高危，须用户当轮同意并 :grant danger（红线 2/16）"
    os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.move(src, dst)
    chains.record("event", "ws release " + os.path.relpath(dst, ws_root())[:120]); return msg + "\n已释放到工作区：" + dst
def main(a):
    yes = "--yes" in a; t = a[a.index("--to") + 1] if "--to" in a else ""
    if not a or a[0] in ("list", "review"): return ls()
    if a[0] == "diff" and len(a) > 1: return diff(a[1], t)
    if a[0] == "release" and len(a) > 1: return release(a[1], t, yes)
    return __doc__.strip().splitlines()[-1]
if __name__ == "__main__": print(main(sys.argv[1:]))
