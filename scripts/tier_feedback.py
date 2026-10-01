#!/usr/bin/env python3
"""tier_feedback.py — 分级超时的「反馈」半边（与 timeout_tiers 阈值真源配对，各自 ≤50 行）。
旧版反馈只说「静默 240s 无任何输出（判为卡死）」，大模型与用户都看不出是哪一级触发、下一步该做什么；
本模块把级别名写进文本并附按级别的建议（2026-10-01 做梦审计错误1·error 链 2ab90541b9）。
用法：python -B tier_feedback.py（打印当前分级快照）。"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timeout_tiers as tiers

NAME = {"T1": "网络/网关单请求超时", "T2": "阶段静默", "T3": "超总预算"}
HINT = {"T1": "单请求已自计时抛错、worker 未被拖死：查网关与网络可达（llm_gateway.timeout／qq.net_timeout）后重试该请求即可",
        "T2": "该阶段长时间无活动戳＝在阶段边界调 run_watch.beat() 打戳，或 set_stage() 声明为长等待阶段（宽档 qq.handle_stall_llm）；已打戳仍静默＝真卡死，查在途子进程与网络",
        "T3": "整条链路耗时超上限：提高 qq.handle_timeout 或把诉求拆小步／转后台任务"}

def report(tier, secs, stage=None, band=None):
    """反馈文本＝级别名＋阈值＋阶段档＋下一步建议（例：「T2 阶段静默 600s（阶段=llm·宽档/llm）·…」）。"""
    s = "%s %s %ds" % (tier, NAME.get(tier, "超时"), tiers._i(secs))
    if tier == "T2": s += "（阶段=%s·%s）" % (stage or "默认", band or "常规档")
    return s + "·" + HINT.get(tier, "查日志定位卡点")

def snapshot():
    """run_watch status 用：三档配置一次摊开（旧版 status 只回两个平铺值，看不出分级）。"""
    return {"tiered": tiers.tiered(), "T1_net_s": tiers.t1("net"), "T1_llm_s": tiers.t1("llm"),
            "T2_normal_s": tiers.t2("inbound")[0], "T2_llm_s": tiers.t2("llm")[0],
            "T2_long_stages": list(tiers.LONG_STAGES), "T3_qq_s": tiers.t3("qq"), "T3_shell_s": tiers.t3("shell")}

if __name__ == "__main__":
    print(json.dumps(snapshot(), ensure_ascii=False, indent=1))
