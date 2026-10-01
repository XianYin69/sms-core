#!/usr/bin/env python3
"""console_font.py — 控制台（conhost）中文字形修复：用户报「TUI 提示中文是方框」。
根因＝传统 conhost 无字体回退（font fallback），默认面 Consolas/Lucida Console 不含 CJK 字形，
WriteConsoleW 写出的中文只能画成豆腐块 □；Windows Terminal（有 WT_SESSION）自带回退不受影响。
本件只在 Windows＋stdout 确为控制台时动手：GetCurrentConsoleFontEx 读当前面，若属无 CJK 面，
就按已装字体表挑一个 CJK 等宽面（宋体 SimSun 优先，MS Gothic 次之）SetCurrentConsoleFontEx 切过去，
字号沿用现值（读不到给 16×16），并读回校验。开关＝settings tui.console_font_fix（默认开）。
修（表930-173346-363 t4）：① _Font 按真 CONSOLE_FONT_INFOEX 排布
cbSize/nFont/dwFontSize/FontFamily/FontWeight/FaceName[32]＝84 字节（旧版多塞 FullFontSize＝88
→ cbSize 错 → GetCurrentConsoleFontEx 恒 WinError 87 → 面名永远读不到 → 修复逻辑永不执行）；
② 显式 ctypes 签名（restype/argtypes），防 64 位句柄截断与 BOOL 宽度错；
③ 有控制台句柄但面名读空不再静默退出，直接按 CJK_FACES 试切一次并读回校验；
④ current() 区分「无控制台」与「API 失败」，后者把 WinError 码留在 last_error() 供诊断。
红线：任何异常一律降级为返回一句提示，绝不抛错、绝不阻断 TUI 启动；不改注册表、不改用户全局终端配置，
只影响当前这个控制台窗口。用法：import console_font; msg = console_font.ensure_cjk()
"""
import os, sys, ctypes
from ctypes import wintypes

NO_CJK = ("consolas", "lucida console", "terminal", "raster fonts", "cascadia mono", "cascadia code", "")
# 顺序＝优先试；英文面名＋conhost 读回的本地化名都列（CP936 允许清单＝*新宋体·CP932＝*ＭＳ ゴシック）
CJK_FACES = [("SimSun", 0x86), ("宋体", 0x86), ("NSimSun", 0x86), ("新宋体", 0x86),
               ("MS Gothic", 0x81), ("ＭＳ ゴシック", 0x81)]
FF_MODERN_FIXED = 0x0005
_BOOL = ctypes.c_int          # Windows BOOL＝4 字节，勿用 c_bool（只写 1 字节·高 3 字节为垃圾）
_ERR = {"kind": "", "code": 0, "msg": ""}


class _COORD(ctypes.Structure):
    _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]


class _Font(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("nFont", wintypes.DWORD),
                ("dwFontSize", _COORD), ("FontFamily", wintypes.DWORD),
                ("FontWeight", wintypes.DWORD), ("FaceName", wintypes.WCHAR * 32)]


def _k32():
    """kernel32＋显式签名（一次设好·防 64 位句柄被当 int 截断）。"""
    k = ctypes.windll.kernel32
    k.GetStdHandle.restype = wintypes.HANDLE
    k.GetStdHandle.argtypes = [wintypes.DWORD]
    k.GetConsoleMode.restype = _BOOL
    k.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    for fn in ("GetCurrentConsoleFontEx", "SetCurrentConsoleFontEx"):
        f = getattr(k, fn)
        f.restype = _BOOL
        f.argtypes = [wintypes.HANDLE, _BOOL, ctypes.POINTER(_Font)]
    return k


def _fail(what, exc=None):
    """记 API 失败（供 last_error 诊断），绝不抛错。"""
    c = 0
    try:
        c = ctypes.GetLastError() or 0
    except Exception:
        pass
    _ERR.update(kind="api", code=c, msg="%s%s" % (what, ("：" + str(exc)[:60]) if exc else ""))


def _console_handle():
    """stdout 是控制台才返回句柄，否则 None（重定向/管道时不折腾）。"""
    try:
        k = _k32()
        h = k.GetStdHandle(-11)          # STD_OUTPUT_HANDLE
        if not h or h in (-1, ctypes.c_void_p(-1).value):
            _ERR.update(kind="nocon", code=0, msg="无标准输出控制台句柄")
            return None
        mode = wintypes.DWORD()
        if not k.GetConsoleMode(h, ctypes.byref(mode)):
            _fail("GetConsoleMode")
            _ERR.update(kind="nocon", code=_ERR["code"], msg="stdout 非控制台（管道/重定向）")
            return None
        return h
    except Exception as e:
        _fail("GetStdHandle/GetConsoleMode", e)
        return None


def _installed():
    """已装字体面名集合（HKLM Fonts 值名去括号后缀·小写·只读不写）。"""
    names = set()
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts")
        for i in range(winreg.QueryInfoKey(k)[1]):
            try:
                v = winreg.EnumValue(k, i)[0]
            except OSError:
                break
            names.add(v.split(" (")[0].strip().lower())
        winreg.CloseKey(k)
    except Exception:
        pass
    return names


def _hit(cand, have):
    """已装判定：注册表值名常为族串（"SimSun & NSimSun"/"宋体, 新宋体"）→ 子串匹配，非精确相等。"""
    c = cand.lower()
    return any(c in n for n in have)


def current():
    """(face, x, y) 当前控制台字体；非控制台/API 失败＝('', 0, 0)，原因见 last_error()。"""
    h = _console_handle()
    if not h:
        return "", 0, 0
    try:
        f = _Font()
        f.cbSize = ctypes.sizeof(_Font)      # 必须＝84，否则 ERROR_INVALID_PARAMETER(87)
        if not _k32().GetCurrentConsoleFontEx(h, False, ctypes.byref(f)):
            _fail("GetCurrentConsoleFontEx")
            return "", 0, 0
        _ERR.update(kind="", code=0, msg="")
        return (f.FaceName or "").strip(), int(f.dwFontSize.X or 0), int(f.dwFontSize.Y or 0)
    except Exception as e:
        _fail("GetCurrentConsoleFontEx", e)
        return "", 0, 0


def last_error():
    """诊断串：''＝正常；nocon＝无控制台（管道/WT 之外场景）；api＝API 失败带 WinError 码。"""
    if not _ERR["kind"]:
        return ""
    if _ERR["kind"] == "nocon":
        return "nocon:" + _ERR["msg"]
    return "api WinError %d (%s): %s" % (_ERR["code"], _ERR["msg"], _winerr_text(_ERR["code"]))


def _winerr_text(code):
    try:
        return ctypes.FormatError(code)[:80]
    except Exception:
        return ""


def needs_fix(face=None):
    """无 WT_SESSION（＝conhost）＋当前面不含 CJK 字形 → 需切面。"""
    face = (face if face is not None else current()[0])
    if os.environ.get("WT_SESSION"):
        return False
    return face.strip().lower() in NO_CJK


def apply(face, size=(0, 0), charset=0x86):
    """切到指定面（size 全 0 沿用现值，仍 0 则 16×16）。返回 (ok, msg)。"""
    h = _console_handle()
    if not h:
        return False, "当前输出不是控制台（管道/重定向），未切字体"
    sx, sy = size
    if not (sx and sy):
        _, sx, sy = current()
    if not (sx and sy):
        sx = sy = 16
    try:
        f = _Font()
        f.cbSize = ctypes.sizeof(_Font)
        f.nFont = 0
        f.FontFamily = (charset << 8) | FF_MODERN_FIXED
        f.FontWeight = 400
        f.dwFontSize = _COORD(int(sx), int(sy))
        f.FaceName = face
        ok = bool(_k32().SetCurrentConsoleFontEx(h, False, ctypes.byref(f)))
        got = current()[0]
        # conhost 按代码页允许清单（HKLM\...\Console\TrueTypeFont）落地，读回常是本地化名
        # → 请求名一致或读回面已含 CJK 字形即算成功，否则误报「未生效」
        same = got.strip().lower() == face.strip().lower()
        # 只有「请求的确实是 CJK 面」时才允许 conhost 的同族落地（否则 apply("Consolas")
        # 会因读回面本来就含 CJK 而误报成功）
        want_cjk = face.strip().lower() not in NO_CJK and charset >= 0x81
        cjk_ok = want_cjk and bool(got) and got.strip().lower() not in NO_CJK
        if ok and (same or cjk_ok):
            return True, "控制台字体已切到 %s %dx%d（请求 %s·仅本窗口·中文不再是方框）" % (got or face, sx, sy, face)
        if not ok:
            _fail("SetCurrentConsoleFontEx")
            return False, "切换失败（请求 %s·%s）" % (face, last_error() or "实际读回 %s" % (got or "?"))
        return False, "切换未生效（请求 %s·实际 %s）" % (face, got or "?")
    except Exception as e:
        return False, "切换异常：%s" % str(e)[:80]


def setting_on():
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import settings
        return bool((settings.eff().get("tui") or {}).get("console_font_fix", True))
    except Exception:
        return True


def _try_faces(sx, sy, have=None):
    """按 CJK_FACES 顺序（SimSun→宋体→NSimSun→MS Gothic·须 _installed 命中）逐个切并读回校验。"""
    have = _installed() if have is None else have
    last = ""
    for cand, cs in CJK_FACES:
        if not have or _hit(cand, have):
            ok, msg = apply(cand, (sx, sy), cs)
            if ok:
                return True, msg
            last = msg
    return False, last


def ensure_cjk():
    """TUI 启动早期调用：需要就修，不需要/修不了只回一句文字，绝不抛错。"""
    try:
        if os.name != "nt" or os.environ.get("WT_SESSION"):
            return ""                      # 非 Windows / Windows Terminal 自带回退，不打扰
        if not _console_handle():
            return ""                      # 管道/重定向：安静返回
        face, sx, sy = current()
        if not face:                       # ③ 有句柄却读不到面 → 不再静默退出，直接试切一次
            ok, msg = _try_faces(sx, sy)
            if ok:
                return msg + "（面名曾读空·已按已装字体直切并读回校验）"
            return "未能切换控制台字体（读面失败：%s）——中文可能仍显示为方框，建议改用 Windows Terminal（自带字体回退）" % (last_error() or msg or "面名读空")
        if not needs_fix(face):
            return ""
        if not setting_on():
            return "conhost 中文字形缺失（方框）——当前面 %s 无 CJK；已按设置 tui.console_font_fix=关 跳过，可改用 Windows Terminal" % face
        ok, msg = _try_faces(sx, sy)
        if ok:
            return msg
        return "未能切换控制台字体（原面 %s·%s）——中文可能仍显示为方框，建议改用 Windows Terminal（自带字体回退）" % (face, last_error())
    except Exception as e:
        return "控制台字体自检失败（不影响启动）：%s" % str(e)[:60]


if __name__ == "__main__":
    print("sizeof(_Font)=%d" % ctypes.sizeof(_Font))
    print("current=%r err=%r" % (current(), last_error()))
    print(ensure_cjk() or "无需修复（当前控制台字体可显示中文，或非 conhost/非 Windows）")
    print("after=%r" % (current(),))
