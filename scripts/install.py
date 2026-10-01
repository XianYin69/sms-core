#!/usr/bin/env python3
"""install.py — skill 包管理器：从本地目录或云端 gh:owner/repo[/sub] 安装到目标 agent 客户端 skills 文件夹；本地→trusted_local，云端→pending_review（trust review 通过前不被 sync push 推送）；云端下载需 network+write 且 --accept-download 用户确认；包内 dependence/ 经 pkg_deps 与技能包同检同净化，未过即拒整包。"""
import os, sys, json, shutil, subprocess

def _targets(a):
    from sync_skills import clients
    want = a[a.index("--clients") + 1] if "--clients" in a else "all"
    return {k: v for k, v in clients().items() if want == "all" or k in want.split(",")}

def _fetch(sms, spec, write):
    parts = spec[3:].split("/"); owner_repo = "/".join(parts[:2])
    dest = os.path.join(sms, "tmp_install", parts[1] if len(parts) > 1 else "repo")
    if not write: return dest, "would git clone --depth 1 https://github.com/%s.git" % owner_repo
    import permissions
    if not (permissions.allow(sms, "network") and permissions.allow(sms, "write")): return None, "DENIED: 云端安装需授予 network + write"
    if not os.environ.get("SMS_ACCEPT_DOWNLOAD"): return None, "CONFIRM: 通过网络下载子skill到目标skill目录须用户同意——加 --accept-download"
    shutil.rmtree(dest, ignore_errors=True); os.makedirs(os.path.dirname(dest), exist_ok=True)
    r = subprocess.run(["git", "clone", "--depth", "1", "https://github.com/" + owner_repo + ".git", dest], capture_output=True, text=True)
    return (os.path.join(dest, "/".join(parts[2:])) if r.returncode == 0 else None), (r.stderr or r.stdout).strip()[:200]

def install(sms, src, cls, write, source):
    from sync_skills import _hash
    if src.startswith("gh:"):
        got, note = _fetch(sms, src, write)
        if not got: return {"error": note}
        src = got
    if not os.path.isdir(src) or not os.path.isfile(os.path.join(src, "SKILL.md")): return {"error": "源缺少 SKILL.md: " + src}
    import pkg_deps
    deps = pkg_deps.check(sms, src, source, write)
    if deps and deps["rejected"]: return {"error": "dependence 检查与净化未过: " + ", ".join(deps["rejected"]), "dependence": deps}
    n = os.path.basename(os.path.normpath(src)); acts = []
    for c, root in sorted(cls.items()):
        dst = os.path.join(root, n)
        if os.path.isdir(dst) and _hash(dst) == _hash(src): acts.append("same " + c); continue
        acts.append(("would install " if not write else "install ") + n + " -> " + c)
        if write: os.makedirs(root, exist_ok=True); shutil.copytree(src, dst, dirs_exist_ok=True)
    if write:
        import trust; trust.mark(sms, n, "pending_review" if source == "cloud" else "trusted_local", source, by="install")
        shutil.rmtree(os.path.join(sms, "tmp_install"), ignore_errors=True)
    return {"skill": n, "source": source, "actions": acts, "dependence": deps, "label": "pending_review" if source == "cloud" else "trusted_local"}

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import resolve_home, permissions
    sms = resolve_home.ensure(); argv = sys.argv[1:]; w = "--write" in argv
    if "--accept-download" in argv: os.environ["SMS_ACCEPT_DOWNLOAD"] = "1"
    pos = [x for i, x in enumerate(argv) if not x.startswith("--") and argv[i - 1] != "--clients"]
    if not pos: print("用法: install.py <path|gh:owner/repo[/sub]> [--clients a,b|all] [--accept-download] --write"); sys.exit(1)
    src = pos[0]
    if w and not permissions.allow(sms, "write"): print("DENIED: 会话未授予 write 权限（permissions.json）"); sys.exit(1)
    print(json.dumps(install(sms, src, _targets(argv), w, "cloud" if src.startswith("gh:") else "local"), ensure_ascii=False, indent=2))
