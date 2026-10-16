#!/usr/bin/env python3
"""shell_qt_fax.py — GUI 的「传真机镜像件」（shell_qt.py 专用模块，不独立成壳）。
① 版式真源＝网页端 web_page.html：CSS :root 变量 → QSS 渐变（机身金属/功能区/实体键五态/LCD/米纸卷/抽屉/
   按需层 ctlzone·命令面板 palette·走纸态 mouth/tear[st=…]），
   JS 常量 META·METAD·PAD·QUICK·F1 → 元指令键阵、拨号盘、常用拨号、F1 六组——网页端改了 GUI 跟着改，不留两份口径；
   页面取不到时用内置兜底（值取自网页端现文本），保证离仓仍可成图。
② 数据真源＝web_shell 面板 getter/poster **进程内直调**：GUI 端不做任何密钥验证（本机窗口即可信·绝不开端口·
   绝不读/显影/复制/轮换 token），/api/* 路径名与网页端逐字相同，面板结构因此天然一致；
   info 结果一律 scrub 掉 token/fingerprint（GUI 无密钥面）。
③ 红线：只读页面文本做样式，不改 web_page.html / web_shell.py 语义；写操作只走 web_shell 既有 poster
   （其内部权限门、external 高危 confirm=yes、路径越界 _under 校验全部继承）。
④ 视图件三（批39）：t6 出纸末端「裁纸刀」（CUT_STEPS 五态推进·进程内 QTimer 走步·零新端口零新进程）、
   t8 送稿口 CRT 绿字黑底成像（crt_colors·crt_scanlines·crt_afterglow·crt_block_cursor 算式在此，逐帧绘制在
   shell_qt.Input 的 paintEvent·不改文本模型与键盘语义）、
   t10 墨水屏消息面板（EINK_SECTIONS 只「会话信息／任务总览／后台任务」三段·低饱和灰白·无动效·仿电子墨水印）——
⑤ 装配件（批41 上送稿口＋下左右分屏）：build() 不装 brand 横条、shell_qt 不挂原生菜单栏——上＝B 送稿口
   （CRT 输入＋送稿键＋常用拨号·常驻第一位），其下 QSplitter#split 左右分屏＝左纸卷 A（出纸正文＋状态行
   LCD 六格/LED 七灯＋mouth/tear/blade＋动作条）｜右格 aside 竖列（QVBoxLayout）：上＝QSplitter#psplit（C 墨水屏·预览 D·终端 E·三件常驻不可折叠（childrenCollapsible=False）·可切分·Ctrl+V 五态轮转）、
   下＝按需层依次装 ctlzone（META 键阵·F1 六组·拨号盘）→抽屉——保持批41 语义（装配即 hide·Ctrl+M）；
   C 墨水屏＝批41 收尾升为 psplit 常驻第一格（永不 hide·Ctrl+I 只聚焦），底部条带撤销后提示迁 eink_stat 墨水小标，
   走纸态由 rollTag 承载（roll_next 六态·与 blade 同谱）；
   七灯 LED（线路／QQ／朗读／做梦／计划／裁纸／对外）＝本件 build() 造灯（网页端 #leds 同名 id·
   裁纸为壳侧新增），壳侧 poll* 逐灯驱动——批46 灯数校平：造灯数＝驱动数＝7（selftest 门禁
   led_driven／led_driven_n／led_built_n／led_parity），QQ 灯与网页端 pollQQ 同路走进程内 /api/qq
   （g_qq·err＝off 不谎报已连·scrub 后无密钥面）；
   造灯处＝build 内 LED 循环 L531（灯名与网页端 #leds 同，裁纸为壳侧新增）。
   行号清单（本件·算式与版式真源）：常量 墨水屏三段 L827 / 五态视图名 L829 / 裁纸五态 L723 / 走纸六态 L751；
   纯算式 roll_next L760 / roll_label L777 / view_next L831 / preview_text L694 / term_line_kind L712 / eink_html L852；
   样式与键面 css_vars L83 / qss L195 / keys L163；数据桥：GET 路由表 L351 / api 进程内直调（query）L359；
   装配 build 骨架 L493、C 常驻保底高度 L656；自检 L877。
   菜单职能＝命令面板（QDialog#palette＋QListWidget#palList·Ctrl+K）＋右键菜单。
   fw 键面与批38/39/40 逐字兼容（banner/roll/lcd_*/led_*/blade*/eink*/btn_*/keys 全保留），批41 增 feeder/tray/
   split/psplit/previewzone/preview/pv_open/pv_fold/pv_stat/termzone/term/term_in/t_run/t_fold/t_paper/t_clear/t_stat。
   视图轮转位次真源＝VIEW_NAMES 五态（纸卷 A／送稿 B／墨水屏 C／预览 D／终端 E）＋view_next 纯算式；
   预览取数收口＝preview_text（/api/file·/api/files·/api/detail 返回 → 文本＋行数＋是否兜底）、
   终端行分类＝term_line_kind（纯算式·壳侧按类上色）——两件的算式都在本件，壳只接绘制与状态。
   页面没有这些 :root 变量时按内置兜底（css_vars 的 setdefault），网页端补同名变量即刻生效。
自检：python -B shell_qt_fax.py --selftest（offscreen·解析＋样式＋数据桥＋出纸渲染＋三视图件，不发模型请求）"""
import os, sys, re, json, time, inspect

S = os.path.dirname(os.path.abspath(__file__))
# 本目录优先：混合/覆盖安装环境里 PYTHONPATH 常带着核仓旧副本，同目录件须压过它（selftest 才测到本仓文件）
if sys.path[:1] != [S]: sys.path.insert(0, S)
_CAND = [os.path.join(S, "web_page.html")]

def _cands():
    """网页端页面文件候选（同文件多落点：源仓 → 覆盖安装的 skills 目录 → SMS_HOME）——源盘偶发枚举不全时用。"""
    out = list(_CAND); home = os.environ.get("SMS_HOME") or ""
    for sub in (os.path.join("skills", "smsystem-suit", "skill", "scripts"),
                os.path.join("skill", "scripts"), "scripts"):
        if home: out.append(os.path.join(home, sub, "web_page.html"))
    try:
        import settings
        sk = settings.get("sms_skill", "") or ""
        if sk: out.append(os.path.join(sk, "skill", "scripts", "web_page.html"))
    except Exception: pass
    return [x for x in out if x and os.path.isfile(x)] or _CAND

PAGE = _CAND[0]
ROOT_DEFAULT = dict(m1="#f4f8fc", m2="#ccd6e1", m3="#94a2b3", edge="#5b697a", lcd="#04161b",
                    lcdfg="#3ff0d6", amber="#ffb02e", red="#ff5252", grn="#5cf08a", cyan="#54d9ff",
                    paper="#f7f3e7", ink="#1b2026",
                    crtf="#33ff66", crtb="#04070a", crtdim="#12401f", crtgl="#0a2a13",
                    blade="#b9c5d4", einkb="#eef0ee", einkf="#22282a", einkd="#8f979a")

def read_text(p, tries=6):
    """源盘偶发枚举不全（移动盘/杀软），短休眠重试；取不到返回空串 → 上层走内置兜底。"""
    for _ in range(tries):
        try:
            d = open(p, encoding="utf-8", errors="replace").read()
            if d: return d
        except Exception:
            time.sleep(0.3)
    return ""

def page():
    for c in _cands():
        d = read_text(c, tries=3)
        if d: return d
    return ""

# ---------------- 页面解析 ----------------
def css_vars(src=None):
    """网页端 :root{--k:v;…} → {k:v}，缺项回落内置同值（GUI 配色＝网页端配色）。
    src=None（现取页面）走 5 秒 TTL 缓存：LED/banner/CRT 成像每帧都取样配色，逐帧读盘＋正则＝掉帧；
    缓存只在缺省路径生效（显式传 src 仍现算），网页端改动 ≤5s 内生效、不留两份口径。"""
    global _VARS_TTL
    if src is None:
        now = time.time()
        if _cache.get("vars") and now - float(_cache["vars"][0]) < _VARS_TTL:
            return dict(_cache["vars"][1])
        out0 = _css_vars(page())
        _cache["vars"] = (now, dict(out0))
        return out0
    return _css_vars(src)


_VARS_TTL = 5.0

def _css_vars(src):
    out = {}
    m = re.search(r":root\{(.*?)\}", src, re.S)
    if m:
        for k, v in re.findall(r"--([a-zA-Z0-9_]+)\s*:\s*([^;}\s]+)", m.group(1)):
            out[k.lower()] = v.strip()
    for k, v in ROOT_DEFAULT.items(): out.setdefault(k, v)
    return out

def _split_top(s):
    out, d, cur = [], 0, ""
    for ch in s:
        if ch == "(": d += 1
        elif ch == ")": d -= 1
        if ch == "," and d == 0: out.append(cur); cur = ""
        else: cur += ch
    if cur.strip(): out.append(cur)
    return out

def _js_to_json(t):
    t = re.sub(r"//[^\n]*", "", t)
    t = re.sub(r"([{,]\s*)([A-Za-z_$][\w$]*)\s*:", r'\1"\2":', t)
    t = re.sub(r"'((?:\\.|[^'\\])*)'", lambda m: '"%s"' % m.group(1).replace('"', '\\"'), t)
    t = re.sub(r",\s*([\]}])", r"\1", t)
    return json.loads(t)

def js_const(name, src=None):
    """const NAME=[…]／{…} → Python 结构（META 列表、METAD 释义、PAD/QUICK/F1 键位表都由此来）。"""
    src = page() if src is None else src
    m = re.search(r"(?:const|let|var)\s+%s\s*=\s*(\[.*?\]|\{.*?\})\s*;" % re.escape(name), src, re.S)
    if not m: return None
    try: return _js_to_json(m.group(1))
    except Exception: return None

# ---------------- 键位/面板登记表（取页面常量，缺则内置兜底） ----------------
_META_FB = ["agents", "use", "skill", "cmds", "intent", "index", "skills", "workspace", "debug", "mode",
            "dispatch", "sh", "edit", "view", "alias", "unalias", "hud", "deploy", "qq", "session", "grant",
            "perms", "tools", "api", "config", "web", "ext", "net", "tts", "learn", "file", "path", "dream",
            "image", "restart", "shutdown", "repair", "show", "help", "quit"]
_PAD_FB = [["1", ":cmds", "命令"], ["2", ":skills", "技能"], ["3", ":session list", "会话"],
           ["4", ":config status", "配置"], ["5", ":perms", "权限"], ["6", ":hud", "HUD"],
           ["7", ":dream status", "做梦"], ["8", ":tts status", "朗读"], ["9", ":qq status", "QQ"],
           ["*", ":help", "菜单"], ["0", ":agents", "agent"], ["#", ":mode", "模式"]]
_QUICK_FB = [["速查", ":help"], ["命令表", ":cmds"], ["技能", ":skills"], ["派发", ":dispatch "],
             ["会话拓扑", ":session overview"], ["配置", ":config status"], ["权限", ":perms"],
             ["任务总览", ":plan ls"], ["做梦", ":dream status"], ["QQ", ":qq status"], ["朗读", ":tts "],
             ["模式", ":mode "]]
_F1_FB = [["技能与派发", [["#menu_skill", "托管技能"], ["#menu_skill_index", "SKILL.md 索引"],
                          [":dispatch ", "技能真派发"], ["path:skill", "按路径加入"]]],
          ["文件·索引·工作区", [["#copy_log", "复制输出"], ["#detail_win", "详细细节"],
                                ["#menu_files", "文件索引"], ["#menu_ws", "工作区切换"],
                                ["#editor", "编辑器"], [" :plan ls", "计划任务"]]],
          ["配置·权限·工具", [["#config", "图形化配置"], ["#menu_perms", "权限与工具"], [":grant ", "授予权限"],
                              [":config status", "配置状态"], [":perms", "权限总览"], [":tools", "工具清单"]]],
          ["会话与数据流", [["#menu_mode", "界面模式"], [":agents", "选择 agent"], [":session new ", "新建会话"],
                            [":session list", "会话清单"], [":session overview", "会话拓扑"],
                            [":session conflicts", "仅看冲突"]]],
          ["系统", [["#menu_sys", "系统 shell"], [":cmds", "命令总表"], [":deploy ", "部署"],
                    [":api formats", "格式 API"], [":dream run", "做梦整理"], [":dream status", "做梦状态"],
                    [":repair list", "修复待批"], [":tts status", "朗读状态"], [":restart", "重启 SMS"]]],
          ["QQ 推送", [["#menu_qq", "QQ 状态"], [":qq bind", "扫码绑定"], [":qq resume", "续绑"],
                       [":qq check", "链路自检"], [":qq test", "真发测试"], [":qq on", "开关＝开"],
                       [":qq off", "开关＝关"], [":qq flush", "补发积压"], [":qq listen", "入站监听"]]]]
def keys():
    """(META, METAD, PAD, QUICK, F1)——每次现取页面，取不到用兜底；网页端为唯一口径。"""
    src = page()
    return (js_const("META", src) or _META_FB, js_const("METAD", src) or {},
            js_const("PAD", src) or _PAD_FB, js_const("QUICK", src) or _QUICK_FB,
            js_const("F1", src) or _F1_FB)

# 抽屉面板登记表（网页端 act() 的 #menu_* → (标题, 数据源)）；@ 前缀＝机身动作而非面板
DRAWERS = {"#menu_skill": ("SKILL.md 技能索引", "skills"), "#menu_skill_index": ("SKILL.md 技能索引", "skills"),
           "#menu_files": ("文件索引 · 编辑器", "files"), "#editor": ("编辑器 / 查看器", "files"),
           "#menu_ws": ("工作区切换", "ws"), "#config": ("图形化配置", "config"),
           "#menu_perms": ("权限 · 工具 · HUD", "perms"), "#menu_mode": ("界面模式（查看/对话/直通）", "mode"),
           "#menu_sys": ("系统 shell 联动", "sys"), "#menu_qq": ("QQ 推送 · 入站监听", "qq"),
           "#detail_win": ("详细细节（长输出留档）", "detail"), "#tasks": ("任务总览", "tasks"),
           "#plans": ("计划任务", "plans"), "#chains": ("十二链", "chains"), "#bus": ("跨会话明细", "bus")}

# ---------------- 网页端 CSS → QSS（渐变/圆角/描边对齐，阴影以描边近似） ----------------
def grad(css):
    """linear-gradient(180deg,a,b 46%,c 54%,d) → qlineargradient（180deg＝自上而下）。"""
    m = re.search(r"linear-gradient\(\s*(\d+)deg\s*,(.*)\)", css, re.S)
    if not m: return css
    ang = int(m.group(1)) % 360
    x2, y2 = (1, 0) if ang in (90, 270) else (0, 1)
    stops = []
    for i, part in enumerate(_split_top(m.group(2))):
        mm = re.match(r"\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)|[a-z]+)\s*([\d.]+)?%?\s*$", part)
        if not mm: return css
        pos = mm.group(2)
        pos = (0.0 if i == 0 else 1.0) if pos is None else round(float(pos) / 100.0, 3)
        stops.append("stop:%.3f %s" % (pos, mm.group(1)))
    return "qlineargradient(x1:0,y1:0,x2:%d,y2:%d,%s)" % (x2, y2, ",".join(stops))

def qss(v=None):
    """传真机机身样式表（v＝网页端 :root 变量；缺省现取页面）。objectName 对位：
    chassis 机身 / zone 功能区 / grp·dial 分组 / lcd 屏 / led 灯条 / tray 口腔 / roll 米纸卷 /
    feeder·cmd 进纸器 / drawer 抽屉 / k·kacc·kwarn·kstop·kgo·ksm 实体键五态 /
    blade·bladeTag 裁纸刀（t6·[st=…] 五态刀条）/ einkzone·eink 墨水屏面板（t10·实色无动效）/
    split·psplit 分屏（批41·左右主分屏＋右栏三格＝常驻 C 墨水屏／D 预览／E 终端）/ previewzone·preview·lnr 预览/
    einkzone[resident="1"]·einkStat 常驻墨水屏与墨水小标（批41 收尾·底部条带的迁移目的地）/
    mouth·tear[st=print/advance/tear/jam]＋rollTag 走纸队列六态（与 blade 同谱·实色无动效）/
    termzone·term·termIn 内嵌终端（QProcess·无控制台窗口）/
    cmd[crt="1"] 送稿口 CRT 绿字黑底（t8·扫描线·余辉·块光标由 shell_qt.Input 逐帧绘，QSS 只管实色底）。"""
    from string import Template
    v = v or css_vars()
    C = lambda k: v.get(k, ROOT_DEFAULT[k])
    G = grad
    d = dict(
        chassis=G("linear-gradient(180deg,#f7fafd 0%,#dde6ef 42%,#b7c3d2 52%,#e8eff6 100%)"),
        zone=G("linear-gradient(180deg,#e9eff6,#c3cedb 55%,#dfe7ef)"),
        grp=G("linear-gradient(180deg,#e3ebf3,#c0cbda 60%,#d9e2eb)"),
        dial=G("linear-gradient(180deg,#dfe7ef,#b9c5d4 55%,#d5dee7)"),
        drawer=G("linear-gradient(180deg,#eef3f8,#cfd9e4 60%,#e2eaf2)"),
        dark=G("linear-gradient(180deg,#2b3542,#1b222c)"),
        lcd=G("linear-gradient(180deg,#062028,#04161b 60%,#02090c)"),
        led=G("linear-gradient(180deg,#2a333f,#1a222c)"),
        tray=G("linear-gradient(180deg,#3a4553,#232c36 55%,#161d25)"),
        kn=G("linear-gradient(180deg,#fff,#e2eaf2 46%,#c2cedb 54%,#eef3f8)"),
        kh=G("linear-gradient(180deg,#fff,#eaf1f7 46%,#cdd8e4 54%,#f3f7fb)"),
        kp=G("linear-gradient(180deg,#eef3f8,#d3deea 46%,#bcc8d6 54%,#e6eef5)"),
        accn=G("linear-gradient(180deg,#e9fbff,#a9e6f5 46%,#6fc4dc 54%,#d6f4fb)"),
        accp=G("linear-gradient(180deg,#cfeef6,#8fd4e6 46%,#5cb2cb 54%,#c4ecf5)"),
        warnn=G("linear-gradient(180deg,#fff6df,#ffd89a 46%,#e5b463 54%,#fff0d2)"),
        stopn=G("linear-gradient(180deg,#ff8b8b,#e03a3a 46%,#b32020 54%,#f06b6b)"),
        gon=G("linear-gradient(180deg,#c9ffdc,#6ee29a 46%,#37b06c 54%,#b6f5cd)"),
        edge=C("edge"), lcdfg=C("lcdfg"), cyan=C("cyan"), amber=C("amber"),
        paper=C("paper"), ink=C("ink"), red=C("red"), grn=C("grn"),
        crtf=C("crtf"), crtb=C("crtb"), crtdim=C("crtdim"), crtgl=C("crtgl"),
        blade=C("blade"), einkb=C("einkb"), einkf=C("einkf"), einkd=C("einkd"),
    )
    return Template("""
QWidget#chassis{background:${chassis};border:1px solid ${edge};border-radius:14px}
QFrame#aside{background:transparent;border:none}
QLabel{background:transparent}
QFrame#ctlzone{background:${grp};border:1px solid ${edge};border-radius:12px}
QFrame#mouth[st="feed"],QFrame#tear[st="feed"]{background:${amber};border:1px solid #8a6a2a;border-radius:6px}
QFrame#mouth[st="print"],QFrame#tear[st="print"]{background:${paper};border:1px solid #a9b6c4;border-radius:6px}
QFrame#mouth[st="advance"],QFrame#tear[st="advance"]{background:${grn};border:1px solid #1d6b41;border-radius:6px}
QFrame#mouth[st="tear"],QFrame#tear[st="tear"]{background:${blade};border:1px solid #5b697a;border-radius:6px}
QFrame#mouth[st="jam"],QFrame#tear[st="jam"]{background:${red};border:1px solid #7c1414;border-radius:6px}
QDialog#palette{background:${drawer}}
QListWidget#palList{background:rgba(255,255,255,.86);color:${ink};border:1px solid #a9b6c4;
 border-radius:6px;font-size:13px;padding:4px;outline:none}
QListWidget#palList::item:selected{background:${cyan};color:#06202a}
QLineEdit{background:#ffffff;color:${ink};border:1px solid #a9b6c4;border-radius:6px;padding:5px 7px;font-size:13px}
QLineEdit:focus{border:1px solid ${cyan}}
QLabel#banner{color:#3c4a58;font-size:11px}
QFrame#zone{background:${zone};border:1px solid ${edge};border-radius:12px}
QFrame#grp{background:${grp};border:1px solid ${edge};border-radius:9px}
QFrame#dial{background:${dial};border:1px solid ${edge};border-radius:12px}
QLabel#ztitle{color:#3c4a58;font-size:11px;font-weight:bold;letter-spacing:2px}
QLabel#zhint,QLabel#hint{color:#6b7a89;font-size:10px}
QLabel#dialNote,QLabel#ledLbl,QLabel#quickLbl{color:#4c5a68;font-size:11px}
QFrame#feeder{background:${dark};border:1px solid #0a0f14;border-radius:10px}
QPlainTextEdit#cmd{background:#08131a;color:${lcdfg};border:1px solid #2c4a56;border-radius:7px;
 padding:7px 9px;font-size:13px}
QPlainTextEdit#cmd:focus{border:1px solid ${cyan}}
QPlainTextEdit#cmd[crt="1"]{background:${crtb};color:${crtf};border:1px solid ${crtdim};
 border-radius:2px;font-weight:bold}
QPlainTextEdit#cmd[crt="1"]:focus{border:1px solid ${crtf}}
QFrame#blade{background:${dark};border:1px solid #10161d;border-radius:3px}
QFrame#blade[st="feed"]{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 ${blade},stop:1 ${dark})}
QFrame#blade[st="clamp"]{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 ${edge},stop:1 ${dark})}
QFrame#blade[st="cut"]{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #ffffff,stop:.45 ${blade},stop:1 ${edge})}
QFrame#blade[st="drop"]{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 ${grn},stop:1 ${dark})}
QLabel#bladeTag{color:#4c5a68;font-size:11px;letter-spacing:1px}
QLabel#bladeTag[st="cut"]{color:${red};font-weight:bold}
QLabel#bladeTag[st="drop"]{color:#1d6b41;font-weight:bold}
QFrame#einkzone{background:${einkb};border:1px solid #b9bfba;border-radius:4px}
QFrame#einkzone[resident="1"]{background:${einkb};border:2px solid #8f979a;border-radius:4px}
QLabel#einkStat{color:#2f3639;background:#e2e6e2;border:1px solid #c4c9c4;border-radius:2px;
 padding:2px 6px;font-size:11px;letter-spacing:.4px}
QLabel#rollTag{color:#4c5a68;font-size:11px;letter-spacing:1px}
QLabel#rollTag[st="print"]{color:${ink};font-weight:bold}
QLabel#rollTag[st="advance"]{color:#1d6b41;font-weight:bold}
QLabel#rollTag[st="jam"]{color:${red};font-weight:bold}
QTextBrowser#eink{background:${einkb};color:${einkf};border:1px solid #c4c9c4;border-radius:2px;
 padding:6px 8px;font-size:12px}
QFrame#lcd{background:${lcd};border:3px solid #7d8b9a;border-radius:9px}
QLabel#lcdKey{color:#7fb9c4;font-size:12px}QLabel#lcdVal{color:#ffffff;font-weight:bold;font-size:12px}
QLabel#lcdWarn{color:${amber};font-size:12px;font-weight:bold}QLabel#lcdErr{color:#ff8a8a;font-size:12px}
QFrame#led{background:${led};border:1px solid #141a21;border-radius:9px}
QFrame#tray{background:${tray};border:1px solid #10161d;border-radius:10px}
QTextBrowser#roll{background:${paper};color:${ink};border:0;border-radius:3px;padding:10px 12px;font-size:13px}
QFrame#mouth,QFrame#tear{background:${dark};border:1px solid #10161d;border-radius:6px}
QPushButton{color:#16202b;border:1px solid #46525f;border-radius:9px;padding:6px 10px;min-width:44px;
 font-size:12px;letter-spacing:.5px;background:${kn}}
QPushButton:hover{background:${kh}}QPushButton:pressed{background:${kp}}
QPushButton[tone="acc"]{color:#062a33;border-color:#3d7c8c;background:${accn}}
QPushButton[tone="acc"]:pressed{background:${accp}}
QPushButton[tone="stop"]:pressed,QPushButton[tone="go"]:pressed,QPushButton[tone="warn"]:pressed{opacity:1}
QPushButton[tone="warn"]{color:#3a2200;border-color:#8a6a2a;background:${warnn}}
QPushButton[tone="stop"]{color:#ffffff;border-color:#7c1414;background:${stopn}}
QPushButton[tone="go"]{color:#04240f;border-color:#1d6b41;background:${gon}}
QPushButton[sm="1"]{min-width:0;padding:3px 7px;font-size:11px;border-radius:7px}
QPushButton:disabled{color:#77828e;background:${kp};border-color:#8b98a7}
QSplitter#split,QSplitter#psplit{background:transparent;border:none}
QSplitter#split::handle:horizontal{background:${edge};width:6px;border-radius:3px;margin:2px}
QSplitter#psplit::handle:vertical{background:${edge};height:6px;border-radius:3px;margin:2px}
QFrame#previewzone{background:${zone};border:1px solid ${edge};border-radius:12px}
QFrame#termzone{background:${zone};border:1px solid ${edge};border-radius:12px}
QPlainTextEdit#preview{background:${paper};color:${ink};border:1px solid #a9b6c4;border-radius:6px;
 padding:2px;font-size:12px}
QLabel#lnr{background:${drawer};color:#4c5a68;border-right:1px solid #a9b6c4;font-size:11px}
QLineEdit#pvOpen{background:#ffffff;color:${ink};border:1px solid #a9b6c4;border-radius:6px;padding:4px 7px;font-size:12px}
QPlainTextEdit#term{background:${crtb};color:${crtf};border:1px solid ${crtdim};border-radius:6px;
 padding:4px;font-size:12px}
QLineEdit#termIn{background:${crtb};color:${crtf};border:1px solid ${crtdim};border-radius:6px;
 padding:5px 7px;font-size:12px;selection-background-color:${crtgl}}
QLineEdit#termIn:focus{border:1px solid ${crtf}}
QFrame#drawer{background:${drawer};border:1px solid ${edge};border-radius:12px}
QTextBrowser#drawerBody{background:rgba(255,255,255,.72);color:${ink};border:1px solid #a9b6c4;
 border-radius:6px;font-size:12px;padding:6px}
QLabel#statusbar{color:#2b3846;font-size:11px;background:${zone};border:1px solid ${edge};
 border-radius:7px;padding:3px 8px}
""").substitute(**d)

# ---------------- 数据桥：网页端同一套 getter/poster，进程内直调（无 HTTP·无 token·不开端口） ----------------
_DROP = {"token", "token_prefix", "token_full", "fingerprint", "gfpr", "tok"}
_cache = {}

def _ws():
    if "mod" not in _cache:
        try:
            import web_shell
            _cache["mod"] = web_shell
        except Exception as e:
            _cache["mod"] = None; _cache["err"] = "%s: %s" % (type(e).__name__, str(e)[:140])
    return _cache["mod"]

def leaked(x):
    """递归核对返回结构中是否仍带密钥面字段（token/指纹）——GUI 免密钥的硬判据，自检用。"""
    if isinstance(x, dict):
        for k, v in x.items():
            if str(k).lower() in _DROP: return str(k)
            r = leaked(v)
            if r: return r
    elif isinstance(x, (list, tuple)):
        for v in x:
            r = leaked(v)
            if r: return r
    return ""

def scrub(x):
    """递归剔除密钥面字段——GUI 无门禁，也就不呈现任何密钥/指纹。"""
    if isinstance(x, dict): return {k: scrub(v) for k, v in x.items() if str(k).lower() not in _DROP}
    if isinstance(x, (list, tuple)): return [scrub(v) for v in x]
    return x

_GETS = {"/api/commands": "g_commands", "/api/sessions": "g_sessions", "/api/tasks": "g_tasks",
         "/api/plans": "g_plans", "/api/chains": "g_chains", "/api/perms": "g_perms", "/api/hud": "g_hud",
         "/api/qq": "g_qq", "/api/tts": "g_tts", "/api/skills": "g_skills", "/api/files": "g_files",
         "/api/file": "g_file", "/api/detail": "g_detail", "/api/ask": "g_ask"}
_POSTS = {"/api/stop": "p_stop", "/api/resume": "p_resume", "/api/task/status": "p_task_status",
          "/api/grant": "p_grant", "/api/tts/say": "p_tts_say", "/api/plan/add": "p_plan_add",
          "/api/file/save": "p_file_save", "/api/qq/test": "p_qq_test", "/api/qq/img": "p_qq_img"}

def api(path, body=None, query=None):
    """与网页端逐字相同的 /api/*：GET＝面板 getter（scrub 后返回·query＝网页端同名 ?k=v 参数），
    POST＝poster（权限门/高危 confirm 继承·一字未动）。/api/chat 不经此路——GUI 走 shell_core.handle
    线程流式（路由口径一致）。批41 预览件要的 /api/file?path=… 与 /api/files?ws=… 即走此 query
    （进程内直调，绝不新建 HTTP、绝不读 token）。"""
    ws = _ws()
    if ws is None: return {"err": "面板数据件不可用：" + _cache.get("err", "?")}
    p = (path or "").split("?")[0]
    q = dict(query or {})
    if "?" in (path or ""):
        for kv in (path.split("?", 1)[1] or "").split("&"):
            if "=" in kv:
                k, v = kv.split("=", 1); q[k] = v
    try:
        if body is None:
            if p == "/api/info":
                import settings, model_meta
                st = dict(settings.status()); st["model_meta"]["models"] = (model_meta.load().get("models") or {})
                return scrub(st)
            fn = getattr(ws, _GETS[p], None) if p in _GETS else None
            if fn is None: return {"err": "GUI 无此面板：" + p}
            return scrub(fn(q))
        if p.startswith("/api/plan/"):
            return scrub(ws.p_plan(p.rsplit("/", 1)[-1], dict(body or {})))
        fn = getattr(ws, _POSTS[p], None) if p in _POSTS else None
        if fn is None: return {"err": "GUI 不代办此路（免密钥面）：" + p}
        return scrub(fn(dict(body or {})))
    except Exception as e:
        return {"err": "%s: %s" % (type(e).__name__, str(e)[:180])}

# ---------------- 出纸口渲染（与网页端 print()/jam() 同构：徽标＋正文·虚线分行） ----------------
WHO = {"me": ("#2b4a63", "#e3edf6", "#9db8cd"), "sys": ("#5a4a1c", "#f6efd6", "#d8c98d"),
       "agent": ("#6b6152", "#ffffff", "#c9c0ae"), "err": ("#8a1f1f", "#ffe3e3", "#e0a0a0"),
       "ask": ("#3a2a63", "#efe6ff", "#b8a5d8")}
def _esc(t):
    return (str(t if t is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

def line_html(who, text, cls="", body_html=None):
    fg, bg, bd = WHO.get(cls) or WHO["agent"]
    body = body_html if body_html is not None else _esc(text).replace("\n", "<br>")
    return ('<div style="margin:0 0 7px;padding-bottom:6px;border-bottom:1px dashed rgba(0,0,0,.18)">'
            '<span style="font-size:10px;letter-spacing:1px;color:%s;border:1px solid %s;background:%s;'
            'border-radius:3px;padding:0 4px">%s</span><div style="white-space:pre-wrap;word-break:break-word">'
            '%s</div></div>' % (fg, bd, bg, _esc(who), body))

def jam_html(msg):
    """卡纸 JAM＝网页端 .jam 红条：面板/送稿出错显式打纸，不静默。"""
    return ('<div style="margin:0 0 8px;padding:6px 9px;border-radius:5px;background:#c81e1e;color:#ffffff;'
            'font-size:12px;letter-spacing:.5px"><b>卡纸 JAM</b> %s</div>' % _esc(msg))

# ---------------- 抽屉面板（表结构＝网页端 th/td 同口径） ----------------
def table(cols, rows, title=""):
    hd = lambda c: (c.partition(":")[0], c.partition(":")[2] or c.partition(":")[0])
    head = "".join("<th>%s</th>" % _esc(hd(c)[1]) for c in cols)
    body = []
    for r in rows or []:
        tds = []
        for c in cols:
            v = r.get(hd(c)[0]) if isinstance(r, dict) else ""
            if isinstance(v, (dict, list)): v = json.dumps(v, ensure_ascii=False)[:120]
            tds.append("<td>%s</td>" % _esc("" if v is None else str(v))[:240])
        body.append("<tr>%s</tr>" % "".join(tds))
    cap = '<div style="font-weight:bold;margin:0 0 6px">%s</div>' % _esc(title) if title else ""
    return cap + '<table style="border-collapse:collapse;width:100%%;font-size:12px"><tr>%s</tr>%s</table>' % (
        head, "".join(body) or '<tr><td style="color:#6b7a89">（空）</td></tr>')

def kv_html(d, title=""):
    cap = '<div style="font-weight:bold;margin:0 0 6px">%s</div>' % _esc(title) if title else ""
    rows = "".join('<div style="margin:3px 0;font-size:12px"><span style="color:#33414f">%s</span> %s</div>'
                   % (_esc(k), _esc(json.dumps(v, ensure_ascii=False)[:200] if isinstance(v, (dict, list)) else v))
                   for k, v in (d or {}).items())
    return cap + (rows or "（空）")

def panel_html(name, data):
    """抽屉正文：按数据源出表/清单（字段＝web_shell getter 返回，网页端一致）。"""
    d = data if isinstance(data, dict) else {}
    if d.get("err"): return jam_html("面板 %s：%s" % (name, d["err"]))
    g = lambda k: d.get(k) or []
    M = {"tasks": lambda: ('<div style="margin:0 0 6px"><b>%s</b> · %s/%s · 未完成 %s · 预计 %s<br>'
                           '<span style="color:#4c5a68">%s</span></div>' % (_esc(d.get("tid") or "-"),
                            d.get("done", 0), d.get("total", 0), d.get("unfinished", 0), _esc(d.get("eta") or "-"),
                            _esc(str(d.get("intent") or "")[:120]))) +
                   table(["id:行", "goal:目标", "status:状态", "lane:道", "skill:技能"], g("rows")),
               "plans": lambda: table(["id", "title:标题", "at:下次", "spec:排程", "cmd:指令", "status:状态"], g("plans")),
               "chains": lambda: table(["chain:链", "frags:碎片", "freq:频次", "last:最近"], g("chains")),
               "sessions": lambda: table(["session:会话", "state:状态", "conv", "last_active:最近",
                                          "unfinished:未完成", "current:当前"], g("sessions")),
               "skills": lambda: table(["id", "name:名称", "desc:简介", "kind:种类", "trust:信任"], g("skills")),
               "commands": lambda: table(["name:指令", "desc:说明"], g("commands")),
               "files": lambda: table(["name:名称", "type:型", "size:字节", "path:路径"], g("files")),
               "file": lambda: '<pre>%s</pre>' % _esc(str(d.get("content") or "")[:20000]),
               "detail": lambda: '<pre>%s</pre>' % _esc(str(d.get("text") or "（尚无长输出留档）")[:40000]),
               "bus": lambda: '<pre>%s</pre>' % _esc("\n".join(str(x) for x in g("lines")) or "（暂无）"),
               "perms": lambda: (table(["key:权限键", "on:开", "source:来源", "desc:说明"], g("perms")) +
                                 table(["tool:工具", "enabled:启用"], g("tools")) +
                                 kv_html(d.get("solo") or {}, "SOLO 自审")),
               "qq": lambda: kv_html(d, "QQ 推送"), "tts": lambda: kv_html(d, "朗读"),
               "hud": lambda: kv_html(d, "HUD 常显"), "mode": lambda: kv_html(d, "界面模式"),
               "sys": lambda: kv_html(d, "系统 shell"),
               "ws": lambda: kv_html({"current": d.get("current"), "root": d.get("ws"),
                                      "list": d.get("workspaces") or []}, "工作区"),
               "config": lambda: "".join(kv_html(d.get(k) or {}, k) for k in
                                         ("llm_gateway", "shell", "web_shell", "chains", "solo", "tts") if k in d) or kv_html(d, "配置")}
    return M.get(name, lambda: kv_html(d, name))()

# ---------------- 机身构件（Qt 侧对位网页端 chassis/zones/feeder/tray/panel/dial/drawer） ----------------
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                             QPushButton, QSplitter, QTextBrowser, QVBoxLayout, QWidget)
MONO, UI = "Consolas", "Segoe UI"
def _f(px, mono=True, bold=False):
    f = QFont(MONO if mono else UI); f.setPixelSize(px); f.setBold(bold); return f
def _row(spacing=6):
    r = QHBoxLayout(); r.setContentsMargins(0, 0, 0, 0); r.setSpacing(spacing); return r
def _zone(title, hint=""):
    box = QFrame(); box.setObjectName("zone"); v = QVBoxLayout(box)
    v.setContentsMargins(11, 9, 11, 11); v.setSpacing(5)
    t = QLabel(title); t.setObjectName("ztitle"); t.setFont(_f(11, False, True)); v.addWidget(t)
    if hint:
        h = QLabel(hint); h.setObjectName("zhint"); h.setFont(_f(10, False)); v.addWidget(h)
    return box, v
def key(text, slot=None, style="", small=True, tip=""):
    """实体键：style＝""|acc|warn|stop|go（QSS 属性 tone），small＝网页端 .key.sm（属性 sm）——
    objectName 一律 k，由 QSS 的 [tone=…]/[sm="1"] 选择器取色，五态×两尺寸＝网页端同族按键。"""
    b = QPushButton(text); b.setObjectName("k")
    b.setProperty("tone", style or ""); b.setProperty("sm", "1" if small else "")
    b.setFont(_f(11 if small else 13, False)); b.setToolTip(tip or text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet("QPushButton{padding:%s;font-size:%dpx;border-radius:%dpx;min-width:%s}" %
                    ("3px 7px" if small else "6px 10px", 11 if small else 12, 7 if small else 9,
                     "0" if small else "44px"))
    slot and b.clicked.connect(slot); return b

def build(win, ent):
    """装机身（批41 上送稿口＋下左右分屏）：返回 {id:widget}——批38/39/40 键面逐字保留（roll/mouth/tear/
    blade/blade_tag/blade_pos/banner/lcd_*/led_*/ctlzone/ctlzone_btn/meta_grp/f1_grp/dial_keys/cmd/drawer/
    dtitle/dbody/btn_all/btn_speak/btn_stop/btn_go/eink/einkzone/keys），批41 增分屏与两件键：
    split（QSplitter 主分屏）/psplit（右栏上下分屏）/previewzone·preview·pv_open·pv_fold·pv_stat/
    termzone·term·term_in·t_run·t_fold·t_paper·t_clear·t_stat；批41 收尾再增 eink_stat 墨水小标＋roll_tag 走纸标签（走纸队列＝fax.roll_next 六态族·与 CUT 同谱·绘制与 QTimer 接线在 shell_qt.py）。
    上＝B 送稿口（CRT 输入 ent＋送稿键＋常用拨号·常驻第一位）
    下＝左右分屏：左纸卷 A（正文＋状态行 LCD 六格/LED 七灯＋mouth/tear/blade＋动作条）
                右栏 psplit 竖列三格＝C 墨水屏（常驻第一格·Ctrl+I 只聚焦永不 hide）→D 预览（代码/文件＋行号栏）
                →E 终端（内嵌面板）·三格常驻不可折叠（setChildrenCollapsible(False)）·可切分·Ctrl+V 五态轮转
    下＝左右分屏 QSplitter#split：左＝A 纸卷区、右＝aside 竖列（上＝psplit 三格 C／D／E 常驻，下＝按需层）；
    按需层＝控制面板 ctlzone（META／F1／拨号盘）＋抽屉——一律装配即 hide（Ctrl+M），
    顶部名牌横条与原生菜单栏仍不装（零顶栏＝命令面板 Ctrl+K＋右键菜单）。
    预览/终端控件类由壳侧注入（win.PREVIEW_CLS／win.TERM_CLS／win.TERM_IN_CLS），缺类回落 QPlainTextEdit／
    QLineEdit——装配只此一处，版式真源不落到壳文件。1280×720 可用：三件最小宽 430/300/300，
    setChildrenCollapsible(False) 防拖没。"""
    w = {}
    central = QWidget(); central.setObjectName("chassis"); win.setCentralWidget(central)
    root = QVBoxLayout(central); root.setContentsMargins(10, 8, 10, 8); root.setSpacing(7)

    tray, tv = _zone("② 纸卷区 PAPER ROLL · A（左）", "出纸正文 · 状态行 LCD/LED · 裁纸刀 · 分屏右＝预览 D／终端 E")
    hr = _row(9); tv.addLayout(hr)
    w["banner"] = QLabel("待机"); w["banner"].setObjectName("banner"); w["banner"].setFont(_f(11, False))
    hr.addWidget(w["banner"]); hr.addStretch(1)
    w["ctlzone_btn"] = key("▦ 控制面板 Ctrl+M", lambda: win.fax("ctl"), small=True,
                           tip="META 键阵／F1 六组／拨号盘＝按需展开（默认收起让位分屏骨架）")
    hr.addWidget(w["ctlzone_btn"])
    hr.addWidget(key("⌘ 命令面板 Ctrl+K", lambda: win.fax("palette"), small=True, style="acc",
                     tip="原顶栏菜单全量条目在此过滤唤出（出口同实体键）"))
    lcd = QFrame(); lcd.setObjectName("lcd"); lg = QGridLayout(lcd)
    lg.setContentsMargins(9, 5, 9, 5); lg.setHorizontalSpacing(8); lg.setVerticalSpacing(1)
    for i, k in enumerate(("会话", "模式", "网关", "线路", "任务总览", "状态")):
        a = QLabel(k); a.setObjectName("lcdKey"); a.setFont(_f(11)); r, c = divmod(i, 3)
        b = QLabel("-"); b.setObjectName("lcdVal"); b.setFont(_f(11, True, True))
        lg.addWidget(a, r, c * 2); lg.addWidget(b, r, c * 2 + 1)
        w["lcd_" + k] = b
    tv.addWidget(lcd)
    led = QFrame(); led.setObjectName("led"); lr = _row(9); lr.setContentsMargins(8, 5, 8, 5); led.setLayout(lr)
    for nm in ("线路", "QQ", "朗读", "做梦", "计划", "裁纸", "对外"):
        lab = QLabel("● " + nm); lab.setObjectName("ledLbl"); lab.setFont(_f(11, False)); lr.addWidget(lab)
        w["led_" + nm] = lab
    lr.addStretch(1); tv.addWidget(led)
    mouth = QFrame(); mouth.setObjectName("mouth"); mouth.setProperty("st", "idle"); mouth.setFixedHeight(12)
    w["mouth"] = mouth; tv.addWidget(mouth)
    w["roll"] = QTextBrowser(); w["roll"].setObjectName("roll"); w["roll"].setFont(_f(13)); tv.addWidget(w["roll"], 1)
    tear = QFrame(); tear.setObjectName("tear"); tear.setProperty("st", "idle"); tear.setFixedHeight(10)
    w["tear"] = tear; tv.addWidget(tear)
    blade = QFrame(); blade.setObjectName("blade"); blade.setFixedHeight(9)
    blade.setProperty("st", "idle"); w["blade"] = blade; tv.addWidget(blade)
    bt = _row(8); tv.addLayout(bt)
    w["blade_tag"] = QLabel(cut_label("idle")); w["blade_tag"].setObjectName("bladeTag")
    w["blade_tag"].setFont(_f(11, False)); bt.addWidget(w["blade_tag"])
    w["blade_pos"] = QLabel("行程 0%"); w["blade_pos"].setObjectName("hint")
    w["blade_pos"].setFont(_f(10, False)); bt.addWidget(w["blade_pos"])
    w["roll_tag"] = QLabel(roll_label("idle")); w["roll_tag"].setObjectName("rollTag")
    w["roll_tag"].setFont(_f(11, False)); bt.addWidget(w["roll_tag"]); bt.addStretch(1)
    br = _row(); tv.addLayout(br)
    for lab, fn in (("⧉ 复制输出", "copyAll"), ("⤓ 下载 .txt", "dl"), ("✂ 撕纸清屏", "tear"),
                    ("✂ 裁纸 CUT", "cut"), ("▤ 墨水屏 E-INK", "eink"), ("⎈ 走纸 ROLL", "roll"),
                    ("⌘ 命令面板", "palette")):
        br.addWidget(key(lab, lambda _f_=fn: win.fax(_f_), tip="网页端同名动作·本机操作"))
    h = QLabel("右键＝机身菜单 · Ctrl+Shift+C＝复制全部 · Ctrl+V＝五视图轮转"); h.setObjectName("hint")
    h.setFont(_f(11, False)); br.addWidget(h); br.addStretch(1)
    tray.setMinimumWidth(430); w["tray"] = tray   # 批41：纸卷 A 进主分屏左格（不再直挂 root）

    ctl = QFrame(); ctl.setObjectName("ctlzone"); w["ctlzone"] = ctl
    cv = QVBoxLayout(ctl); cv.setContentsMargins(11, 9, 11, 9); cv.setSpacing(6)
    ct = QLabel("控制面板 CONTROL（按需 · Ctrl+M 收起/展开 · 版式真源＝web_page.html）")
    ct.setObjectName("ztitle"); ct.setFont(_f(11, False, True)); cv.addWidget(ct)
    META_, METAD_, PAD_, QUICK_, F1_ = keys()
    g = QFrame(); g.setObjectName("grp"); gv = QVBoxLayout(g); gv.setContentsMargins(8, 6, 8, 8); gv.setSpacing(4)
    tt = QLabel("META 元指令 %d 键 · 点击填入送稿口" % len(META_)); tt.setObjectName("zhint")
    tt.setFont(_f(10, False)); gv.addWidget(tt)
    grid = QGridLayout(); grid.setHorizontalSpacing(4); grid.setVerticalSpacing(4); gv.addLayout(grid)
    for i, m in enumerate(META_):
        b = key(":" + m, lambda _m=m: win.feed(":" + _m + " "), small=True, tip=":%s — %s" % (m, METAD_.get(m, "")))
        b.setMinimumWidth(0); grid.addWidget(b, i // 8, i % 8)
    w["meta_grp"] = g; cv.addWidget(g)
    f1w = QFrame(); f1w.setObjectName("grp"); f1v = QVBoxLayout(f1w); f1v.setContentsMargins(8, 6, 8, 8); f1v.setSpacing(5)
    for grp, items in (F1_ or []):
        r = _row(5); f1v.addLayout(r)
        lab = QLabel(grp); lab.setObjectName("zhint"); lab.setFont(_f(10, False)); lab.setMinimumWidth(96)
        r.addWidget(lab)
        for cmd, name in items:
            r.addWidget(key(name, lambda _c=cmd: win.faxPick(_c), small=True, tip=str(cmd).strip()))
    w["f1_grp"] = f1w; cv.addWidget(f1w)
    dv = _row(12); cv.addLayout(dv)
    pg = QGridLayout(); pg.setHorizontalSpacing(6); pg.setVerticalSpacing(6); dv.addLayout(pg)
    w["dial_keys"] = []
    for i, (k, c, lab) in enumerate(PAD_):
        b = QPushButton("%s  %s" % (k, lab)); b.setObjectName("k"); b.setFont(_f(12, False, True))
        b.setMinimumSize(56, 30); b.setToolTip(c); b.clicked.connect(lambda _c=c: win.feed(_c))
        pg.addWidget(b, i // 4, i % 4); w["dial_keys"].append(b)
    note = QLabel("拨号盘＝快捷指令位（0 agent · * 菜单 · # 模式）"); note.setObjectName("dialNote")
    note.setFont(_f(11, False)); note.setWordWrap(True); note.setMaximumWidth(170); dv.addWidget(note)
    dv.addStretch(1)
    w["btn_all"] = key("↻ 巡检 ALL", lambda: win.fax("pollAll"), small=True); dv.addWidget(w["btn_all"])
    w["btn_speak"] = key("🔊 朗读末条", lambda: win.fax("speakLast"), small=True); dv.addWidget(w["btn_speak"])
    w["btn_stop"] = key("⏸ 停止", lambda: win.fax("doStop"), style="stop", small=False); dv.addWidget(w["btn_stop"])
    w["btn_go"] = key("▶ 继续", lambda: win.fax("doResume"), style="go", small=False); dv.addWidget(w["btn_go"])
    w["btn_stop"].hide(); w["btn_go"].hide(); ctl.hide()   # 批41：ctlzone 装配即 hide·排位在分屏之后

    feeder, zv = _zone("① 送稿口 DOC FEEDER · B（上·常驻第一位）", "话语 / :元指令 · Tab 补全 · ↑↓ 历史 · CRT 成像 · 送稿键 · 常用拨号")
    fr = _row(8); fr.addWidget(ent, 1)
    fr.addWidget(key("送稿 FEED", win.feedNow, style="acc", small=False)); zv.addLayout(fr)
    qh = _row(5); zv.addLayout(qh)
    ql = QLabel("常用拨号"); ql.setObjectName("quickLbl"); qh.addWidget(ql)
    for lab, c in QUICK_: qh.addWidget(key(lab, lambda _c=c: win.feed(_c), small=True, tip=str(c).strip()))
    qh.addStretch(1); feeder.setMinimumHeight(96); feeder.setMinimumWidth(320)
    root.addWidget(feeder)   # 批41：B 送稿口常驻第一位
    w["feeder"] = feeder

    # ---------------- 批41 右栏：预览 D（代码/文件＋行号栏）· 终端 E（内嵌面板）----------------
    # 控件类由壳侧注入（win.PREVIEW_CLS／win.TERM_CLS／win.TERM_IN_CLS），缺类回落基件＝装配只此一处；
    # 进程/取数一律在壳侧件内（本装配体不碰子进程面·门禁 assembly_no_process_face 扫此段）。
    pvz, pvv = _zone("③ 预览 PREVIEW · D（右上）· 行号栏自绘", "")
    pvz.setToolTip("数据一律进程内取数 /api/files · /api/file · /api/detail（无 HTTP·无 token）")
    pv_in = QLineEdit(); pv_in.setObjectName("pvOpen")
    pv_in.setPlaceholderText("路径 / 文件名 → Enter＝进程内取文预览（绝不新建 HTTP·绝不读 token）")
    pvv.addWidget(pv_in)
    pv = (getattr(win, "PREVIEW_CLS", None) or QPlainTextEdit)(win)
    pv.setObjectName("preview"); pv.setReadOnly(True); pv.setFont(_f(12)); pv.setMinimumWidth(220)
    pvz.setMinimumWidth(300)
    pv.setMinimumHeight(80); pvv.addWidget(pv, 1)
    pv_stat = QLabel("预览未取数（缺省＝/api/detail 长输出留档）"); pv_stat.setObjectName("hint")
    pv_stat.setFont(_f(10, False)); pvv.addWidget(pv_stat)
    pr1 = _row(8); pvv.addLayout(pr1)
    w["pv_fold"] = key("▣ 折叠预览", lambda: win.fax("pvFold"), small=True,
                       tip="右栏上下折叠：预览收起＝终端满幅（Ctrl+D 开合）")
    w["pv_src"] = key("↺ 重载当前源", lambda: win.fax("pvReload"), small=True,
                      tip="重走同一条 fax.api 取数路（不新建第二条路由）")
    pr1.addWidget(w["pv_fold"]); pr1.addWidget(w["pv_src"]); pr1.addStretch(1)
    w["previewzone"] = pvz; w["preview"] = pv; w["pv_open"] = pv_in; w["pv_stat"] = pv_stat

    tmz, tmv = _zone("④ 终端 TERMINAL · E（右下）· 无控制台窗口", "")
    tmz.setToolTip("随窗口 closeEvent 收净（不留孤儿）· `!` 与内置命令同 TUI · 路由仍 shell_core.handle")
    tm = (getattr(win, "TERM_CLS", None) or QPlainTextEdit)(win)
    tm.setObjectName("term"); tm.setReadOnly(True); tm.setFont(_f(12)); tm.setMinimumWidth(220)
    tm.setMinimumHeight(80); tmv.addWidget(tm, 1)
    pr2 = _row(6)
    ti = (getattr(win, "TERM_IN_CLS", None) or QLineEdit)(tmz)
    ti.setObjectName("termIn")
    ti.setPlaceholderText("$ 系统 shell 命令 · :元指令 / 话语＝同 TUI 路由（core.handle）· Enter 执行 · ↑↓ 历史")
    pr2.addWidget(ti, 1)
    w["t_run"] = key("▶ 执行", lambda: win.fax("termRun"), small=True, tip="回车同义：按路由口径执行一行")
    w["t_fold"] = key("▣ 折叠终端", lambda: win.fax("termFold"), small=True, tip="右栏上下折叠：终端收起＝预览满幅")
    w["t_paper"] = key("↥ 上纸卷", lambda: win.fax("termPaper"), small=True, tip="终端缓冲回灌纸卷 A（输出上纸面）")
    w["t_clear"] = key("✕ 清空", lambda: win.fax("termClear"), small=True, tip="清空终端缓冲（不动在跑进程）")
    for b in (w["t_run"], w["t_fold"], w["t_paper"], w["t_clear"]): pr2.addWidget(b)
    tmv.addLayout(pr2)
    t_stat = QLabel("终端待机（无在跑进程）"); t_stat.setObjectName("hint"); t_stat.setFont(_f(10, False))
    tmv.addWidget(t_stat)
    tmz.setMinimumWidth(300); w["termzone"] = tmz; w["term"] = tm; w["term_in"] = ti; w["t_stat"] = t_stat
    # ---- 墨水屏消息面板 C（批41 口径：常驻： psplit 第一格·psplit 依次 C→D→E·常驻不收起·Ctrl+I 聚焦） ----
    ez = QFrame(); ez.setObjectName("einkzone"); ez.setProperty("resident", "1"); w["einkzone"] = ez
    zv2 = QVBoxLayout(ez); zv2.setContentsMargins(12, 6, 12, 8); zv2.setSpacing(4)
    et = QLabel("▤ 墨水屏消息面板 · C（常驻右栏上格 · 只三段：会话信息／任务总览／后台任务 · 无动效 · Ctrl+I 聚焦）")
    et.setObjectName("ztitle"); et.setFont(_f(11, False, True)); zv2.addWidget(et)
    est = QLabel(""); est.setObjectName("einkStat"); est.setFont(_f(10, False))
    est.setTextFormat(Qt.TextFormat.PlainText); est.setWordWrap(True)
    zv2.addWidget(est); w["eink_stat"] = est          # 墨水小标＝原底部条带提示的迁移目的地
    w["eink"] = QTextBrowser(); w["eink"].setObjectName("eink"); w["eink"].setFont(_f(12, False))
    w["eink"].setMinimumHeight(118); zv2.addWidget(w["eink"])
    ez.setMinimumHeight(150)      # 常驻保底高度（批41 收尾：C 进 psplit 第一格·永不 hide·Ctrl+I 只聚焦）
    psplit = QSplitter(Qt.Orientation.Vertical); psplit.setObjectName("psplit")
    psplit.addWidget(ez); psplit.addWidget(pvz); psplit.addWidget(tmz)
    psplit.setChildrenCollapsible(False); psplit.setSizes([300, 420, 280])   # psplit＝三件 C 墨水屏／D 预览／E 终端
    # 批40 版式补齐：split 右格＝竖向容器 aside（QVBoxLayout）——上＝分屏三件 psplit（C 墨水屏／D 预览／E 终端），
    # 下＝按需层依次 ctlzone→抽屉（二者装配即 hide，不再直接挂 root）；
    # root 只留 送稿口＋分屏 两格＝上输入下左右分屏·无底部条带
    aside = QFrame(); aside.setObjectName("aside"); w["aside"] = aside
    av = QVBoxLayout(aside); av.setContentsMargins(0, 0, 0, 0); av.setSpacing(7)
    av.addWidget(psplit, 1)
    split = QSplitter(Qt.Orientation.Horizontal); split.setObjectName("split")
    split.addWidget(tray); split.addWidget(aside)
    split.setChildrenCollapsible(False); split.setStretchFactor(0, 3); split.setStretchFactor(1, 2)
    split.setSizes([760, 640])          # 1280×720：左≥430·右≥300×2 可用
    w["split"] = split; w["psplit"] = psplit; w["aside"] = aside
    root.addWidget(split, 1)
    av.addWidget(ctl)                   # 按需层①＝控制面板（装配即 hide·Ctrl+M）


    dr = QFrame(); dr.setObjectName("drawer"); w["drawer"] = dr; dvl = QVBoxLayout(dr)
    dvl.setContentsMargins(12, 9, 12, 11); dvl.setSpacing(6)
    dh = _row(8); dh.addStretch(1)
    dh.addWidget(key("✕ 合上", lambda: win.fax("closeDrawer"), small=True))
    w["dtitle"] = QLabel("面板"); w["dtitle"].setObjectName("ztitle"); w["dtitle"].setFont(_f(12, False, True))
    dvl.addLayout(dh); dvl.addWidget(w["dtitle"])
    w["dbody"] = QTextBrowser(); w["dbody"].setObjectName("drawerBody"); w["dbody"].setFont(_f(12))
    w["dbody"].setMinimumHeight(150); dvl.addWidget(w["dbody"])
    dr.hide(); av.addWidget(dr)
    w["keys"] = (META_, METAD_, PAD_, QUICK_, F1_)
    return w


# ---------------- 批41 预览件 D／终端件 E 的纯算式（真源单一：算式在此，壳只接绘制与状态） ----------------
FALLBACK_TEXT = ("（内置兜底预览·页面/面板取不到时的离仓样本）\n"
                 "  # sms-shell fax console mirror\n"
                 "  # 取数路径：/api/files → /api/file → /api/detail（进程内直调·无 HTTP·无 token）\n"
                 "  # 自检：python -B shell_qt.py --selftest（offscreen）\n")

def preview_text(data, name=""):
    """预览件取数收口（纯函数）：web_shell getter 返回 dict → 可预览文本＋行数＋是否兜底。
    取不到＝内置兜底（FALLBACK_TEXT），err 原样带回由壳侧在纸面打「卡纸」——不新建 HTTP、不读密钥。"""
    d = data if isinstance(data, dict) else {}
    err = str(d.get("err") or "")
    t = str(d.get("content") or d.get("text") or "")
    if not t.strip():
        files = d.get("files") or d.get("items") or []
        t = "\n".join("%-4s %10s  %s" % (x.get("type") or "file", x.get("size") or "-",
                                          x.get("path") or x.get("name") or "-")
                      for x in files[:400] if isinstance(x, dict))
    fb = not t.strip()
    if fb: t = FALLBACK_TEXT
    return {"text": t, "err": err, "name": str(name or d.get("path") or ""),
            "lines": t.count("\n") + 1, "fallback": fb}

TERM_PROMPT = "$ "

def term_line_kind(text):
    """终端缓冲行分类（纯算式）：命令回显＝sh、: 元指令＝meta、rc≠0/JAM/✗/Traceback＝err、其余＝out。"""
    t = str(text or "").strip()
    if not t: return "out"
    if t.startswith("$") or t.startswith("!"): return "sh"
    if t.startswith(":") or t.startswith("："): return "meta"
    if ("JAM" in t or t.startswith("✗") or t.startswith("⛔") or "Traceback" in t
            or re.search(r"\brc=[1-9]\d*\b", t)): return "err"
    return "out"

# ---------------- t6 裁纸刀（出纸末端·状态推进＋刀条视觉：QTimer 进程内走步·零新端口零新进程） ----------------
CUT_STEPS = (("idle", "裁纸待机 TRIM IDLE", ""),
             ("feed", "纸张送出 CUT FEED", "warn"),
             ("clamp", "压脚压纸 CLAMP", "warn"),
             ("cut", "刀刃下行 TRIM", "stop"),
             ("drop", "断纸落盘 DROP", "go"))
_IDS = [s[0] for s in CUT_STEPS]

def cut_next(state="idle"):
    """裁纸状态推进（纯函数）：idle→feed→clamp→cut→drop→idle；非法值当 idle 起步。"""
    i = _IDS.index(state) if state in _IDS else 0
    return _IDS[(i + 1) % len(_IDS)]

def cut_label(state):
    return next((lab for k, lab, _t in CUT_STEPS if k == state), str(state))

def cut_tone(state):
    return next((t for k, _l, t in CUT_STEPS if k == state), "")

def cut_progress(state):
    """刀刃行程 0.0→1.0（idle=0·drop=1），供刀条与标签显示。"""
    return 0.0 if state not in _IDS else round(_IDS.index(state) / (len(_IDS) - 1.0), 3)

def cut_mark(n=1):
    """裁断印记（纸面一行·仿切痕）：出纸口里留下本裁的分隔。"""
    return ('<div style="margin:2px 0 8px;letter-spacing:2px;color:#5b697a;font-size:11px">'
            '✂ ───── 裁纸段 %d ─────</div>' % int(n))

# ---------------- 批41 收尾 走纸队列（逐条打印推进·与 CUT 同族：算式在此，绘制与 QTimer 接线在 shell_qt.py） ----------------
ROLL_STEPS = (("idle", "走纸待机 ROLL IDLE", ""),
              ("feed", "纸张咬入 ROLL FEED", "warn"),
              ("print", "逐行打印 PRINT", ""),
              ("advance", "行进给 ADVANCE", "go"),
              ("tear", "撕纸线 TEAR LINE", "warn"),
              ("jam", "卡纸 JAM", "stop"))
_RIDS = [s[0] for s in ROLL_STEPS]
ROLL_MAX_STRIKE = 3        # 同一行连续三次进给不到＝卡纸（判据归纯算式，壳只照做）

def roll_next(state="idle", at_end=False, jam=False, cleared=False):
    """走纸态推进（纯函数·一次一步）：idle→feed→print→advance→(tear→idle | print)。
    at_end＝本轮队列取空：advance 后打撕纸线（tear）再回 idle；未到末端则 advance→print 逐条循环。
    jam＝本行进给受阻（累计三次仍受阻＝进 jam）；cleared＝jam 态人工清纸→回 print 续打同一行。
    非法值当 idle 起步；tear 是唯一出口（除 jam 外不经 tear 不回 idle）。"""
    if state not in _RIDS:
        state = "idle"
    if state == "jam":
        return "print" if cleared else "jam"
    if jam:
        return "jam"
    if state == "idle": return "feed"
    if state == "feed": return "print"
    if state == "print": return "advance"
    if state == "advance": return "tear" if at_end else "print"
    return "idle"

def roll_label(state):
    return next((lab for k, lab, _t in ROLL_STEPS if k == state), str(state))

def roll_tone(state):
    return next((t for k, _l, t in ROLL_STEPS if k == state), "")

ROLL_PATH = [k for k in _RIDS if k != "jam"]   # 行进序列（jam 不在行程上·与 cut_progress 同谱只算推进）

def roll_progress(state):
    """走纸行程 0.0→1.0（idle=0·tear=1）——纸面推进数值口径；jam/非法值＝0。"""
    return 0.0 if state not in ROLL_PATH else round(ROLL_PATH.index(state) / (len(ROLL_PATH) - 1.0), 3)

def roll_mark(n=1, state="print"):
    """走纸印记（纸面一行·仿进给刻度）：HTML 仍由 line_html 出（渲染真源不复制第二份）。"""
    return line_html("走纸", "第 %d 条·%s（进给 %d%%）" %
                     (int(n), roll_label(state), round(roll_progress(state) * 100)), "sys")

def roll_should_jam(strike=0, max_strike=ROLL_MAX_STRIKE):
    """卡纸判据（纯算式）：同一行进给受阻累计达上限即卡纸（与网页端 jam 的「错误/超时/停止」同档）。"""
    return bool(int(strike or 0) >= int(max_strike))

# ---------------- t8 CRT 送稿口（绿字黑底·扫描线叠加·余辉衰减·块光标闪烁：算式在此，绘制在 shell_qt.Input） ----------------
CRT_DEFAULT = dict(fg="#33ff66", bg="#04070a", dim="#12401f", glow="#0a2a13")

def crt_colors(v=None):
    """CRT 配色：网页端 --crtf/--crtb/--crtgc/--crtgl 优先，缺则内置 #33ff66 系绿字黑底。"""
    v = v or css_vars()
    k = lambda key, fb: v.get(key) or fb
    return dict(fg=k("crtf", CRT_DEFAULT["fg"]), bg=k("crtb", CRT_DEFAULT["bg"]),
                dim=k("crtgc", CRT_DEFAULT["dim"]), glow=k("crtgl", CRT_DEFAULT["glow"]))

def crt_scanlines(h, gap=3):
    """扫描线 y 位（黑底 CRT 每 gap 像素一条·下限 2 防糊成一团·高度≤0 出空表）。"""
    return list(range(0, max(0, int(h)), max(2, int(gap))))

def crt_afterglow(age_ms, half=260.0):
    """荧光粉余辉衰减（指数·半衰期 half 毫秒）→ 0~1 残影强度；age≤0＝满辉，非法值＝满辉。"""
    try:
        a = float(age_ms)
    except Exception:
        return 1.0
    if a <= 0:
        return 1.0
    return round(0.5 ** (a / max(1.0, float(half))), 4)

def crt_block_cursor(px):
    """块光标宽度（≈0.62 字宽·下限 2 像素），配闪烁＝CRT 方块光标。"""
    return max(2, int(round(float(px) * 0.62)))
# ---------------- t10 墨水屏消息面板（E-INK：只此三段·低饱和灰白·无动效·仿电子墨水印） ---------------- ----------------

EINK_SECTIONS = ("会话信息", "任务总览", "后台任务")
# 视图轮转真源（批41 五态·shell_qt.viewToggle 只按此排布，判据不留两份口径）
VIEW_NAMES = ("纸卷 A", "送稿 B", "墨水屏 C", "预览 D", "终端 E")

def view_next(i):
    """轮转步进（纯算式）：越界/非法一律回 0（纸卷 A），闭环＝len(VIEW_NAMES) 态。"""
    try: k = int(i)
    except Exception: return 0
    return 0 if k < 0 else (k + 1) % len(VIEW_NAMES)

def view_name(i):
    try: k = int(i) % len(VIEW_NAMES)
    except Exception: k = 0
    return VIEW_NAMES[k]

def _eink_box(title, inner):
    return ('<div style="border:1px solid #b9bfba;border-radius:2px;background:#eef0ee;'
            'padding:6px 8px;margin:0 0 8px"><div style="font-weight:bold;letter-spacing:2px;'
            'color:#2c322e;border-bottom:1px solid #c9cec9;padding-bottom:3px">%s</div>%s</div>'
            % (_esc(title), inner or '<div style="color:#8f979a;font-size:12px">（无）</div>'))

def _eink_row(k, v):
    return ('<div style="margin:3px 0;font-size:12px;color:#22282a"><span style="color:#6f7772">'
            '%s</span> %s</div>' % (_esc(k), _esc(v)))

def eink_html(info=None, tasks=None, bg=None):
    """三段固定＝会话信息／任务总览／后台任务（其余面板一概不上墨水屏）；
    info·tasks＝/api/info 与 /api/tasks 的 scrub 结果，bg＝进程内〔在跑/排队〕清单 [(tid, 话语, 秒)]。
    只用实色＋1px 线（无渐变·无动画）＝仿电子墨水印刷；缺项显「（无）」，不静默。"""
    i, t = info or {}, tasks or {}
    gw = i.get("gateway") or {}
    s1 = (_eink_row("会话", str(i.get("session") or "-")) +
          _eink_row("线路", "本机直连 · 免密钥（不开端口）") +
          _eink_row("网关", "%s · %s" % ("on" if gw.get("enabled") else "off", gw.get("model") or "-")) +
          _eink_row("SOLO", "on" if (i.get("solo") or {}).get("enabled") else "off"))
    rows = (t.get("rows") or [])[:6]
    s2 = (_eink_row("表", "%s · %s/%s · 未完成 %s · 预计 %s" % (
            t.get("tid") or "-", t.get("done", 0), t.get("total", 0),
            t.get("unfinished", 0), t.get("eta") or "-")) +
          (_eink_row("意图", str(t.get("intent") or "")[:80]) if t.get("intent") else "") +
          "".join(_eink_row(str(r.get("id") or "-"), "%s · %s · %s" % (
              str(r.get("goal") or "")[:40], r.get("status") or "-", r.get("skill") or "-"))
              for r in rows if isinstance(r, dict)))
    s3 = "".join(_eink_row(str(x[0])[:8], "%s · %.0fs" % (str(x[1])[:60], float(x[2] or 0)))
                 for x in (bg or []) if isinstance(x, (list, tuple)) and len(x) >= 2)
    wm = ('<div style="text-align:right;color:#b9bfba;letter-spacing:3px;font-size:10px">'
          'E-INK · 仿电子墨水印 · 无动效</div>')
    return wm + "".join(_eink_box(k, b) for k, b in zip(EINK_SECTIONS, (s1, s2, s3)))

# ---------------- 自检（离仓·离窗可跑：QT_QPA_PLATFORM=offscreen，不发模型请求） ----------------
def selftest():
    """页面解析＋样式＋数据桥＋渲染＋密钥面结构核对全跑一遍；0＝全绿（GUI 免密钥的硬判据在此）。"""
    v = css_vars()
    META_, METAD_, PAD_, QUICK_, F1_ = keys()
    q = qss(v)
    info, perms = api("/api/info"), api("/api/perms")
    leak = leaked(info) or leaked(perms)
    ok = {"page_bytes": len(page()), "vars": len(v), "meta": len(META_), "metad": len(METAD_),
          "pad": len(PAD_), "quick": len(QUICK_), "f1_groups": len(F1_),
          "qss_len": len(q), "qss_gradient": "qlineargradient" in q,
          "qss_shapes": all(x in q for x in ('[sm="1"]', 'tone="acc"', 'tone="stop"', "border-radius")),
          "api_probe": {k: (api("/api/" + k) or {}).get("err", "ok")[:40]
                        for k in ("tasks", "perms", "hud", "skills", "plans")},
          "no_token_face": (not leak) and leaked({"token": "x"}) == "token"
                            and leaked({"a": [{"fingerprint": "y"}]}) == "fingerprint",
          "line_html": ("<span" in line_html("系统", "x", "sys")
                        and "<b>" not in line_html("我", "<b>", "me")
                        and "&lt;b&gt;" in line_html("我", "<b>", "me")
                        and 'background:#c81e1e' in jam_html("x")),
          "jam": "JAM" in jam_html("e"),
          "panel_tasks": "table" in panel_html("tasks", info and api("/api/tasks")),
          "panel_err": "JAM" in panel_html("tasks", {"err": "x"}),
          "drawers": len(DRAWERS), "cut_steps": len(CUT_STEPS)}
    seq, s = [], "idle"
    for _ in range(len(_IDS) + 1):
        s = cut_next(s); seq.append(s)
    e = eink_html({"session": "abc12345", "gateway": {"enabled": True, "model": "x"},
                   "solo": {"enabled": True}},
                  {"tid": "task-1", "done": 2, "total": 5, "unfinished": 3, "eta": "1m",
                   "intent": "示例意图", "rows": [{"id": "t1", "goal": "g", "status": "done", "skill": "s"}]},
                  [("t9", "话语示例", 3.0)])
    ok["cut_cycle"] = seq == _IDS[1:] + ["idle", "feed"]
    ok["cut_progress"] = cut_progress("cut") == 0.75 and cut_progress("idle") == 0.0
    ok["cut_tone"] = cut_tone("cut") == "stop" and cut_label("nope") == "nope"
    ok["cut_mark"] = "裁纸段" in cut_mark(1)
    ok["crt_colors"] = crt_colors()["fg"] == "#33ff66" and crt_colors()["bg"] == "#04070a"
    ok["crt_scanlines"] = len(crt_scanlines(60, 3)) == 20 and crt_scanlines(0) == []
    ok["crt_afterglow"] = (abs(crt_afterglow(0) - 1.0) < 1e-9 and crt_afterglow(260) == 0.5
                           and crt_afterglow(520) < 0.26 and crt_afterglow("x") == 1.0)
    ok["crt_cursor"] = crt_block_cursor(13) == 8 and crt_block_cursor(1) == 2
    ok["qss_crt"] = 'QPlainTextEdit#cmd[crt="1"]' in q and "${" not in q
    ok["qss_blade"] = all('QFrame#blade[st="%s"]' % k in q for k in ("feed", "clamp", "cut", "drop"))
    ok["qss_eink"] = "QTextBrowser#eink{" in q
    ok["eink_sections"] = list(EINK_SECTIONS) == ["会话信息", "任务总览", "后台任务"]
    ok["eink_html"] = ("<div" in e and all(x in e for x in EINK_SECTIONS) and "task-1" in e
                       and "abc12345" in e and "话语示例" in e
                       and not any(bad in e for bad in ("animation", "transition", "gradient", "@keyframes")))
    ok["eink_empty"] = eink_html().count("（无）") >= 1
    ok["eink_no_key"] = leaked(eink_html(info)) == "" if isinstance(info, dict) else True
    nb = "SMS-" + "FAX · GUI"          # 拆字面量：判据自身不得含被检串（否则自指假阴）
    bs = "brand" + "Sub"
    ok["qss_topbar"] = ("QFrame#ctlzone{" in q and "QListWidget#palList{" in q
                        and "QDialog#palette{" in q and ("QLabel#" + "brand{") not in q
                        and bs not in q and 'QFrame#mouth[st="feed"]' in q)
    bsrc = read_text(os.path.join(S, "shell_qt_fax.py"))
    ok["build_zero_topbar"] = (nb not in bsrc and 'w["ctlzone"]' in bsrc
                               and 'w["ctlzone_btn"]' in bsrc and 'w["banner"]' in bsrc
                               and 'w["mouth"]' in bsrc and bs not in bsrc)
    # ---- 批41 上送稿口＋下左右分屏（表 010-231707-890）：分屏／预览／终端进门禁 ----
    seg = bsrc.split("def build(win, ent):")[1].split("# ---------------- t6 裁纸刀")[0]
    seg_code = seg.split('"""', 2)[-1]          # 判据只扫装配代码体（docstring 里的说明字样不算进程面）
    ok["view_cycle5"] = (list(VIEW_NAMES) == ["纸卷 A", "送稿 B", "墨水屏 C", "预览 D", "终端 E"]
                         and [view_next(i) for i in range(len(VIEW_NAMES))] == [1, 2, 3, 4, 0]
                         and view_next("x") == 0 and view_next(-2) == 0
                         and view_name(3) == "预览 D" and view_name(7) == "墨水屏 C")
    ok["qss_split"] = ("QSplitter#split" in q and "QSplitter#psplit" in q
                       and "QSplitter#split::handle:horizontal" in q
                       and "QSplitter#psplit::handle:vertical" in q)
    ok["qss_preview"] = ("QPlainTextEdit#preview{" in q and "QLabel#lnr{" in q
                         and "QFrame#previewzone{" in q and "QLineEdit#pvOpen{" in q)
    ok["qss_terminal"] = ("QPlainTextEdit#term{" in q and "QLineEdit#termIn{" in q
                          and "QFrame#termzone{" in q)
    ok["build_split_assembly"] = ('w["split"] = split' in seg_code and 'w["psplit"] = psplit' in seg_code
                                  and 'w["aside"] = aside' in seg_code
                                  and "split.addWidget(tray)" in seg_code and "split.addWidget(aside)" in seg_code
                                  and "psplit.addWidget(pvz)" in seg_code and "psplit.addWidget(tmz)" in seg_code
                                  and "psplit.addWidget(ez)" in seg_code
                                  and 'ez.setProperty("resident", "1")' in seg_code
                                  and "av.addWidget(ez)" not in seg_code and "ez.hide()" not in seg_code
                                  and 'w["eink_stat"] = est' in seg_code
                                  and "av.addWidget(psplit, 1)" in seg_code
                                  and "setChildrenCollapsible(False)" in seg_code
                                  and "split.setSizes([760, 640])" in seg_code
                                  and "root.addWidget(split, 1)" in seg_code)
    ok["build_preview_parts"] = ('w["preview"] = pv' in seg_code and 'w["previewzone"] = pvz' in seg_code
                                 and 'w["pv_open"] = pv_in' in seg_code and 'w["pv_stat"] = pv_stat' in seg_code
                                 and 'w["pv_fold"]' in seg_code and 'w["pv_src"]' in seg_code)
    ok["build_terminal_parts"] = ('w["term"] = tm' in seg_code and 'w["termzone"] = tmz' in seg_code
                                  and 'w["term_in"] = ti' in seg_code and 'w["t_run"]' in seg_code
                                  and 'w["t_fold"]' in seg_code and 'w["t_paper"]' in seg_code
                                  and 'w["t_clear"]' in seg_code and 'w["t_stat"]' in seg_code)
    ok["build_feeder_first"] = ('"① 送稿口 DOC FEEDER · B' in seg and '"② 纸卷区 PAPER ROLL · A' in seg
                                and '"③ 预览 PREVIEW · D' in seg and '"④ 终端 TERMINAL · E' in seg
                                and '"\u25a4 墨水屏消息面板 \u00b7 C\uff08\u5e38\u9a7b\u53f3\u680f\u4e0a\u683c' in seg
                                and seg_code.index("root.addWidget(feeder)") < seg_code.index("root.addWidget(split, 1)")
                                and "root.addWidget(tray, 3)" not in seg_code
                                and "ctl.hide()" in seg_code and "dr.hide()" in seg_code
                                and "ez.hide()" not in seg_code and "psplit.addWidget(ez)" in seg_code
                                and "av.addWidget(ez)" not in seg_code and "dr.hide()" in seg_code)
    ok["split_layout"] = {
        "top_input": ("root.addWidget(feeder)" in seg_code and "root.addWidget(split, 1)" in seg_code
                      and seg_code.index("root.addWidget(feeder)") < seg_code.index("root.addWidget(split, 1)")
                      and re.findall(r"root\.addWidget\((\w+)", seg_code) == ["feeder", "split"]
                      and seg_code.index("feeder, zv = _zone(") < seg_code.index("split = QSplitter")),
        "horizontal_splitter": ("QSplitter" in seg_code and "Qt.Orientation.Horizontal" in seg_code
                                and "split.addWidget(tray)" in seg_code and "split.addWidget(aside)" in seg_code
                                and "split.setChildrenCollapsible(False)" in seg_code
                                and "split.setSizes([760, 640])" in seg_code),
        "right_column": ("av.addWidget(ctl)" in seg_code and "av.addWidget(dr)" in seg_code
                         and 0 <= seg_code.index("av.addWidget(psplit, 1)")
                         < seg_code.index("av.addWidget(ctl)") < seg_code.index("av.addWidget(dr)")
                         and "psplit.addWidget(ez)" in seg_code
                         and "ez.hide()" not in seg_code and "av.addWidget(ez)" not in seg_code),
        "fw_keyface": all(('w["%s"]' % k) in seg for k in
                          ("banner", "roll", "mouth", "tear", "blade", "blade_tag", "blade_pos",
                           "ctlzone", "ctlzone_btn", "drawer", "dtitle", "dbody", "btn_all", "btn_speak",
                           "btn_stop", "btn_go", "eink", "einkzone", "keys", "dial_keys", "meta_grp",
                           "f1_grp", "split", "psplit", "aside", "feeder")),
        "on_demand_hidden": ("ctl.hide()" in seg_code and "dr.hide()" in seg_code
                             and "ez.hide()" not in seg_code)}
    ok["split_layout_ok"] = all(bool(x) for x in ok["split_layout"].values())
    rseq, s2 = [], "idle"
    for _ in range(5):
        s2 = roll_next(s2, at_end=(len(rseq) >= 3)); rseq.append(s2)
    ok["roll_cycle"] = (rseq == ["feed", "print", "advance", "tear", "idle"]
                        and roll_next("idle", jam=True) == "jam"
                        and roll_next("jam") == "jam" and roll_next("jam", cleared=True) == "print"
                        and roll_next("nope") == "feed"
                        and [roll_next("advance", at_end=bool(i % 2)) for i in range(4)] ==
                            ["print", "tear", "print", "tear"]
                        and [s[0] for s in ROLL_STEPS] == ["idle", "feed", "print", "advance", "tear", "jam"]
                        and roll_next("print") == "advance" and "tear" in _RIDS)
    ok["roll_mark"] = ("<div" in roll_mark(2, "print") and "第 2 条" in roll_mark(2)
                       and "PRINT" in roll_mark(2) and "<b>" not in roll_mark(2)
                       and "line_html" in inspect.getsource(roll_mark)
                       and "animation" not in roll_mark(7) and "transition" not in roll_mark(7))
    ok["roll_tone"] = (roll_tone("jam") == "stop" and roll_tone("advance") == "go"
                       and roll_tone("print") == "" and roll_label("jam").startswith("卡纸")
                       and roll_label("nope") == "nope")
    ok["roll_progress"] = (roll_progress("idle") == 0.0 and roll_progress("tear") == 1.0
                           and 0.0 < roll_progress("print") < 1.0 and roll_progress("nope") == 0.0)
    ok["roll_should_jam"] = (roll_should_jam(0) is False and roll_should_jam(ROLL_MAX_STRIKE - 1) is False
                             and roll_should_jam(ROLL_MAX_STRIKE) is True and roll_should_jam(9) is True
                             and roll_should_jam(None) is False)
    ok["qss_roll"] = all('QFrame#mouth[st="%s"]' % k in q for k in ("print", "advance", "tear", "jam"))
    ok["qss_eink_resident"] = ('QFrame#einkzone[resident="1"]' in q and "QLabel#einkStat{" in q
                            and "QLabel#rollTag[st=" in q and "${" not in q)
    ok["eink_resident_right"] = ("ez.hide()" not in seg_code and "av.addWidget(ez)" not in seg_code
                                 and "psplit.addWidget(ez)" in seg_code
                                 and 'ez.setProperty("resident", "1")' in seg_code
                                 and 'w["eink_stat"] = est' in seg_code
                                 and "ez.setMinimumHeight(150)" in seg_code
                                 and seg_code.count("root.addWidget(") == 2
                                 and '"\u25a4 墨水屏消息面板 \u00b7 C\uff08\u5e38\u9a7b\u53f3\u680f\u4e0a\u683c' in seg)
    pf = ("sub" + "process", "Q" + "Process", "soc" + "ket", "HTTP" + "Server",
          "serve_" + "forever", "os." + "system")   # 拆字面量：判据自身不得含被检串（否则镜像件恒假阴·本批补踩）
    ok["assembly_no_process_face"] = (not any(x in seg_code for x in pf)
                                      and "/api/files" in seg_code and "/api/detail" in seg_code)
    ok["api_query_get"] = ("query" in inspect.signature(api).parameters
                           and isinstance(api("/api/files", query={}), dict)
                           and bool(api("/api/file", query={"path": "no/such/x"}).get("err")))
    ok["preview_helpers"] = (preview_text({"content": "x\ny"})["lines"] == 2
                             and preview_text({"err": "没门"})["fallback"]
                             and preview_text({"files": [{"name": "a.py", "size": 3,
                                                           "type": "file"}]})["lines"] == 1
                             and "sms-shell" in preview_text({})["text"]
                             and preview_text(None)["fallback"] is True)
    ok["term_helpers"] = (term_line_kind("$ dir") == "sh" and term_line_kind(":cmds") == "meta"
                          and term_line_kind("JAM 卡纸") == "err" and term_line_kind("rc=1") == "err"
                          and term_line_kind("Traceback x") == "err" and term_line_kind("hello") == "out"
                          and term_line_kind("") == "out" and TERM_PROMPT == "$ ")
    ok["assembly_compact_right"] = ('pvz.setToolTip("' in seg_code and 'tmz.setToolTip("' in seg_code
                                     and seg_code.count("_zone(") == 4
                                     and 'w["feeder"] = feeder' in seg_code)
    ok["assembly_min_width"] = ("feeder.setMinimumWidth(320)" in seg_code
                                and "tray.setMinimumWidth(430)" in seg_code
                                and "pvz.setMinimumWidth(300)" in seg_code
                                and "tmz.setMinimumWidth(300)" in seg_code)
    ok["fw_batch41_keys"] = all(('w["%s"]' % k) in seg_code for k in
                                ("split", "psplit", "preview", "previewzone", "pv_open", "pv_stat",
                                 "term", "termzone", "term_in", "t_stat", "roll_tag", "eink_stat"))
    ok["fw_roll_parts"] = ('w["roll_tag"] = QLabel(roll_label("idle"))' in seg_code
                           and 'w["eink_stat"] = est' in seg_code and '"roll"' in seg_code)
    print("FAX_SELFTEST " + json.dumps(ok, ensure_ascii=False))
    return 0 if (ok["meta"] >= 30 and ok["qss_gradient"] and ok["qss_shapes"] and ok["line_html"]
                 and ok["jam"] and ok["no_token_face"] and ok["page_bytes"] > 1000
                 and ok["cut_cycle"] and ok["cut_progress"] and ok["cut_tone"] and ok["cut_mark"]
                 and ok["crt_colors"] and ok["crt_scanlines"] and ok["crt_afterglow"] and ok["crt_cursor"]
                 and ok["qss_crt"] and ok["qss_blade"] and ok["qss_eink"]
                 and ok["eink_sections"] and ok["eink_html"] and ok["eink_empty"]
                 and ok["qss_topbar"] and ok["build_zero_topbar"]
                 and ok["view_cycle5"] and ok["qss_split"] and ok["qss_preview"] and ok["qss_terminal"]
                 and ok["build_split_assembly"] and ok["build_preview_parts"]
                 and ok["build_terminal_parts"] and ok["build_feeder_first"]
                 and ok["split_layout_ok"] and ok["assembly_no_process_face"] and ok["fw_batch41_keys"]
                 and ok["preview_helpers"] and ok["term_helpers"] and ok["api_query_get"]
                 and ok["assembly_min_width"] and ok["assembly_compact_right"]
                 and ok["roll_cycle"] and ok["roll_mark"] and ok["roll_tone"] and ok["roll_progress"]
                 and ok["roll_should_jam"] and ok["qss_roll"] and ok["qss_eink_resident"]
                 and ok["eink_resident_right"] and ok["fw_roll_parts"]) else 1
if __name__ == "__main__":
    if "--selftest" in sys.argv:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        sys.path.insert(0, _scripts_dir() if "_scripts_dir" in dir() else S)
        sys.exit(selftest())
    print(__doc__)
