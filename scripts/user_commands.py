#!/usr/bin/env python3
"""user_commands.py — 个性化指令：用户自定义指令格式（名称/描述/参数占位符/步骤模板）存 <SMS_HOME>/commands/user_commands.json；步骤三类：script:调 SMS 脚本（参数按 token 传递，Windows 路径/带空格值不破坏，写盘仍经 emit 门控）、delegate:必须回 SMS 由 dispatch 派托管 skill 执行、say:提示文本；add/rm/list/expand/run。"""
import os, sys, json, subprocess, shlex
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
def load(sms):
    try: return json.load(open(os.path.join(sms, "commands", "user_commands.json"), encoding="utf-8"))
    except Exception: return {"schema": "sms_user_commands", "version": "1.0.0", "commands": []}
def find(doc, name): return next((c for c in doc["commands"] if c["name"] == name), None)
def _save(sms, doc, write): import emit; return emit.write_json(os.path.join(sms, "commands", "user_commands.json"), doc, sms, not write)
def add(sms, name, desc, arg_names, steps, write):
    doc = load(sms)
    if find(doc, name): return {"error": "已存在，先 rm 再建: " + name}
    doc["commands"].append({"name": name, "description": desc, "arg_names": arg_names, "steps": steps})
    return {"command": name, "saved": _save(sms, doc, write)}
def rm(sms, name, write):
    doc = load(sms)
    if not find(doc, name): return {"error": "未找到: " + name}
    doc["commands"] = [x for x in doc["commands"] if x["name"] != name]
    return {"deleted": name, "saved": _save(sms, doc, write)}
def expand(sms, name, args):
    c = find(load(sms), name)
    if not c: return {"error": "无此个性化指令（先 alias 定义）: " + name}
    subs = dict(zip(c.get("arg_names", []), args))
    def sub(s):
        for k, v in subs.items(): s = s.replace("{" + k + "}", v)
        return s.replace("{args}", " ".join(args[len(subs):]))
    return {"command": name, "plan": [sub(s) for s in c.get("steps", [])]}
def run(sms, name, args):
    if not (c := find(load(sms), name)): return expand(sms, name, args)
    subs = dict(zip(c.get("arg_names", []), args)); rest = " ".join(args[len(subs):]); out = []
    sstr = lambda t: __import__("functools").reduce(lambda x, kv: x.replace("{" + kv[0] + "}", kv[1]), subs.items(), t).replace("{args}", rest)
    for tpl in c.get("steps", []):
        kind, _, body = tpl.partition(":")
        if kind == "script":
            toks = [t.strip('"') for x in shlex.split(body, posix=False) for t in (args[len(subs):] if x == "{args}" else [sstr(x)])]
            p = subprocess.run([sys.executable, "-B", os.path.join(HERE, toks[0])] + toks[1:], capture_output=True, text=True, encoding="utf-8", errors="replace")
            out.append({"script": " ".join(toks), "rc": p.returncode, "out": (p.stdout or p.stderr).strip()[:400]})
        elif kind == "delegate": out.append({"delegate": sstr(body), "next": "回 SMS：dispatch 派托管 skill 执行、整合结果作答（红线 6·批16 LLM 主导：动手必真执行）"})
        else: out.append({"say": sstr(body)})
    return {"command": name, "executed": out}
if __name__ == "__main__":
    import resolve_home
    sms = resolve_home.ensure(); a = sys.argv[1:]; w = "--write" in a
    cmd = a[0] if a else "list"; pos = [x for x in a[1:] if not x.startswith("--")] or a[1:2]; kv = dict(x[2:].split("=", 1) for x in a[1:] if x.startswith("--") and "=" in x)
    if cmd == "add": r = add(sms, pos[0], kv.get("desc", ""), kv["args"].split(",") if "args" in kv else [], [x[7:] for x in a[1:] if x.startswith("--step=")], w)
    elif cmd == "rm": r = rm(sms, pos[0], w)
    elif cmd == "expand": r = expand(sms, a[1], a[2:])
    elif cmd == "run": r = run(sms, a[1], a[2:])
    else: r = {"commands": load(sms)["commands"], "usage": "list | add <name> --desc=.. --args=a,b --step='script:..|delegate:..|say:..' [--write] | rm <name> [--write] | expand <name> [args] | run <name> [args]"}
    print(json.dumps(r, ensure_ascii=False, indent=2))
