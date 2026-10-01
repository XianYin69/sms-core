#!/usr/bin/env python3
"""skill_doc.py — SKILL.md 解释器（SMS 内置·免为读 skill.md 再写专用 python·2026-09-26 用户需求）：frontmatter(doc) 解析顶层 k:v；refs(base,doc,entry) 从正文抽取明示引用的 *.md/*.py/*.ps1/*.sh/*.cmd/*.json 相对路径（markdown 链接/行内代码/裸路径 token 通用正则），只收真实存在且位于技能目录内文件（绝不列举/遍历目录，红线 17）；invokers() 产「脚本调用清单」（python -B 绝对路径·ps1/cmd/sh 直通），随 SKILL.md 全文＋被引子文档（≤8 篇·单篇 ≤12k 字·总预算默认 90k）打包成 package() 注入派发对话——模型免再 exec 回读子文件，修复旧 run_skill 只喂 SKILL.md 单文件导致派发对话到处摸文件空转烧轮次；(mtime,size) 内存缓存。用法：python -B skill_doc.py "<技能安装路径>" [budget]"""
import os, re, json, sys
_REL = re.compile(r"(?<![\w/\\.])([\w\-\.\u4e00-\u9fff/\\ ]+?\.(?:md|py|ps1|sh|cmd|json))(?![\w])")
_C = {}
def _read(p):
    try: k = (os.path.getmtime(p), os.path.getsize(p))
    except Exception: return ""
    if (e := _C.get(p)) and e[0] == k: return e[1]
    try: t = open(p, encoding="utf-8", errors="replace").read()
    except Exception: t = ""
    _C[p] = (k, t); return t
def frontmatter(doc):
    m = re.match(r"^---\s*\n(.*?)\n---", doc, re.S); d = {}
    for ln in (m.group(1).splitlines() if m else []):
        if ":" in ln and not ln.startswith((" ", "\t")): d[ln.split(":", 1)[0].strip()] = ln.split(":", 1)[1].strip()
    return d
def refs(base, doc, entry="SKILL.md"):
    rb = os.path.realpath(str(base)); out = []
    for rel in _REL.findall(doc):
        p = os.path.realpath(os.path.join(rb, rel.strip().replace("\\", os.sep).replace("/", os.sep)))
        if (p not in out and p != rb and p.startswith(rb + os.sep) and os.path.isfile(p) and os.path.relpath(p, rb) != entry.replace("/", os.sep) and _read(p)): out.append(p)
    return out[:16]
def invokers(base, doc, entry="SKILL.md"):
    sc = [p for p in refs(base, doc, entry) if p.endswith((".py", ".ps1", ".sh", ".cmd"))][:12]
    if not sc: return "（本技能无脚本调用器）"
    return "脚本调用清单（exec 一步调用·禁止再探索技能目录）：\n" + "\n".join(("python -B " if p.endswith(".py") else "powershell -File " if p.endswith(".ps1") else "") + '"' + p + '" [args…] ← ' + os.path.relpath(p, os.path.realpath(str(base))) for p in sc)
def package(base, entry="SKILL.md", budget=90000):
    rb = os.path.realpath(os.path.expanduser(str(base))); doc = _read(os.path.join(rb, str(entry)))
    if not doc: return ""
    parts = [doc]; used = len(doc)
    for p in refs(rb, doc, entry):
        if not p.endswith(".md") or used >= budget: continue
        t = _read(p)[:12000]; parts.append("\n\n--- 引用子文档：" + os.path.relpath(p, rb) + " ---\n" + t); used += len(t)
    parts.append("\n\n" + invokers(rb, doc, entry)); return "".join(parts)[:budget]
if __name__ == "__main__":
    b = sys.argv[1] if len(sys.argv) > 1 else "."
    doc = _read(os.path.join(os.path.realpath(b), "SKILL.md"))
    print(json.dumps({"frontmatter": frontmatter(doc), "refs": [os.path.relpath(x, b) for x in refs(b, doc)], "chars": len(package(b, "SKILL.md", int(sys.argv[2]) if len(sys.argv) > 2 else 90000))}, ensure_ascii=False))
