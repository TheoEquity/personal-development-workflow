# 测试稿、验收与事件完成阶段

只在 `current_stage=writing_test` 或 `acceptance` 时完整读取。测试稿、实际报告、失败回传和 validator 规范化结果以 `writing-test-drafts` 为唯一合同；本 reference 只规定个人工作流的路由和完成边界。

## 兼容 `writing_test`

新事件的初始测试稿已在 `writing_spec` 子节点形成，不在编码后首次编写。`writing_test` 只兼容已有游标，或验收失败后仅需修正操作、数据或环境的旧回环。

使用 `writing-test-drafts` 修改 `tests/<change_id>.md`，不得改变正确的 Spec 行为契约。提交后只更新 `test_ref`，再把阶段设为 `acceptance` 并立即停止；登记版 `change_ref` 保持不变。

## 实际验收

1. 用户要求验收后，按绑定版本测试稿实际操作。
2. 执行第一个测试项前，确认实际运行内容与总账 `code_ref` 指向同一 Git commit，并确认没有会改变受测行为的相关未提交改动。无法证明时返回 `tdd_coding` 并停止。
3. 按 `writing-test-drafts` 唯一报告合同生成并提交一份新的独立验收报告，不覆盖旧失败报告。
4. 调用 `writing-test-drafts` 的唯一 validator，把当前 `change_id`、`test_ref` 和 `code_ref` 作为期望绑定。validator 无效时停止；有效时只消费其规范化结果，再用 `managing-change-ledger` 只更新 `evidence_ref`。

结果路由：

- 全部通过：校验报告、测试稿、完整 SHA、六类引用和实际受测代码，然后进入最终逻辑稿门禁。
- 包含失败：事件保持 `in_progress`，保留已提交失败报告，按下面回环处理。
- 没有失败但存在未执行：总体未完成，保留本阶段并说明原因。

## 开发与验收回环

内部 TDD、自测或验收失败始终使用当前 `change_id`，不建立新变更事件：

```text
Spec 与测试稿 → Plan → TDD 编码 → 内部验收 → 独立验收报告
                                             ├─ 通过 → 最终逻辑稿 → 完成事件
                                             └─ 失败 → 失败回传 → 最早责任阶段 → 再验收
```

失败事实必须来自可复现 TDD/自测或 validator 规范化结果。出现失败、需求修正、追加、范围扩展、reviewer/代码调查或基线漂移时，才完整读取 [material-change-assessment.md](material-change-assessment.md)，基于当前不可变 `spec_ref`、`plan_ref` 输出 Spec 与 Plan 两份结论并等待确认。

确认后只倒回最早责任阶段：Spec 变化回 `writing_spec`；仅 Plan 变化回 `writing_plan`；两者无需修改且属于实现偏差时回 `tdd_coding`；测试操作/数据/环境有误按测试稿路径处理。每次只更新一个阶段并立即停止。已完成事件之后的变化或外部反馈建立新事件，旧事件和引用不可修改。

## 验收通过后的最终逻辑稿

验收报告全部通过之后、完成变更事件之前，才加载 `writing-final-logic-drafts`，原样传入同一 `change_id`、当前 `spec_ref`、`plan_ref`、`test_ref`、`code_ref`、`evidence_ref`。

候选与保存稿固定为 `logic/<change_id>.md`，标题 `# <change_id> 最终逻辑稿`，必填 `## 功能逻辑`，可选 `## 注意事项`。内容按真实顺序讲清核心机制、触发、处理、结果及必要层级、重复触发或清理行为，不写代码导读或测试证据。

先在对话中完整展示候选并停止。用户确认后才保存 canonical 文件；未确认、材料冲突或正文无法由实际代码与验收事实证明时保持 `acceptance`，不修改 `change.md`、SQLite 或代码。保存后仍保持本阶段并停止；不增加 SQLite 阶段或 `logic_ref`。

## 完成变更事件

下一轮确认 canonical 逻辑稿存在后，按 `managing-change-ledger` 完成合同形成最终 `change.md`：同一 `change_id`、`status: completed`、与总账逐字一致的 `spec_ref`、`plan_ref`、`test_ref`、`code_ref`、`evidence_ref`，以及唯一 `logic/<change_id>.md` 和最终结论。

最终 `change_ref` 的同一 Git commit tree 必须包含完成版 `change.md` 和逻辑稿。取得 SHA 后调用：

```text
complete <change_id> --change-ref changes/<change_id>/change.md@<final-sha>
```

即执行 `complete <change_id> --change-ref changes/<change_id>/change.md@<final-sha>`；成功后阶段变为 `completed` 并立即停止。

只有材料角色、报告绑定、阶段和 Git 对象检查全部通过，命令才在一个事务内原子更新最终 `change_ref` 和 `status=completed`。总账完成后关闭该事件游标，使其为 `current_stage=completed`、`state=closed`。已完成事件允许幂等查询。

阶段切换后立即停止；本轮不得读取或执行集线、归位、branch finishing 或清理。下一轮进入 `completed` 路由时，才自动展示归位与清理候选卡。

## 停止信号

- 受测内容与 `code_ref` 不一致，或存在相关未提交行为差异；
- 报告未提交、validator 无效、失败证据将被覆盖、或有未执行项；
- 验收通过却准备跳过最终逻辑稿、用户确认或同 commit 锚定；
- 完成条件、六类引用、Git 对象或 ledger 身份不一致；
- 完成事件后准备在同一轮做归位、清理或远端动作。
