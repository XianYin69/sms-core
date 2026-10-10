#!/usr/bin/env python3
"""weekly_inspect_collect.py — 〔批40 A9〕周六巡检采集固化脚本：把「取证」从对话内联
PowerShell/python -c 收编成一条命令（此前实测：内联 PowerShell 变量被吞、python -c 多行被
引号截断＝同类失败连续 3 次；结果经管道落盘带 UTF-16/BOM 让后续读取踩坑）。

一次跑完四面取证，全部落 UTF-8 文件（不经 stdout 管道）：
  errors/  skill_errors.json 台账（签名计数、状态分布、TOP 复现）
  logs/    debug.log / spin.log / dream.log / residual_sweeper.log 错误行归类
  chains/  error 链签名统计（复用 chain_error.sig 归一）
  git/     各技能仓＋SMS-core：ls-remote 健康（串行＋退避，不用 API、不碰凭据）、ahead/behind、脏文件
  heart/   qq_listen / dream_bg / plan serve 心跳时效
输出：<SMS_HOME>/planned/inspect/inspect-<YYYYMMDD>.json（结构化）＋ .md（可直接粘进计划表的取证面）。
〔落点纪律〕绝不落 <SMS_HOME>/planned 顶层：planned_tasks.py 把该目录当计划任务真源扫
（glob planned/*.json），取证 json 混进去＝validate 报不合格、tick 白读——故落 inspect 子目录。
用法：python -B weekly_inspect_collect.py [--window 7] [--out DIR] [--no-remote]
纪律：404/超时＝站点或网络问题（记 note 不记缺陷）；ls-remote 失败分「无凭据/网络/无仓」三类。"""
import argparse, io, json, os, re, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import resolve_home, no_window
SMS = resolve_home.ensure()
DATE = time.strftime("%Y-%m-%dT%H:%M:%S")
DAY = time.strftime("%Y%m%d")


def _w(path, text):
    """直写 UTF-8（无 BOM）——不靠 shell 重定向（PowerShell > 默认 UTF-16LE）。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path


def _days(window):
    return time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400 * window))


def skill_errors(sms, since):
    p = os.path.join(sms, "errors", "skill_errors.json")
    try:
        d = json.load(open(p, encoding="utf-8-sig"))
    except Exception as e:
        return {"error": str(e)[:120]}
    es = d.get("entries", [])
    win = [e for e in es if str(e.get("last", "")) >= since]
    st = {}
    for e in es:
        st[e.get("status", "?")] = st.get(e.get("status", "?"), 0) + 1
    top = sorted(win, key=lambda e: -int(e.get("count", 0)))[:12]
    return {"total": len(es), "in_window": len(win), "status": st,
            "sigs_in_window": len({(e.get("skill"), e.get("where"), e.get("sig") or str(e.get("msg"))[:40]) for e in win}),
            "top": [{"skill": e.get("skill"), "where": e.get("where"), "count": e.get("count"),
                     "status": e.get("status"), "msg": str(e.get("msg", ""))[:160]} for e in top]}


def logs(sms, since):
    out = {}
    for name in ("debug.log", "spin.log", "dream.log", "residual_sweeper.log", "serve.log"):
        p = os.path.join(sms, "logs", name)
        if not os.path.isfile(p):
            continue
        try:
            L = open(p, encoding="utf-8-sig", errors="replace").read().splitlines()
        except Exception as e:
            out[name] = {"error": str(e)[:100]}
            continue
        err = [l for l in L if "[ERR]" in l or "Traceback" in l]
        win = [l for l in err if ("[" + since[5:]) in l or not re.match(r"\[\d{2}-\d{2}", l)]
        sig = {}
        for l in win:
            k = re.sub(r"\d+", "<n>", l.split("]", 2)[-1])[:80].strip().lower()
            sig[k] = sig.get(k, 0) + 1
        out[name] = {"lines": len(L), "err": len(err), "err_in_window": len(win),
                     "top": sorted(sig.items(), key=lambda x: -x[1])[:6]}
    return out


def error_chain(sms, since):
    root = os.path.join(sms, "chains", "error")
    if not os.path.isdir(root):
        return {"error": "无 error 链目录"}
    try:
        import chain_error as ce
    except Exception as e:
        ce = None
    fr, open_n, sig = 0, 0, {}
    for f in os.listdir(root):
        if not f.endswith(".json"):
            continue
        try:
            d = json.load(open(os.path.join(root, f), encoding="utf-8-sig"))
        except Exception:
            continue
        items = d if isinstance(d, list) else [d]
        for x in items:
            t = str(x.get("text", ""))
            if not t:
                continue
            fr += 1
            if "[已修]" in t:
                continue
            open_n += 1
            body = t[4:] if t.startswith("err:") else t
            k = ce.sig(body) if ce else re.sub(r"\d+", "<n>", body)[:80].lower()
            sig[k] = sig.get(k, 0) + int(x.get("freq", 1) or 1)
    return {"frags": fr, "open": open_n, "signatures": len(sig),
            "top": sorted(sig.items(), key=lambda x: -x[1])[:10]}


def _git(repo, *a, timeout=25):
    try:
        return no_window.run(("git", "-C", repo) + a, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=timeout)
    except Exception as e:
        return None


CLASS = (("Please enter your username", "无凭据"), ("Authentication failed", "无凭据"),
         ("could not read Username", "无凭据"), ("Repository not found", "无仓/改名"),
         ("Failed to connect", "网络"), ("timed out", "网络"), ("Could not resolve host", "网络"),
         ("Connection reset", "网络"), ("The requested URL returned error: 404", "站点404"))


def remotes(sms, do_remote=True, delay=0.6):
    """技能仓健康：只用 git ls-remote（不碰凭据、不打 GitHub API＝无 404 抖动）；
    串行＋间隔（实测并发批查 39 仓全 404、单查 200＝并发是假象来源）。"""
    roots = [os.path.join(sms, "skills"), os.path.join(sms, "skills", "sub_skills")]
    dirs = [r for r in roots if os.path.isdir(r)]
    out = {"repos": 0, "synced": 0, "ahead_behind": [], "no_git": [], "remote_fail": [], "uncommitted": []}
    for base in dirs:
        for name in sorted(os.listdir(base)):
            d = os.path.join(base, name)
            if not os.path.isdir(d) or name in ("__pycache__", ".git"):
                continue
            if os.path.isfile(os.path.join(d, "SKILL.md")) or os.path.isdir(os.path.join(d, "scripts")):
                pass
            if not os.path.isdir(os.path.join(d, ".git")):
                out["no_git"].append(name)
                continue
            out["repos"] += 1
            st = _git(d, "status", "--porcelain")
            dirty = len((st.stdout or "").splitlines()) if st else 0
            if dirty:
                out["uncommitted"].append({"skill": name, "files": dirty})
            sb = _git(d, "status", "-sb")
            if sb and re.search(r"\[ahead|\[behind|\[ahead.*behind", sb.stdout or ""):
                out["ahead_behind"].append({"skill": name, "state": (sb.stdout or "").splitlines()[0][:120]})
            if not do_remote:
                continue
            r = _git(d, "ls-remote", "--heads", "origin", timeout=25)
            if r is None or r.returncode != 0:
                err = ((r.stderr or "") + (r.stdout or "")) if r else "timeout"
                kind = next((v for k, v in CLASS if k.lower() in err.lower()), "其他")
                out["remote_fail"].append({"skill": name, "kind": kind, "err": err.strip()[:160]})
            else:
                out["synced"] += 1
            time.sleep(delay)  # 退避：不打被限流
    core = os.environ.get("SMS_CORE") or ""
    if core and os.path.isdir(os.path.join(core, ".git")):
        sb = _git(core, "status", "-sb")
        rl = _git(core, "rev-list", "--count", "origin/main..HEAD")
        st = _git(core, "status", "--porcelain")
        out["core"] = {"head": (_git(core, "rev-parse", "--short", "HEAD").stdout or "").strip(),
                       "ahead": (rl.stdout or "").strip(), "uncommitted": len((st.stdout or "").splitlines()),
                       "branch": (sb.stdout or "").splitlines()[0][:120] if sb else ""}
    return out


def hearts(sms):
    out = {}
    for label, p in (("qq_listen", os.path.join(sms, "qq", "listen.heartbeat")),
                     ("dream", os.path.join(sms, "chains", "dream.heartbeat")),
                     ("plan_serve", os.path.join(sms, "planned", "serve.pid")),
                     ("stall", os.path.join(sms, "qq", "stall.json"))):
        if not os.path.isfile(p):
            out[label] = "缺失"; continue
        age = int(time.time() - os.path.getmtime(p))
        out[label] = "%ds前" % age + ("〔陈旧〕" if age > 3600 else "")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=7)
    ap.add_argument("--out", default="")  # 缺省 <SMS>/planned/inspect（不入计划任务真源目录）
    ap.add_argument("--no-remote", action="store_true")
    a = ap.parse_args()
    since = _days(a.window)
    rep = {"generated": DATE, "window_days": a.window, "since": since, "sms": SMS,
           "skill_errors": skill_errors(SMS, since), "logs": logs(SMS, since),
           "error_chain": error_chain(SMS, since), "git": remotes(SMS, not a.no_remote),
           "heartbeats": hearts(SMS)}
    od = a.out or os.path.join(SMS, "planned", "inspect")  # 子目录＝避开计划任务真源扫描面
    jp = _w(os.path.join(od, "inspect-%s.json" % DAY), json.dumps(rep, ensure_ascii=False, indent=1))
    md = [u"# 巡检取证 %s（窗口 %d 天·固化脚本产出）" % (rep["generated"], a.window),
          u"- skill_errors：总 %s｜窗口内 %s（签名 %s）｜状态 %s" % (
              rep["skill_errors"].get("total"), rep["skill_errors"].get("in_window"),
              rep["skill_errors"].get("sigs_in_window"), rep["skill_errors"].get("status")),
          u"- error 链：碎片 %s｜未修 %s｜签名 %s 类" % (
              rep["error_chain"].get("frags"), rep["error_chain"].get("open"), rep["error_chain"].get("signatures")),
          u"- git：仓 %s｜ls-remote 通 %s｜无 .git %s｜远端失败 %s｜领先/落后 %s｜脏仓 %s" % (
              rep["git"]["repos"], rep["git"]["synced"], len(rep["git"]["no_git"]),
              len(rep["git"]["remote_fail"]), len(rep["git"]["ahead_behind"]), len(rep["git"]["uncommitted"])),
          u"- 心跳：%s" % rep["heartbeats"]]
    for lg, v in rep["logs"].items():
        md.append(u"- 日志 %s：%s" % (lg, v))
    md.append(u"## error 链 TOP\n")
    for k, n in rep["error_chain"].get("top", []):
        md.append(u"- ×%d %s" % (n, k))
    mp = _w(os.path.join(od, "inspect-%s.md" % DAY), "\n".join(md))
    print(json.dumps({"json": jp, "md": mp, "repos": rep["git"]["repos"], "synced": rep["git"]["synced"],
                      "remote_fail": len(rep["git"]["remote_fail"]),
                      "err_frags": rep["error_chain"].get("frags")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
