#!/usr/bin/env python3
"""task_table_cli.py — 任务表命令行入口（自 task_table.py 拆出以守 ≤50 行红线）：plan|new|show|next|eta|status|add|remove|skill|pending。用法：python -B task_table_cli.py new <步骤逗号分隔> | status <tid> <t#> done | pending [conv]"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import task_table as tt
def main(a):
    if a[0] == "plan" and len(a) > 1: d = tt.plan(" ".join(a[1:])); print(tt.block(d) if d else "（脚本判非复杂·模型判复杂可 task_table_cli new <步骤逗号分隔> 自建）")
    elif a[0] == "new" and len(a) > 1: print(tt.new_table(" ".join(a[1:]), " ".join(a[1:])))
    elif a[0] == "pending": print(tt.pending(a[1] if len(a) > 1 else "") or "（本对话无未完成任务表）")
    elif len(a) > 1: print(tt.revise(a[0], a[1], a[2] if len(a) > 2 else "", " ".join(a[3:])))
    else: print(tt.__doc__.strip().splitlines()[-1])
if __name__ == "__main__": main(sys.argv[1:] or ["help"])
