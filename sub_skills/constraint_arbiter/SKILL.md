---
name: constraint_arbiter
description: >
  约束冲突仲裁子技能：多个 skill 的约束互相冲突时按确定性优先级阶梯（用户当轮话语＞SMS治理＞
  目标技能红线＞描述行）裁决（arbiter.py judge）；同主题反极性判冲突、同级冲突不擅断转问用户；
  结果记 logic 链审计，供 SMS 派发前统一执行序。
license: MIT
metadata:
  category: governance
---

# constraint_arbiter

使用 `constraint_arbiter` skill 来完成用户请求。SMS 的**约束冲突仲裁**子技能：多技能同时命中、或技能 SKILL.md 红线与 SMS 治理/彼此互斥时，先派本技能出「执行约束序＋冲突裁决」，再按裁决派发（红线 4/6：仲裁也是托管技能在跑，SMS 本体不拍脑袋）。

## 何时派发

- 路由命中 ≥2 技能且其约束疑似打架（同主题一禁一须）。
- 目标技能约束与 SMS AGENTS.md / resistance 红线、或与其子技能约束冲突。
- 派发前需要一份合并去矛盾的「执行约束清单」。

## 用法

```
python -B skill/sub_skills/constraint_arbiter/scripts/arbiter.py judge <技能id[,id…]> [用户话语]
python -B skill/sub_skills/constraint_arbiter/scripts/arbiter.py constraints <技能id[,id…]> --json
```

- 优先级阶梯恒定：**P0 用户当轮话语 ＞ P1 SMS 治理（AGENTS＋resistance）＞ P2 目标技能红线节 ＞ P3 描述行**。
- 冲突检测＝约束句 CJK 2-gram 主题交集 ≥2 且极性相反（禁/不得/勿 ↔ 必须/须/应/仅）。
- 同级冲突不擅断：输出 need_user → SMS 经 ask_user 请用户拍板。
- 裁决记 logic 链（frm→to：why），[dream.py](../../scripts/dream.py) 可复盘。

## 联动

- 路由注入见 [skill_route.py](../../scripts/skill_route.py) 与 [gateway.py](../../scripts/gateway.py) SYS 治理句；派发经 [agent_tools.py](../../scripts/agent_tools.py) skill 工具对等对话（批23 每派发自开独立 conv）。
- 输出 order/conflicts 供 [agent_task.py](../../scripts/agent_task.py) 拆任务时附入子任务提示词。

## 红线

- 本技能只裁约束序，不执行任务本身、不代答用户（红线 4/6）。
- 不得删改任何 skill 的 resistance/约束原文——只裁决不改写。
- 悬空链接 = 0；本文件 ≤ 50 行；SKILL.md 含 YAML frontmatter。
