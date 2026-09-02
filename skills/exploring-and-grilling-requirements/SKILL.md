---
name: exploring-and-grilling-requirements
description: Use when a requirement has material ambiguity, competing product choices, or high-risk behavior that must be explored before implementation.
---

# 按需探索需求

## 何时使用

本 Skill 是按需能力。只有需求存在实质歧义、多个会改变用户体验的方案、或权限、数据、安全、计费等高风险影响时使用。清晰任务不调用，由上层工作流直接选择 `direct`、`light` 或 `full`。

## 工作方式

1. 先读取与问题直接相关的现有行为、Spec 和代码事实。
2. 只提出会改变实现或验收结果的问题；紧密相关的问题可以一次成组询问。
3. 每个关键选择给出推荐方案、主要取舍和不选择其他方案的具体原因。
4. 用户已经授权模型自行判断、且不存在高风险外部影响时，可以采用唯一合理推荐并明确记录假设。
5. 不把技术实现细节包装成产品问题交给用户，也不为了流程完整而制造竞争解释。

## 输出

讨论结束时给出一份简短、可确认的决策结果：

- 目标；
- 关键选择；
- 用户可观察行为；
- 边界和明确排除项；
- 成功条件；
- 未决项（没有则写“无”）。

存在会改变结果的未决项时停止；否则把确认结果交回调用方。本 Skill 不创建 CE、不写 Spec、不修改代码，也不决定是否并行。
