# Spec 阶段

只在 `current_stage=writing_spec` 时完整读取。`direct` 不进入本阶段。先读取持久 `flow`：`light` 使用短 Spec；`full` 使用完整 Spec 和测试稿子节点。只有 Full 的 Worker 隔离、持久 handoff、摘要和恢复以 [stage-worker-contract.md](stage-worker-contract.md) 为唯一规范源，派发只使用 [spec-worker-prompt.md](spec-worker-prompt.md)。

## 输入

读取同一 `change_id` 的登记版 `change_ref`、当前有效行为约定和用户验收输入。只有 Full 读取用于影响调查的完整 `code_sha`；Light 不强制代码 SHA 扫描。从本阶段开始不得读取或依赖讨论稿，历史摘要只作为搜索线索。

## Light profile

调用 `writing-specs` 时明确传入 `profile=light`。候选只包含问题、触发条件、期望行为、本次范围、完成条件，以及有直接相关项时的必须保持不变行为或关键兼容边界。Light 不强制既有功能影响表，不强制代码 SHA 扫描，不生成正式 `test_ref`，也不生成正式 `plan_ref`。

按 `review_mode` 展示并确认或自动发布 `specs/<change_id>.md`，形成有效 `spec_ref` 后直接把阶段设为 `tdd_coding`。需要拆步骤时在 `.local/deliveries/<delivery_id>/changes/<change_id>/tasks.md` 维护运行态清单；它不提交 Git，不成为 Plan。

Light 不加载 `material-change-assessment.md`。已有或明确相关行为约定发生变化时，只在本短 Spec 中写清新的期望行为、范围与兼容边界；范围扩大到 Full 条件时停止并报告，不在 Light 中制造 Spec/Plan 双结论。

## Full Spec Worker

1. 总控按 stage-worker contract 初始化或验证 `writing_spec/spec_worker` handoff，再用全新 Spec Worker 执行 `writing-specs`，明确传入 `profile=full`。平台支持时使用 `fork_turns=none`。
2. draft 模式只写 `.local/stage-workers/.../writing_spec/candidate.md`，不写 canonical Spec，不形成 `spec_ref`。
3. Spec 必须包含 `## 既有功能与流程影响`：用稳定 `impact_id` 记录直接相关既有行为与保持、兼容扩展或明确改变；没有直接关联项时使用 `writing-specs` 的唯一无影响结论。行为影响不确定时保持本阶段。
4. Worker 返回 `candidate_ready` 后，总控用 `scripts/stage_worker_handoff.py validate --config <当前配置>` 验证 workflow、change、stage、role、input refs、固定路径、摘要和 revision；读取候选一次完成审核，并在对话中完整展示。文件链接不能代替正文。
5. 用户确认必须绑定当前 `candidate_sha256`。确认前不得保存 canonical Spec、生成测试稿、更新引用或推进阶段。新对话必须重新展示并确认；durable handoff 不恢复授权。
6. 用户确认后恢复原 Worker；不可恢复时派发新的 publish Worker，只传已确认候选、确认事实、摘要和同一有效 handoff。helper 必须核对 `confirmed_candidate_sha256` 后才能保存 `specs/<change_id>.md` 并形成 `spec_ref`。
7. 只有 Full 的 publish Worker 按 `writing-specs` 调用 `writing-test-drafts` 作为本阶段子节点，生成 `tests/<change_id>.md` 和 `test_ref`。用户提供的步骤、流程和预期优先；测试稿不因影响表自动扩展回归项，本工作流不修改 `writing-test-drafts`。

`writing-specs` 是“可能的影响范围”的唯一规范源；总控只把该章节传给下一阶段，不重述或扩大含义。Spec Worker 不修改 SQLite。

## 阶段收尾

Light 验证 `spec_ref` 后进入 `tdd_coding`。Full 验证有效 handoff；`spec_ref` 与 `test_ref` 及真实 Git 对象都有效后，再用 `managing-change-ledger` 更新引用并进入 `writing_plan`。登记版 `change_ref` 始终保持不变；测试稿子节点不新增工作流阶段。

## 停止信号

- 当前行为或 Light 的范围与完成条件无法确认；
- 正准备让 Light 进入 Plan，或在阶段切换后继续编码；
- 以下 Worker、handoff、完整候选展示和代码基线信号只适用于 Full：材料变更评估尚未确认；Worker 不是新鲜上下文或 handoff 身份/摘要/revision 不匹配；主 Agent 未审核、未完整展示候选或用户未确认精确摘要；完整影响或代码基线无法验证；正准备让主 Agent 代写 Full 候选或让 Worker 修改 SQLite。
