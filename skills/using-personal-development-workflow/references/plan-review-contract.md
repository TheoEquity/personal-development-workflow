# Plan 机械校验与语义评审合同

本文件是个人开发工作流 `writing_plan` 阶段的 Lean Plan 审查合同。writer 固定使用 `writing-lean-plans`，reviewer 固定使用 `lean-plan-document-reviewer-prompt.md`，并遵守本文件规定的机械门禁、语义范围、复审收敛和时间预算。

## 固定顺序

```text
不可变候选 plan_ref
  → adopt-plan --dry-run 机械校验
  → 一名语义 reviewer
  → Plan Worker approved handoff
  → 主 Agent 审核
  → manual 用户确认 / auto 总控采用精确候选
  → adopt-plan 正式采用
```

任何候选内容变化都必须形成新的不可变 `plan_ref`，从机械校验重新开始。旧 lint 结果、旧 reviewer 结论和旧用户确认不得沿用。

## 确定性 plan-lint

Plan Worker 在派发 reviewer 前运行：

```powershell
python <managing-change-ledger>/scripts/change_ledger.py --config <config-path> `
  adopt-plan <change_id> `
  --workflow-id <workflow_id> `
  --plan-ref <candidate-plan-ref> `
  --dry-run
```

`--config` 必须是当前项目向上发现的第一份配置。dry-run 绑定该配置中的 Spec Vault、SQLite、实现仓库，以及当前 `change_id`、`workflow_id`、`spec_ref`、候选 `plan_ref`、代码基线和适用 AGENTS；不得省略、替换或跨项目复用。

dry-run 使用正式 `adopt-plan` 的同一验证路径，至少机械检查：

- Lean profile 标记、Plan 标题、头字段、章节顺序与 `Task N` grammar；
- 每个 Task 的精确 Outcome、Files、`Consumes`、`Produces`、Implementation notes、Test goal 和 checkbox Step；
- 禁止占位符和空洞字段；
- Spec impact 表、Plan 实现兼容性表、覆盖关系、技术状态和真实 Task 映射；
- canonical 引用角色、Plan 自有的代码仓库与完整 Git 基线、Plan 目标路径与适用 AGENTS；
- 当前项目配置、活动游标、事件身份和 `writing_plan` 阶段。
- 默认 1–3 个垂直 Task；4+ Task 候选的逐项独立交付、依赖或风险理由。
- 每个 Task 至少包含一个非测试、文档或配置的生产代码 Create/Modify 目标；支持性工作必须归入产生对应行为的垂直 Task。

只有标准输出返回 `status=validated` 才能派发语义 reviewer。dry-run 不修改 SQLite、`plan_ref`、`change_ref` 或 `current_stage`；失败时 Plan Worker 修正候选、形成新 `plan_ref` 并重新运行，不能让 reviewer 代替机械校验。

## 一名语义 reviewer

每个候选审查循环只派发一名独立 reviewer。首次派发使用 `fork_turns=none` 并继承当前有效配置；Plan Worker 在 `report.md` 记录 reviewer 的稳定任务身份，修正后的复审必须核对并继续使用该 reviewer，不为每轮修正另派 reviewer。reviewer 收到精确候选、lint 成功结果、正式 Spec 与测试稿、选定代码树、基线字段、影响要求、适用 AGENTS、工作区差异，以及 Lean reviewer 模板。

语义 reviewer 只检查以下阻断项：

1. **错误方案**：架构、所有权、数据或控制流、状态和失败策略与 Spec 或精确代码事实冲突。
2. **缺失行为**：已确认的用户可观察行为、边界、失败行为或关联不变量没有被 Plan 覆盖。
3. **不可实现接口**：Plan 依赖的接口、签名、数据形状、调用顺序或依赖关系在选定代码树中不存在、互相矛盾或无法按 Plan 建立。

“错误方案”同时包括不真实的 Task 边界：把可共同交付的工作拆成多个微 Task、把测试/文档/配置单独包装成 Task，或 4+ Task 的理由与实际交付、依赖、风险边界不相符。reviewer 必须核对 Task 粒度与例外理由，不能因 lint 已通过而跳过这项语义判断。

标题、checkbox、占位符、impact 表字段、引用、SHA、`--config` 等机械问题不再交给 reviewer；措辞、风格、展开密度和可选改进也不进入语义结论。reviewer 不能用建议逐步扩大阻断范围。

语义结论只允许 `Approved` 或 `Issues Found`。每个 issue 必须归入上述三类之一并指向具体 Plan 位置；确实影响整份 Plan 时使用 `[Plan-wide]`。不输出措辞、风格、展开密度或可选优化建议，`Recommendations` 固定为空或“无”。

## 时间预算与复审收敛

- **首次评审：15 分钟。** 检查完整候选及关联不变量，在这一轮内穷尽当时能够发现的全部语义阻断项。不能完成全量检查时不得返回 `Approved`，reviewer 返回 `Issues Found`，Plan Worker 将本轮标为流程阻断 `semantic-review-incomplete`；它不是第四类 Plan 语义问题。
- **第一次复审：10 分钟。** 只检查修改区、此前阻断项和修改所关联的不变量或接口。未经 Spec、范围、基线、架构或适用 AGENTS 变化，不重新全量审查。
- 第一次复审发现新的架构问题时，可以修正一次并进入第二次复审；第二次复审仍使用同一 reviewer，预算仍为 10 分钟，检查范围与第一次复审相同。若修正会改变整份 Plan 的架构，不把它包装成局部补丁，而是结束当前循环并重新编写 Plan。
- **第二次复审仍出现此前未报告的新架构问题时停止补丁循环。** 当前候选不得批准。关键技术事实未知时返回有界 Spike；事实已知但方案需要重构时返回 `writing_plan` 重新编写 Plan。若问题会改变用户可观察行为，按既有材料变更评估返回 `writing_spec`。

时间预算从 reviewer 派发到返回最终结论按墙钟计算，是每一轮的上限。总控能够计时时，超时即停止该轮并记录 `semantic-review-incomplete`；该轮的迟到结果无效。运行环境不能可靠计时时，不得声称满足预算，按同一流程阻断处理。恢复时必须重新完成一次 15 分钟全量首审；精确候选、项目配置和全部输入未变化时可沿用原 lint，否则先重新 dry-run。

已报告但尚未修复的阻断项不属于“新的架构问题”，必须继续保持 `Issues Found`。第二次复审只有在旧阻断全部解决、修改区及关联不变量没有新的语义阻断时才能返回 `Approved`。

reviewer 不可恢复时，本次审查循环不能伪造 `Approved` 或静默更换 reviewer；Plan Worker 返回阻塞状态。需要换 reviewer 时，由总控重新启动一次完整的首次评审循环。

“返回有界 Spike”不新增 SQLite 工作流阶段：Plan Worker 返回 `spike_required` 阻断及明确待验证事实、范围和退出条件，由总控完成 Spike 后开启新的 Plan 候选循环。若同一问题会改变用户可观察行为，`writing_spec` 与材料变更评估优先于 Spike。
