#!/usr/bin/env python3
"""workspace.py — SMS_WORKSPACE 工作区管理（2026-09-26 v2·与数据根分离）：SMS_HOME 恒指一开始创建的 SMS 目录（配置/记忆/注册表/虚拟工作区都在内），工作区＝智能体操作文件的目录（resolve_home.workspace：env SMS_WORKSPACE > 配置 sms_workspace > 虚拟）——切换只经 settings 写 workspaces/sms_workspace（config.json·dot-path 唯一属主不变·记 event 链）＋env，gateway exec/agent CLI 的 cwd 即时按新工作区起，SMS_HOME 与配置零改动（修复 v1「切换工作区＝换数据根→配置看似被重置」）。真实与虚拟工作区一律自动创建 tmp/ 子目录（switch/begin 时经 resolve_home.wtmp·生成文件只落 tmp·大模型/技能配置直读 <SMS_HOME>/config 不复制进工作区·env SMS_TMP 供子进程）；tmp 内目标为工作区文件的产物经用户审核可经 ws_release.py（list/review→diff→release --yes＋:grant danger）收编回工作区（review|diff|release 子命令同径转发）。虚拟工作区生命周期（用户 2026-09-26 指示"对话完成后立马删除"）：begin <conv> 无真实工作区时建 <SMS_HOME>/workspaces/_virtual/<conv>；end 收口即删——仅允许删除 _virtual 前缀内路径，有产物先列明细告警再删。repair-home 清理 v1 残留：bootstrap sms_home 被 v1 切换改指 → 改回初始 SMS 目录，v1 bootstrap workspaces 键迁入配置系统。用法：python -B workspace.py current|list|add <path>|switch <path>|remove <path>|use-virtual|begin <conv>|end <path>|tmp|review|diff <tmp文件> --to <目标>|release <tmp文件> --to <目标> [--yes]|repair-home。"""
import os, sys, json, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import resolve_home, settings, chains
def _abs(p): return os.path.abspath(os.path.expanduser(p))
def current(): return resolve_home.workspace()
def vroot(): return os.path.join(resolve_home.resolve(), "workspaces", "_virtual")
def is_virtual(p=None): q = os.path.realpath(p or current()); r = os.path.realpath(vroot()); return q == r or q.startswith(r + os.sep)
def list_ws():
    ws = [x for x in (settings.get("workspaces", []) or []) if isinstance(x, str) and x]; cur = current(); return ([cur] if cur not in ws and not is_virtual(cur) else []) + ws
def add(p):
    if not os.path.isdir(p := _abs(p)): return "拒绝：工作区目录不存在 " + p
    if p not in list_ws(): settings.set("workspaces", list_ws() + [p])
    return "已登记工作区：" + p
def switch(p):
    if not p: return use_virtual()
    if (msg := add(p)).startswith("拒绝"): return msg
    settings.set("sms_workspace", _abs(p)); os.environ["SMS_WORKSPACE"] = _abs(p); resolve_home.wtmp(); return msg + "\n已切换工作区 → " + _abs(p) + "（即时生效：gateway exec/agent CLI 在此目录操作·已建 tmp/ 收生成文件；SMS_HOME 与配置不动）"
def remove(p):
    old = list_ws(); ws = [x for x in old if x != _abs(p)]; settings.set("workspaces", ws); return "已移除登记：" + p if len(ws) < len(old) else "无登记工作区：" + p
def use_virtual():
    settings.set("sms_workspace", None); os.environ.pop("SMS_WORKSPACE", None); return "已回退内置虚拟工作区（每对话独立·开建口删）"
def begin(conv):
    if not is_virtual(p := current()): resolve_home.wtmp(); return p, False
    p = os.path.join(os.path.realpath(p), "".join(c for c in str(conv) if c.isalnum() or c in "-_.")[:40]); os.makedirs(p, exist_ok=True); os.environ["SMS_WORKSPACE"] = p; resolve_home.wtmp(); chains.record("event", "ws begin " + p[:120]); return p, True
def end(p, virt=True):
    if not virt or not is_virtual(p): return None
    os.environ.pop("SMS_WORKSPACE", None); files = [str(os.path.relpath(os.path.join(dp, fn), p)) for dp, _, ns in os.walk(p) for fn in ns]
    shutil.rmtree(p, ignore_errors=True); chains.record("event", "ws end " + p[:120]); return "虚拟工作区已收口删除：" + p + (("\n⚠ 丢弃未收编产物 " + str(len(files)) + " 个：" + "、".join(files[:5]) + ("…" if len(files) > 5 else "") + "\n（提示：删除前可 :workspace review/diff/release 把目标为工作区的产物经审核收编）") if files else "")
def boot(): return os.environ.get("SMS_BOOT") or os.path.join(resolve_home._cache() or os.path.expanduser("~"), "SMS", "config", "config.json")
def repair_home():
    b = boot(); msgs = []; orig = os.path.dirname(os.path.dirname(b))
    try: d = json.load(open(b, encoding="utf-8-sig"))
    except Exception: d = {}
    if d.get("sms_home") and _abs(str(d["sms_home"])) != _abs(orig): d["sms_home"] = orig; msgs.append("SMS_HOME 已修复指向初始 SMS 目录 " + orig)
    if isinstance(d.get("workspaces"), list):
        [settings.set("workspaces", (settings.get("workspaces", []) or []) + [w]) for w in d.pop("workspaces") if w and os.path.isdir(w) and w not in (settings.get("workspaces", []) or [])]
        msgs.append("v1 工作区清单已迁入配置系统")
    if msgs: json.dump(d, open(b, "w", encoding="utf-8"), ensure_ascii=False, indent=2); chains.record("event", "workspace repair-home " + "；".join(msgs)[:120])
    return "；".join(msgs) or "无 v1 残留（bootstrap 干净）"
if __name__ == "__main__":
    a = sys.argv[1:] or ["list"]; cmd = a[0]
    if cmd == "current": print(current())
    elif cmd == "list": print("\n".join(("* " if w == current() else "  ") + w for w in list_ws()) + "\n◎ 虚拟工作区：" + vroot() + ("（当前）" if is_virtual(current()) else ""))
    elif cmd in ("add", "switch", "remove", "begin", "end", "use-virtual", "repair-home", "tmp") and (len(a) > 1 or cmd in ("use-virtual", "repair-home", "tmp")): print({"add": add, "switch": switch, "remove": remove, "begin": begin, "end": lambda x: end(x, True), "use-virtual": use_virtual, "repair-home": repair_home, "tmp": resolve_home.wtmp}[cmd](*( [" ".join(a[1:])] if cmd in ("add", "switch", "remove", "begin", "end") else [])))
    elif cmd in ("list-tmp", "review", "diff", "release"): import ws_release; print(ws_release.main(["list" if cmd == "list-tmp" else cmd] + a[1:]))
    else: print(__doc__.strip().splitlines()[-1])
