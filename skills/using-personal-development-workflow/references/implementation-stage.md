# 正式 TDD 编码阶段

只在 `current_stage=tdd_coding` 时完整读取。代码实现开始前先读取持久 `flow`：`direct/light` 使用本节的轻量执行合同；`full` 按 Plan 的 `base_source` 重新核对基线，并依 [execution-contract.md](execution-contract.md) 和 [stage-worker-contract.md](stage-worker-contract.md) 执行后续 SDD 门禁。

## Direct / Light 轻量执行

- `direct` 依据当前 CE 的既有行为和验收要求；`light` 依据当前短 Spec。两者都用 `test-driven-development` 完成最小 RED、实现和验证，不生成正式 Plan、`test_ref` 或 `evidence_ref`。
- 实施存在多个先后步骤时，只在 `.local/deliveries/<delivery_id>/changes/<change_id>/tasks.md` 维护简短清单；`direct` 的单任务使用内部 `T1`，不创建任务文档。
- 新增或改变正式行为时由 direct 切到 light，先补最小短 Spec；仍是恢复已有行为时可保持或切回 direct。发现 full 风险时停止并报告，不在轻量执行中自动升级。

## Worker 与 Delivery

开发使用滚动 Delivery：一个 Delivery Worktree 负责接收串行集成、最终候选验证和准备 MR。一个 Full CE 只使用一个实现 Worker Worktree，绑定当前 `change_id + plan_ref` 并在其中执行整份 Plan；1–3 个 SDD Task 是这个 Worker 内的实现/review 边界，不创建额外外层 Worker、worktree 或集成候选。Direct/light 也默认使用一个当前 CE 范围的 Worker。不同 CE 可以并发开发，集成必须串行。

在已开启的个人工作流内，Worktree 是 Delivery/Worker 身份和后续 `code_ref` 的组成部分。用户拒绝创建或使用 Worktree 时保持 `tdd_coding` 并停止，不得在原 checkout 降级开发；如需脱离这套约束，用户必须明确关闭个人工作流后另行决定，现有 CE 和游标不会因此被自动完成或清理。

状态只保存在 Spec Vault `.local`，不新增总账表或正式材料：

```text
.local/deliveries/<delivery_id>/delivery.json
.local/deliveries/<delivery_id>/workers/<worker_id>.json
.local/deliveries/<delivery_id>/changes/<change_id>/tasks.md
```

修改前必须用真实 Git 状态复核目录、分支、绑定 CE/Plan、基线 SHA 和 dirty 状态。Worker 身份不匹配、已经集成或记录与 Git 不一致时停止，不复用它做新 CE 或新 Plan。Worker 合入后记录实际 `integrated_commit`；Worker 不直接修改 `change.md`。

`review_mode=manual` 时本地 commit 仍需当前节点确认；`review_mode=auto` 允许在当前 CE 已登记 Worker 分支和本地 Spec Vault 中创建范围内本地 commit。两种模式都不授权 Worker 合入 Delivery、Push、MR、合并、部署或删除 Worktree。

## 可选 Loop 与 Code Review

`loop_mode: off | on` 默认关闭，只能由用户显式开启。Loop 只允许 direct/light；Full 必须回复“复杂任务不能进入 Loop”。Loop 只能在 `direct` 与 `light` 之间切换，按“轻量验证清单 → 每个关键可视步骤截图或无界面机器证据 → `systematic-debugging` 根因排查 → 最小充分修改 → 从头重试”运行。范围扩大、重复不稳定或出现 full 风险时停止，不无限循环。

`code_review: skip | run` 默认可跳过，不进入总账。用户要求 run 时，在 Delivery 固定同一受测 SHA 和以下精确范围：

```text
review_scope: CE | batch
review_base: <sha>
review_head: <sha>
reviewed_worker_head: <sha | null>
review_commits: [<integrated_commit>...]
```

CE 范围时，`review_base` 取该 CE 的 `delivery_before_sha`。Full 的 `reviewed_worker_head` 绑定最终审查对象，`review_head` 记录受审的 Worker SHA；`code_ref` 另行记录 Delivery merge SHA。Delivery 用 Git 证明 Worker SHA 是 merge SHA 的祖先，且 `--no-ff` 集成没有改写该 CE 的已审 diff；`review_commits` 只取当前 CE 的集成记录，按 Delivery 祖先顺序排列、不得重复。该证明把 SDD 最终整体 review 绑定到最终候选，而不要求 Worker SHA 与 merge SHA 相等。Full 的 SDD 最终整体 review 同时满足 Full CE 级代码 review，Coordinator、Root 和 Delivery 不得追加等价代码 review；`code_review=run` 只核对并复用该精确范围的最终 review。Direct/light 明确要求 CE review 时只增加一次范围化只读 review，不派测试 Agent 重跑已有证据。

只有用户明确要求跨 CE 批次 review，才在 `review_base=freeze_base`、`review_head=freeze_head` 和该批次全部、且仅限该批次的 `integrated_commit` 上增加一次批次级只读审查。它只审查跨 CE 交互，不重做各 CE 已完成的内部代码 review；它消费已有自动化证据，相同证据键不得重跑测试。审查不得修改、commit 或移动受测 SHA。`code_review`、`loop_mode` 在 CE 完成后关闭，新会话不恢复。

## Full 的 SDD 专用门禁

Full 实现不固定角色模型或推理档位。Implementation Coordinator 按任务复杂度选择足够完成任务的最低合理档位；没有代表性结果证明收益时，不因 reviewer、返工或 Full 身份自动升级。

Plan 刚采用或新对话恢复时，先从当前 `plan_ref`、配置仓库和 Plan 基线实例化并完整显示不可变 `authorization_offer`，然后逐字询问：**“是否开启 Subagent-Driven Development 进行开发？”** 阶段状态为“等待 SDD 选择”。offer 缺字段时不能提问。只回复“继续”不算明确开启 SDD。

只接受用户对该门禁明确表达“开启 / 使用 SDD”的肯定答复或明确“不启动”。“继续”“开始开发”、沉默、含糊回答、Plan 批准或旧对话都不是 SDD/commit 授权。展示 offer 后立即停止；同一轮不得 fetch、创建开发 worktree、修改代码或 commit。

用户明确回复“开启”后才进入 SDD 门禁并执行。用户明确回复“不启动”时，保持 `tdd_coding`，不创建 worktree、不修改代码、不创建本地 commit，并停止。用户之后另行明确选择非 SDD 执行方式时，才可使用带独立逐任务 reviewer 的 `executing-plans`；不启动本身不自动降级。

以上提问只适用于 `review_mode=manual`。`review_mode=auto` 在当前已绑定 CE、当前精确 `plan_ref` 和一个实现 Worker 范围内不再询问 SDD，可实例化同样不可变的 offer 并授权创建/进入隔离 worktree、执行 SDD 与创建该 CE 范围内本地 commits；它不得扩展到另一个 CE、仓库或 Delivery，也不授权合入 Delivery、Push、MR、部署或删除 Worktree。需求不清、范围扩大、基线漂移、offer/contract 不一致或 4+ Task 缺用户例外确认时立即停止。

## 开发前远程基线门禁

仅当 `base_source=remote` 且 offer 已被当前对话明确接受时执行：

1. 核对 offer 与 Plan 的结构化来源字段仍逐字一致。
2. 第一项动作是 `git fetch --no-tags <base_remote> +refs/heads/<base_branch>:refs/remotes/<base_remote>/<base_branch>`，只更新该 remote-tracking ref；再以 `<base_remote>/<base_branch>^{commit}` 解析最新完整 SHA。总控不对主 checkout 执行 `git pull`、merge 或 reset。
3. fetch、认证、网络、ref 更新或解析失败时保持本阶段并停止；不得创建或复用开发 worktree，不得写 RED、测试或生产代码，不得创建本地 commit。同一对话且 offer 未变时，用户之后回复继续可重试同一受限 fetch；瞬时执行失败本身不制造材料变更评估。
4. 最新 SHA 等于 Plan `base_sha` 时，才把该 SHA 作为强制 `start_point` 交给 `using-git-worktrees`。实际 worktree 的 `HEAD` 必须等于该 SHA、工作区干净、仓库和 AGENTS 仍与评审输入一致。
5. SHA 不一致才属于漂移：旧 offer 失效，记录差异，只审查这段远程差异对 Spec、Plan 兼容性、Task 和 AGENTS 的影响；保持当前阶段并先执行材料变更评估。确认后至少返回 `writing_plan`，用户可观察行为改变则返回 `writing_spec`，不得由 Plan 自行决定。重新评审、提交并由 `adopt-plan` 采用后才能再显示门禁。

## 开发前本地基线门禁

仅当 `base_source=local` 且 offer 已接受时执行。不执行远程 fetch 或远程相等性比较。使用结构化 `base_worktree`、`base_local_branch`、`base_detached_sha` 核对定位对象和 commit，不能解析可读 `base_locator`。

只有现有隔离 worktree 的 `HEAD` 必须逐字等于 `base_sha`、工作区必须干净，仓库与 AGENTS 仍一致时才复用；否则从精确 SHA 创建新的隔离 worktree。来源对象移动、commit 不存在或 offer 变化时先做材料变更评估，确认后返回 `writing_plan` 重新选择基线。不得退回远程 SHA、主 checkout、其他本地 HEAD 或混入选择时排除的 dirty 修改。

## 合同派生与 Implementation Coordinator

来源门禁通过且实际 worktree 验证后，才从已接受 offer 机械派生最终 `execution_contract`；只补入 `using-git-worktrees` 实际返回的 `workspace_or_branch`，其余字段逐字复制。出现第二仓库、更宽 Plan/Task、不同 TDD/commit/finishing 边界时停止。

总控重新核对 `change_ref`、`spec_ref`、`plan_ref`、`test_ref` 和基线，初始化或验证唯一 `implementation/implementation_coordinator` handoff。helper 将规范化 offer/contract 原样固化为当前 run 的 `authorization-offer.json`、`execution-contract.json` 和 SHA-256。使用 [implementation-worker-prompt.md](implementation-worker-prompt.md) 派发这一个实现 Worker/Coordinator；它只读取 helper 文件，逐字节、摘要和逐字段验证后启动 `subagent-driven-development`。

Coordinator 是 SDD controller，不是 Task Implementer。它在同一 Worker worktree 内按正式 Plan 的默认 1–3 个 Task 串行派发逐任务 Implementer、独立 Task Reviewer、必要 Fixer 和 Final Reviewer；这些内部角色不是新的外层 Worker。Task 角色不得自行派发 reviewer 或辅助 Subagent。已接受 offer 与同一序列化内容原样传给所有角色，不能在 Task 间改写。全部任务结束后写完整报告，短返回有效 handoff 并返回本入口；不得调用 `finishing-a-development-branch` 或执行任何集成动作。

## TDD、验证与 code_ref

使用 `test-driven-development`；它是有效 RED 顺序、可复现实现前基线和结构化证据的唯一规范源。Task Implementer 负责 TDD 和 Task 聚焦测试；Reviewer 使用已有测试证据审查，不默认重跑。任务不满足有效 RED/豁免与证据定义时，不得进入 reviewer、报告 DONE 或开始下一 Task。

自动化证据的复用键固定为 `code_sha + command + environment_fingerprint + input_fingerprint`。四项完全相同的成功证据只执行和记录一次；Coordinator 汇总 Task 结果与 SDD 最终整体 review，不重跑完整测试；Root 只验证引用、SHA、范围和证据，不重跑测试或追加 review。`environment_fingerprint` 是影响结果的工具链、运行时和配置的稳定摘要，`input_fingerprint` 是参数、fixture、数据集和跨 CE 组合输入的稳定摘要；时间戳、run id 和临时路径只有在会改变行为时才纳入。审计用 `scope` 另行记录，但会改变执行内容的范围必须进入 `input_fingerprint`。任一复用键维度变化，相关证据失效并重新执行；新代码 SHA 或新的跨 CE 组合状态不是重复证据。失败证据始终保留且不可复用；原键重试只限已记录的瞬时失败，否则先修复导致变化的代码、环境或输入。

可跨角色复用的成功证据只在相关实现已经提交后绑定 Worker `HEAD`；TDD 的提交前 RED 和中间 GREEN 仍保留在 Task 记录中，但不伪装成可跨阶段复用的已提交版本证据。Implementation Coordinator 完成 handoff 时必须通过 helper 写入结构化 `verification_evidence`，每项包含 `code_sha`、`command`、`environment_fingerprint`、`input_fingerprint`、`scope`、`result=passed` 与 `produced_by=task_implementer`；helper 要求 `code_sha` 等于 Worker `HEAD`、复用键不重复，并锁定 `report.md` 摘要。

更新 `code_ref` 前，本次相关测试和生产代码必须包含在一个获得明确授权的本地 commit 中；不得用仍指向旧内容的 `HEAD` 表示未提交修改。Delivery 在最终候选合并版本上执行一次 CE 完整自动化验证，作为该候选 SHA 的完整证据所有者。

合同不授权 commit 时，保留范围内未提交测试和代码，保持 `tdd_coding`、原 `code_ref` 和事件 `in_progress`，状态写“待授权提交”，不得误报 blocker。用户随后明确授权时，按 flow 核对当前 CE 的既有行为或短 Spec 与 diff；Full 另核对精确 Plan。之后运行新鲜验证，只提交授权文件。

形成唯一 Worker 提交后，只读确认本次相关文件没有遗漏在 commit 之外，把 Worker 标记为待集成候选。Worker 不直接写 `code_ref`。用户明确授权本地合入后，Delivery 形成一个最终候选 merge；冲突或验证失败立即停止，候选保持原状。

该 CE 的唯一 Worker 已集成，且最终候选 SHA 的一次 CE 完整自动化验证通过后，才从实际 Delivery Worktree 调用：

```text
set-code-ref <change_id> --worktree <absolute-delivery-worktree-root>
```

`managing-change-ledger` 用 Git common directory匹配配置仓库，从 Delivery 读取完整 `HEAD` 并原子写入单一 `code_ref`；Worker 的 `integrated_commit` 仍留在本地状态，用于 CE 归属和审核范围，不把 `code_ref` 改成数组。提交事务前 HEAD 变化则回滚。

引用成功后，direct/light 核对轻量验证清单，full 核对 `test_ref`、Delivery 完整自动化证据和 SDD 最终 review。若 `code_review=run`，按上文复用 CE review 或执行用户明确要求的跨 CE 批次 review；通过后才把阶段从 `tdd_coding` 进入 `acceptance`。`manual` 立即停止；`auto` 可重新加载验收路由继续，并在最终验收确认门停止。

## 返工与停止信号

当前 flow 的行为约定、代码事实或 Git 引用冲突时停止，不通过代码补设计。Direct/light 的新增可观察行为返回短 Spec，恢复既有行为的实现偏差留在当前 CE 最小修复；Full 的 Spec 变化返回 `writing_spec`，纯实现兼容或 Plan 变化返回 `writing_plan`。

- 所有 flow：worktree 身份不精确、相关 dirty 内容未进入受测提交、TDD 或新鲜验证将被跳过；正准备把编码/commit 授权解释成 push、MR、合并、清理或 finishing；阶段切换后正准备开始验收。
- 以下 Plan、SDD offer、Coordinator、独立 reviewer 和材料变更评估信号只适用于 Full：offer 未被明确接受；远程 fetch/解析失败、SHA 漂移或本地来源移动；offer、最终合同或 handoff 被改写、扩大或摘要不匹配；正准备跳过 Coordinator 或 Full 的独立 reviewer。
