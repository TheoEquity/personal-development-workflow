# 测试稿、验收与事件完成阶段

只在 `current_stage=writing_test` 或 `acceptance` 时完整读取。先按持久 `flow` 选择完成门：direct/light 使用轻量验证与历史摘要；full 使用正式测试稿、验收报告、validator 和最终逻辑稿。

## Direct / Light 验收

在 Delivery 的当前 `code_ref` 快照上核对轻量验证清单。已绑定相同 `code_sha + command + environment_fingerprint + input_fingerprint` 的成功自动化证据直接复用，只实际执行尚未覆盖的项目；记录复用引用、实际命令、关键结果和必要截图或机器证据。相关未提交行为差异、失败或未执行项都不能完成；失败保留原 `change_id` 并返回实现，除非发现新的独立交付范围。

验证通过后，由 CE 收尾过程统一把最终结果写进完成版 `changes/<change_id>/change.md` 的 `## 修改与验证摘要`；Worker 不直接修改 `change.md`。摘要只保留：

```text
类型：Bug 或小需求
模块：主要影响区域
问题：当时出现了什么问题或需要什么行为
修改：最终大致怎样处理
验证：怎样确认结果有效
来源：source_ce（没有则省略）
```

历史摘要不是当前行为合同。判断现在应该怎样表现时，以当前有效 Spec 或最新相关 CE 的行为约定为准；旧摘要只作为调查线索，不能覆盖新行为。

direct 完成必需 `change_ref`、`code_ref` 和上述摘要；light 额外必需 `spec_ref`。两者不强制 `plan_ref`、`test_ref`、`evidence_ref` 或最终逻辑稿，不得创建空占位材料。

## Full：兼容 `writing_test`

新事件的初始测试稿已在 `writing_spec` 子节点形成，不在编码后首次编写。`writing_test` 只兼容已有游标，或验收失败后仅需修正操作、数据或环境的旧回环。

使用 `writing-test-drafts` 修改 `tests/<change_id>.md`，不得改变正确的 Spec 行为契约。提交后只更新 `test_ref`，再把阶段设为 `acceptance` 并立即停止；登记版 `change_ref` 保持不变。

## Full：实际验收

1. 用户要求验收或 `full + auto` 到达验收阶段后，按绑定版本测试稿逐项核对覆盖状态。
2. 执行第一个尚未覆盖的测试项前，确认实际运行内容与总账 `code_ref` 指向同一 Git commit，并确认没有会改变受测行为的相关未提交改动。无法证明时返回 `tdd_coding` 并停止。
3. Acceptance 复用绑定同一 `code_ref` 的自动化证据：当 `code_sha + command + environment_fingerprint + input_fingerprint` 与 Delivery 成功证据完全一致，且证据包含 `scope`、`result=passed` 和 `produced_by=delivery` 时，只在报告中按 `writing-test-drafts` 的 `复用自动化证据：<compact-json>` 结构引用，不实际重跑；validator 机械核对证据结构和 `code_sha`。只执行测试稿中尚未覆盖的手工步骤、外部环境或真实服务验收。任一维度变化时旧证据失效并重新执行；复用通过项是 `passed`，不是 `not_executed`。
4. 按 `writing-test-drafts` 唯一报告合同生成并提交一份新的独立验收报告，不覆盖旧失败报告；每一项明确标记复用证据或本阶段实际执行证据。
5. 调用 `writing-test-drafts` 的唯一 validator，把当前 `change_id`、`test_ref` 和 `code_ref` 作为期望绑定。validator 无效时停止；有效时只消费其规范化结果，再用 `managing-change-ledger` 只更新 `evidence_ref`。

结果路由：

- 全部通过：校验报告、测试稿、完整 SHA、六类引用和实际受测代码，然后进入最终逻辑稿门禁。
- 包含失败：事件保持 `in_progress`，保留已提交失败报告，按下面回环处理。
- 没有失败但存在未执行：总体未完成，保留本阶段并说明原因。

## Full：开发与验收回环

内部 TDD、自测或验收失败始终使用当前 `change_id`，不建立新变更事件：

```text
Spec 与测试稿 → Plan → TDD 编码 → 内部验收 → 独立验收报告
                                             ├─ 通过 → 最终逻辑稿 → 完成事件
                                             └─ 失败 → 失败回传 → 最早责任阶段 → 再验收
```

失败事实必须来自可复现 TDD/自测或 validator 规范化结果。出现失败、需求修正、追加、范围扩展、reviewer/代码调查或基线漂移时，才完整读取 [material-change-assessment.md](material-change-assessment.md)，基于当前不可变 `spec_ref`、`plan_ref` 输出 Spec 与 Plan 两份结论并等待确认。

确认后只倒回最早责任阶段：Spec 变化回 `writing_spec`；仅 Plan 变化回 `writing_plan`；两者无需修改且属于实现偏差时回 `tdd_coding`；测试操作/数据/环境有误按测试稿路径处理。每次只更新一个阶段并立即停止。已完成事件之后的变化或外部反馈建立新事件，旧事件和引用不可修改。

## Full：验收通过后的最终逻辑稿

验收报告全部通过之后、完成变更事件之前，才加载 `writing-final-logic-drafts`，原样传入同一 `change_id`、当前 `spec_ref`、`plan_ref`、`test_ref`、`code_ref`、`evidence_ref`。

候选与保存稿固定为 `logic/<change_id>.md`，标题 `# <change_id> 最终逻辑稿`，必填 `## 功能逻辑`，可选 `## 注意事项`。内容按真实顺序讲清核心机制、触发、处理、结果及必要层级、重复触发或清理行为，不写代码导读或测试证据。

`full + auto` 可以在已有有效验收报告后自动生成最终逻辑稿候选，但不能自动确认它。先在对话中完整展示候选并停止，形成最终验收确认门。用户确认后才保存 canonical 文件；未确认、材料冲突或正文无法由实际代码与验收事实证明时保持 `acceptance`，不修改 `change.md`、SQLite 或代码。保存后仍保持本阶段并停止；不增加 SQLite 阶段或 `logic_ref`。

## 完成变更事件

Full 在确认 canonical 逻辑稿存在后，按 `managing-change-ledger` 完成合同形成最终 `change.md`：同一 `change_id`、`status: completed`、与总账逐字一致的 `spec_ref`、`plan_ref`、`test_ref`、`code_ref`、`evidence_ref`，以及唯一 `logic/<change_id>.md` 和最终结论。Direct/light 则只写本节规定的真实引用和修改与验证摘要。

Full 的最终 `change_ref` 同一 Git commit tree 必须包含完成版 `change.md` 和逻辑稿；direct/light 的最终提交只需包含其完成版 `change.md` 和当前 flow 的真实材料。取得 SHA 后调用：

```text
complete <change_id> --change-ref changes/<change_id>/change.md@<final-sha>
```

即执行 `complete <change_id> --change-ref changes/<change_id>/change.md@<final-sha>`；成功后阶段变为 `completed` 并立即停止。

只有当前 flow 要求的材料、阶段和 Git 对象检查全部通过，命令才在一个事务内原子更新最终 `change_ref` 和 `status=completed`；Full 另要求材料角色与报告绑定。总账完成后关闭该事件游标，使其为 `current_stage=completed`、`state=closed`。已完成事件允许幂等查询。

阶段切换后立即停止；本轮不得读取或执行集线、归位、branch finishing 或清理。下一轮进入 `completed` 路由时，才自动展示归位与清理候选卡。

## 停止信号

- 受测内容与 `code_ref` 不一致，或存在相关未提交行为差异；
- 当前 flow 必需的验证失败、未执行，或失败证据将被覆盖；
- 以下报告、validator、最终逻辑稿和六类引用信号只适用于 Full：报告未提交、validator 无效、准备跳过最终逻辑稿或同 commit 锚定、六类引用不一致；
- 当前 flow 的完成条件、Git 对象或 ledger 身份不一致；
- 完成事件后准备在同一轮做归位、清理或远端动作。
