---
name: writing-test-drafts
description: Use for optional formal acceptance when a milestone, migration, security boundary, critical data flow, or user request needs named test cases and an evidence-backed report.
---

# 按需正式验收

## 使用边界

这是按需正式验收能力。Direct/Light 默认不调用；Full 也只有在系统里程碑、迁移、安全、关键数据流程、跨系统集成或用户明确要求逐项验收时使用。普通完成验证不需要制造正式测试稿。

## 测试稿

正式测试稿使用 `tests/<change_id>.md`。每个测试项使用稳定 ID，例如 `T-001`，并包含：

- 目的；
- 前置条件；
- 操作；
- 可观察的预期结果。

测试项覆盖关键成功路径、重要失败路径和需求明确要求的兼容边界。不按代码文件或实现步骤机械扩张用例。

## 验收报告

报告绑定实际 `change_id`、测试稿版本和 `code_ref`。每个测试项只使用：

- `passed`：已执行或核对有效自动化证据，结果符合预期；
- `failed`：实际结果偏离预期；
- `not_executed`：未执行并说明原因。

总体状态由逐项状态推导。失败和未执行项必须如实保留，不得用摘要覆盖。相同代码、命令、环境和输入的有效成功证据可以复用；任一维度变化则重新验证。

## 可选 Validator

`scripts/acceptance_report.py` 是可选的严格格式 validator，适合需要机器校验、长期审计或重复执行的项目。个人工作流总账不解析其 Markdown grammar，也不把使用该脚本设为所有 Full 任务的完成条件。

涉及真实外部写入、付费操作、部署或删除时，执行前仍需用户明确授权。报告不得记录密码、Token、Cookie 或其他凭据。
