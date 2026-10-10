#!/usr/bin/env python3
"""no_window_audit.py — 静态审计：禁止裸 subprocess/os.system 调用点（闪黑框·抢前台根因）。

口径：AST 解析（注释与文档字符串里的字样不算命中）——
· subprocess.run|Popen|call|check_output|check_call、os.system|os.popen 一律违规；
· `from subprocess import run…` / `from os import system` 同样违规（别名绕过）；
· 例外①白名单文件 no_window.py＝静默封装本体；
· 例外②调用行或其上两行含标记 `# sms-visible`＝有意可见控制台（GUI 起 TUI、入口交棒壳）。
一切子进程须经 no_window.run/Popen；需脱离父进程仍保 DETACHED 语义者传 sms_detach=True
（封装内 OR 合并 creationflags，绝不丢原标志）。

批41 F4 扫描面扩展：默认扫 SMS-core 本体仓（doctor 口径不变＝rc=0 才算干净），
`--skills` 或 settings `no_window.scan_roots`（列表·绝对路径）追加技能安装根——本体静默
≠技能静默，技能被派发执行时同样弹前台。violations 每条带 root 字段（命中所属根），
按根汇总 roots＝[{root,scanned,violations,exists}]，白名单规则一字未改。
用法：python -B no_window_audit.py [扫描根] [--skills] [--json]；有违规 exit 1。
"""
import ast, json, os, sys

CALLS = ("run", "Popen", "call", "check_output", "check_call")
MARK = "# sms-visible"
WHITELIST = {"no_window.py": "静默子进程封装本体：唯一允许直接触碰 subprocess 的模块"}
PRUNE = {".git", ".kilo", "__pycache__", ".pytest_cache", "tmp", "SMS", "registry",
         "sessions", "workspaces", "node_modules", "vendor", "dependence", "deps"}


def _marked(lines, lineno):
    """调用行本身或其上两行带 # sms-visible 即视为有意可见控制台。"""
    return any(MARK in ln for ln in lines[max(0, lineno - 3):lineno])


def hits(src, name=""):
    """返回该源码的裸子进程调用点列表 [{line, why, file}]。"""
    lines = src.splitlines()
    out = []
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [{"line": e.lineno or 0, "why": "无法解析（语法错误）：%s" % e.msg, "file": name}]
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                mod, attr = f.value.id, f.attr
                if mod == "subprocess" and attr in CALLS and not _marked(lines, node.lineno):
                    out.append({"line": node.lineno, "why": "subprocess." + attr, "file": name})
                elif mod == "os" and attr in ("system", "popen") and not _marked(lines, node.lineno):
                    out.append({"line": node.lineno, "why": "os." + attr, "file": name})
        elif isinstance(node, (ast.ImportFrom,)):
            if node.module == "subprocess" and any(a.name in CALLS for a in node.names):
                if not _marked(lines, node.lineno):
                    out.append({"line": node.lineno, "why": "from subprocess import 别名绕过", "file": name})
            elif node.module == "os" and any(a.name in ("system", "popen") for a in node.names):
                if not _marked(lines, node.lineno):
                    out.append({"line": node.lineno, "why": "from os import system/popen", "file": name})
    return out
def _py_files(root):
    for d, ds, fs in os.walk(root):
        ds[:] = [x for x in ds if x not in PRUNE]
        for f in sorted(fs):
            if f.endswith(".py") and f not in WHITELIST:
                yield os.path.join(d, f)


def scan(root, tag=""):
    """扫描根 → {"root","tag","scanned","violations","whitelist"}（每条违规带 root）。"""
    bad, n = [], 0
    for p in _py_files(root):
        n += 1
        try:
            src = open(p, encoding="utf-8").read()
        except Exception as e:
            bad.append({"line": 0, "why": "读取失败：%s" % str(e)[:80], "file": p, "root": tag or root})
            continue
        bad += [dict(h, root=tag or root) for h in hits(src, os.path.relpath(p, root))]
    return {"root": root, "tag": tag, "scanned": n, "violations": bad,
            "whitelist": WHITELIST, "marker": MARK}


def skills_root():
    """技能安装根＝<SMS_HOME>/skills（register.json install_path 同处）。"""
    try:
        import resolve_home
        return os.path.join(resolve_home.ensure(), "skills")
    except Exception:
        return ""


def extra_roots():
    """settings no_window.scan_roots（绝对路径列表·缺省无）——扩展口径由配置承载，
    命令面 `--skills` 只加技能安装根，两者可并存。"""
    try:
        import settings
        v = settings.get("no_window.scan_roots") or []
        return [str(x) for x in (v if isinstance(v, list) else [v]) if x]
    except Exception:
        return []


def report(roots):
    """多根汇总：violations 合计（本体口径＝第一条根）、roots 逐项计数。"""
    out, per, total = [], [], 0
    for r in roots:
        total += r["scanned"]
        out += r["violations"]
        per.append({"root": r.get("tag") or r["root"], "exists": os.path.isdir(r["root"]),
                    "scanned": r["scanned"], "violations": len(r["violations"])})
    return {"scanned": total, "violations": out, "roots": per,
            "marker": MARK, "whitelist": WHITELIST}


def main():
    a = [x for x in sys.argv[1:] if x != "--skills"]
    here = os.path.dirname(os.path.abspath(__file__))
    body = os.path.dirname(os.path.dirname(here))            # SMS-core 本体仓
    roots = [os.path.abspath(a[0]) if a else body]
    tags = ["core"] if not a else ["arg"]
    if "--skills" in sys.argv[1:]:
        sk = skills_root()
        if sk and os.path.isdir(sk):
            roots.append(sk); tags.append("skills")
    roots += [r for r in extra_roots() if os.path.isdir(r) and r not in roots]
    tags += ["config"] * (len(roots) - len(tags))
    r = report([scan(p, t) for p, t in zip(roots, tags)])
    print(json.dumps(r, ensure_ascii=False))
    # 本体红线不变：core 根有违规即 exit 1；技能根命中＝报告（余量分批修，不阻塞 doctor）
    core_bad = [v for v in r["violations"] if (v.get("root") or "") not in ("skills", "config")]
    sys.exit(1 if core_bad else 0)


if __name__ == "__main__":
    main()
