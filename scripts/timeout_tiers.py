#!/usr/bin/env python3
"""timeout_tiers.py — 超时分级（T1/T2/T3）阈值真源。为什么分级＝做梦审计错误1（error 链 2ab90541b9·freq=5）：
run_watch.run_with_timeout 原只有一档平铺静默值 qq.handle_stall=240，而深层链路（qq_inbound.handle → 网关 LLM 请求 →
技能对话）在长时间合法等待期间不调用 rw.beat() 打活动戳，于是静默看门狗 240s 早于总预算 900s 触发，把「慢但活着」
的调用判为卡死强杀（用户表现＝QQ 发进去没回复/被中止）。三档各自可配、缺新键取保守默认、既有键含义不变。
用法：被 run_watch 导入（直接跑需同目录 settings.py）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings
# 已知「合法长等待」阶段：拿不到逐行输出，T2 必须走宽档，否则就是误杀（error 2ab90541b9）
LONG_STAGES = ("llm", "llm_stream", "gateway", "skill", "ask", "dispatch_llm", "subconv")

def _i(v, d=0):
    try: return int(v)
    except Exception: return d

def tiered():
    """分级总开关（默认开）；false＝退回旧「一档平铺静默」，留一条不改代码即可回滚的路。"""
    try: return bool(settings.get("qq.tiered_timeout", True))
    except Exception: return True

def t1(kind="net"):
    """T1＝网络/网关单请求超时（短·自计时·到点即抛不拖 worker）：llm 取 llm_gateway.timeout，其余取 qq.net_timeout。"""
    llm = kind == "llm"
    try: return max(5, _i(settings.get("llm_gateway.timeout" if llm else "qq.net_timeout"), 120 if llm else 30))
    except Exception: return 120 if llm else 30

def t2(stage=None, base=None):
    """T2＝阶段静默阈值 (秒, 档位名)：长等待阶段走宽档 qq.handle_stall_llm（默认 600·下限 60），
    普通阶段沿用调用方 base（＝qq.handle_stall 240）——旧版只有这一档平铺值，正是误杀的根源。"""
    st = str(stage or "").lower()
    try:
        if st in LONG_STAGES: return max(60, _i(settings.get("qq.handle_stall_llm"), 600)), "宽档/" + st
        v = _i(base) if base else max(30, _i(settings.get("qq.handle_stall"), 240))
        return max(15, v), ("常规档/" + st) if st else "常规档"
    except Exception: return max(15, _i(base, 240)), "常规档"

def t3(kind="qq"):
    """T3＝总预算墙钟：qq.handle_timeout（入站派发）／shell.exec_timeout（子进程与脚本）。"""
    sh = kind == "shell"
    try: return max(5 if sh else 60, _i(settings.get("shell.exec_timeout" if sh else "qq.handle_timeout"), 600 if sh else 900))
    except Exception: return 600 if sh else 900
