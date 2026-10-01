"""deps_scan.py — AST 扫技能 .py 得「关联 python」：顶层 import 剔标准库/自带模块，module→pip 发行名→安装状态。"""
import ast, glob, importlib.util, importlib.metadata as md, os, sys

ALIAS = {"cv2": "opencv-python", "PIL": "pillow", "yaml": "pyyaml", "bs4": "beautifulsoup4", "fitz": "pymupdf",
         "docx": "python-docx", "serial": "pyserial", "usb": "pyusb", "Cryptodome": "pycryptodome"}


def top_imports(pys):
    mods = set()
    for f in pys:
        try:
            tree = ast.parse(open(f, encoding="utf-8", errors="ignore").read())
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and not n.level and n.module:
                mods.add(n.module.split(".")[0])
    return mods


def py_deps(path):
    pys = glob.glob(os.path.join(path, "**", "*.py"), recursive=True)
    local = {os.path.basename(f)[:-3] for f in pys}
    pkgs = md.packages_distributions()
    out = []
    for m in sorted(top_imports(pys) - set(sys.stdlib_module_names) - local):
        try:
            inst = importlib.util.find_spec(m) is not None
        except (ImportError, ValueError):
            inst = False
        out.append({"module": m, "dist": ALIAS.get(m) or (pkgs.get(m) or [m])[0], "installed": inst})
    return out
