---
name: writing-specs
description: Use when a confirmed behavior change needs a light or full functional specification before implementation.
---

# 编写行为 Spec

## Profile

调用方传入同一 CE 的 `change_id` 和 `profile=light` 或 `profile=full`。Direct 不调用本 Skill。

- `profile=light`：行为明确、范围局部、风险低。
- `profile=full`：存在重要方案选择，或涉及架构、公共契约、数据、安全和较大影响面。

Spec 只描述系统应该怎样表现，不写文件级实现步骤。正式文件使用 `specs/<change_id>.md`；需要不可变定位时使用路径加完整 Git SHA。

## Light

Light Spec 只包含：

```markdown
# <change_id> Spec

## 问题

## 触发

## 期望行为

## 范围

## 完成条件
```

确有必要时补一小段“必须保持不变”。不强制影响表、代码调查、Plan 或正式测试稿。

## Full

Full Spec 根据需求实际需要覆盖：

- 目标、用户和主要场景；
- 触发、状态变化、输出与失败行为；
- 系统边界、外部依赖和明确排除项；
- 关键数据、权限、安全或兼容性不变量；
- 已有行为中必须保持、迁移或明确改变的部分；
- 可验证的完成标准。

从零开发完整系统时，Full Spec 可以作为系统级合同，后续用多个纵向 CE 逐步实现。只记录影响当前设计的架构决策，不预写整个系统的类、函数和文件结构。

影响分析使用最小充分形式：没有影响就写结论；存在重要影响时列出对象、当前行为、决定和验证方式。不强制六列表格或稳定编号。

正式测试稿按风险决定。系统里程碑、迁移、安全、关键数据流程或用户明确要求逐项验收时，可在 Spec 确认后调用 `writing-test-drafts`；普通 Full 任务也可以直接使用验证清单。

## 完成条件

Spec 必须没有会改变用户可观察行为的未决项。实现调查中发现需求本身需要改变时，回到本 Skill 更新必要部分；纯实现细节由实现者判断，不反写进 Spec。
