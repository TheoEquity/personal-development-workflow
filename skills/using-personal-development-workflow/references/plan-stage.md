# Plan 阶段

只在 `current_stage=writing_plan` 且 `flow=full` 时完整读取。Direct/light 不进入本阶段；需要拆步骤时只维护 `.local` 运行态任务清单，不生成正式 `plan_ref`。Full 以整个工作流任务及其一个变更事件为边界；一个工作流任务始终只对应一份 Plan。Plan 内可以有多个 `Task N`，但不得为实现 Task 新建 Plan、游标或事件。重新规划仍更新 `plans/<change_id>.md`，历史版本由新的完整 Git SHA 区分。

## 固定采用顺序

```text
稳定基线确认
→ 全新 Plan Worker 写不可变候选
→ adopt-plan --dry-run 机械校验
→ 同一名独立语义 reviewer Approved
→ 主 Agent 审核有效 handoff 与精确候选
→ manual 用户确认 / auto 总控采用同一候选
→ managing-change-ledger adopt-plan 原子采用
```

完整执行 [plan-review-contract.md](plan-review-contract.md)。lint、reviewer、主 Agent 审核和用户确认互不替代；候选内容变化后旧结论一律失效。

## 固定 Lean Plan 与基线门禁

所有正式 Plan 始终采用 Lean，固定使用 `writing-lean-plans`，不再展示 profile 方案卡。Plan 必须保留 `> **Plan profile:** lean` 机器标记；这不是用户需要选择的配置。安全、支付、供应商或其他高风险场景只提高验证要求，不切换成长篇微步骤 Plan。

正式 Plan 默认 1–3 个执行 Task。每个 Task 必须是完整实现与 review 边界，并至少包含一个非测试、文档或配置的生产代码 Create/Modify 目标；支持性工作归入产生该行为的垂直 Task。超过 3 个 Task 时，Plan 必须为每一个 Task 在 `## Task 数量例外` 中写明具体且逐项唯一的独立交付、依赖或风险边界，并取得用户例外确认；单字符、复制理由、缺行或与 Task 内容不符时不得采用。该确认只允许主 Agent 根据当前用户消息在正式采用时传入 `--user-confirmed-task-count-exception`，不得由 Worker、reviewer、Plan 自述或 `review_mode=auto` 自行推导；第一轮不为此增加账本字段或授权材料。

每次创建正式 Plan 或形成新的 `plan_ref`，都执行 [plan-baseline-selection.md](plan-baseline-selection.md) 的稳定基线候选卡。用户选定并验证 `base_sha` 前，不得调查代码、调用 writer 或 reviewer。新需求和并发需求的轮次冻结、候选来源及不可混合基线也由该 reference 唯一定义。

## Worker、候选与兼容性

基线确认后，按 [stage-worker-contract.md](stage-worker-contract.md) 初始化或验证 `writing_plan/plan_worker` handoff，使用 [plan-worker-prompt.md](plan-worker-prompt.md) 派发全新 Worker并加载 `writing-lean-plans`。派发使用 `fork_turns=none` 并继承当前有效配置。Worker 读取当前 `change_ref`、完整 Spec 和全部 `impact_id`、测试稿、选定 Git tree、适用 AGENTS 与已确认工作区差异，不读取 Spec Worker 聊天或讨论稿。

Plan Worker 必须在选定 `base_sha` 的精确 Git tree 上执行代码影响调查：定位相关文件、符号、调用链、状态和测试接缝，再把结论写入 `## 实现兼容性分析` 与真实 `Task N`。Spec 不提供代码路径、符号或 `code_sha`，Plan 不得从讨论稿补足这些事实。

候选必须包含：

- `## 开发基线`：`base_repository`、`base_source`、结构化 `base_locator`；`base_sha` 必须是 40 位完整 Git commit SHA。远程来源另有 `base_remote`/`base_branch`，本地来源另有 `base_worktree`/`base_local_branch`/`base_detached_sha`、pushed 状态和 dirty 排除。机械验证不得从可读 locator 反向解析。
- `## 实现兼容性分析`：逐项记录 Spec `impact_id` 或 `implementation-only`、现有代码或方法、新方案交点、技术影响、处理方式和对应任务。`无影响` 给代码证据并写 `无需任务`；`需要适配`/`需要迁移` 映射到编号规范且唯一的真实 `Task N`；`阻塞` 或待确认项不能采用。Spec 标为 `明确改变` 的每项至少有一条适配或迁移任务。

## 机械 lint 与语义 reviewer

Plan Worker 对每个不可变候选先运行当前项目配置的 `adopt-plan --dry-run`。确定性 plan-lint 检查标题和 Task grammar、checkbox、Files、Consumes/Produces、占位符、impact 表、覆盖、引用、完整 SHA、代码基线和适用 AGENTS。只有 `status=validated` 才派发 reviewer；dry-run 不修改 SQLite、引用或阶段。

lint 通过后只派发一名独立语义 reviewer，使用 `fork_turns=none` 并继承当前有效配置，复审继续同一 reviewer。固定使用 `lean-plan-document-reviewer-prompt.md`，由 review contract 将阻断范围收窄为错误方案、缺失行为和不可实现接口三类。首次评审 15 分钟并一轮穷尽阻断；第一次复审 10 分钟，只看修改区、旧阻断和关联不变量；第二次复审仍出现新的架构问题时停止补丁循环，按未知事实返回有界 Spike、按已知事实重写 Plan，用户可观察行为变化时返回 `writing_spec`。

任何候选变化都形成新 `plan_ref`，重新 dry-run，再由同一 reviewer 复审。`Issues Found` 时保持本阶段。机械、风格或可选建议不得扩大语义阻断范围；reviewer 不可恢复时阻塞，不能静默换人或伪造 fresh review。

只有 dry-run `validated` 且 reviewer 精确返回 `Approved`，Worker 才写 `approved` handoff，`artifact_ref` 绑定 `plans/<change_id>.md@<完整 SHA>`。Plan 必须写明需求输入、完整 Spec 和全部 `impact_id`，不得用讨论稿补足。总控验证 handoff、候选引用、lint 和 reviewer 输入，读取候选一次审核，并向用户展示文件、Lean 标记、基线、任务摘要、全部阻塞与简短非阻塞建议。完整 review 只在异常或用户要求高审计时读取。

## 原子采用与收尾

`review_mode=manual` 时，用户确认必须绑定该精确候选。`review_mode=auto` 时，只有 dry-run `validated`、reviewer `Approved`、主 Agent 审核通过、候选未变化且 `blockers` 为空，才自动调用 `adopt-plan`；不得修改候选或绕过任一门禁。超过 3 个 Task 时，`auto` 仍必须停下取得用户例外确认。只有对应采用事实与 handoff 全部有效，才调用：

```text
adopt-plan <change_id> --workflow-id <workflow_id> --plan-ref <plan_ref>
```

普通候选执行 `adopt-plan <change_id> --workflow-id <workflow_id> --plan-ref <plan_ref>`；经用户确认的 4+ Task 例外另加 `--user-confirmed-task-count-exception`。成功后，`manual` 在此停止；`auto` 重新读取 `workflow-status` 并按新阶段精确路由继续，但不得预读或绕过实现门禁。

该机械命令解析 Spec impact、Plan 兼容性、覆盖、技术状态和真实 Task；成功时只写 `plan_ref` 并把阶段原子改为 `tdd_coding`，`change_ref` 保持登记版不变。失败时保留原引用和 `writing_plan`，不得拆成 `set-ref` 与 `workflow-set-stage`。

`manual` 采用成功后立即停止，不得在本轮读取执行合同、实例化 SDD offer、创建开发 worktree 或开始实现；下一轮由 `tdd_coding` 路由加载这些内容。`auto` 只通过重新路由进入实现规则。reviewer 回复不是第七类正式材料，Plan 批准和 Vault commit 不授予集成、远端或清理权限。

## 停止信号

- 稳定基线未展示并确认；
- 代码树、正式引用、AGENTS 或 handoff 输入不一致；
- dry-run 未通过却派 reviewer，或把 dry-run 当正式采用；
- reviewer、主 Agent 或当前模式的采用门禁缺失；4+ Task 缺逐项理由或用户例外确认；
- 正准备让主 Agent 代写 Plan、把 reviewer 写入 SQLite，或在阶段切换后读取实现规则。
