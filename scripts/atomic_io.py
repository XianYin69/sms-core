# -*- coding: utf-8 -*-
"""atomic_io.py — 并发安全读写（2026-09-26 并行任务实测崩溃根因修复）：多线程/多进程同写 config.json、链碎片、resume 文件时，旧版 open(w)+json.dump 非原子、读侧无重试——par8/par9 实测读到空文件抛 JSONDecodeError。wjson：进程内 RLock＋同目录临时文件＋os.replace 原子换入（Windows 目标被占短暂 PermissionError 重试 8×30ms）；rjson：读损坏/空文件按 6×25ms 重试后仍失败才抛。用法：wjson(path, obj[, encoding]); rjson(path[, default])。"""
import os, json, time, threading
LK = threading.RLock()
def _tmp(path): return path + ".tmp%d" % (threading.get_ident() % 100000)
def wjson(path, obj, encoding="utf-8"):
    d = os.path.dirname(os.path.abspath(path)); os.makedirs(d, exist_ok=True); t = _tmp(path)
    with LK:
        with open(t, "w", encoding=encoding) as f: json.dump(obj, f, ensure_ascii=False, indent=1)
        for a in range(8):
            try: os.replace(t, path); return
            except PermissionError:
                if a == 7: raise
                time.sleep(0.03)
def rjson(path, encoding="utf-8-sig", default=None):
    last = None
    for a in range(6):
        try:
            with open(path, encoding=encoding) as f: return json.load(f)
        except FileNotFoundError:
            if default is not None: return default
            raise
        except Exception as e: last = e; time.sleep(0.025)
    if default is not None: return default
    raise last
