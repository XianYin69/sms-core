#!/usr/bin/env python3
"""deploy.py — 部署＝仅把工具的 bin 统一入口文件（sms-shell(.cmd)＋原生 DOS TUI 七件 ps1（sms_shell/sms_state/sms_chain/sms_dos/sms_gw/sms_gw_http/sms_route·零 python）＋locate.py＋sms_formats.py——格式 API 已并入 sms-shell：`api` 子命令/`:api`）复制到指定路径，绝不整包复制 skill：目标=位置参数目录，或 --Path P [--NewFolder Yes] [--FolderName F]（init 语义，flag 名大小写不敏感、值保真）；同时在 <SMS_HOME>/config/config.json 登记源安装绝对路径（sms_skill），目标处的 ps1/locate.py 按 相邻→SMS_SKILL→sms_skill 三级定位回源，sms-shell 在任意路径直接可用。默认预览，--write 且已授予 write 才执行。"""
import os, sys, json, shutil
HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIN = os.path.join(HERE, "bin")
FLAGS = ("--path", "--newfolder", "--foldername", "--folder")
def _targets(raw):
    skip = set()
    for i, lx in ((i, x.lower()) for i, x in enumerate(raw)):
        if lx in FLAGS and i + 1 < len(raw) and not raw[i + 1].startswith("--"):
            raw[i] = lx + "=" + raw[i + 1]; skip.add(i + 1)
    kv = dict((x[2:].split("=", 1)[0].lower(), x[2:].split("=", 1)[1]) for i, x in enumerate(raw) if x.startswith("--") and "=" in x and i not in skip)
    dirs = [os.path.expandvars(os.path.expanduser(x)) for i, x in enumerate(raw) if i not in skip and not x.startswith("--")]
    if kv.get("path"):
        base = os.path.expandvars(os.path.expanduser(kv["path"]))
        fol = kv.get("foldername") or kv.get("folder")
        dirs.append(os.path.join(base, fol) if fol and (kv.get("newfolder") or "yes").lower() != "no" else base)
    return dirs
def _register(sms, write):
    conf = os.path.join(sms, "config", "config.json")
    doc = json.load(open(conf, encoding="utf-8")) if os.path.isfile(conf) else {}
    if doc.get("sms_skill") == HERE: return "registered(unchanged) " + HERE
    if write:
        doc["sms_skill"] = HERE
        json.dump(doc, open(conf, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return ("register " if write else "would register ") + "sms_skill=" + HERE
def _copy(d, write):
    acts = []
    for name in sorted(os.listdir(BIN)):
        src = os.path.join(BIN, name)
        if not os.path.isfile(src): continue
        dst = os.path.join(d, name)
        acts.append(("deploy bin " if write else "would deploy ") + dst)
        if write:
            os.makedirs(d, exist_ok=True); shutil.copy2(src, dst)
            if not dst.endswith(".cmd"): os.chmod(dst, 0o755)
    return acts
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home, permissions
    sms = resolve_home.ensure(); raw = [x for x in sys.argv[1:] if x.lower() != "init"]; w = "--write" in raw
    dirs = _targets(raw)
    if not dirs:
        print("用法: deploy.py [init] <dir...> | --Path P [--NewFolder Yes] [--FolderName F] [--write]"); sys.exit(1)
    try:  # 后台/非交互：SOLO 自审不入此路（无人应答·防阻塞与成本失控）
        import permissions; permissions.set_noninteractive(True)
    except Exception: pass
    if w and not permissions.allow(sms, "write"):
        print("DENIED: 会话未授予 write 权限（permissions.json）"); sys.exit(1)
    print(json.dumps({"targets": dirs, "actions": [_register(sms, w)] + [a for d in dirs for a in _copy(d, w)]}, ensure_ascii=False, indent=2))
