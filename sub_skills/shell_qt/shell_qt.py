#!/usr/bin/env python3
"""shell_qt.py — sms-shell 图形壳（PyQt6）＝网页端传真机界面的本机镜像（批38 重写）：
批40 起机身 chassis＝零顶栏；批41 起骨架＝上送稿口＋下左右分屏：上＝B 送稿口 DOC FEEDER（话语/:元指令·Tab 补全·
↑↓ 历史·常用拨号·CRT 成像·送稿键·常驻第一位），其下 QSplitter#split 左右分屏＝左 A 纸卷区 PAPER ROLL（出纸正文＋
状态行 LCD 六格/LED 七灯＋mouth 口腔·tear 撕纸线·blade 裁纸刀＋复制/下载/撕纸/裁纸/墨水屏/命令面板动作条）｜
右格 aside 竖列（QVBoxLayout）上＝QSplitter#psplit 三件＝C 墨水屏 E-INK（常驻第一格·Ctrl+I 只聚焦永不 hide）→D 预览 PREVIEW（QPlainTextEdit＋独立行号栏自绘·取数一律进程内 /api/files·
/api/file·/api/detail，绝不新建 HTTP·绝不读 token，取不到＝内置兜底＋纸面卡纸）与 E 终端 TERMINAL
（内嵌面板·QProcess 复用 shell_core.handle 路由口径，`!` 系统 shell 与内置命令同 TUI，输出可回灌纸卷，
进程随窗口 closeEvent 一律 terminate→kill 收净·不留孤儿·无控制台窗口＝no_window 审计点带 `# sms-visible`
之外的合法件——本壳有意开窗处仍只有 `tui` 一处）；aside 列下方＝按需层依次控制面板
（META 键阵＋F1 六组＋拨号盘＋↻巡检/🔊朗读/⏸停止/▶继续·Ctrl+M）＋抽屉面板（任务总览/计划/链/会话/技能/文件/配置/权限/明细）。
批39 三视图件（算式与版式真源全在 shell_qt_fax.py，本文件只接绘制与状态推进·零新端口零新进程零子线程）：
t6 出纸末端裁纸刀（✂ 裁纸 CUT：fax.cut_next 五态推进·进程内 QTimer 每 200ms 走一步·刀条 QFrame#blade[st=…]
随态换渐变＋行程百分比＋裁纸指示灯·落 drop 在纸面留裁断印记·途中再点＝中止）；t8 送稿口 CRT（绿字 #33ff66
黑底＋扫描线叠加＋余辉衰减＋块光标闪烁：Input.paintEvent/_crt_overlay 三层成像，keyPressEvent 与
路由/stop/ask 口径一字未改，fax("crt") 可关成像层）；t10 墨水屏消息面板（▤ 墨水屏 E-INK：只显示
fax.EINK_SECTIONS 三段＝会话信息／任务总览／后台任务·低饱和灰白实色·无动效·仿电子墨水印，
数据仍走 fax.api 进程内直调）。自检含三件断言（cut_ok/crt_ok/eink_ok）。
**GUI 端不做任何密钥验证**：网页端的门禁插令牌区（#gate）在图形壳不存在——本机窗口即可信，面板数据经
shell_qt_fax.api() 进程内直调 web_shell 同一套 getter/poster，绝不开端口、绝不读/显影/复制/轮换 token，
info 结果一律 scrub 掉 token/指纹。版式与键位每次现取 web_page.html（CSS :root 变量→QSS 渐变、
JS META·METAD·PAD·QUICK·F1→机身件），页面取不到时用内置兜底，网页端改了图形壳跟着改、不留两份口径。
路由完全复用 shell_core.handle：`:` 元指令、`!` 系统 shell、裸内置词、话语→数据流一律同 TUI/网页端；
并行、停止、提问、明细、任务总览、HUD、编辑器与旧壳同口径（Task worker·stop_channel/ask_channel/chains.ACTIVE
线程隔离·shell.parallel=false 或达 shell.max_parallel 排队续发·stop <tid> 只停一个·ask_user 下一条输入即答复）。
零裸子进程：唯一有意开窗处（`tui` 另起终端壳）带 `# sms-visible` 标记，其余一律 no_window；
批41 终端件起的 QProcess 走管道直连、无控制台窗口（不经裸壳调用），故审计面无新增。
批40 零顶栏：机身不装原生菜单栏、不装 brand 横条；批41 装配改骨架＝上送稿口＋下左右分屏（QSplitter·1280×720 可用·
右格 aside 竖列：上＝C/D/E 三格常驻不可折叠（psplit setChildrenCollapsible(False)）·可切分（C 第一格）、下＝按需层依次 ctlzone→抽屉），root 只两格＝上送稿口＋下分屏。菜单职能仍＝命令面板
Ctrl+K（条目同源 MENU_ITEMS·preview/terminal 动作纳入同源条目·出口同实体键 feed/faxPick/_open/submit·不留第二条路由）
＋右键菜单；原菜单快捷键 F3/F5/F8/Ctrl+T/P/J/H/E/I/R/M/V/K 一律保 QAction 级（_menu_actions·不挂 menuBar），
批41 增 Ctrl+D 预览／Ctrl+U 终端／Ctrl+B 终端上纸卷。Ctrl+V 视图轮转扩为五态（纸卷 A／送稿 B／墨水屏 C／预览 D／
终端 E·位次真源＝fax.VIEW_NAMES＋fax.view_next）。fw 键面逐字兼容批38/39/40
（banner/roll/drawer/dtitle/dbody/lcd_*/led_*/blade*/eink*/btn_*/keys 全保留），批41 增 split/psplit/
preview(zone)/pv_open/pv_stat/term(zone)/term_in/t_*。
批41 收尾三处偏差：C 墨水屏升为 psplit 常驻第一格（按需层只剩 ctlzone→抽屉）·主页面底部条带撤销
（提示迁 QLCD 小标 eink_stat·root 只两格）·走纸队列 fax.roll_next 六态（feed/print/advance/tear/idle＋jam）逐条推进绘于纸面。
批45 预览取数收口（候选目录 L961／取数三路 L972）：裸名不再单点问工作区根——候选去重保序＝工作区根→
SMS_TMP→当前目录，逐个进程内 /api/files?ws=… 回查命中再 /api/file?path=…；候选全 miss＝明确 err＋内置兜底＋
纸面卡纸（绝不把目录列表充当文件内容）；selftest 以真 _ws_hint 取证（门禁 pv_ws_roots／pv_abs_lines≥3）。
批46 灯数校平（QQ 灯 pollQQ L1392／一键巡检 pollAll L1417／节拍 tick L1334）：镜像件造七灯＝线路/QQ/朗读/做梦/计划/裁纸/对外
（网页端 #leds 六 id 同名口径·裁纸为壳侧新增），壳侧自此七灯全驱动——QQ 灯与网页端同路走进程内 /api/qq
（web_shell g_qq），取不到＝off 不谎报；门禁 led_driven_n／led_built_n／led_lamps 三者相等＝7 且 led_parity
且 qq_lamp_ok（造几灯＝驱动几灯，缺灯不放行）。
行号清单（本文件·装配→件→取数→巡检→自检）：装配＝机身 Shell L396、命令面板同源条目 MENU_ITEMS L467、QAction 快捷键保号 L518、界面口径串 about_text L504；件＝送稿口 CRT L316、预览 D L217、终端 E L271；动作＝分派表 L642（面板与实体键同源·不留第二条路由）、走纸队列 L780/L832、裁纸 L753、五态轮转 L932、C 只聚焦 L1144；取数＝候选目录 L961、三路 L972、折叠 L1025、终端 QProcess L1039（随窗收净不留孤儿）；巡检＝节拍 L1334、灯态 L1360、pollInfo L1369、pollSolo L1384、pollQQ L1392、pollTasks L1400、pollAll L1417；自检＝取证 L1542、灯计 led_lamps L1754／led_driven_n L1760／led_built_n L1761、放行式 L1837。
跑法：bin/sms-shell-gui（图形入口·批37 双入口）或 python -B shell_qt.py · 自检：python -B shell_qt.py --selftest
（offscreen 成图＋机身件计数＋抽屉面板渲染，不发模型请求）；端到端回归：--probe=:help||:cmds（输出落 txt）。"""
import os, sys, time, html, re, json, io, contextlib, subprocess
for _s in (sys.stdout, sys.stderr):
    with contextlib.suppress(Exception): _s.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONUTF8", "1"); os.environ.setdefault("PYTHONIOENCODING", "utf-8")
def _scripts():
    """壳脚本目录定位：自身目录 → env SMS_SHELL_SCRIPTS → <SMS_HOME>/config 的 sms_skill 覆盖安装态 →
    相邻 ../SMS-core（与 sms.py 的 _core_scripts 同口径，换机/换目录仍可跑）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    if os.path.isfile(os.path.join(here, "shell_core.py")): return here
    import json as _j
    cand = [os.environ.get("SMS_SHELL_SCRIPTS") or ""]
    home = os.environ.get("SMS_HOME") or ""
    if not home:
        la = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        for c in (os.path.join(la, "SMS"), os.path.join(os.path.expanduser("~"), "SMS")):
            if os.path.isfile(os.path.join(c, "config", "config.json")): home = c; break
    if home:
        try: skill = _j.load(io.open(os.path.join(home, "config", "config.json"), encoding="utf-8-sig")).get("sms_skill") or ""
        except Exception: skill = ""
        for base in (skill, home):
            if not base: continue
            for sub in ("skill/scripts", os.path.join("skills", "smsystem-suit", "skill", "scripts"),
                        os.path.join("skills", "skill_manage_system", "skill", "scripts")):
                cand.append(os.path.join(base, sub))
        for c in (os.path.join(home, "skills", "sms-shell", "scripts"),
                  os.path.join(skill or "", "..", "sms-shell", "scripts") if skill else "",
                  os.path.join(skill or "", "..", "sms-shell", "skill", "scripts") if skill else ""):
            if c: cand.append(os.path.normpath(c))
    root = os.path.normpath(os.path.join(here, "..", ".."))
    for name in ("SMS-core", "sms-core", "SMS-shell", "sms-shell"):
        cand.append(os.path.join(root, name, "skill", "scripts"))
    return next((c for c in cand if c and os.path.isfile(os.path.join(c, "shell_core.py"))), here)
S = _scripts()
# 本目录优先：混合/覆盖安装环境里 PYTHONPATH 带着核仓旧副本，同目录件须压过它
if sys.path[:1] != [S]: sys.path.insert(0, S)
import shell_core as core                      # 壳共享路由（元指令＋数据流）＝唯一真源
import msg_flow, detail_bus, atomic_io, settings as st
import stop_channel as stop
def _load_fax():
    """镜像件按「与本文件同目录」显式装载：引擎件（shell_core 等）会把核仓旧副本插到 sys.path 最前，
    裸 import 可能拿到旧版 shell_qt_fax.py 配新机身；成对件必须同源（覆盖安装态＝同一路径，行为不变）。"""
    import importlib.util as _u
    here = os.path.dirname(os.path.abspath(__file__))
    # shell_qt_fax.py is in the sibling sub_skills/shell_qt_fax/ directory
    p = os.path.join(here, "..", "shell_qt_fax", "shell_qt_fax.py")
    if not os.path.isfile(p): raise ImportError("shell_qt_fax.py 不在 %s" % p)
    old = sys.modules.get("shell_qt_fax")
    if old is not None and os.path.abspath(getattr(old, "__file__", "") or "") == p: return old
    spec = _u.spec_from_file_location("shell_qt_fax", p)
    m = _u.module_from_spec(spec); sys.modules["shell_qt_fax"] = m; spec.loader.exec_module(m)
    return m

try:
    fax = _load_fax()                           # 传真机镜像件（版式取网页端·数据直调 web_shell·无密钥面）
except ImportError as e:                        # 缺件＝覆盖安装不完整，明确交棒终端入口而非半瞎窗口
    sys.exit("图形壳缺镜像件 shell_qt_fax.py（%s）——跑 deploy.py 或 install_overlay.py --write 补全，"
             "或用 bin/sms-shell-tui 终端入口" % e)
from PyQt6.QtCore import Qt, QRect, QSize, QThread, QTimer, QProcess, pyqtSignal
from PyQt6.QtGui import (QAction, QColor, QFont, QKeySequence, QPainter, QTextCharFormat,
                         QTextFormat)
from PyQt6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMainWindow, QMenu, QPlainTextEdit, QPushButton,
                             QTextBrowser, QTextEdit, QVBoxLayout, QWidget, QSizePolicy)
SMS = core.SMS; TD = os.path.join(SMS, "tasks")
SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
PAPE = dict(bg="#f7f3e7", ink="#1b2026", dim="#6b6152", blue="#2b4a63", green="#1d6b41", yellow="#8a6a2a",
            red="#c81e1e", mauve="#6b3fa0", teal="#0f6b7a", peach="#b45309", line="#c9c0ae", sys="#5a4a1c")
def esc(t): return html.escape(str(t), quote=False)
def paint(t):
    """一行文本 → 纸面 HTML（传真墨色口径：⧉技能紫·$ 命令棕橙·✗ 红·✎ 黄·• 绿·路径青·`code` 棕橙）"""
    t = str(t)
    if t.startswith("⧉") and "▸" in t:
        name, _, rest = t[1:].partition("▸")
        return '<span style="color:%s;font-weight:bold">⧉%s</span> <span style="color:%s">▸</span> %s' % (
            PAPE["mauve"], esc(name), PAPE["mauve"], _rich(rest.lstrip()))
    head = {"$ ": (PAPE["peach"], "$ "), "✗ ": (PAPE["red"], "✗ "), "✎ ": (PAPE["yellow"], "✎ "),
            "• ": (PAPE["green"], "• "), "! ": (PAPE["peach"], "! ")}
    for pre, (col, label) in head.items():
        if t.startswith(pre):
            return '<span style="color:%s;font-weight:bold">%s</span>%s' % (col, esc(label),
                                                                            _rich(t[len(pre):], col if pre == "$ " else None))
    return _rich(t)
PATH = re.compile(r"[A-Za-z]:[\\/][^\s，。！？；：,]+|[\w\-\./\\]+\.(?:py|md|ps1|cmd|json|txt|html|csv|sh|js|ts)\b")
CODE = re.compile(r"`([^`\n]+)`")
def _rich(s, base=None):
    out, pos = [], 0
    ms = sorted(list(PATH.finditer(s)) + list(CODE.finditer(s)), key=lambda m: m.start())
    for m in ms:
        if m.start() < pos: continue
        out.append(esc(s[pos:m.start()]))
        if m.group(0).startswith("`"): out.append('<span style="color:%s;font-weight:bold">%s</span>' % (PAPE["peach"], esc(m.group(1))))
        else: out.append('<span style="color:%s">%s</span>' % (PAPE["teal"], esc(m.group(0))))
        pos = m.end()
    out.append(esc(s[pos:]))
    return '<span style="color:%s">%s</span>' % (base or PAPE["ink"], "".join(out))
def badge(h):
    """〔技能:x〕〔工具:x→y〕徽章着色；入参＝paint 已产出的安全 HTML（不再二次转义）"""
    return re.sub(r"〔(技能|工具):([^〕]*)〕", lambda m: '<span style="color:%s;font-weight:bold">〔%s:%s〕</span>' %
                  (PAPE["mauve"], m.group(1), m.group(2)), str(h))

class Task(QThread):
    """一条用户输入＝一个并行任务 worker（tid 绑 stop_channel/ask_channel/chains.ACTIVE 线程本地）。"""
    line = pyqtSignal(str); step = pyqtSignal(str); env = pyqtSignal(object); bye = pyqtSignal(str); over = pyqtSignal(str, object)
    def __init__(self, text, tid):
        super().__init__(); self.text, self.tid, self.t0 = text, tid, time.time()
    def run(self):
        stop.bind(self.tid)
        try:
            import ask_channel; ask_channel.bind(self.tid)
        except Exception: pass
        def _st(n): self.step.emit(str(n))
        done = None
        try:
            done = core.handle(self.text, lambda s: self.line.emit(str(s)), _st, lambda e: self.env.emit(e))
        except stop.Stopped as e:
            self.line.emit("⛔ 任务 %s 已停止（%s）——在途输出中断·旗标已复位" % (self.tid, str(e)[:80]))
        except Exception as e:
            import traceback
            core.debug.enabled() and core.debug.log("EXC " + traceback.format_exc())
            self.line.emit("✗ 处理异常：" + (repr(e)[:200] if not core.debug.enabled() else traceback.format_exc()[-900:]))
        finally:
            try:
                import ask_channel; ask_channel.flush(self.tid)
            except Exception: pass
            stop.clear(self.tid)
        self.over.emit(self.tid, done)


class Editor(QMainWindow):
    """窗内文本编辑器（:edit/:view 令牌与 F8 用），保存＝atomic_io 之外的直写（工作区与用户文件均可）。"""
    def __init__(self, path, ro=False):
        super().__init__(); self.path, self.ro = path, ro
        self.setWindowTitle(("查看 " if ro else "编辑 ") + os.path.basename(path or "") + " — sms-shell GUI")
        self.resize(900, 620)
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(6, 6, 6, 6)
        self.bar = QHBoxLayout(); v.addLayout(self.bar)
        self.ed = QPlainTextEdit(); f = QFont("Cascadia Mono"); f.setStyleHint(QFont.StyleHint.Monospace)
        self.ed.setFont(f); v.addWidget(self.ed)
        try:
            self.ed.setPlainText(open(path, encoding="utf-8", errors="replace").read())
        except Exception as e:
            self.ed.setPlainText("（读取失败：%s）" % e)
        self.ed.setReadOnly(ro)
        for label, fn in (("保存", self.save), ("重载", self.reload), ("关闭", self.close)):
            b = QPushButton(label); b.clicked.connect(fn); self.bar.addWidget(b)
        self.stat = QLabel(path or ""); self.stat.setStyleSheet("color:%s" % M["dim"]); self.bar.addWidget(self.stat, 1)
        self.setCentralWidget(w)
    def save(self):
        if self.ro: self.stat.setText("只读——:edit <路径> 可写"); return
        try:
            with open(self.path, "w", encoding="utf-8", newline="\n") as f: f.write(self.ed.toPlainText())
            self.stat.setText("已保存 %s · %s" % (self.path, time.strftime("%H:%M:%S")))
        except Exception as e:
            self.stat.setText("✗ 保存失败：" + str(e)[:160])
    def reload(self):
        try: self.ed.setPlainText(open(self.path, encoding="utf-8", errors="replace").read()); self.stat.setText("已重载")
        except Exception as e: self.stat.setText("✗ 重载失败：" + str(e)[:160])


class LineNumberArea(QWidget):
    """预览件行号栏（批41·独立自绘）：宽度＝位数×字宽＋边距；绘制一律走 Preview.lnr_rows()
    的块几何（document().documentLayout()），不自存行号数组、不改文本模型。"""
    def __init__(self, ed):
        super().__init__(ed); self.ed = ed
    def sizeHint(self):
        fm = self.ed.fontMetrics()
        return QSize(max(34, 9 + fm.horizontalAdvance("9" * max(2, len(str(self.ed.blockCount()))))), 0)
    def paintEvent(self, ev): self.ed.lnr_paint(ev)


class Preview(QPlainTextEdit):
    """预览件 D（批41）：代码/文件只读预览＋行号栏＋当前行整行高亮。数据只由 Shell.previewOpen 经
    进程内 fax.api()（/api/files·/api/file·/api/detail）灌入——绝不新建 HTTP、绝不读 token；
    折行关闭＝行号与源行一一对应。取不到＝preview_text 内置兜底＋纸面「卡纸」（不静默）。"""
    def __init__(self, win=None):
        super().__init__(); self.win = win
        self.lnr = LineNumberArea(self)
        self.blockCountChanged.connect(self.lnr_resize)
        self.updateRequest.connect(self.lnr_update)
        self.cursorPositionChanged.connect(self.lnr_highlight)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setReadOnly(True); self.setObjectName("preview")
        f = QFont("Cascadia Mono"); f.setStyleHint(QFont.StyleHint.Monospace); self.setFont(f)
        self.lnr_resize(0); self.lnr_highlight()

    def lnr_width(self): return int(self.lnr.sizeHint().width())
    def lnr_resize(self, _h=0):
        self.setViewportMargins(self.lnr_width(), 0, 0, 0)
        self.lnr.setGeometry(0, 0, self.lnr_width(), self.height() or 0)
    def lnr_update(self, r, dy):
        if dy: self.lnr_resize(0)
        else: self.lnr.update(0, r.y(), self.lnr_width(), r.height())
    def lnr_rows(self, limit=4000):
        """可见块 → [(行号, 视口 y)]：几何一律取 QPlainTextEdit.blockBoundingGeometry(block)
        .translated(contentOffset)（Qt 官方口径），字体/DPI/行高变了判据不改；paintEvent 与自检共用此式。"""
        out = []
        with contextlib.suppress(Exception):
            off = self.contentOffset(); vh = self.viewport().height(); b = self.firstVisibleBlock()
            while b.isValid() and len(out) < limit:
                r = self.blockBoundingGeometry(b).translated(off)
                top = int(r.top())
                if top > vh + 24: break
                if b.isVisible() and top + int(r.height()) > 0:
                    out.append((int(b.blockNumber()) + 1, top))
                b = b.next()
        return out
    def lnr_paint(self, ev):
        try:
            p = QPainter(self.lnr); fm = self.fontMetrics()
            p.fillRect(ev.rect(), QColor("#eef3f8")); p.setPen(QColor("#4c5a68"))
            for num, y in self.lnr_rows():
                if y + fm.ascent() > 0: p.drawText(4, y + fm.ascent(), str(num))
            p.end()
        except Exception: pass               # 行号失败绝不影响预览正文
    def lnr_highlight(self):
        with contextlib.suppress(Exception):
            sel = QTextEdit.ExtraSelection(); sel.format.setBackground(QColor("#dfeaf5"))
            sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            sel.cursor = self.textCursor(); sel.cursor.clearSelection()
            self.setExtraSelections([sel])
    def line_count(self):
        return int(self.blockCount())


class Terminal(QPlainTextEdit):
    """终端件 E（批41）：面板只管成像与缓冲——进程由 Shell._termSpawn 起（QProcess·无控制台窗口·
    随窗口 closeEvent 收净）。上色按 fax.term_line_kind（纯算式真源在镜像件）。"""
    def __init__(self, win=None):
        super().__init__(); self.win = win
        self.setObjectName("term"); self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        f = QFont("Cascadia Mono"); f.setStyleHint(QFont.StyleHint.Monospace); self.setFont(f)
        self.lines = []                       # [(kind, text)]
    def put(self, kind, text):
        """一行进缓冲＋成像（kind 缺省＝按 fax.term_line_kind 判色）；多行文本逐行入缓冲。"""
        t = str(text or "")
        for one in (t.split("\n") if t else [""]):
            k = kind or fax.term_line_kind(one)
            self.lines.append((k, one))
            c = self.textCursor(); c.movePosition(c.MoveOperation.End)
            fmt = QTextCharFormat(); fmt.setForeground(QColor(TERM_INK.get(k, "#cfe6d8")))
            c.insertText(one + "\n", fmt)
        self.lines = self.lines[-4000:]
        sb = self.verticalScrollBar(); sb.setValue(sb.maximum())
        return kind or fax.term_line_kind(t.split("\n")[0])
    def tail(self, n=200):
        return "\n".join(t for _k, t in self.lines[-int(n or 200):])
    def wipe(self):
        self.clear(); self.lines = []

TERM_INK = {"sh": "#33ff66", "out": "#9fd8c0", "meta": "#54d9ff", "err": "#ff5252",
            "sys": "#ffb02e"}          # 终端面板用色（CRT 同族·由 fax 配色补值）


class TermIn(QLineEdit):
    """终端输入行（批41）：`!xxx`＝系统 shell（QProcess 起 sys_shells 本体＝`!` 真源，权限门继承）；
    `:元指令`／裸内置词／话语＝一律交 Shell.submit → shell_core.handle（同 TUI·唯一路由口·不新建第二条）。
    Enter 执行 · ↑↓ 终端历史。"""
    def __init__(self, win):
        super().__init__(win); self.win = win
        self.setObjectName("termIn")
        f = QFont("Cascadia Mono"); f.setStyleHint(QFont.StyleHint.Monospace); self.setFont(f)
    def keyPressEvent(self, ev):
        k = ev.key()
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter): self.win.termRun(); return
        if k in (Qt.Key.Key_Up, Qt.Key.Key_Down): self.win.termHist(k == Qt.Key.Key_Up); return
        super().keyPressEvent(ev)


class Input(QPlainTextEdit):
    """上方输入（t8 CRT 送稿口，批40 起居机身第一格）：Enter 提交 · Ctrl+Enter 换行 · ↑↓ 历史 · Tab 元指令补全——
    keyPressEvent 与路由/stop/ask 口径一字未改；CRT 只是叠加成像：绿字黑底（#33ff66 系·QSS cmd[crt="1"]）
    ＋扫描线叠加＋余辉衰减＋块光标闪烁。算式真源＝shell_qt_fax.crt_*（单点），绘制＝_crt_overlay，
    走进程内 QTimer·零新端口、零新进程、零子线程。"""
    def __init__(self, win):
        super().__init__(win); self.win = win; self.hist_pos = None
        self.setObjectName("cmd"); self.setProperty("crt", "1")   # QSS 对位镜像件送稿口区（CRT 实色底）
        self.crt_on = True; self.crt_force = False; self._glow_t = time.time(); self._cur_on = True
        self.setPlaceholderText("话语回车 → 当前 agent 数据流 · :help 元指令 · stop/停止 收口当前任务 · quit 退出（Ctrl+Enter 换行 · ↑↓ 历史 · Tab 补全）")
        f = QFont("Cascadia Mono"); f.setStyleHint(QFont.StyleHint.Monospace); self.setFont(f)
        self.setFixedHeight(64)
        self.textChanged.connect(self._crt_glow)
        self.t_crt = QTimer(self); self.t_crt.timeout.connect(self._crt_blink); self.t_crt.start(500)
        with contextlib.suppress(Exception): self.style().polish(self)

    def _crt_glow(self):
        """打字＝荧光粉重新点亮：余辉计时归零（衰减算式＝fax.crt_afterglow）。"""
        self._glow_t = time.time()

    def _crt_blink(self):
        """块光标闪烁（500ms 进程内 QTimer·不动文本模型）。"""
        self._cur_on = not bool(getattr(self, "_cur_on", True))
        with contextlib.suppress(Exception): self.viewport().update()

    def crt_cursor_rect(self):
        """块光标矩形（视口坐标·宽≈0.62 字宽＝fax.crt_block_cursor）。"""
        r = self.cursorRect()
        try:
            r.setWidth(fax.crt_block_cursor(self.fontMetrics().averageCharWidth() or 8))
        except Exception:
            r.setWidth(7)
        return r

    def crt_scan(self):
        """扫描线 y 位表（每 3px 一条·真源＝fax.crt_scanlines）。"""
        with contextlib.suppress(Exception):
            return fax.crt_scanlines(self.viewport().height(), 3)
        return []

    def _crt_overlay(self, p, w=0, h=0):
        """CRT 三层成像（余辉→扫描线→块光标）画到任意 painter：paintEvent 与自检走同一条路。"""
        vp = self.viewport()
        c = fax.crt_colors()
        g = fax.crt_afterglow((time.time() - float(getattr(self, "_glow_t", time.time()))) * 1000.0)
        r = QRect(0, 0, int(w or vp.width()), int(h or vp.height()))
        wash = QColor(c["glow"]); wash.setAlpha(int(96 * g))
        p.fillRect(r, wash)
        pen = QColor("#000000"); pen.setAlpha(70); p.setPen(pen)
        for y in self.crt_scan():
            if y < r.height(): p.drawLine(0, y, r.width(), y)
        cr = QRect()
        if getattr(self, "_cur_on", True) and (self.hasFocus() or getattr(self, "crt_force", False)):
            cr = self.crt_cursor_rect()
            p.fillRect(cr, QColor(c["fg"]))
            txt = self.toPlainText(); idx = self.textCursor().position()
            ch = txt[idx] if 0 <= idx < len(txt) else ""
            if ch.strip(): p.setPen(QColor(c["bg"])); p.drawText(cr, Qt.AlignmentFlag.AlignCenter, ch)
        return {"glow": round(g, 4), "scanlines": len(self.crt_scan()), "cursor": not cr.isNull()}

    def paintEvent(self, ev):
        super().paintEvent(ev)               # 文本照常由 QPlainTextEdit 绘（输入语义不变）
        if not getattr(self, "crt_on", True): return
        try:
            p = QPainter(self.viewport()); self._crt_overlay(p); p.end()
        except Exception: pass               # 成像失败不得影响输入与路由
    def keyPressEvent(self, ev):
        k, m = ev.key(), ev.modifiers()
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if m & Qt.KeyboardModifier.ControlModifier:
                self.insertPlainText("\n"); return
            self.win.submit(self.toPlainText()); return
        if k == Qt.Key.Key_Tab:
            self.win.complete(self); return
        if k in (Qt.Key.Key_Up, Qt.Key.Key_Down) and self.toPlainText().count("\n") == 0:
            if self.win.history(self, k == Qt.Key.Key_Up): return
        super().keyPressEvent(ev)



class Shell(QMainWindow):
    """传真机机身容器（批41 收尾口径＝上送稿口＋下左右分屏）：装配由 shell_qt_fax.build() 产出——root 只两格
    ＝上 B 送稿口＋下 QSplitter 左右分屏（左 A 纸卷区｜右栏 psplit 竖列三格＝C 墨水屏（常驻第一格·Ctrl+I 只聚焦
    永不 hide）→D 预览→E 终端·三格 childrenCollapsible=False 不可折叠拖没·可切分）；按需层只剩控制面板
    （META 键阵·F1 六组·拨号盘）与抽屉（Ctrl+M·装配即 hide），主页面底部条带已撤（no_bottom_strip）＝提示迁
    QLCD 小标 eink_stat、走纸队列 fax.roll_next 六态逐条推进绘于纸面；顶部原生菜单栏与名牌横条仍不装，
    菜单职能＝命令面板 Ctrl+K＋右键菜单（条目同源 MENU_ITEMS·preview/terminal 同源·快捷键保 QAction 级）；
    路由/并行/停止/提问/明细一律沿用旧壳引擎件（终端 E 也只是再起一条 core.handle 子进程·不新建第二条口径）。"""
    # 批41：右栏两件的控件类（镜像件 build() 按 win.PREVIEW_CLS／win.TERM_CLS／win.TERM_IN_CLS 取类，
    # 缺类回落基件——版式与件清单只 shell_qt_fax.build 一处，本文件只供行为类）
    PREVIEW_CLS = Preview
    TERM_CLS = Terminal
    TERM_IN_CLS = TermIn

    def __init__(self):
        super().__init__()
        self.setWindowTitle("sms-shell · 传真机图形壳（免密钥·默认 smsystem-suit 数据流）")
        self.resize(1420, 860)
        self.running, self.pend, self.hist, self.details = {}, [], [], []
        self.seq = self.bus_off = self.hi = 0
        self.awaiting = None; self.task_prog = ""; self.steps = []; self.editors = []
        self._bus_off = None; self._info = {}; self._panel = ""; self._last_out = ""
        self._tasks_cache = {}; self._eink_on = True     # 批41 收尾：C 常驻＝开机即聚焦态
        self.cut_state = "idle"; self.cut_seq = 0; self._cut_timer = None
        # 批41 收尾 走纸队列（偏差③）：逐条打印推进——算式真源＝fax.ROLL_STEPS/roll_next，此处只接线与绘制
        self.roll_state = "idle"; self.roll_q = []; self.roll_seq = 0; self.roll_strike = 0
        self.roll_stall = False; self.roll_cur = None; self._roll_timer = None
        self._view_i = 0; self._pv_src = ""; self._pv_lines = 0
        self._term_hist = []; self._term_hi = 0; self.term_procs = []   # 批41 预览/终端状态
        try:
            import session_reg as sr; SELF = sr.bind("client", os.getpid(), "Qt壳")
            os.environ.setdefault("SMS_SESSION", SELF)
        except Exception: pass
        self._ui(); self._timers()      # 批40 零顶栏：不挂 menuBar（菜单＝命令面板 Ctrl+K＋右键菜单）
        self._side_i = 0
        self.echo(core.banner())
        with contextlib.suppress(Exception):
            sb = core.startup_block(); sb and self.echo(sb)
        with contextlib.suppress(Exception):
            import ask_channel; ask_channel.arm()
        self.fax("pollAll")

    # ---------- 装配（批41：无 menuBar·无 brand 横条·上送稿口＋下左右分屏＋按需层） ----------
    def _ui(self):
        self.ent = Input(self)
        self.fw = fax.build(self, self.ent)              # 批41 骨架（版式真源＝网页端·零顶栏＋分屏装配）
        self.setStyleSheet(fax.qss())
        self.out = self.fw["roll"]; self.drawer = self.fw["drawer"]
        # 批41 收尾（偏差②）：主页面底部条带撤销——原 QLabel#statusbar 不再进主布局，
        # 提示文本迁进 C 墨水屏顶部「墨水小标」（fw["eink_stat"]＝QLabel#einkStat·实色无动效）。
        # self.stat 改指那只墨水件：既有 self.stat.setText(...) 调用点（on_over 等）一字不改＝不留第二条口径。
        # Editor 窗口内部的 self.stat 是另一件（不动）；QLabel#statusbar 的 QSS 保留供 Editor 用。
        self.stat = self.fw["eink_stat"]
        self.stat.setTextFormat(Qt.TextFormat.PlainText)
        self.stat.setText("● 就绪 · 上送稿口 Enter 送稿 · 下左右分屏（左纸卷 A｜右 墨水屏 C 常驻／预览 D／终端 E）· "
                          "Tab 补全 · Ctrl+K 命令面板（顶栏替代）· Ctrl+V 五视图轮转 · Ctrl+D 预览 · Ctrl+U 终端 · "
                          "Ctrl+B 终端上纸卷 · Ctrl+M 控制面板 · Ctrl+I 聚焦墨水屏 · Ctrl+E 裁纸 · Ctrl+G 走纸 · "
                          "Ctrl+R CRT · 右键＝机身菜单 · 免密钥（本机窗口）· F3 速查 · F8 编辑器 · F12 停止")
        with contextlib.suppress(Exception):
            self.fw["pv_open"].returnPressed.connect(
                lambda: self.previewOpen(self.fw["pv_open"].text()))
        self.previewOpen("")                             # 开机取一次预览（取不到＝内置兜底＋纸面报错·不静默）
        self._menu_actions()                             # QAction 快捷键＝原 menuBar 条目（同源不复制口径）

    def _timers(self):
        self.t_ui = QTimer(self); self.t_ui.timeout.connect(self.tick); self.t_ui.start(150)
        self.t_ask = QTimer(self); self.t_ask.timeout.connect(self.ask_poll); self.t_ask.start(400)
        self.t_bus = QTimer(self); self.t_bus.timeout.connect(self.bus_poll); self.t_bus.start(1000)
        self.t_task = QTimer(self); self.t_task.timeout.connect(lambda: self.fax("pollTasks")); self.t_task.start(4000)

    # ---------- 顶栏替代件（批40 零顶栏：命令面板＋右键菜单·原菜单条目一字不差搬入） ----------
    MENU_ITEMS = (
        ("速查 :help", "shell", lambda w: w.echo(core.HELP), "F3"),
        ("命令表 :cmds", "shell", lambda w: w._meta("cmds"), "Ctrl+H"),
        ("技能清单 :skills", "shell", lambda w: w._open("skills"), ""),
        ("会话拓扑 :session overview", "shell", lambda w: w._meta("session", "overview"), "Ctrl+J"),
        ("任务总览面板", "shell", lambda w: w._open("tasks"), "Ctrl+T"),
        ("配置面板", "shell", lambda w: w._open("config"), "Ctrl+P"),
        ("权限面板", "shell", lambda w: w._open("perms"), ""),
        ("编辑器（:edit）", "shell", lambda w: w.open_editor(), "F8"),
        ("巡检 ALL", "shell", lambda w: w.fax("pollAll"), "F5"),
        ("重启壳（换前端 :restart）", "shell", lambda w: w.submit(":restart"), ""),
        ("撕纸清屏", "fax", lambda w: w.fax("tear"), ""),
        ("复制输出", "fax", lambda w: w.fax("copyAll"), "Ctrl+Shift+C"),
        ("下载 .txt", "fax", lambda w: w.fax("dl"), ""),
        ("详细细节（长输出）", "fax", lambda w: w._open("detail"), ""),
        ("跨会话明细", "fax", lambda w: w._open("bus"), ""),
        ("合上抽屉", "fax", lambda w: w.fax("closeDrawer"), ""),
        ("裁纸 CUT（五态推进）", "fax", lambda w: w.fax("cut"), "Ctrl+E"),
        ("墨水屏消息面板（常驻右栏上格·三段·无动效）", "fax", lambda w: w.fax("eink"), "Ctrl+I"),
        ("走纸 ROLL（逐条打印推进·六态含卡纸）", "fax", lambda w: w.fax("roll"), "Ctrl+G"),
        ("CRT 送稿口成像开关", "fax", lambda w: w.fax("crt"), "Ctrl+R"),
        ("控制面板展开/收起", "fax", lambda w: w.fax("ctl"), "Ctrl+M"),
        ("视图轮转（纸卷／送稿／墨水屏／预览／终端）", "fax", lambda w: w.fax("view"), "Ctrl+V"),
        ("预览 D 取数（空＝/api/detail·填＝/api/file·/api/files）", "fax",
         lambda w: w.fax("preview", w.fw["pv_open"].text()), "Ctrl+D"),
        ("预览 D 折叠/展开（右栏上下分屏）", "fax", lambda w: w.fax("pvFold"), ""),
        ("预览 D 重载当前源", "fax", lambda w: w.fax("pvReload"), ""),
        ("终端 E 执行输入行（QProcess·同 shell_core.handle 口径）", "fax",
         lambda w: w.fax("termRun"), "Ctrl+U"),
        ("终端 E 折叠/展开", "fax", lambda w: w.fax("termFold"), ""),
        ("终端 E 缓冲回灌纸卷 A", "fax", lambda w: w.fax("termPaper"), "Ctrl+B"),
        ("终端 E 清空缓冲", "fax", lambda w: w.fax("termClear"), ""),
        ("命令面板（顶栏替代）", "fax", lambda w: w.fax("palette"), "Ctrl+K"),
        ("界面口径（网页端镜像·免密钥）", "help", lambda w: w.echo(w.about_text()), ""),
        ("关于", "help", lambda w: w.echo(core.banner()), ""),
    )

    def about_text(self):
        return ("本壳＝sms-shell 网页端传真机界面的本机镜像·批41 上送稿口＋下左右分屏（零顶栏沿用批40）：上＝B 送稿口"
                "（CRT 绿字黑底·扫描线·余辉·块光标·常驻第一位），其下左右分屏＝左 A 纸卷区（出纸正文＋状态行 "
                "LCD 六格/LED 七灯＋裁纸刀）｜右＝D 预览（QPlainTextEdit＋行号栏自绘·取数一律进程内 /api/files·"
                "/api/file·/api/detail）＋E 终端（内嵌面板·QProcess 复用 shell_core.handle·`!` 与内置命令同 TUI·"
                "随窗口收净不留孤儿）；右栏 psplit 三格＝C 墨水屏→D 预览→E 终端（常驻·不可折叠（childrenCollapsible=False）·可切分），下按需层依次 控制面板（Ctrl+M）→抽屉"
                "（META 键阵·F1 六组·拨号盘）、抽屉＝按需展开（Ctrl+M·装配即 hide）。Ctrl+V 轮转＝五态"
                "（纸卷 A／送稿 B／墨水屏 C／预览 D／终端 E·位次真源＝fax.VIEW_NAMES）。机身不挂原生菜单栏、不装 brand 横条——"
                "菜单职能由命令面板 Ctrl+K（条目同源 MENU_ITEMS·出口同实体键）＋右键菜单承担，快捷键一律保 QAction 级。"
                "版式与键位现取 web_page.html，数据经 web_shell 面板件进程内直调——GUI 端不做任何密钥验证："
                "不开端口、不读/不显影/不复制 token，LCD 只标『本机直连』；主页面底部条带已撤＝提示迁墨水小标 "
                "eink_stat、走纸态由 roll_next 六态（feed/print/advance/tear/idle＋jam）逐条推进。"
                "路由仍走 shell_core（同 TUI）。")

    def _menu_actions(self):
        """MENU_ITEMS → QAction（挂窗口不挂菜单栏＝零顶栏下 F3/F5/F8/Ctrl+* 全部入口不丢）。"""
        self.acts = []
        for label, _grp, fn, sc in self.MENU_ITEMS:
            a = QAction(label, self)
            a.triggered.connect(lambda _f=fn: _f(self))
            with contextlib.suppress(Exception):
                sc and a.setShortcut(QKeySequence(sc))
            self.addAction(a); self.acts.append(a)
        return len(self.acts)

    def palette_rows(self, q=""):
        """命令面板数据源（纯构造·可离线单测·不新建口径）：META 元指令＋F1 快捷＋常用拨号＋拨号盘
        ＋抽屉面板＋MENU_ITEMS 动作＋最近历史 → [(组, 名, 副标, 可调用)]，kw 模糊过滤。"""
        kw = str(q or "").strip().lower()
        rows = []
        META_, METAD_, PAD_, QUICK_, F1_ = (self.fw.get("keys") or fax.keys())
        for m in META_ or []:
            sub = METAD_.get(m, "") if isinstance(METAD_, dict) else ""
            rows.append(("元指令", ":" + m, sub, lambda c=":" + m: self.feed(c + " ")))
        for _g, items in (F1_ or []):
            for cmd, name in items:
                rows.append(("快捷", name, str(cmd).strip(), lambda c=cmd: self.faxPick(c)))
        for lab, c in QUICK_ or []:
            rows.append(("拨号", lab, str(c).strip(), lambda _c=c: self.feed(_c)))
        for k, c, lab in PAD_ or []:
            rows.append(("盘面", "%s %s" % (k, lab), str(c).strip(), lambda _c=c: self.feed(_c)))
        for menu_id, (title, src) in fax.DRAWERS.items():
            rows.append(("面板", title, menu_id, lambda s=src, t=title: self._open(s, t)))
        for label, grp, fn, sc in self.MENU_ITEMS:
            rows.append(("动作·" + grp, label, sc or "", lambda _f=fn: _f(self)))
        for h in self.hist[-12:]:
            rows.append(("历史", str(h)[:70], "回车重发", lambda t=h: self.feed(t)))
        if not kw:
            return rows
        return [r for r in rows if any(kw in str(x or "").lower() for x in (r[0], r[1], r[2]))]

    def palette(self):
        """命令面板＝被去掉的顶部菜单的全量替代（Ctrl+K）：过滤＋↑↓＋回车执行＋Esc 关闭。
        出口一律同实体键/菜单（feed／faxPick／_open／submit）＝路由仍 shell_core.handle，不新建口径。"""
        win = self
        box = QDialog(win); box.setObjectName("palette")
        box.setWindowTitle("命令面板 · 顶栏替代（零顶栏·条目同源 MENU_ITEMS·出口同实体键）")
        box.resize(780, 480)
        v = QVBoxLayout(box); v.setContentsMargins(8, 8, 8, 8); v.setSpacing(6)
        holder = {"rows": []}

        def run_row():
            i = box.lst.currentRow(); rows = holder["rows"]
            if not (0 <= i < len(rows)):
                box.done(0); return
            fn = rows[i][3]
            box.done(0)
            try:
                fn()
            except Exception as e:
                win.paper("系统", "命令面板执行失败：%s: %s" % (type(e).__name__, str(e)[:120]), "err")

        def fill():
            rows = win.palette_rows(box.ed.text()); holder["rows"] = rows
            box.lst.clear()
            for kind, name, sub, _fn in rows[:400]:
                box.lst.addItem(QListWidgetItem("%-9s %s%s" % (kind, name, ("   " + sub) if sub else "")))
            box.lst.setCurrentRow(0)

        class Edit(QLineEdit):
            def keyPressEvent(self, ev):
                k = ev.key()
                if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter): run_row(); return
                if k == Qt.Key.Key_Escape: box.done(0); return
                if k == Qt.Key.Key_Down:
                    box.lst.setCurrentRow(min(box.lst.count() - 1, 0)); box.lst.setFocus(); return
                super().keyPressEvent(ev)

        class List(QListWidget):
            def keyPressEvent(self, ev):
                k = ev.key()
                if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter): run_row(); return
                if k == Qt.Key.Key_Escape: box.done(0); return
                if k == Qt.Key.Key_Up: self.setCurrentRow(max(0, self.currentRow() - 1)); return
                if k == Qt.Key.Key_Down: self.setCurrentRow(min(self.count() - 1, self.currentRow() + 1)); return
                if len(ev.text() or "") and ev.text().strip():
                    box.ed.setFocus(); box.ed.keyPressEvent(ev); return
                super().keyPressEvent(ev)

        box.ed = Edit(box); box.ed.setObjectName("palEdit")
        box.ed.setPlaceholderText("输入过滤（元指令／动作／面板／快捷／历史）· 回车执行 · Esc 关闭 · 顶栏替代 Ctrl+K")
        box.ed.setFont(fax._f(14))
        box.lst = List(box); box.lst.setObjectName("palList"); box.lst.setFont(fax._f(13))
        box.lst.setAlternatingRowColors(True)
        v.addWidget(box.ed); v.addWidget(box.lst, 1)
        hint = QLabel("↑↓ 选择 · 回车执行 · Esc 关闭 · 与实体键/右键菜单同源（MENU_ITEMS·不第二条口径）")
        hint.setObjectName("hint"); hint.setFont(fax._f(11, False)); v.addWidget(hint)
        box.ed.textChanged.connect(fill)
        box.lst.itemDoubleClicked.connect(lambda _i=None: run_row())
        fill(); box.ed.setFocus()
        box.exec()
        with contextlib.suppress(Exception):
            win.ent.setFocus()
        return {"ok": True, "rows": len(holder["rows"])}

    def contextMenuEvent(self, ev):
        """右键菜单＝零顶栏下的常驻菜单入口（光标在纸卷上只给纸动作，其余给全量三段）。"""
        in_roll = False
        with contextlib.suppress(Exception):
            in_roll = bool(self.fw["roll"].underMouse())
        m = QMenu(self)
        groups = ("fax",) if in_roll else ("shell", "fax", "help")
        for label, grp, fn, sc in self.MENU_ITEMS:
            if grp not in groups: continue
            a = QAction(label, self)
            a.triggered.connect(lambda _f=fn: _f(self))
            m.addAction(a)
        m.exec(ev.globalPos() if hasattr(ev, "globalPos") else ev.pos())

    # ---------- 机身动作（网页端同名动作的 Qt 对应体·函数名字面一致便于对照） ----------
    def feed(self, text):
        """填入送稿口（网页端 setCmd 同义）：焦点回进纸器、光标落末尾。"""
        self.ent.setPlainText(text or ""); c = self.ent.textCursor()
        c.movePosition(c.MoveOperation.End); self.ent.setTextCursor(c); self.ent.setFocus()

    def feedNow(self):
        self.submit(self.ent.toPlainText())

    def fax(self, act, arg=None):
        """机身/抽屉动作分派（异常一律卡纸打纸，不外抛·不静默）。"""
        try:
            fn = {"pollAll": self.pollAll, "pollTasks": self.pollTasks, "pollInfo": self.pollInfo,
                  "pollSolo": self.pollSolo, "pollQQ": self.pollQQ, "doStop": lambda a=None: self.stop_one(""),
                  "doResume": self.doResume, "tear": self.tear, "copyAll": self.copyAll, "dl": self.dl,
                  "speakLast": self.speakLast, "closeDrawer": self.closeDrawer,
                  "cut": self.cut, "cutStep": self._cut_step, "eink": self.einkToggle,
                  "roll": self.rollToggle, "rollStep": self._roll_step, "rollClear": self.rollClear,
                  "crt": self.crtToggle, "ctl": self.ctlToggle, "view": self.viewToggle,
                  "palette": self.palette,
                  "preview": self.previewOpen, "pvFold": self.pvToggle, "pvReload": self.pvReload,
                  "termRun": lambda a=None: self.termRun(), "termFold": self.termFold,
                  "termPaper": self.termPaper, "termClear": lambda a=None: self.termClear(),
                  "previewDetail": lambda a=None: self.previewOpen(""),
                  "hist(-1)": lambda a=None: self.history(True), "hist(1)": lambda a=None: self.history(False),
                  "clear()": lambda a=None: self.feed("")}.get(act)
            if fn is None: return self.paper("系统", "机身无此动作：%s" % act, "sys")
            r = fn(arg) if arg is not None else fn()
            if isinstance(r, dict) and r.get("err"): self.paper("系统", "卡纸：%s（%s）" % (act, r["err"]), "err")
            return r
        except Exception as e:
            self.paper("系统", "机身动作 %s 异常：%s: %s" % (act, type(e).__name__, str(e)[:140]), "err")

    def faxPick(self, cmd):
        """F1 六组键：`#` 前缀＝机身动作、`:` 前缀＝填入送稿口、其余（path:…）＝原样填。"""
        c = str(cmd or "").strip()
        if c.startswith("#"):
            d = fax.DRAWERS.get(c)
            if d and not str(d[1]).startswith("@"): return self._open(d[1], d[0])
            return {"@copy": self.copyAll, "@stop": lambda: self.stop_one(""),
                    "@resume": self.doResume}.get(str(d[1] if d else ""), lambda: self.feed(c))()
        if c.startswith(":"): return self.feed(c if c.endswith(" ") else c + " ")
        if c.startswith("path:"): return self._open("skills", "按路径加入技能")
        return self.feed(c + " ")

    # ---------- 抽屉面板 ----------
    def _open(self, name, title=None):
        """开抽屉：数据＝网页端同路径 /api/<name>（进程内直调·scrub 去密钥面）。"""
        d = fax.DRAWERS
        title = title or next((v[0] for v in d.values() if v[1] == name), name)
        self._panel = name
        if name == "bus":
            data = {"lines": list(self.details)[-80:]}
        else:
            path = "/api/" + ({"ws": "files", "mode": "hud", "sys": "commands"}.get(name, name))
            data = fax.api(path, {"ws": self._ws_hint()} if name in ("files", "file") else None)
        self.fw["dtitle"].setText("⑤ 抽屉面板 · " + title)
        self.fw["dbody"].setHtml(fax.panel_html(name, data))
        self.drawer.show()
        if isinstance(data, dict) and data.get("err"):
            self.paper("系统", "面板 %s 卡纸：%s" % (name, data["err"]), "err")

    def _ws_hint(self):
        with contextlib.suppress(Exception):
            import workspace; return workspace.current()
        return ""

    def closeDrawer(self):
        self.drawer.hide(); self._panel = ""

    def refreshDrawer(self):
        if getattr(self, "_panel", "") in ("tasks", "perms", "config", "bus"): self._open(self._panel)

    # ---------- 出纸口（网页端 print()/jam() 同构·米纸逐行走） ----------
    def paper(self, who, text, cls="", body_html=None):
        """出纸一行（网页端 print 同义）：who＝徽标（我/系统/agent/错误/模型提问），cls＝纸面色类。"""
        if not str(text).strip() and body_html is None: return
        self.papers = getattr(self, "papers", 0) + 1
        self._last_out = str(text)
        self.out.append(fax.line_html(who, text, cls, body_html))
        sb = self.out.verticalScrollBar(); sb.setValue(sb.maximum())
        self.roll_enqueue((who, str(text), cls))    # 批41 收尾：一条出纸＝一行进给（纸面已落·此处只驱动走纸）

    def copyAll(self):
        QApplication.clipboard().setText(self.out.toPlainText())
        self.paper("系统", "输出已复制（%d 字）" % len(self.out.toPlainText()), "sys")

    def dl(self):
        p = os.path.join(os.environ.get("SMS_TMP") or core.SMS,
                         "sms-fax-%s.txt" % time.strftime("%Y%m%d-%H%M%S"))
        try:
            io.open(p, "w", encoding="utf-8").write(self.out.toPlainText())
            self.paper("系统", "已下载 → %s" % p, "sys")
        except Exception as e: self.paper("系统", "下载失败：%s" % str(e)[:120], "err")

    def tear(self):
        """撕纸清屏：纸卷清空回纸头（明细/任务总览面板不受影响）。"""
        self.out.clear(); self.cut_state = "idle"; self._cut_apply()
        self.roll_q = []; self._roll_end()       # 批41 收尾：回纸头＝走纸队列一并清空回待机
        self.paper("系统", "已撕纸·出纸口回纸头", "sys")

    # ---------- t6 裁纸刀（出纸末端·状态推进：进程内 QTimer 走步·零新端口零新进程零子线程） ----------
    def cut(self, arg=None):
        """✂ 裁纸 CUT：起一轮裁纸（feed→clamp→cut→drop→idle），每步 200ms 由进程内 QTimer 推进；
        途中再点＝中止回待机（状态一律上刀条标签，不静默、不外抛）。"""
        if getattr(self, "_cut_timer", None) is not None:
            self._cut_end("裁纸中止 TRIM HALT")
            self.paper("系统", "裁纸中止·刀条回待机", "sys"); return {"ok": "halt"}
        self._cut_timer = QTimer(self); self._cut_timer.timeout.connect(self._cut_step)
        self._cut_timer.start(200)
        self.cut_state = "idle"; self._cut_apply()
        self.paper("系统", "裁纸开始：纸张送出→压脚压纸→刀刃下行→断纸落盘", "sys")
        return {"ok": "run"}

    def _cut_end(self, msg=""):
        with contextlib.suppress(Exception):
            self._cut_timer.stop(); self._cut_timer.deleteLater()
        self._cut_timer = None; self.cut_state = "idle"; self._cut_apply()
        if msg: self.banner(msg, "warn")

    def _cut_step(self):
        """推进一态（真源＝fax.cut_next）：落 drop＝纸面留裁断印记并计数，落 idle＝本轮收口。"""
        self.cut_state = fax.cut_next(self.cut_state)
        self._cut_apply()
        if self.cut_state == "drop":
            self.cut_seq += 1
            self.paper("裁纸", "", "sys", body_html=fax.cut_mark(self.cut_seq))
        elif self.cut_state == "idle":
            self._cut_end()
            self.paper("系统", "裁纸完成：第 %d 裁落盘（纸面 %d 字）" %
                       (self.cut_seq, len(self.out.toPlainText())), "sys")
        return self.cut_state

    def _cut_apply(self):
        """当前态刷到刀条视觉：QFrame#blade[st=…] 五态渐变＋标签文案/行程百分比＋裁纸指示灯。"""
        st = self.cut_state
        try:
            b = self.fw["blade"]; b.setProperty("st", st); b.style().unpolish(b); b.style().polish(b)
            tg = self.fw["blade_tag"]; tg.setText(fax.cut_label(st))
            tg.setStyleSheet("color:%s;font-size:11px;letter-spacing:1px;font-weight:bold" %
                             (fax.css_vars().get({"stop": "red", "warn": "amber", "go": "grn"}
                                                  .get(fax.cut_tone(st), ""), "") or "#4c5a68"))
            self.fw["blade_pos"].setText("行程 %d%%" % round(fax.cut_progress(st) * 100))
        except Exception: pass
        self.led("裁纸", "off" if st == "idle" else ("warn" if fax.cut_tone(st) == "warn"
                                                   else "err" if fax.cut_tone(st) == "stop" else "on"))

    # ---------- 批41 收尾 走纸队列（偏差③：纸面逐条打印推进·算式真源＝fax.ROLL_STEPS/roll_next） ----------
    # 与 t6 裁纸同族：只用进程内 QTimer（180ms 一步）——不新增线程件（Task worker 仍是唯一 worker 件）、
    # 不新增进程/端口；纸面 HTML 一律复用 fax.roll_mark→line_html 与 fax.jam_html，渲染真源仍只一份。
    def rollPaper(self, who, text, cls="sys"):
        """走纸机制自身的系统提示＝上纸面但不进队列（防自激励活锁：完成提示再排队→再完成→……）。"""
        self._roll_suppress = True
        try:
            self.paper(who, text, cls)
        finally:
            self._roll_suppress = False

    def roll_enqueue(self, item):
        """一条出纸＝一行进给（idle 就地起步·在跑只排队，由 _roll_step 逐条取）。"""
        if getattr(self, "_roll_suppress", False): return
        if item not in self.roll_q: self.roll_q.append(item)
        if self.roll_state == "idle" and self._roll_timer is None:
            self._roll_begin()

    def _roll_begin(self):
        if self._roll_timer is not None: return
        self._roll_timer = QTimer(self); self._roll_timer.timeout.connect(self._roll_step)
        self._roll_timer.start(180)
        self.roll_state = "idle"; self._roll_apply()

    def rollToggle(self, arg=None):
        """⎈ 走纸 ROLL／Ctrl+G：待机＝起一轮逐条打印推进；卡纸＝人工清纸续打；在跑＝中止回待机。"""
        if self.roll_state == "jam": return self.rollClear()
        if self._roll_timer is not None:
            self._roll_end()
            self.rollPaper("系统", "走纸中止：回走纸待机 ROLL IDLE")
            return {"ok": "halt"}
        self._roll_begin()
        self.rollPaper("系统", "走纸开始：咬纸→逐行打印→行进给→（队列取空）撕纸线→待机")
        return {"ok": "run"}

    def rollClear(self, arg=None):
        """卡纸恢复（网页端 jam 同档）：jam→print 续打同一行·受阻计数归零。"""
        if self.roll_state != "jam":
            self.rollPaper("系统", "无卡纸可清（当前＝%s）" % fax.roll_label(self.roll_state))
            return {"ok": False}
        self.roll_strike = 0; self.roll_stall = False
        self.roll_state = fax.roll_next("jam", cleared=True); self._roll_apply()
        self.rollPaper("系统", "卡纸已清·续打同一行（%s）" % fax.roll_label(self.roll_state))
        return {"ok": True}

    def _roll_end(self, state="idle"):
        with contextlib.suppress(Exception):
            if self._roll_timer is not None:
                self._roll_timer.stop(); self._roll_timer.deleteLater()
        self._roll_timer = None; self.roll_state = state; self.roll_cur = None; self.roll_stall = False
        self._roll_apply()

    def _roll_step(self):
        """推进一态（真源＝fax.roll_next）：print＝从队列取一条打走纸印记；advance＝受阻探测（三次即卡纸）；
        队列取空＝advance→tear 打撕纸线再回 idle；jam＝原地等人清纸（不静默、不外抛）。"""
        try:
            st = self.roll_state
            if st == "jam":
                self._roll_apply(); return st
            if st == "print" and self.roll_q:
                self.roll_cur = self.roll_q.pop(0)
                self.roll_seq += 1; self.roll_strike = 0    # 新一行＝受阻计数归零（jam 判据锁同一行）
                self._roll_print_mark()
            if st == "advance":
                self._roll_nudge()
                if self.roll_stall:
                    self.roll_strike += 1
                    if fax.roll_should_jam(self.roll_strike):
                        self.roll_state = fax.roll_next(self.roll_state, jam=True)
                        self._roll_apply()
                        self.out.append(fax.jam_html("走纸受阻 %d 次·同一行进给不到位"
                                                    "（⎈ 走纸 ROLL／Ctrl+G＝人工清纸）" % self.roll_strike))
                        self.roll_stall = False
                        self.banner("卡纸 JAM", "err")
                        return self.roll_state
                    self.roll_stall = False
                    self._roll_apply()
                    return self.roll_state          # 同一行原地重试（不越行＝逐条打印推进的真语义）
                self.roll_strike = 0
            at_end = (not self.roll_q) and (st == "advance")
            self.roll_state = fax.roll_next(st, at_end=at_end)
            self.roll_stall = False
            self._roll_apply()
            if self.roll_state == "tear":
                self.rollPaper("系统", "走纸一轮完成：第 %d 条·纸面 %d 字（撕纸线已打·回待机）" %
                               (self.roll_seq, len(self.out.toPlainText())))
            elif self.roll_state == "idle":
                self._roll_end()
            return self.roll_state
        except Exception as e:
            self.paper("系统", "走纸推进异常：%s: %s" % (type(e).__name__, str(e)[:120]), "err")
            self._roll_end()
            return "idle"

    def _roll_print_mark(self):
        """本条走纸印记（渲染真源＝fax.roll_mark→line_html·不复制第二份 HTML 生成）。"""
        self.out.append(fax.roll_mark(self.roll_seq, self.roll_state))
        sb = self.out.verticalScrollBar(); sb.setValue(sb.maximum())

    def _roll_apply(self):
        """当前走纸态刷到机身视觉：mouth/tear[st=…] 换底＋rollTag 文案与进给百分比＋裁纸指示灯（同族复用）。"""
        st = self.roll_state
        try:
            for k in ("mouth", "tear"):
                b = self.fw[k]; b.setProperty("st", st); b.style().unpolish(b); b.style().polish(b)
            tg = self.fw["roll_tag"]; tg.setText(fax.roll_label(st))
            tg.setStyleSheet("color:%s;font-size:11px;letter-spacing:1px;font-weight:bold" %
                             (fax.css_vars().get({"stop": "red", "warn": "amber", "go": "grn"}
                                                  .get(fax.roll_tone(st), ""), "") or "#4c5a68"))
        except Exception: pass

    def _roll_nudge(self):
        """行进给受阻探测（判据＝网页端 jam 同档·只看「正在打印的那一条」：错误行/Traceback/停止旗标，
        自检可钉死 _roll_force_stall）。不扫纸面尾部——否则清卡后旧 JAM 印记被当成新受阻，永远回不了 idle。"""
        try:
            txt = str((self.roll_cur or ("", "", ""))[1] or "")
            stall = (bool(getattr(self, "_roll_force_stall", False)) or fax.term_line_kind(txt) == "err"
                     or txt.strip().startswith("\u2717") or "Traceback" in txt
                     or (stop.is_stop_word(txt[-24:]) if txt.strip() else False))
            self.roll_stall = bool(stall)
        except Exception: pass

    # ---------- t8 CRT 送稿口开关（成像层开/关·键盘与路由口径不动） ----------
    def crtToggle(self, arg=None):
        on = not bool(self.ent.crt_on)
        self.ent.crt_on = on
        with contextlib.suppress(Exception):
            self.ent.setProperty("crt", "1" if on else "")
            self.ent.style().unpolish(self.ent); self.ent.style().polish(self.ent)
            self.ent.viewport().update()
        self.paper("系统", "CRT 送稿口成像层＝%s（绿字黑底·扫描线·余辉·块光标；键盘与路由口径不变）" %
                   ("开" if on else "关"), "sys")
        return {"ok": on}

    # ---------- 控制面板按需化（批40 零顶栏起：控制面不常驻·按需展开） ----------
    def ctlToggle(self, arg=None):
        """控制面板（META 键阵／F1 六组／拨号盘）展开/收起——去顶栏后控制件不常驻，Ctrl+M 唤出。"""
        z = self.fw.get("ctlzone")
        if z is None:
            self.paper("系统", "机身无控制面板件（ctlzone）", "err"); return {"ok": False}
        show = not bool(z.isVisible())
        z.setVisible(show)
        if show:
            with contextlib.suppress(Exception):
                sb = self.fw["roll"].verticalScrollBar(); z.setParent(self) if False else None
            self.paper("系统", "控制面板已展开（META 键阵 %d 键 · F1 六组 · 拨号盘 12 位）——Ctrl+M 收起" %
                       len((self.fw.get("keys") or fax.keys())[0] or []), "sys")
        with contextlib.suppress(Exception):
            self.fw["ctlzone_btn"].setText("▦ 收起控制面 Ctrl+M" if show else "▦ 控制面板 Ctrl+M")
        self._hud("ctl", "控制面板 " + ("展开" if show else "收起"), 600)
        return {"ok": show}

    def viewToggle(self, arg=None):
        """视图循环（批41 五态·位次真源＝fax.VIEW_NAMES＋fax.view_next）：
        纸卷 A／送稿 B／墨水屏 C／预览 D／终端 E（五态齐序·前两态与批40 逐字同义）：C 态＝psplit 常驻
        第一格只聚焦/展开（永不 hide），D／E 态＝右栏两格互让展开（1280×720 也满幅可用）。"""
        self._view_i = fax.view_next(getattr(self, "_view_i", 0))
        names = tuple(fax.VIEW_NAMES)
        if self._view_i == 2:                                  # C 墨水屏（批41 收尾＝常驻件·此态只做聚焦/展开）
            self._eink_on = True
            with contextlib.suppress(Exception):
                self.fw["einkzone"].setVisible(self._eink_on)      # 批41：常驻不收起
                self.fw["psplit"].setSizes([420, 280])
            self.einkRefresh()
        with contextlib.suppress(Exception):                   # A 态才谈控制面板（Ctrl+M 按需）
            self.fw["ctlzone"].setVisible(self._view_i == 0 and bool(self.fw["ctlzone"].isVisible()))
        if self._view_i == 3:                                  # D 预览展开·终端让位
            with contextlib.suppress(Exception):
                self.fw["previewzone"].setVisible(True); self.fw["termzone"].setVisible(True)
                self.fw["psplit"].setSizes([220, 560, 200])   # 批41 收尾：右列两格（D／E）（C 常驻·D 满幅）
            if not self._pv_src: self.previewOpen("")
        if self._view_i == 4:                                  # E 终端展开·预览让位
            with contextlib.suppress(Exception):
                self.fw["previewzone"].setVisible(True); self.fw["termzone"].setVisible(True)
                self.fw["psplit"].setSizes([220, 200, 560])   # 批41 收尾：右列两格（D／E）（C 常驻·E 满幅）
            with contextlib.suppress(Exception): self.fw["term_in"].setFocus()
        self.paper("系统", "视图焦点＝%s（五视图轮转 Ctrl+V·上送稿口＋下左右分屏）" %
                   names[self._view_i], "sys")
        return {"ok": names[self._view_i], "i": self._view_i}

    # ---------- 批41 预览件 D：代码/文件预览＋行号栏（数据一律进程内 /api/*，绝不新建 HTTP·绝不读 token） ----------
    def _pv_candidates(self):
        """裸名回查候选目录（批45·去重保序）：工作区根 → SMS_TMP → 当前目录——
        生成件一律落 <工作区>\tmp\，而 /api/files 只列所给目录顶层，只问工作区根必 miss（抽屉/送稿口裸名）。
        仍只走进程内 /api/files?ws=…（core `_under` 白名单校验），不新建 HTTP、不读密钥、不碰文件系统直读。"""
        seen, out = set(), []
        for d in (self._ws_hint(), os.environ.get("SMS_TMP") or "", os.getcwd()):
            d = str(d or "").strip()
            if d and d.replace("\\", "/").rstrip("/").lower() not in seen:
                seen.add(d.replace("\\", "/").rstrip("/").lower()); out.append(d)
        return out

    def previewOpen(self, target=""):
        """取数三路（与网页端同名·全经 fax.api 进程内直调）：
        空＝/api/detail（长输出留档）；带路径＝/api/file?path=…；否则＝裸名进候选目录逐个 /api/files?ws=… 回查命中。
        任一路 err＝preview_text 内置兜底＋纸面「卡纸」，不静默。"""
        t = str(target or "").strip().strip('"')
        data, how = {}, ""
        try:
            if not t:
                data, how = fax.api("/api/detail"), "/api/detail"
            elif t.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", t):
                data, how = fax.api("/api/file", query={"path": t}), "/api/file?path=…"
            else:
                base = t.replace("\\", "/").rsplit("/", 1)[-1]
                if "/" in t or "\\" in t:
                    data, how = fax.api("/api/file", query={"path": t}), "/api/file?path=…"
                else:
                    hit, roots = "", self._pv_candidates()
                    for d in roots:                          # 批45 候选目录回查（顶层列不到＝下一候选）
                        lst = fax.api("/api/files", query={"ws": d})
                        hit = next((x.get("path") for x in (lst.get("files") or [])
                                    if str(x.get("name") or "") == base), "")
                        if hit:
                            break
                    if hit:
                        data = fax.api("/api/file", query={"path": hit})
                        how = "/api/file?path=…"
                    else:   # 候选全 miss＝明确 err（不把目录列表充当文件内容·不静默）
                        data = {"err": "裸名未在候选目录命中：%s（回查 %d 个根）"
                                % (base, len(roots))}
                        how = "/api/files?ws=…"
            r = fax.preview_text(data, t or how)
        except Exception as e:
            r = {"text": fax.FALLBACK_TEXT, "err": "%s: %s" % (type(e).__name__, str(e)[:120]),
                 "name": t, "lines": 0, "fallback": True}
            how = how or "内置兜底"
        ed = self.fw["preview"]
        ed.setPlainText(r["text"])
        with contextlib.suppress(Exception): ed.lnr_highlight()
        self._pv_src = r["name"] or t or how
        self._pv_lines = int(r["lines"] or 0)
        with contextlib.suppress(Exception):
            self.fw["pv_stat"].setText("预览源＝进程内 %s · %s 行 · %s%s" % (
                how, self._pv_lines, self._pv_src[:60],
                " · 兜底样本" if r["fallback"] else ""))
        if r["err"]:
            self.paper("系统", "预览取数卡纸：%s（%s·已落内置兜底文本）" % (r["err"][:140], how), "err")
        self._hud("pv", "预览 %s 行" % self._pv_lines, 1200)
        return {"ok": True, "lines": self._pv_lines, "src": self._pv_src,
                "fallback": bool(r["fallback"]), "err": r["err"]}

    def pvReload(self, arg=None):
        return self.previewOpen(self._pv_src or "")

    def pvToggle(self, arg=None):
        """预览折叠/展开（右栏上下分屏·与终端互让）——两件都可折叠，切分由 QSplitter 手柄承担。"""
        z = self.fw.get("previewzone")
        if z is None:
            self.paper("系统", "机身无预览件（previewzone）", "err"); return {"ok": False}
        show = not bool(z.isVisible())
        z.setVisible(show)
        with contextlib.suppress(Exception):
            ps = self.fw["psplit"]
            ps.setSizes([170, 520, 200] if show else [170, 24, 700])  # 批41 收尾：右列两格（D／E）（C 份额不动）
        self.paper("系统", "预览 D＝%s（Ctrl+D 折叠/展开 · 右栏上下可切分）" % ("展开" if show else "折叠"), "sys")
        return {"ok": show}

    # ---------- 批41 终端件 E：QProcess 复用 shell_core.handle 路由（`!` 系统 shell 与内置命令同 TUI） ----------
    def _termSpawn(self, line):
        """起一条 QProcess（同一份路由真源）：子进程内 import shell_core 后 handle(line)——
        `:` 元指令、`!` 系统 shell、裸内置词、话语一律与 TUI/网页端逐字同口径；stdout 逐行回灌面板。
        无控制台窗口（QProcess 管道直连·不走裸壳调用），进程登记在 self.term_procs 由 closeEvent 收净。"""
        code = ("import sys,os,io;"
                "sys.stdout.reconfigure(encoding='utf-8',errors='replace');"
                "p=r'%s';sys.path.insert(0,p);"
                "import shell_core as c;line=sys.stdin.read();"
                "c.handle(line,lambda s:print(str(s),flush=True),"
                "lambda n:print('▸ '+str(n),flush=True))") % S.replace("'", "")
        p = QProcess(self)
        p.setProgram(sys.executable)
        p.setArguments(["-B", "-c", code])
        p.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        p.setWorkingDirectory(self._ws_hint() or S)
        try:    # 以系统环境为底（裸表会丢 PYTHONPATH→子进程 import shell_core 缺 no_window）
            from PyQt6.QtCore import QProcessEnvironment
            env = QProcessEnvironment.systemEnvironment()
            env.insert("PYTHONUTF8", "1"); env.insert("PYTHONIOENCODING", "utf-8")
            env.insert("SMS_FRONT", "qt-term")
            env.insert("PYTHONPATH", S + os.pathsep + (env.value("PYTHONPATH") or ""))
            p.setProcessEnvironment(env)
        except Exception: pass
        p.readyReadStandardOutput.connect(lambda: self._termDrain(p))
        p.finished.connect(lambda rc, cs: self._termDone(p, rc, cs))
        p.errorOccurred.connect(lambda e: self.fw["term"].put("err", "进程错误：%s" % e))
        self.term_procs.append(p)
        p.start()
        with contextlib.suppress(Exception):
            p.write(line.encode("utf-8")); p.closeWriteChannel()   # 话语走 stdin，写完即关＝子进程不挂等
        self.fw["term"].put("sh", "$ " + line)
        self._termUpdate("执行中 %s（QProcess·无控制台窗口）" % line[:30])
        return p

    def _termDrain(self, p):
        with contextlib.suppress(Exception):
            for one in bytes(p.readAllStandardOutput()).decode("utf-8", "replace").split("\n"):
                self.fw["term"].put(None, one)          # 空行也进缓冲＝与 TUI 版面一致

    def _termDone(self, p, rc, cs):
        with contextlib.suppress(Exception): self.term_procs.remove(p)
        self.fw["term"].put("err" if int(rc) else "sys", "rc=%s（%s）" % (rc, cs))
        self._termUpdate("待机 · 退出码 %s" % rc)
        p.deleteLater()

    def _termUpdate(self, msg):
        with contextlib.suppress(Exception): self.fw["t_stat"].setText("终端·" + msg)
        self.led("线路", "warn" if self.term_procs else "on")

    def termRun(self, arg=None):
        ti = self.fw.get("term_in")
        line = str(ti.text() if ti else "").strip()
        if not line: return {"ok": False}
        with contextlib.suppress(Exception): ti.setText("")
        self._term_hist.append(line); self._term_hist = self._term_hist[-60:]; self._term_hi = len(self._term_hist)
        return {"ok": True, "proc": bool(self._termSpawn(line))}

    def termHist(self, up=True):
        if not self._term_hist: return False
        self._term_hi = max(0, min(len(self._term_hist) - 1,
                                   self._term_hi + (-1 if up else 1)))
        with contextlib.suppress(Exception):
            self.fw["term_in"].setText(self._term_hist[self._term_hi])
        return True

    def termFold(self, arg=None):
        z = self.fw.get("termzone")
        if z is None:
            self.paper("系统", "机身无终端件（termzone）", "err"); return {"ok": False}
        show = not bool(z.isVisible())
        z.setVisible(show)
        with contextlib.suppress(Exception): self.fw["psplit"].setSizes([170, 240, 500] if show else [170, 620, 24])
        self.paper("系统", "终端 E＝%s（Ctrl+U 折叠/展开）" % ("展开" if show else "折叠"), "sys")
        return {"ok": show}

    def termPaper(self, arg=None):
        """终端缓冲回灌纸卷 A（输出上纸面·走同一 paper 出口）。"""
        t = self.fw["term"].tail(200)
        if not t.strip():
            self.paper("系统", "终端缓冲为空，无可回灌", "sys"); return {"ok": 0}
        self.paper("终端", "回灌 %d 行" % (t.count("\n") + 1), "sys",
                   body_html="<pre>%s</pre>" % esc(t[:20000]))
        return {"ok": t.count("\n") + 1}

    def termClear(self, arg=None):
        self.fw["term"].wipe(); self._termUpdate("已清空缓冲（在跑进程不受影响）")
        return {"ok": True}

    def termAlive(self):
        return [p for p in self.term_procs if p.state() != QProcess.ProcessState.NotRunning]

    def termStopAll(self):
        """收进程（closeEvent 与自检共用）：先 terminate 等 900ms，未退再 kill——绝不留孤儿。"""
        gone = 0
        for p in list(self.term_procs):
            with contextlib.suppress(Exception):
                if p.state() != QProcess.ProcessState.NotRunning:
                    p.terminate(); p.waitForFinished(900)
                    if p.state() != QProcess.ProcessState.NotRunning:
                        p.kill(); p.waitForFinished(600)
                gone += 1
        self.term_procs = [p for p in self.term_procs if p.state() != QProcess.ProcessState.NotRunning]
        return gone

    # ---------- t10 墨水屏消息面板（只三段·无动效·数据仍走进程内 api） ----------
    def einkToggle(self, arg=None):
        """Ctrl+I（批41 口径）＝C 墨水屏＝ psplit 第一格 常驻件（永不 hide·Ctrl+I 聚焦）。
        C 无收起态＝任何路径不得 hide（门禁 eink_resident/eink_no_hide）；所谓让位只是份额收缩（setSizes），可见性永不翻转。"""
        self._eink_on = True                                  # 批41：C 常驻＝永不 hide，Ctrl+I 只聚焦
        with contextlib.suppress(Exception):
            self.fw["einkzone"].setVisible(True)
            self.fw["psplit"].setSizes([300, 420, 280])
            self.fw["eink"].setFocus()
        if self._eink_on:
            self.einkRefresh()
            self.paper("系统", "墨水屏已展开（会话信息／任务总览／后台任务·无动效·常驻第一格·再按 Ctrl+I 只聚焦不收起）", "sys")
        return {"ok": "on" if self._eink_on else "off"}

    def eink_bg(self):
        """后台任务＝进程内在跑/排队（本壳 worker·不起新进程）。"""
        out = [(tid, str(info.get("text") or "")[:60],
                time.time() - float(info.get("t0") or time.time()))
               for tid, info in (self.running or {}).items()]
        out += [("排队", str(t)[:60], 0.0) for t in (self.pend or [])]
        return out

    def einkRefresh(self):
        """墨水屏刷新（批41 收尾：C 常驻＝每轮巡检都刷，不再被开关门挡·数据只取 fax.api 结果与进程内明细）。"""
        try:
            self.fw["eink"].setHtml(fax.eink_html(self._info, self._tasks_cache, self.eink_bg()))
        except Exception as e:
            self.paper("系统", "墨水屏刷新失败：%s" % str(e)[:100], "err")

    def speakLast(self):
        t = (self._last_out or "").strip()
        if not t: return self.paper("系统", "无可朗读内容", "sys")
        try:
            import tts; r = tts.speak(t[:600], False)
            self.paper("系统", "已朗读末条（%s）" % str(r)[:60], "sys")
        except Exception as e: self.paper("系统", "朗读不可用：%s" % str(e)[:100], "err")

    def doResume(self):
        r = fax.api("/api/resume", {})
        self.paper("系统", r.get("err") and ("续跑受阻：" + r["err"]) or "已请求续跑未完成计划表（网页壳同口径）", "sys")
        self.pollTasks(); return r


    # ---------- 送稿（路由真源＝shell_core.handle·与 TUI/网页端逐字同口径） ----------
    def echo(self, s, kind=""):
        """兼容旧口径的输出入口：可见正文→出纸口（着色），非可见行→明细（右栏/抽屉）。"""
        t = str(s)
        if not t.strip(): return
        if kind != "raw" and not msg_flow.visible(t):
            if not msg_flow.blank(t): self._push(t)
            return
        self._push_cache(t)
        who = {"me": "我", "err": "错误", "info": "系统"}.get(kind, "系统")
        cls = {"me": "me", "err": "err", "info": "sys"}.get(kind, "")
        body = "<br>".join(badge(paint(x)) or "&nbsp;" for x in t.split("\n"))
        self.paper(who, "", cls, body_html=body)

    def _push_cache(self, t):
        ("$ " in t or ".py" in t or ".md" in t or "config:" in t) and self.steps.append(t[:160]) if len(self.steps) < 4000 else None
    def _push(self, t):
        d = self.details
        if d and d[-1].startswith(("◌", "〔◌")) and t.startswith(("◌", "〔◌")) and len(d[-1]) < 3000:
            d[-1] = d[-1] + " " + t.lstrip("◌ ")
        else: d.append(t[:3000])
        self.details = d[-150:]
        if getattr(self, "_panel", "") == "bus": self.refreshDrawer()

    def _par(self):
        try: return bool(st.get("shell.parallel", True))
        except Exception: return True
    def _cap(self):
        try: return int(st.get("shell.max_parallel", 4) or 0)
        except Exception: return 4
    def _room(self):
        if not self._par(): return not self.running
        c = self._cap()
        return not c or len(self.running) < c

    def submit(self, text):
        text = (text or "").strip(); self.ent.setPlainText("")
        if not text: return
        w = text.split(" ", 1); one = w[1].strip() if len(w) > 1 else ""
        if stop.is_stop_word(text) or (stop.is_stop_word(w[0]) and one in self.running):
            self.stop_one(one); return
        if self.awaiting:
            import ask_channel
            self.echo("sms> （答复）" + text, kind="me")
            ask_channel.reply(text, self.awaiting[0]); self.awaiting = None; return
        lo = text.lower()
        if lo in (":gui", ":qt", "gui"):
            self.hist.append(text); self.hi = len(self.hist)
            self.echo("当前＝传真机图形壳（shell_qt.py 镜像网页端 · 免密钥）· Qt %s · 并行 %d/%s · 明细 %d 条\n"
                      "三视图件：✂ 裁纸 CUT（fax.cut_next 五态推进·进程内 QTimer）· CRT 送稿口（绿字黑底＋扫描线"
                      "＋余辉＋块光标·键盘口径不变）· ▤ 墨水屏（只三段：会话信息／任务总览／后台任务·无动效）\n"
                      "可用本地指令：:gui 本壳状态 · :clear 撕纸清屏 · :reload 巡检/重开抽屉 · tui 另起 Textual 终端壳；"
                      "其余 `:` 元指令一律交 shell_core（同 TUI/网页端）。" % (
                          self.qtver(), len(self.running), (self._cap() or "无限"), len(self.details)), kind="info")
            return
        if lo in (":clear", ":reload"):
            self.hist.append(text); self.hi = len(self.hist)
            if lo == ":clear": self.tear()
            else: self.fax("pollAll"); self.refreshDrawer()
            return
        if lo in ("tui", ":tui"):
            self.hist.append(text); self.hi = len(self.hist)
            _dn = open(os.devnull, "r+b")
            # sms-visible：GUI 另起可见 Textual TUI 终端壳（有意开新控制台窗·与 shell_gui.py 同口径）
            subprocess.Popen([sys.executable, "-B", os.path.join(S, "shell_tui_textual.py")],
                             stdin=_dn, stdout=_dn, stderr=_dn, close_fds=True)
            self.echo("已另起 Textual TUI 终端壳", kind="info"); return
        self.hist.append(text); self.hi = len(self.hist)
        if not self._room():
            self.pend.append(text)
            self.echo("已排队 %d 条 · %s·有空位自动续发" % (len(self.pend),
                      "并发已达上限 %d" % self._cap() if self._par() else "并行已关（:config set shell.parallel false）"),
                      kind="info")
            return
        self.start(text)

    def start(self, text):
        self.seq += 1; tid = "t%d" % self.seq
        self.echo("sms> %s%s" % (text, ("   〔并行第 %d 个任务〕" % (len(self.running) + 1)) if self.running else ""),
                  kind="me")
        self.running[tid] = {"text": text, "t0": time.time()}
        self._hud("session", (text[:60] or "sms-shell GUI"), 1800)
        w = Task(text, tid)
        w.line.connect(lambda s, t=tid: self.on_line(t, s))
        w.step.connect(lambda s, t=tid: self.on_step(t, s))
        w.env.connect(lambda e, t=tid: self.on_env(t, e))
        w.over.connect(self.on_over)
        w.start(); self.running[tid]["w"] = w
        self.tick()

    def on_line(self, tid, s):
        tag = ("[%s] " % tid) if len(self.running) > 1 else ""
        t = str(s)
        if msg_flow.visible(t): self.echo((tag or "") + t)
        elif not msg_flow.blank(t): self._push((tag + t)[:3000])
    def on_step(self, tid, n):
        tag = ("[%s] " % tid) if len(self.running) > 1 else ""
        self._push(tag + "▸ " + str(n)); self.last_step = str(n)
        self._hud("step", str(n)[:80], 120)
    def on_env(self, tid, e):
        try:
            if not isinstance(e, dict): return
            k, m = e.get("kind"), e.get("meta") or {}
            if k == "task":
                eta = int(m.get("eta_s") or 0)
                self.task_prog = "≡ %s %s/%s%s" % (str(m.get("id", ""))[-6:], m.get("done", 0),
                                                   m.get("total", 0), (" · " + msg_flow.fmt(eta)) if eta else "")
                self.fw["lcd_任务总览"].setText(self.task_prog)
            elif k == "edit":
                self._push("✎ " + str(e.get("text") or ""))
            elif k == "err":
                self.echo("✗ " + str(e.get("text") or ""), kind="err")
        except Exception: pass
    def on_over(self, tid, done):
        info = self.running.pop(tid, None) or {}
        el = time.time() - float(info.get("t0") or time.time())
        if self.awaiting and self.awaiting[0] == tid: self.awaiting = None
        if self.running:
            self.echo("✔ 任务 %s 收口（%.1fs）·仍在并行跑 %d 个：%s" %
                      (tid, el, len(self.running), "、".join(sorted(self.running))), kind="info")
        else:
            self.stat.setText("● 就绪 · 上一条用时 %.1fs · 明细 %d 条（F3 速查 · F8 编辑器 · F5 巡检）" %
                              (el, len(self.details)))
            self._hud("hide", "", 0)
        if isinstance(done, str) and done.startswith(("edit:", "view:")):
            self.open_editor(done.split(":", 1)[1], ro=done.startswith("view:")); done = None
        if done == "exit": self.close(); return
        if done == "config": self.echo(core._cfgline())
        self.refreshDrawer(); self.pollTasks()
        while self.pend and self._room(): self.start(self.pend.pop(0))

    def stop_one(self, one=""):
        if self.awaiting:
            import ask_channel; ask_channel.reply("用户已请求停止任务（stop）", self.awaiting[0]); self.awaiting = None
        if one and one in self.running:
            stop.request("GUI 输入 stop " + one, one)
            self.echo("⛔ 已请求停止任务 %s（其余 %d 个不受影响）" % (one, len(self.running) - 1), kind="info"); return
        if one and one not in self.running:
            self.echo("无此在跑任务：%s（现行 %s）" % (one, "、".join(sorted(self.running)) or "无"), kind="info"); return
        if self.running:
            for tid in list(self.running): stop.request("GUI 输入 stop（全部）", tid)
            self.echo("⛔ 已请求停止全部 %d 个在跑任务——各任务在下一检查点收口" % len(self.running), kind="info"); return
        r = fax.api("/api/stop", {"why": "传真机壳 STOP 键（无在跑任务·清停止旗标）"})
        stop.clear(); self.echo("空闲：无进行中任务·停止状态已清（%s）" % str(r.get("status") or "")[:60], kind="info")
    def stop_all(self): self.stop_one("")


    # ---------- 巡检（LCD/指示灯/纸卡/抽屉·数据＝web_shell 面板件进程内直调） ----------
    def tick(self):
        self._side_i = getattr(self, "_side_i", 0) + 1
        if self._side_i % 40 == 0: self.pollInfo()
        if self._side_i % 20 == 0: self.pollSolo(); self.pollQQ()
        n = len(self.running)
        sp = SPIN[int(time.time() * 8) % 10] if n else "●"
        sess = conv = "-"
        with contextlib.suppress(Exception): sess = core.chains.cur_sess()
        with contextlib.suppress(Exception): conv = (_envs().get("SMS_CONV") or "-")
        el = " · 已用 %.0fs" % (time.time() - min(float(v.get("t0") or time.time())
                                                  for v in self.running.values())) if n else ""
        cur = self.task_prog or getattr(self, "last_step", "") or "进纸待机"
        try:
            self.fw["lcd_会话"].setText("%s · %s" % (str(sess)[-8:], str(conv)[-8:]))
            self.fw["lcd_模式"].setText("对话 · 并行 %d · 排队 %d%s" % (n, len(self.pend), el))
        except Exception: pass
        if n: self.banner("送稿中 %.0fs%s" % (time.time() - min(float(v.get("t0") or 0)
                                            for v in self.running.values()), el), "warn")
        if self._side_i % 13 == 0: self._bus_ui()

    def banner(self, text, tone=""):
        b = self.fw["banner"]; b.setText(text)
        b.setObjectName({"warn": "lcdWarn", "err": "lcdErr"}.get(tone, "banner"))
        b.setStyleSheet("color:%s;font-size:11px" % {"warn": fax.css_vars().get("amber"),
                                                    "err": fax.css_vars().get("red")}.get(tone) or "#3c4a58")

    def led(self, name, state):
        lab = self.fw.get("led_" + name)
        if lab is None: return
        col = {"on": fax.css_vars().get("grn"), "warn": fax.css_vars().get("amber"),
               "err": fax.css_vars().get("red"), "off": "#55606c"}.get(state, "#55606c")
        lab.setText(("● " if state == "on" else "◆ " if state == "warn" else
                     "✸ " if state == "err" else "○ ") + name)
        lab.setStyleSheet("color:%s;font-size:11px" % col)

    def pollInfo(self):
        i = fax.api("/api/info")
        if i.get("err"): return self.led("线路", "err")
        self._info = i
        g = i.get("gateway") or {}
        try:
            self.fw["lcd_网关"].setText("%s · %s" % ("on" if g.get("enabled") else "off", g.get("model") or "-"))
            self.fw["lcd_线路"].setText("本机直连 · 免密钥（GUI 不开端口）")
            self.fw["lcd_状态"].setText(i.get("session") and "SOLO on" or "就绪")
        except Exception: pass
        self.led("线路", "on")
        self.led("对外", "warn" if (i.get("external") or {}).get("enabled") else "off")
        self.led("做梦", "on" if (i.get("dream") or {}).get("enabled") else "off")
        self.led("朗读", "on" if (i.get("tts") or {}).get("enabled") else "off")

    def pollSolo(self):
        r = fax.api("/api/perms")
        if r.get("err"): return
        s = r.get("solo") or {}
        self.led("线路", "warn" if s.get("enabled") else "on")
        try: self.fw["lcd_状态"].setText("SOLO %s" % ("on·权限自审" if s.get("enabled") else "off·需确认"))
        except Exception: pass

    def pollQQ(self):
        """QQ 灯（批46 灯数校平）：与网页端 pollQQ 同名同路＝进程内直调 web_shell g_qq（/api/qq）。
        err＝off（取不到不谎报已连）·开＝on·关＝off；返回值一律 fax.api scrub 后，绝不显影 openid/appId/
        clientSecret——图形壳免密钥面口径一字未改。七灯自此全驱动（线路/QQ/朗读/做梦/计划/裁纸/对外）。"""
        r = fax.api("/api/qq")
        self.led("QQ", "off" if (r.get("err") or not r.get("enabled")) else "on")
        return {"ok": not r.get("err"), "enabled": bool(r.get("enabled")), "err": bool(r.get("err"))}

    def pollTasks(self):
        r = self._tasks_cache = fax.api("/api/tasks")
        if r.get("err"):
            self.fw["lcd_任务总览"].setText("巡检不可用"); self.led("计划", "err"); return
        rows = r.get("rows") or []
        dn = r.get("done", 0); tot = r.get("total", 0); un = r.get("unfinished", 0)
        self.fw["lcd_任务总览"].setText("%s/%s %s · %s" % (dn, tot, str(r.get("tid") or "-")[-6:],
                                                        r.get("eta") or "-") if tot else "无未完成")
        show = bool(tot and un > 0)
        self.fw["btn_stop"].setVisible(show); self.fw["btn_go"].setVisible(show)
        if show:
            self.fw["btn_stop"].setText("⏸ 停止 %d/%d" % (dn, tot))
            self.fw["btn_go"].setText("▶ 继续 %d/%d" % (dn, tot))
        self.led("计划", "warn" if show else "off")
        if getattr(self, "_panel", "") == "tasks": self.refreshDrawer()
        self.einkRefresh()

    def pollAll(self):
        self.pollInfo(); self.pollSolo(); self.pollQQ(); self.pollTasks()
        self.paper("系统", "巡检完成（线路/QQ/LCD/指示灯/任务总览）", "sys")
        return {"ok": True}

    def ask_poll(self):
        if self.awaiting: return
        try:
            import ask_channel; r = ask_channel.poll_any()
        except Exception: return
        if not r: return
        tid, q = r; self.awaiting = (tid, q)
        self.paper("模型提问", ("〔任务 %s〕" % tid if tid else "") + str(q), "ask")
        self.banner("等答复%s" % ("（%s）" % tid if tid else ""), "warn")

    def bus_poll(self):
        try:
            if self.bus_off is None:
                p = detail_bus.path(core.SMS)
                self.bus_off = os.path.getsize(p) if os.path.isfile(p) else 0
                return
            own = os.environ.get("SMS_SESSION") or ""
            off, rows = detail_bus.tail(self.bus_off, 120, core.SMS)
            self.bus_off = off
            for e in rows:
                if e.get("sess") == own: continue
                line = "〔%s·%s〕%s" % (str(e.get("sess") or "-")[-6:], e.get("kind"), str(e.get("text") or ""))
                self._push(line)
            if rows and getattr(self, "_panel", "") == "bus": self.refreshDrawer()
        except Exception: pass
    def _bus_ui(self): pass

    # ---------- 沿用件 ----------
    def _hud(self, key, text, ttl):
        try:
            self._hud_last = getattr(self, "_hud_last", {})
            k = "hud:" + key; now = time.time()
            last_txt, last_at = self._hud_last.get(k, ("", 0))
            if key != "hide" and text == last_txt and now - last_at < 2.0: return
            self._hud_last[k] = (text, now)
            import hud
            if key == "hide": hud._hide(); return
            hud._set(key, text, ttl)
        except Exception: pass
    def _meta(self, cmd, rest=""):
        self.submit(":%s%s" % (cmd, (" " + rest) if rest else ""))
    def open_editor(self, path="", ro=False):
        path = path or (os.environ.get("SMS_TMP") or core.SMS)
        if os.path.isdir(path):
            e = Editor(os.path.join(path, "untitled.md"), ro); path = os.path.join(path, "untitled.md")
        else: e = Editor(path, ro)
        e.show(); self.editors.append(e)
        self.paper("系统", "已打开编辑器（%s）：%s" % ("查看" if ro else "编辑", path), "sys")
    def history(self, up):
        if not self.hist: return True
        self.hi = max(0, min(len(self.hist), self.hi + (-1 if up else 1)))
        self.set_text_line(self.hist[self.hi] if self.hi < len(self.hist) else "")
        return True
    def set_text_line(self, t):
        self.ent.setPlainText(t)
        c = self.ent.textCursor(); c.movePosition(c.MoveOperation.End); self.ent.setTextCursor(c)
    def complete(self, ent):
        txt = ent.toPlainText()
        if not txt.strip().startswith(":"): return
        cand = [":" + m for m in (self.fw.get("keys") or fax.keys())[0]]
        cand += [":%s" % m for m in ("help", "cmds", "skills", "config", "session", "dispatch", "sh", "hud",
                                     "agents", "use", "resume", "plan", "debug", "edit", "view", "deploy",
                                     "workspace", "web", "tts", "dream", "mode", "grant", "perms", "tools", "api")]
        head = txt.split("\n")[-1].strip()
        hits = sorted({c for c in cand if c.startswith(head)})
        if len(hits) == 1: ent.setPlainText(txt[: len(txt) - len(head)] + hits[0] + " ")
        elif hits: self.paper("系统", "补全候选：" + "、".join(hits[:20]), "sys")
    def qtver(self):
        try:
            from PyQt6.QtCore import QT_VERSION_STR; return QT_VERSION_STR
        except Exception: return "?"
    def probe_finish(self):
        """--probe 端到端回归：出纸口纯文本落盘并退出（CLI/CI 无窗验证路由结果）。"""
        try:
            p = os.environ.get("SMS_QT_PROBE_DUMP") or "qt_probe.txt"
            io.open(p, "w", encoding="utf-8").write(self.out.toPlainText())
            sh = os.environ.get("SMS_QT_SHOT")
            sh and self.grab().save(sh)
            print("PROBE_DUMP " + p + " chars=" + str(len(self.out.toPlainText())) +
                  " details=" + str(len(self.details)) + " keys=" + str(len(self.fw)))
        except Exception as e:
            print("PROBE_FAIL " + repr(e)[:160])
        QApplication.instance().quit()
    def closeEvent(self, ev):
        for w in list(self.running.values()):
            with contextlib.suppress(Exception): w["w"].requestInterruption(); w["w"].quit(1200)
        with contextlib.suppress(Exception): self._roll_end()   # 批41 收尾：走纸 QTimer 随窗口收净
        # 批41：内嵌终端 QProcess 随窗口收干净（terminate→kill·不留孤儿子进程）
        with contextlib.suppress(Exception): self.termStopAll()
        with contextlib.suppress(Exception):
            import ask_channel; ask_channel.disarm()
        super().closeEvent(ev)

def _envs(): return os.environ
def _c(hexcol):
    from PyQt6.QtGui import QColor; return QColor(hexcol)


def main(argv=None):
    argv = [a for a in (argv if argv is not None else sys.argv[1:]) if a != "--"]
    selftest = "--selftest" in argv
    if selftest: os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication(sys.argv[:1])
    app.setApplicationName("sms-shell-gui")
    win = Shell()
    if selftest: return _selftest(app, win)
    win.show()
    pos = [a for a in argv if a != "--selftest" and not a.startswith("--probe")]
    probe = next((a.split("=", 1)[1] for a in argv if a.startswith("--probe=")), "")
    if probe:
        os.environ["SMS_QT_PROBE_DUMP"] = os.environ.get("SMS_QT_PROBE_DUMP") or os.path.join(
            os.environ.get("SMS_TMP") or os.getcwd(), "qt_probe.txt")
        parts = [x.strip() for x in probe.split("||") if x.strip()]
        for i, one in enumerate(parts):
            QTimer.singleShot(200 + i * 400, lambda t=one: win.submit(t))
        QTimer.singleShot(int(os.environ.get("SMS_QT_PROBE_MS", "9000")), win.probe_finish)
    elif pos:
        QTimer.singleShot(120, lambda: win.submit(" ".join(pos)))
    return app.exec()

def _selftest(app, win):
    """离线自检（不发模型请求）：传真机机身成图＋机身件计数＋免密钥面核对＋行分类/上色/排队/停止/抽屉面板全跑。"""
    win.show(); app.processEvents()
    cases = ["sms-shell 速查", "• notice 行", "$ exec ls -la", "◌ 思考过程行", "▸ 步骤行", "✗ 错误行",
             "⧉general_answer▸ 派发对话正文", "! sh 输出", "≡ task 进度", "带 `代码` 与 C:\\path\\file.py 的正文"]
    for c in cases: win.on_line("t9", c)
    win.echo("用户话语测试行", kind="me")
    for e in ({"kind": "task", "meta": {"id": "task-20261009-000000-000", "done": 3, "total": 5, "eta_s": 96}},
              {"kind": "edit", "text": "已改 tmp/a.py"}):
        win.on_env("t9", e)
    win.running.setdefault("t9", {"text": "x", "t0": time.time() - 3})
    win.tick(); app.processEvents()
    win.stop_one("t9")
    win.pend.append("排队行示例")
    win.pollAll(); app.processEvents()
    panels = {}
    for nm in ("tasks", "plans", "chains", "sessions", "skills", "files", "config", "perms",
               "detail", "bus", "ws", "mode", "sys", "qq", "tts"):
        win._open(nm); app.processEvents()
        panels[nm] = len(win.fw["dbody"].toHtml())
    win._open("tasks"); app.processEvents()
    task_tbl = win.fw["dbody"].toPlainText()
    win.closeDrawer(); app.processEvents()
    win.paper("系统", "卡纸示例", "err")
    # ---- 批39 t6 裁纸刀：五态推进（按纯函数逐格走＋_cut_apply 落视觉，自检里不等 QTimer 空转） ----
    cut_seen = [win._cut_step() for _ in range(len(fax._IDS))]     # 一轮＝feed→clamp→cut→drop→idle
    win.cut_state = "cut"; win._cut_apply()
    cut_ok = (cut_seen == ["feed", "clamp", "cut", "drop", "idle"]
              and win.cut_seq == 1 and "裁纸段" in win.out.toHtml()
              and win.fw["blade"].property("st") == "cut"
              and win.fw["blade_tag"].text() == fax.cut_label("cut")
              and win.fw["blade_pos"].text().endswith("75%"))
    win.cut_state = "idle"; win._cut_apply()
    # ---- 批39 t8 CRT 送稿口：离屏走同一条绘制路（余辉＋扫描线＋块光标） ----
    from PyQt6.QtGui import QPixmap
    # 闪烁相由 t_crt（500ms）推——自检里钉死相位，取证才确定
    win.ent.crt_force = True; win.ent._cur_on = True
    win.ent.setPlainText(":cmds "); win.ent._glow_t = time.time()
    pm = QPixmap(420, 64); p = QPainter(pm); crt = win.ent._crt_overlay(p, 420, 64); p.end()
    win.ent._cur_on = False; p = QPainter(pm); crt_off = win.ent._crt_overlay(p, 420, 64); p.end()
    win.ent._cur_on = True
    win.ent.crt_force = False
    win.fax("crt"); win.fax("crt")                                  # 成像层开关（分派走 fax() 机身口）
    crt_ok = (bool(crt.get("scanlines")) and crt.get("cursor") and float(crt.get("glow") or 0) > 0
              and not crt_off.get("cursor") and win.ent.objectName() == "cmd")
    # ---- 批39 t10 墨水屏：三段面板（只三段·无动效·数据走进程内 api） ----
    win._eink_on = True; win.fw["einkzone"].show()
    win.running.setdefault("t8", {"text": "墨水屏示例话语", "t0": time.time() - 2})
    win.einkRefresh(); app.processEvents()
    eink_txt = win.fw["eink"].toPlainText(); eink_html_src = win.fw["eink"].toHtml()
    eink_ok = (all(s in eink_txt for s in fax.EINK_SECTIONS) and len(fax.EINK_SECTIONS) == 3
               and not any(bad in eink_html_src for bad in ("animation", "transition", "@keyframes"))
               and "墨水屏示例话语" in eink_txt)
    win.fax("eink"); win.fax("eink")                                # Ctrl+I 聚焦→让位→聚焦（截图留痕用聚焦态）
    win.running.pop("t8", None)
    # ---- 批41 口径：C 墨水屏＝ psplit 第一格（常驻）·aside 依次 psplit→ctl→抽屉·C 墨水屏常驻 ----
    av_lay = win.fw["aside"].layout()
    eink_idx = int(win.fw["psplit"].indexOf(win.fw["einkzone"]))   # 位次真源＝右列第四格（0 psplit/1 ctl/2 ez/3 dr）
    with contextlib.suppress(Exception):
        win._eink_on = False; win.fw["einkzone"].setVisible(True)   # batch41: C permanent (focus-only)
    app.processEvents()
    eink_resident = (eink_idx == 0 and int(win.fw["psplit"].indexOf(win.fw["previewzone"])) == 1
                     and int(win.fw["psplit"].indexOf(win.fw["termzone"])) == 2
                     and win.fw["psplit"].count() == 3
                     and int(av_lay.indexOf(win.fw["psplit"])) == 0
                     and int(av_lay.indexOf(win.fw["ctlzone"])) == 1
                     and int(av_lay.indexOf(win.fw["drawer"])) == 2
                     and win.fw["einkzone"].isVisible() and not win.fw["ctlzone"].isVisible()
                     and not win.fw["drawer"].isVisible() and not win.fw["split"].childrenCollapsible())
    win.fax("eink"); shown_by_i = bool(win.fw["einkzone"].isVisible())      # Ctrl+I＝聚焦（常驻不收起）
    win.fax("eink"); hidden_by_i = bool(win.fw["einkzone"].isVisible())     # 再按仍可见＝永不 hide
    eink_cycle = [shown_by_i, hidden_by_i]
    eink_no_hide = bool(shown_by_i)      # 判据更名保留：Ctrl+I 确实可唤出（不是死件）
    win.fax("eink")                       # 复位＝展开态，后续三段取证与截图照旧可用

    # ---- 批41 收尾 偏差②：主页面底部条带撤销（root 只两格·机身内无可见 QLabel#statusbar·提示落墨水小标） ----
    from PyQt6.QtWidgets import QLabel as _QLb
    lay0 = win.centralWidget().layout()
    strip_labels = [w for w in win.centralWidget().findChildren(_QLb)
                    if w.objectName() == "statusbar" and w.isVisibleTo(win)]
    no_bottom_strip = (lay0.count() == 2 and lay0.itemAt(0).widget() is win.fw["feeder"]
                       and lay0.itemAt(1).widget() is win.fw["split"] and not strip_labels
                       and win.stat is win.fw["eink_stat"]
                       and "Ctrl+K" in win.fw["eink_stat"].text() and "墨水屏" in win.fw["eink_stat"].text())
    # ---- 批41 收尾 偏差③：走纸队列逐条推进（同 cut 手法·手动步进不等 QTimer 空转） ----
    win._roll_end(); win.roll_q = []; win.roll_seq = 0; win.roll_strike = 0
    win.roll_q = [("我", "走纸样例一", "me"), ("我", "走纸样例二", "sys")]
    n0 = len(win.out.toHtml())
    roll_seen = [win._roll_step() for _ in range(7)]
    roll_marks = win.out.toHtml()[n0:].count("走纸")
    roll_cycle_ok = (roll_seen == ["feed", "print", "advance", "print", "advance", "tear", "idle"]
                     and win.roll_seq == 2 and roll_marks >= 2 and win._roll_timer is None
                     and not win.roll_q)
    win._roll_force_stall = True; win.roll_q = [("我", "走纸样例三", "sys")]
    win.roll_state = "idle"; win.roll_strike = 0
    jam_seen = [win._roll_step() for _ in range(6)]
    jam_in = win.roll_state == "jam" and "JAM" in win.out.toPlainText()
    win._roll_force_stall = False
    jam_clear = win.rollClear()["ok"] is True and win.roll_state == "print"
    win.roll_state = "idle"; win.roll_q = []; win._roll_apply()
    roll_ok = roll_cycle_ok and jam_in and jam_clear
    shot = os.path.join(os.environ.get("SMS_TMP") or os.getcwd(), "qt_fax_selftest.png")
    ok = win.grab().save(shot)
    from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
    META_, METAD_, PAD_, QUICK_, F1_ = win.fw.get("keys") or fax.keys()
    leak = fax.leaked(fax.api("/api/info")) or fax.leaked(fax.api("/api/perms"))
    out = {"visible_rows": getattr(win, "papers", 0),
           "roll_plain": win.out.toPlainText().count("\n"),
           "keys_total": len(win.fw), "details": len(win.details),
           "meta_keys": len(META_), "metad": len(METAD_), "pad": len(PAD_), "quick": len(QUICK_),
           "f1_groups": len(F1_), "drawers": len(fax.DRAWERS),
           "page_bytes": len(fax.page()), "qss_len": len(win.styleSheet()),
           "panels": panels, "panel_min": min(panels.values()) if panels else 0,
           "task_table_len": len(task_tbl),
           "no_token_face": not leak, "leaked_key": leak,
           "gate_removed": not hasattr(win, "gate") and not hasattr(win, "tok"),
           "no_gate_text": ("TOKEN" not in win.out.toPlainText()),
           "stop_word_hit": stop.is_stop_word("停止"), "paint_html": bool(paint("$ ls")),
           "queued": len(win.pend), "running": sorted(win.running), "screenshot": shot, "saved": bool(ok),
           "qt": QT_VERSION_STR, "pyqt": PYQT_VERSION_STR, "banner": win.fw["banner"].text(),
           "banner_len": len(core.banner()), "hud_state": os.path.join(core.SMS, "hud", "state.json"),
           "led_names": len([k for k in win.fw if str(k).startswith("led_")]),
           "cut_steps": len(fax.CUT_STEPS), "cut_seq": cut_seen, "cut_ok": cut_ok,
           "crt_overlay": crt, "crt_overlay_off": crt_off, "crt_ok": crt_ok,
           "crt_now": bool(win.ent.crt_on), "eink_ok": eink_ok, "eink_len": len(eink_txt),
           "eink_sections": list(fax.EINK_SECTIONS), "eink_now": bool(win._eink_on),
           "eink_resident": eink_resident, "eink_no_hide": eink_no_hide, "eink_cycle": eink_cycle, "eink_idx": eink_idx,
           "no_bottom_strip": no_bottom_strip, "roll_cycle": roll_cycle_ok,
           "roll_seen": roll_seen, "roll_seq": win.roll_seq, "roll_jam": bool(jam_in),
           "roll_clear": bool(jam_clear), "roll_marks": roll_marks, "roll_ok": roll_ok}
    # ---- 批40 零顶栏取证（命令面板＝顶栏替代·控制面板按需化·无菜单栏/无 brand 横条） ----
    src_self = io.open(__file__, encoding="utf-8", errors="replace").read()
    n_acts = len(getattr(win, "acts", []))
    rows_all = win.palette_rows("")
    rows_f = win.palette_rows(":cmds")
    names_all = [r[1] for r in rows_all]
    win.fax("ctl"); ctl_on = bool(win.fw["ctlzone"].isVisible())
    win.fax("ctl"); ctl_off = not bool(win.fw["ctlzone"].isVisible())
    win._eink_on = False
    with contextlib.suppress(Exception): win.fw["einkzone"].setVisible(False)
    for _ in range(2): win.fax("view")                   # 纸卷 A→送稿 B→墨水屏 C（第 3 态唤出墨水屏）
    view_i = getattr(win, "_view_i", -1)
    eink_open_by_view = bool(win._eink_on) and bool(win.fw["einkzone"].isVisible())
    win.fax("view"); win._view_i = 0
    # ---- 批41 上送稿口＋下左右分屏：预览 D／终端 E／五态轮转一律进门禁（防只改视觉不进门禁） ----
    pv = win.fw["preview"]; tm = win.fw["term"]
    tmp_dir = os.environ.get("SMS_TMP") or os.getcwd()   # 取证期列目录根＝样本所在目录
    sample = os.path.join(tmp_dir, "b41_preview_sample.txt")
    with contextlib.suppress(Exception):
        io.open(sample, "w", encoding="utf-8").write("\n".join("b41 sample line %d" % i for i in range(40)))
    pvd = win.previewOpen("")                                    # 空＝/api/detail 长输出留档
    pvr = win.previewOpen(sample) if os.path.isfile(sample) else {"lines": 0, "err": "无样本"}
    pv_rows_after = int(pv.line_count())
    pv_nums = [r[0] for r in pv.lnr_rows() if r[1] >= 0]
    _p = QPainter(pv.lnr); pv_painted = pv.lnr.width() >= 30; _p.end()
    out["pv_ws_roots"] = win._pv_candidates()                   # 批45 裸名候选目录（真 _ws_hint·不 monkeypatch）
    win.fw["pv_open"].setText(os.path.basename(sample))
    win.fax("preview", win.fw["pv_open"].text())                 # 裸名→候选目录回查命中→/api/file
    pv_by_box = int(pv.line_count()) >= 3
    win.fax("preview", sample)                                   # 绝对路径→/api/file（抽屉双击同路）
    out["pv_abs_lines"] = int(pv.line_count())
    pv_jam = win.previewOpen("no/such/file_b41.txt")             # 越界＝err＋内置兜底＋纸面卡纸
    pv_jam_paper = "预览取数卡纸" in win.out.toPlainText()
    win.fw["term_in"].setText("!echo b41term"); win.fax("termRun")
    term_started = bool(win.term_procs)
    t0 = time.time()
    while win.termAlive() and time.time() - t0 < 15.0:
        app.processEvents(); time.sleep(0.02)
    for _ in range(20):                                          # 末块输出在 finished 前经 readyRead 落缓冲
        app.processEvents(); time.sleep(0.02)
    term_tail = tm.tail(400); term_rows = len(tm.lines)
    term_rc = ("rc=" in term_tail) and ("b41term" in term_tail)
    win.fax("termPaper"); paper_after_term = win.out.toPlainText().count("\n")
    win.fax("termClear"); term_cleared = (len(tm.lines) == 0)
    win.fw["term_in"].setText("!ping -n 20 127.0.0.1"); win.fax("termRun")   # 长驻进程：验收净
    app.processEvents(); alive_before_close = len(win.termAlive())
    win.fax("termPaper")
    closed_clean = (win.termStopAll() >= 1) and not win.termAlive()
    win.fax("pvFold"); pv_fold_hidden = win.fw["previewzone"].isVisible()
    win.fax("pvFold"); pv_fold_shown = win.fw["previewzone"].isVisible()
    win.fax("termFold"); tm_fold_hidden = win.fw["termzone"].isVisible()
    win.fax("termFold")
    with contextlib.suppress(Exception):                 # 分屏可切分性取证：右栏上下各自拿到尺寸
        win.fw["psplit"].setSizes([420, 280]); app.processEvents()
    pv_sizes = list(win.fw["psplit"].sizes())
    pv_minw = (int(win.fw["preview"].minimumWidth()), int(win.fw["term"].minimumWidth()))
    win.previewOpen(pvr.get("src") or "")
    cyc = []
    for _ in range(len(fax.VIEW_NAMES)):
        r = win.fax("view"); cyc.append((win._view_i, r.get("ok")))
    win.fax("view"); win._view_i = 0
    required = ("banner", "roll", "drawer", "dtitle", "dbody", "blade", "blade_tag", "blade_pos",
                "eink", "einkzone", "ctlzone", "keys", "btn_stop", "btn_go", "btn_all", "btn_speak",
                "split", "psplit", "preview", "previewzone", "pv_open", "pv_stat", "pv_fold",
                "term", "termzone", "term_in", "t_run", "t_fold", "t_paper", "t_clear", "t_stat")
    missing = [k for k in required if k not in win.fw]
    n_acts = len(getattr(win, "acts", []))
    rows_all = win.palette_rows("")
    rows_f = win.palette_rows(":cmds")
    names_all = [r[1] for r in rows_all]
    src_self = io.open(__file__, encoding="utf-8", errors="replace").read()
    mb = "self." + "menuBar()"; nb = "SMS-" + "FAX · GUI"
    out["zero_topbar"] = (mb not in src_self and nb not in src_self
                          and all(hasattr(win, x) for x in ("palette", "palette_rows", "ctlToggle",
                                                             "contextMenuEvent", "_menu_actions")))
    out["palette_rows"] = len(rows_all); out["palette_filtered"] = len(rows_f)
    out["palette_has_meta_and_panels"] = (":cmds" in names_all and "任务总览" in names_all
                                         and "十二链" in names_all)
    out["qactions"] = n_acts; out["menu_items"] = len(win.MENU_ITEMS)
    out["ctl_cycle"] = [ctl_on, ctl_off]; out["view_cycle"] = [view_i, eink_open_by_view]
    out["fw_missing_required"] = missing
    out["lcd_cells"] = len([k for k in win.fw if str(k).startswith("lcd_")])
    out["led_lamps"] = len([k for k in win.fw if str(k).startswith("led_")])
    # ---- 批46 灯数校平取证：造几灯＝驱动几灯·QQ 灯必须真走 /api/qq（err 不谎报） ----
    qq_probe = win.pollQQ()
    led_driven = sorted({k for k in re.findall(r'self\.led\("([^"]+)"', src_self)})
    led_built = sorted({str(k)[4:] for k in win.fw if str(k).startswith("led_")})
    out["led_driven"] = led_driven
    out["led_driven_n"] = len(led_driven)
    out["led_built_n"] = len(led_built)
    out["led_parity"] = (led_built == led_driven)
    out["qq_lamp_ok"] = (qq_probe.get("ok") is True and "QQ" in led_driven)
    # ---- 批41 取证字段（分屏骨架／预览／终端／五态轮转·全进 ok_all 放行式） ----
    lay = win.centralWidget().layout()
    out["split_parts"] = [type(win.fw["split"]).__name__, type(win.fw["psplit"]).__name__,
                          win.fw["split"].orientation().name, win.fw["psplit"].orientation().name,
                          bool(win.fw["split"].childrenCollapsible()),
                          [int(x) for x in win.fw["split"].sizes()], pv_sizes, pv_minw]
    out["feeder_first"] = (lay.indexOf(win.fw["feeder"]) == 0 and lay.indexOf(win.fw["split"]) == 1)
    out["preview_rows"] = pv_rows_after
    out["preview_lnr_rows"] = len(pv_nums)
    out["preview_lnr_first"] = pv_nums[0] if pv_nums else -1
    out["preview_lnr_width"] = int(pv.lnr.sizeHint().width())
    out["preview_lnr_painted"] = bool(pv_painted)
    out["preview_by_box"] = bool(pv_by_box)
    out["preview_detail_ok"] = bool(pvd.get("lines", 0) >= 1 and not pvd.get("err"))
    out["preview_from_api"] = bool(pvr.get("lines", 0) >= 40 and not pvr.get("err"))
    out["preview_jam_fallback"] = bool(pv_jam.get("err") and pv_jam.get("fallback") and pv_jam_paper)
    out["term_available"] = bool(term_started and term_rows >= 1)
    out["term_rows"] = term_rows
    out["term_rc_shown"] = bool(term_rc)
    out["term_procs_alive"] = alive_before_close
    out["term_close_clean"] = bool(closed_clean)
    out["term_paper_back"] = paper_after_term
    out["term_clear_ok"] = bool(term_cleared)
    out["pv_fold_cycle"] = [bool(pv_fold_hidden), bool(pv_fold_shown), bool(tm_fold_hidden)]
    out["view_names"] = list(fax.VIEW_NAMES)
    out["view_cycle5"] = cyc
    out["fw_keys_41"] = len([k for k in ("split", "psplit", "preview", "term") if k in win.fw])
    # 1280×720 可用性：窗口最小宽须容得下窄屏，分屏两格与右栏两件都拿到真实尺寸
    win.resize(1280, 720); win.show()
    for _ in range(6): app.processEvents()
    narrow = {"min_w": int(win.minimumSizeHint().width()), "w": int(win.width()),
              "h": int(win.height()),
              "split": [int(x) for x in win.fw["split"].sizes()],
              "psplit": [int(x) for x in win.fw["psplit"].sizes()],
              "split_h": int(win.fw["split"].height()),
              "min_h": int(win.minimumSizeHint().height()),
              "roll_wh": [int(win.fw["roll"].width()), int(win.fw["roll"].height())],
              "pv_wh": [int(win.fw["preview"].width()), int(win.fw["preview"].height())],
              "tm_wh": [int(win.fw["term"].width()), int(win.fw["term"].height())]}
    win.resize(1420, 860)
    for _ in range(4): app.processEvents()
    out["narrow_1280"] = narrow
    # ---- 批40 版式补齐实测（offscreen 几何真值）：上＝送稿口（ent 所在区）·下＝左纸卷 A／右 aside 列 ----
    from PyQt6.QtCore import QPoint as _QP
    _lay = win.centralWidget().layout()
    with contextlib.suppress(Exception):
        if win.fw["ctlzone"].isVisible(): win.fax("ctl")        # 量前收净按需层（不残留展开态）
    with contextlib.suppress(Exception):
        # 批41 收尾：量完窄屏不再 hide C——常驻件绝不可见性翻转（只恢复默认份额）
        win.fw["psplit"].setSizes([200, 300, 210]); win.fw["einkzone"].setVisible(True)
    for _ in range(4): app.processEvents()
    _g = lambda x: x.mapTo(win, _QP(0, 0))
    _ent = _g(win.ent); _roll = _g(win.fw["roll"])
    _right = _g(win.fw.get("aside") or win.fw["psplit"])
    out["split_layout"] = {"top_input": bool(_ent.y() < _roll.y()),
                           "left_roll": bool(_roll.x() < _right.x()),
                           "horizontal": win.fw["split"].orientation() == Qt.Orientation.Horizontal,
                           "feeder_slot": int(_lay.indexOf(win.fw["feeder"])),
                           "split_slot": int(_lay.indexOf(win.fw["split"])),
                           "y_ent": int(_ent.y()), "y_roll": int(_roll.y()),
                           "x_roll": int(_roll.x()), "x_right": int(_right.x())}
    pv_term = [r for r in rows_all if str(r[0]).startswith("动作·") and
               ("预览 D" in r[1] or "终端 E" in r[1])]
    out["palette_pv_term"] = [len(pv_term), sorted(str(r[1])[:10] for r in pv_term)]
    out["palette_single_route"] = (len([r for r in rows_all if "视图轮转" in r[1]]) == 1 and
                                   len([r for r in rows_all if "命令面板" in r[1]]) >= 1)
    seg_pv = src_self.split("def previewOpen(self")[1].split("def pvToggle")[0]
    seg_tm = src_self.split("def _termSpawn(self")[1].split("def termHist")[0]
    out["no_second_route"] = ("core.handle(" not in seg_pv + seg_tm and " fax.api(" in seg_pv
                              and ("sock" + "et") not in seg_pv + seg_tm
                              and ("HTTP" + "Server") not in seg_pv + seg_tm
                              and ("sub" + "process.") not in seg_tm and "QProcess(" in seg_tm)
    print("SELFTEST " + json.dumps(out, ensure_ascii=False))
    ok_all = (out["saved"] and out["visible_rows"] >= 10 and out["meta_keys"] >= 30
              and out["no_token_face"] and out["f1_groups"] >= 5 and out["roll_plain"] >= 4
              and out["details"] >= 5 and out["panel_min"] >= 40 and out["task_table_len"] >= 2
              and len(panels) == 15 and out["qss_len"] > 1500
              and out["cut_ok"] and out["cut_steps"] == 5 and out["led_names"] == 7
              and out["crt_ok"] and out["eink_ok"] and out["eink_len"] > 8
              and out["eink_resident"] and out["eink_no_hide"] and out["eink_idx"] == 0 and out["eink_cycle"] == [True, True] and out["eink_idx"] == 0
              and out["no_bottom_strip"] and out["roll_ok"] and out["roll_cycle"]
              and out["roll_jam"] and out["roll_clear"] and out["roll_marks"] >= 2
              and out["roll_seen"] == ["feed", "print", "advance", "print", "advance", "tear", "idle"]
              and out["zero_topbar"] and out["palette_rows"] >= 60 and out["qactions"] >= out["menu_items"]
              and out["ctl_cycle"] == [True, True] and not out["fw_missing_required"]
              and out["palette_has_meta_and_panels"] and 0 < out["palette_filtered"] < out["palette_rows"]
              and out["lcd_cells"] == 6 and out["led_lamps"] == 7 and out["view_cycle"] == [2, True]
              and out["led_driven_n"] == out["led_lamps"] == out["led_built_n"] == 7
              and out["led_parity"] and out["qq_lamp_ok"]
              and out["fw_keys_41"] == 4 and not out["fw_missing_required"] and out["feeder_first"]
              and out["split_parts"][0] == "QSplitter" and out["split_parts"][1] == "QSplitter"
              and out["split_parts"][2] == "Horizontal" and out["split_parts"][3] == "Vertical"
              and out["split_parts"][4] is False
              and len(out["split_parts"][5]) == 2 and min(out["split_parts"][5]) > 0
              and max(out["split_parts"][5]) >= 300
              and len(out["split_parts"][6]) == 3 and min(out["split_parts"][6]) > 0   # 右列两格（D／E）＝C/D/E
              and max(out["split_parts"][7]) <= 300
              and out["narrow_1280"]["min_w"] <= 1280 and out["narrow_1280"]["w"] <= 1280
              and min(out["narrow_1280"]["split"]) >= 300
              and min(out["narrow_1280"]["psplit"]) >= 120
              and min(out["narrow_1280"]["roll_wh"]) > 0 and min(out["narrow_1280"]["pv_wh"]) > 0
              and min(out["narrow_1280"]["tm_wh"]) > 0
              and out["narrow_1280"]["min_h"] <= 720
              and out["preview_rows"] >= 40 and out["preview_from_api"] and out["preview_by_box"] and out["pv_abs_lines"] >= 3
              and bool(out["pv_ws_roots"])
              and out["preview_detail_ok"] and out["preview_lnr_rows"] >= 3
              and out["preview_lnr_first"] == 1 and out["preview_lnr_width"] >= 30
              and out["preview_lnr_painted"] and out["preview_jam_fallback"]
              and out["term_available"] and out["term_rc_shown"] and out["term_clear_ok"]
              and out["term_procs_alive"] >= 1 and out["term_close_clean"]
              and out["term_paper_back"] > out["roll_plain"]
              and out["pv_fold_cycle"] == [False, True, False]     # 预览可折可复·终端可折
              and out["view_names"] == ["纸卷 A", "送稿 B", "墨水屏 C", "预览 D", "终端 E"]
              and [c[0] for c in out["view_cycle5"]] == [1, 2, 3, 4, 0]
              and all(c[1] == fax.view_name(c[0]) for c in out["view_cycle5"])
              and [c[1] for c in out["view_cycle5"]] == list(fax.VIEW_NAMES[1:]) + [fax.VIEW_NAMES[0]]
              and out["split_layout"]["top_input"] and out["split_layout"]["left_roll"]
              and out["split_layout"]["horizontal"] and out["split_layout"]["feeder_slot"] == 0
              and out["split_layout"]["split_slot"] == 1
              and out["palette_pv_term"][0] >= 7 and out["palette_single_route"]
              and out["no_second_route"])
    return 0 if ok_all else 1

if __name__ == "__main__":
    if sys.stdout is None or sys.stderr is None:
        # pythonw 无控制台：print 会抛，统一兜到 devnull（日志仍走 debug/log）
        _dn = open(os.devnull, "w", encoding="utf-8")
        sys.stdout = sys.stdout or _dn; sys.stderr = sys.stderr or _dn
    sys.exit(main())
