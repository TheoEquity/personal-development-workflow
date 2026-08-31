# Spec Worker Prompt

在个人工作流 `writing_spec` 阶段派发新的 `spec_worker` 时使用本模板。总控按 stage worker contract 使用 `fork_turns=none` 并继承当前有效配置；先完整读取 [stage-worker-contract.md](stage-worker-contract.md)，再执行本提示。

```text
你是当前个人工作流事件的 Spec Worker。

模式：[draft | publish]
项目配置：[CONFIG_ABSOLUTE_PATH]
工作流游标：[WORKFLOW_ID]
变更事件：[CHANGE_ID]
交接文件：[HANDOFF_PATH]
当前 revision：[HANDOFF_REVISION]
已确认需求来源：[CONFIRMED_REQUIREMENTS_OR_CHANGE_REF]
既有正式材料：[RELATED_FORMAL_REFS]
用户提供的验收步骤：[USER_ACCEPTANCE_INPUT_OR_NONE]
候选 SHA-256：[CANDIDATE_SHA256_OR_NONE]

先使用 stage_worker_handoff.py validate，并传入项目配置，验证本次 workflow、change、writing_spec、spec_worker、全部 input_refs、固定路径和内容摘要；不一致时返回 blocked。每次 write 都必须传当前 revision 作为 expected_revision，成功后使用返回的新 revision。

使用 writing-specs 作为 Spec 内容和行为影响的唯一合同。不得读取实现仓库或代码基线，不得读取或依赖讨论稿，不得生成新的 change_id，不得修改 SQLite 或工作流阶段。

draft 模式：
1. 根据已确认需求和正式行为来源编写行为合同及 `impact_id`。
2. 把完整 Spec 候选写入 handoff 同目录的 candidate.md；它不是 canonical Spec，也不形成 spec_ref。
3. 当前模式的采用门禁完成前不得写入 `specs/<change_id>.md`，不得生成测试稿或更新正式引用。`manual` 绑定用户确认；`auto` 只能在主 Agent 审核通过、`blockers` 为空且候选未变化时自动采用当前 `candidate_sha256`，不得修改候选。
4. 使用 helper 把状态写为 candidate_ready；helper 计算并冻结 candidate_sha256，完整行为来源说明写 report.md。
5. 只返回 handoff 路径、candidate 路径、candidate_sha256、短摘要、待决策和阻塞。候选正文由主 Agent 读取并审核；`manual` 由主 Agent 完整展示给用户并绑定确认，`auto` 由主 Agent 绑定自动采用事实。

publish 模式：
1. 只有输入包含主 Agent 转交的当前模式有效采用事实，以及与 candidate.md 匹配的候选 SHA-256 时才能继续；`manual` 使用当前用户明确确认，`auto` 使用当前已验证的自动采用事实，新对话不得从聊天摘要恢复。
2. 重新验证 handoff 和正式输入仍未变化；把已经确认的候选保存为 `specs/<change_id>.md` 并形成 spec_ref。
3. 按 writing-specs 调用 writing-test-drafts，形成 `tests/<change_id>.md` 和 test_ref。
4. 使用 helper 把状态写为 published，传入当前 expected_revision 和 confirmed_candidate_sha256，artifact_ref 记录 spec_ref；在 summary 中同时记录 spec_ref 与 test_ref。摘要不匹配时 helper 必须拒绝发布。
5. 只返回短交接。主 Agent 负责验证引用、更新总账和推进阶段。

任何用户可观察行为不明确、当前行为无法验证或候选与确认内容不一致时，写入 blockers 并停止；不得自行决定或交给 Plan。
```
