---
name: general_answer
description: >
  通用回答子技能：一般知识/概念/解释类诉求的可选托管作答口（answer_general.py 调网关一次性作答）。
  批16 LLM 主导后主壳问答可直答，本技能保留为显式派发目标（:dispatch general_answer）与兜底作答口；
  不确定明说、不动文件不联网、网关未启用即明确报错；结果记 tool_call/knowledge 链供做梦沉淀。
license: MIT
metadata:
  category: answer
---

# general_answer

使用 `general_answer` skill 来完成用户请求。SMS 的**通用回答**子技能：把「模型本身就能答」的诉求收拢到一个可派发目标（批16 LLM 主导后为可选作答口——主壳问答可直答，显式 `:dispatch general_answer` 或模型选择本技能时经托管执行、SMS 整合转达）。

## 何时派发

- 用户话语是知识问答/概念解释/对比说明/闲聊寒暄且希望走托管作答口（`:dispatch general_answer`）；主壳 LLM 主导下简单问答已可直答，本口用于需留账/统一口径的作答。
- 其他技能明确"只干活不代答"后需要一段面向用户的说明文字。
- 需要动手（读写/执行/联网）→ 不派本技能，派 file_ops / 目标技能。

## 用法

```
python -B skill/sub_skills/general_answer/scripts/answer_general.py ask "<问题>"
python -B skill/sub_skills/general_answer/scripts/answer_general.py ask "<问题>" --json
```

- 非流式一次性作答（≤600 字·批24 内部英语处理·输出用户语言）；返回整段文本供 SMS 整合。
- 网关未启用 / 返回空正文 → 明确报错退出（exit 2），绝不静默代答。

## 联动

- 路由注入见 [skill_route.py](../../scripts/skill_route.py)〔参考〕句与 [gateway.py](../../scripts/gateway.py) SYS 治理句（批16：问答可直答·本口可选）。
- 作答记 tool_call 链＋knowledge 链（挂 conv/sess 边），由 [dream.py](../../scripts/dream.py) 做梦沉淀。
- 壳内等价入口：直接话语自动路由，或 `:dispatch general_answer <问题>`。

## 红线

- 不执行文件、命令、联网动作——发现诉求含执行意图时回退 SMS 改派具执行能力的技能（红线 6）。
- 回答经 SMS 整合后转达用户，本技能不直接面向用户会话。
- 悬空链接 = 0；本文件 ≤ 50 行；SKILL.md 含 YAML frontmatter。
