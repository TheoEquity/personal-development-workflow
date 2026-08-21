# Spec 与测试稿阶段

只在 `current_stage=writing_spec` 时完整读取。Worker 的隔离、持久 handoff、摘要和恢复以 [stage-worker-contract.md](stage-worker-contract.md) 为唯一规范源；派发只使用 [spec-worker-prompt.md](spec-worker-prompt.md)。

## 输入

读取同一 `change_id` 的登记版 `change_ref`、已经明确为直接相关的不可变正式引用、用户验收输入，以及配置仓库中用于调查的完整 `code_sha`。从本阶段开始不得读取或依赖讨论稿。

已有或明确相关正式材料可能变化时，先完整读取并执行 [material-change-assessment.md](material-change-assessment.md)，展示两份结论并等待确认；没有直接相关正式材料的新需求不制造空评估。

## Spec Worker

1. 总控按 stage-worker contract 初始化或验证 `writing_spec/spec_worker` handoff，再用全新 Spec Worker 执行 `writing-specs`。平台支持时使用 `fork_turns=none`。
2. draft 模式只写 `.local/stage-workers/.../writing_spec/candidate.md`，不写 canonical Spec，不形成 `spec_ref`。
3. Spec 必须包含 `## 既有功能与流程影响`：用稳定 `impact_id` 记录直接相关既有行为与保持、兼容扩展或明确改变；没有直接关联项时使用 `writing-specs` 的唯一无影响结论。行为影响不确定时保持本阶段。
4. Worker 返回 `candidate_ready` 后，总控用 `scripts/stage_worker_handoff.py validate --config <当前配置>` 验证 workflow、change、stage、role、input refs、固定路径、摘要和 revision；读取候选一次完成审核，并在对话中完整展示。文件链接不能代替正文。
5. 用户确认必须绑定当前 `candidate_sha256`。确认前不得保存 canonical Spec、生成测试稿、更新引用或推进阶段。新对话必须重新展示并确认；durable handoff 不恢复授权。
6. 用户确认后恢复原 Worker；不可恢复时派发新的 publish Worker，只传已确认候选、确认事实、摘要和同一有效 handoff。helper 必须核对 `confirmed_candidate_sha256` 后才能保存 `specs/<change_id>.md` 并形成 `spec_ref`。
7. publish Worker 按 `writing-specs` 调用 `writing-test-drafts` 作为本阶段子节点，生成 `tests/<change_id>.md` 和 `test_ref`。用户提供的步骤、流程和预期优先；测试稿不因影响表自动扩展回归项，本工作流不修改 `writing-test-drafts`。

`writing-specs` 是“可能的影响范围”的唯一规范源；总控只把该章节传给下一阶段，不重述或扩大含义。Spec Worker 不修改 SQLite。

## 阶段收尾

总控验证有效 handoff、`spec_ref`、`test_ref` 及其真实 Git 对象，再用 `managing-change-ledger` 只更新这两份引用；登记版 `change_ref` 保持不变。`spec_ref` 与 `test_ref` 都成功更新后把阶段设为 `writing_plan` 并立即停止。测试稿子节点属于本阶段收尾，不是另一个工作流阶段。

## 停止信号

- 材料变更评估适用但尚未确认；
- Worker 不是新鲜上下文，或 handoff 身份/摘要/revision 不匹配；
- 主 Agent 未审核、未完整展示候选，或用户未确认精确摘要；
- 当前行为、影响或代码基线无法验证；
- 正准备让主 Agent 代写候选、让 Worker 修改 SQLite，或在同一轮开始规划。
