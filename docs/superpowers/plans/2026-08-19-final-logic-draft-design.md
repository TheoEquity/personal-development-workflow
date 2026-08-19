# Final Logic Draft Design

## Goal

个人工作流在真实验收全部通过后、完成变更事件前，维护一份轻量的最终逻辑稿。它让读者不查看代码也能按时间顺序还原功能如何运行，但不扩展成架构文档、测试报告或实现文件清单。

## Confirmed contract

- 每个变更事件使用总控既有的 `change_id`，固定路径为 `logic/<change_id>.md`。
- 正常粒度以用户给出的 Tooltip 视觉快照示例为准：先讲核心机制，再按真实发生顺序讲触发、处理、页面结果、关键层级或状态，以及必要的重复触发和清理逻辑。
- 文档主体只有必填的 `## 功能逻辑`；确有正文之外的提醒时可增加 `## 注意事项`，没有注意事项时省略。
- 不强制拆成“核心思路、用户流程、内部顺序、数据关系、异常路径、支持范围、副作用”等固定栏目，也不要求穷举所有边界。
- 不写具体函数、类、文件清单、逐步测试过程或验收证据；这些内容继续由代码、Plan、测试稿和验收报告负责。
- 逻辑稿必须根据当前正式 Spec、已评审 Plan、最终 `code_ref` 和已经通过 validator 的验收报告归纳真实行为。材料互相冲突或行为尚未验收时停止，不能用预期行为代替最终行为。
- 生成时机固定为验收报告全部通过之后、最终 `change.md` 与事件完成之前。工作流游标继续停在 `acceptance`，不增加 SQLite 阶段。
- 最终 `change.md` 包含一个 `## 最终逻辑稿` 章节，正文只记录 canonical 路径 `logic/<change_id>.md`。
- 最终逻辑稿与最终 `change.md` 必须同时存在于最终 `change_ref` 指向的 Git commit tree。其派生版本为 `logic/<change_id>.md@<final-change-ref-sha>`，但 SQLite 不增加 `logic_ref` 字段。
- `complete` 必须验证 canonical 路径、最终提交中的文件存在性、文档身份和最小结构。已完成事件保持不可变；之后的需求变化或外部 Bug 仍创建新事件及新的逻辑稿。

## Document shape

```markdown
# CE-0007 最终逻辑稿

## 功能逻辑

[用连续段落或少量项目符号，按真实顺序说明核心机制和运行流程。]

## 注意事项

[仅记录正文之外确实需要提醒的少量事项；没有时省略本节。]
```

## Ownership

- 新增个人 Skill `writing-final-logic-drafts`，负责读取最终正式材料、形成上述粒度的候选稿、展示给用户确认并保存 canonical 文件。
- `using-personal-development-workflow` 负责在验收通过后调用该 Skill，并且只在逻辑稿就绪后形成最终 `change.md`。
- `managing-change-ledger` 只负责完成门的机械验证和最终 `change_ref` 原子安装；它不在 SQLite 中保存逻辑稿正文或新增字段。
- 安装脚本、发布包 README 与包合同同步包含新个人 Skill。Superpowers 原生 Skill 保持只读。

## Failure handling

- 验收失败或存在未执行项：不生成最终逻辑稿，继续既有返工回环。
- 正式引用无效、材料冲突或无法证明实际行为：停在 `acceptance`，报告缺口。
- 用户要求修改候选逻辑稿：只修改尚未完成事件的 `logic/<change_id>.md` 候选内容；完成后不可修改。
- `complete` 发现逻辑稿缺失、路径错误、正文空壳或最终 `change.md` 未关联 canonical 路径：事务无写入，事件保持 `in_progress`。
