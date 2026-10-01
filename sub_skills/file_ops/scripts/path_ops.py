#!/usr/bin/env python3
"""path_ops.py — file_ops 子技能·路径查询（只读）：resolve 相对/绝对定位（可回退 <SMS_HOME>/ 或 temp 分配）、which 可执行定位、exists、glob 通配列举、tree 目录树（限深限数）、env 关键路径一览。仅 read 权限，不改盘；结果记 tool_call 链。用法：python -B path_ops.py resolve <path> [--sms] | which <cmd> | exists <path> | glob <dir> <pat> [--n] | tree <dir> [--depth n] | env。"""
import os, sys, json, glob as _g, shutil
PS = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts")); sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), PS]
import resolve_home, chains
SMS = resolve_home.ensure()
def resolve(p, to_sms=False):
    a = p if os.path.isabs(p) else (os.path.join(SMS, p.lstrip("\\/")) if to_sms else os.path.abspath(p))
    return json.dumps({"input": p, "abs": os.path.normpath(a), "exists": os.path.exists(a), "kind": "dir" if os.path.isdir(a) else "file" if os.path.isfile(a) else "-"}, ensure_ascii=False)
def temp(rel="", mkdir=False):
    try: return resolve_home.temp(SMS, rel, bool(mkdir))
    except SystemExit as e: return str(e)
def exists(p): return str(os.path.exists(p))
def which(cmd): return shutil.which(cmd) or "（PATH 未找到）"
def glob_(d, pat="*", n=300):
    if not os.path.isdir(d): return "目录不存在：" + d
    r = sorted(_g.glob(os.path.join(d, pat)))[:int(n)]
    return "\n".join(x.replace("\\", "/") for x in r) or "（无匹配）"
def tree(d, depth=2, _i=0):
    if not os.path.isdir(d): return "目录不存在：" + d
    out = ["  " * _i + os.path.basename(d.rstrip("\\/")) or d]
    if _i >= int(depth): return "\n".join(out)
    for e in sorted(os.listdir(d))[:120]:
        fp = os.path.join(d, e)
        out.append(tree(fp, depth, _i + 1) if os.path.isdir(fp) and e not in (".git", "__pycache__", "node_modules") else "  " * (_i + 1) + e)
    return "\n".join(out)
def env():
    return json.dumps({"SMS_HOME": SMS, "home": os.path.expanduser("~"), "cwd": os.getcwd(),
                       "temp_alloc": os.path.join(SMS, "tmp"), "skill_dir": os.path.abspath(os.path.join(PS, ".."))}, ensure_ascii=False, indent=1)
if __name__ == "__main__":
    a = sys.argv[1:] or ["env"]; c = a[0]; argv = [x for x in a[1:] if not x.startswith("--")]
    chains.log("tool", "path_ops:" + c)
    if c == "resolve": print(resolve(argv[0], "--sms" in a))
    elif c == "temp": print(temp(argv[0] if argv else "", "--mkdir" in a))
    elif c == "which": print(which(argv[0]))
    elif c == "exists": print(exists(argv[0]))
    elif c == "glob": print(glob_(argv[0], argv[1] if len(argv) > 1 else "*", a[a.index("--n") + 1] if "--n" in a else 300))
    elif c == "tree": print(tree(argv[0], a[a.index("--depth") + 1] if "--depth" in a else 2))
    else: print(env())
