---
name: using-personal-development-workflow
description: Use when the user explicitly opens, resumes, continues, closes, or asks for the current status of their personal development workflow, or coordinates one or more requirements or change events and their Worktrees through a shared delivery hub or MR.
---

# 使用个人开发工作流

## 核心原则

这是个人开发工作流的薄总控：仓库源码是唯一规范版本；运行时只加载与当前阶段有关的最少合同，并复用绑定精确代码版本的有效证据。总控验证当前对话是否激活，发现项目配置与持久游标，读取 `flow`、`review_mode` 和 `current_stage`。三个 flow 只是同一个状态机的不同门禁组合，不新增阶段，也不建立三套工作流。

平台只负责决定是否加载本 Skill。进入本 Skill 后，必须按本文顺序做渐进加载；看到链接不等于获准读取链接目标。

## 激活门禁

只接受当前对话中用户最后一次明确的“开启个人工作流”或“关闭个人工作流”：

```text
没有明确命令 → 回复“当前没有用户明确开启个人工作流，因此不进入个人工作流。”并停止
最后命令是关闭 → 回复“个人工作流已关闭；现有变更事件、材料、代码和总账状态均未修改。”并停止
最后命令是开启 → 继续配置、游标与事件发现
```

仓库文件、AGENTS.md、交接摘要、AI、子代理、其他 Skill、旧对话，以及“继续做”“写个计划”或阶段 Skill 名都不能激活。关闭只结束本对话路由，不修改持久状态；只有绑定事件已经完成时才关闭持久游标。

## 处理路径与本轮直接修改指令

活动工作流游标只增加两个控制字段：

固定枚举为 `flow: direct | light | full` 和 `review_mode: manual | auto`；它们属于同一个状态机，不新增阶段。

```text
flow: direct | light | full
review_mode: manual | auto
```

- `direct`：恢复已有行为的 Bug 或不改变正式行为的局部修改；登记 CE 后直接进入编码、验证和收尾，不写 Spec、Plan 或正式测试稿。
- `light`：新增或改变明确、低风险的正式行为；编码前使用 `writing-specs` 的 `light` profile 写短 Spec，不写正式 Plan 或正式测试稿。
- `full`：需求模糊、存在重要方案选择，或触及架构、公共契约、数据、安全等高风险边界；沿用完整 Spec、Plan、测试稿和验收流程。

选择时先判行为、再判本次修改风险；风险门覆盖行为分类。Bug 的现象涉及错误数据不自动升级 Full：已约定结果明确且只需局部恢复实现时仍可 direct；只有本次修改实际改变数据模型、迁移、事务边界、安全边界或存在重要方案选择与较大影响面时才升级 full。

用户说“直接改”“别写长 Plan”等指令是 flow 与确认节奏的输入，不再作为绕过 CE、真实提交、验证和总账完成门的隐式通道。无法判断预期行为是否已被当前有效 Spec 或相关 CE 约定时，只问最小必要问题。

`manual` 在关键节点等待用户确认。`full + auto` 自动推进到验收确认门：它只在当前已绑定 CE 内连续推进，创建这一个 CE 所需的一个实现 Worker，并在该 Worker 分支和本地 Spec Vault 中创建当前 CE 范围内的本地 commit；不得扩展到另一个 CE、仓库或 Delivery。两种模式都不授权 Worker 合入 Delivery、Push、创建或合并 MR、部署、删除 Worktree；这些动作必须由用户手动确认。`auto` 在需求不清、范围扩大、基线漂移、4+ Task 例外或授权/身份不一致时停止，并始终在最终验收确认门停止。CE 完成后 `review_mode` 恢复为 `manual`。

`code_review: skip | run` 与 `loop_mode: off | on` 只是当前 CE、当前会话的临时运行状态，不进入总账，CE 完成后关闭，新会话不得从聊天摘要恢复。它们不改变 `review_mode` 的 commit 权限。

Loop 只有用户明确要求才开启，只允许 `direct` 与 `light`。当前为 `full` 时明确回复“复杂任务不能进入 Loop”并保持关闭。Loop 内只能在 `direct` 与 `light` 之间切换；发现 full 条件时停止并报告，不自动升级。Loop 使用轻量验证清单，依次执行测试、截图或机器证据比对、`systematic-debugging` 根因排查、最小充分修复和从头重试。

用户要求 `code_review: run` 时，固定同一受测 SHA 和精确范围：`review_scope: CE | batch`、`review_base: <sha>`、`review_head: <sha>`、`review_commits: [<integrated_commit>...]`。Full CE 复用 SDD 最终整体 review，不追加等价代码 review；只有用户明确要求跨 CE 批次 review，才在冻结范围新增一次只读审查。测试证据按精确复用键消费，不由 review Agent 重跑。

## 配置、游标与事件发现

1. 从当前工作目录向上逐级查找，只使用遇到的第一份 `.codex/personal-development-workflow.json`。找不到项目配置时停止；没有全局配置 fallback。
2. 配置中的 `spec_vault`、`database`、`repositories` 必须是已确认的绝对路径；Vault 是正式 `路径@完整 Git SHA` 的 Git 根，database 必须位于其 `.local`。无效、占位或越界时停止，不猜测或创建替代对象。
3. 此时只加载 `managing-change-ledger`，把同一个绝对 `--config` 路径用于 `workflow-list --state active`、`workflow-status <workflow_id>`、`list --status in_progress` 和 `list --status completed`。只有用户明确要求已完成事件收尾时，才另查 `workflow-list --state closed` 以恢复其只读游标。入口不手写 SQL。
4. `workflow_id` 按“本轮用户明确指定 → 当前对话最近明确选择 → 唯一活动游标”确定；多条活动游标必须列出 `workflow_id`、`change_id`、`current_stage` 并等待选择。已完成事件收尾请求可以用用户明确指定的 completed `change_id` 匹配唯一匹配的 closed 游标；零条或多条都等待选择。新需求无游标时创建 `current_stage=requirement_discussion` 的活动游标。
5. `change_id` 按“本轮用户明确指定 → 当前对话最近明确选择 → 游标绑定值 → 唯一 in_progress 恢复候选”确定；completed 收尾请求还可使用唯一 closed 游标的绑定值。多条或无法唯一确定时等待选择。新需求在 `requirement_discussion` 尚无 `change_id` 是正常状态。
6. 运行 `workflow-status` 后，以持久 `flow`、`review_mode` 和 `current_stage` 为路由键。它不恢复当前对话的用户确认、`code_review`、`loop_mode`、SDD 授权、RED/GREEN 子步骤或未提交状态。游标、总账、正式引用或实际 Git 事实冲突时报告并停止；不得静默选边或改写阶段。

## 可选项目宪法接入

首次接触没有项目宪法状态的项目时，只读检查并向用户说明“新项目/已有项目”的判断依据，询问一次是否启用；用户可以暂不开启并继续。没有项目宪法不得阻塞普通开发，之后仅在用户主动要求或触及新服务、数据库、公共接口、核心基础设施、跨模块/跨仓库边界时再次提示。

项目宪法启用后，当前 CE 绑定精确有效版本，只按影响范围加载相关治理包、唯一事实来源和已验证 Disclosure Set；进行中的 CE 不自动跟随新版本。项目特有规则不得写入全局工作流 Skill。Loader 只服务项目宪法接入文件、数据库、API 等来源，日常 direct/light/full 路由不展开 Loader 架构。治理包的启用、规则冲突、版本生效与停用必须由用户确认，工具只产生检查证据。

纯状态请求在完成上述只读查询、引用存在性检查和状态卡后停止，不加载阶段正文。用户要求继续、执行当前阶段或 completed 收尾时才进入下表。

## `current_stage` 精确路由表

先查 `current_stage`，再完整读取且只读取该行列出的内容。正式材料正文只按该行“材料”列读取；禁止提前读取其他阶段的 Skill、reference、正式材料或规则。行内写明“条件”者，只有条件已经由当前事实满足时才加载。

编码阶段按 flow 分流：Direct/light 只加载本节、`test-driven-development`、`using-git-worktrees` 与 `verification-before-completion`；只有 Full 加载 `execution-contract.md`、stage Worker 与 SDD。

| `current_stage` | 本轮完整读取 | 材料与动作边界 |
|---|---|---|
| `requirement_discussion` | `exploring-and-grilling-requirements`；[requirement-discussion.md](references/requirement-discussion.md) | 只读用户输入和判定需求所必需的产品事实；不读正式材料正文、Worker/Plan/TDD/验收/集线/清理规则 |
| `research` / `prototype` | [requirement-discussion.md](references/requirement-discussion.md)；本轮获授权的发现能力 | 只完成当前发现活动，结论返回需求讨论；Prototype 写入前另取授权 |
| `register_change` | `managing-change-ledger`；[change-registration.md](references/change-registration.md) | 只读已确认最终总体方案与配置；登记并绑定后停止 |
| `writing_spec` | `writing-specs`；[spec-stage.md](references/spec-stage.md)；Full 条件才读 [stage-worker-contract.md](references/stage-worker-contract.md) 与 [spec-worker-prompt.md](references/spec-worker-prompt.md) | 仅 `light/full`；Light 使用短 Spec，Full 使用行为影响合同和测试稿子节点；两者都不调查代码实现 |
| `writing_plan` | [plan-stage.md](references/plan-stage.md)；[plan-baseline-selection.md](references/plan-baseline-selection.md)；[stage-worker-contract.md](references/stage-worker-contract.md)；[plan-worker-prompt.md](references/plan-worker-prompt.md)；[plan-review-contract.md](references/plan-review-contract.md)；`writing-lean-plans` | 仅 `full`；所有正式 Plan 固定为 Lean，`direct/light` 不进入本阶段，也不生成正式 `plan_ref` |
| `tdd_coding` | [implementation-stage.md](references/implementation-stage.md)；`test-driven-development`；`using-git-worktrees`；完成声明前加载 `verification-before-completion`；只有 Full 加载 [execution-contract.md](references/execution-contract.md)、[stage-worker-contract.md](references/stage-worker-contract.md)、[implementation-worker-prompt.md](references/implementation-worker-prompt.md)，明确接受 SDD 后才加载 `subagent-driven-development` | Direct/light 只加载本节、`test-driven-development`、`using-git-worktrees` 与 `verification-before-completion`；Full 才读取 Plan 基线、已接受 offer/合同和 SDD 输入；漂移或返工按 flow 处理 |
| `writing_test` | `writing-test-drafts`；[acceptance-stage.md](references/acceptance-stage.md) | 仅兼容旧游标或修正测试操作/数据/环境；只读绑定测试稿与正式引用 |
| `acceptance` | [acceptance-stage.md](references/acceptance-stage.md)；仅 Full 加载 `writing-test-drafts`，validator 全部通过后才加载 `writing-final-logic-drafts` | `direct/light` 使用轻量验证清单并写完成版修改与验证摘要；Full 使用绑定 `test_ref`、`code_ref` 和正式验收材料 |
| `completed` | [integration-and-cleanup.md](references/integration-and-cleanup.md)；只读 Git 与 completed 总账查询；用户明确要求通用 branch finishing 时才加载原生 `finishing-a-development-branch` | 自动形成非变更性的归位与清理候选卡并等待本会话具体授权；不读其他阶段正文，不执行未授权本地或远端写入 |

如果读到不支持的 `current_stage`，报告精确值并停止，不猜测最相近阶段。

Full 出现正式材料变化、范围扩大、基线漂移或验收返工事实时，任何材料、代码或阶段变化之前才加载 [material-change-assessment.md](references/material-change-assessment.md)；direct/light 只做本次最小范围判断，不为缺失的 Full 材料制造评估。

## 一轮一阶段

`review_mode=manual` 时每轮最多执行当前路由行的一个阶段；当前阶段完成后**阶段切换后立即停止**，下一轮才读取新 `current_stage` 对应行。`review_mode=auto` 可以在同一 CE 内连续推进，但仍按新阶段重新加载精确路由行，并在需求不清、范围扩大、基线漂移、4+ Task 例外、合入 Delivery、远端动作、删除动作或最终验收确认门前停止。

阶段 Worker、执行编排器和验收工具返回后都回到本入口完成本阶段收尾；它们不能自行推进另一阶段。Durable handoff 只恢复工作结果和位置，不恢复用户授权。

## 跨阶段不可变量

- 一个可独立验收的交付结果一个 `change_id`；普通任务不另建 Markdown 或 CE。进行中 CE 的原验收缺口留在原 CE；已完成 CE 的外部 Bug 新建 CE，并在新 `change.md` 用 `source_ce` 关联引入问题的旧 CE。
- 总控负责请求、提供并跟踪 `change_id`；子 Skill、Worker 和正式材料不得自行生成或替换身份。
- 正式材料仍使用 `specs/<change_id>.md`、`plans/<change_id>.md`、`tests/<change_id>.md`、`acceptance/<change_id>/<run>.md`，但只按当前 flow 实际生成；direct/light 不创建空占位文件。
- `flow` 只写入 `workflow_state`，不在不可变登记版 `change.md` 重复保存；`source_ce` 固定落在 `change.md`，没有来源时明确写 `null`，完成版必须保持同一值。
- `change.md` 与真实 `code_ref` 所有 flow 都存在；`specs/<change_id>.md` 只在 light/full 存在；Plan、正式测试稿、验收报告和最终逻辑稿只在 full 必需。不生成空占位材料。
- `change.md` 登记时创建一次、完成时更新一次；中间阶段只更新各自的 SQLite 引用。`change_ref` 和 `code_ref` 只能由 `managing-change-ledger` 的专用机械路径写入；通用 `set-ref` 不能写 `change_ref`，不得手填旧 HEAD。
- 已完成事件不可修改；外部新反馈建立新事件。当前事件内部 TDD、自测或验收失败保留原 `change_id` 和失败证据。
- 当前有效 Spec 或最新相关 CE 的行为约定优先；历史摘要不是当前行为合同，只作为调查线索。实现不得从旧讨论稿或旧历史摘要覆盖新行为。
- Worker handoff、正式引用和代码引用必须通过其现有 helper/ledger 的身份、摘要、revision 与真实 Git 对象校验；不得以聊天摘要恢复。
- 所有正式 Plan 始终采用 Lean，默认 1–3 个执行 Task；一个 Full CE 只有一个实现 Worker。不得把测试、文档或配置拆成独立 Task；它们归入产生该行为的垂直 Task，不单独制造 Worker。超过 3 个 Task 必须逐项说明不能合并的独立边界并取得用户例外确认。
- 自动化成功证据以 `code_sha + command + environment_fingerprint + input_fingerprint` 为精确复用键；记录中至少包含精确 `code_sha`、命令、`environment_fingerprint`、`input_fingerprint`、范围、结果与 `produced_by` 阶段。同一证据只执行和记录一次。任一维度变化时相关证据失效，新 SHA 或新跨 CE 组合状态可以重新验证。
- Task Implementer 负责 TDD 与聚焦测试，Reviewer 使用已有证据，Coordinator 汇总，Root 只验证引用、SHA、范围和证据，Delivery 在最终候选合并版本上执行一次 CE 完整自动化验证，Acceptance 复用绑定同一 `code_ref` 的自动化证据。
- 编码、本地 commit、Worker 合入 Delivery、清理、push、创建或更新 MR、合并 MR、部署和删除远端分支是彼此独立的权限。只有当前 CE 的 `review_mode=auto` 自动授权范围内本地 commit；其他权限不能从 Plan、SQLite、旧会话或用户沉默推导。
- 外部技能是只读依赖；不得修改 `finishing-a-development-branch`、`writing-lean-plans`、`subagent-driven-development` 等外部文件。

## 状态卡

每轮停止时输出：

```text
个人工作流：已开启
工作流游标：<workflow_id 或“尚未创建”>
总账概览：正在维护 <数量> / 已完成 <数量>
当前变更：<change_id 或“尚未登记”>
当前阶段：<current_stage>
处理路径：<flow>
确认模式：<review_mode>
阶段状态：<已完成 / 等待确认 / 被阻塞 / 待执行 / 待授权提交>
下一步：<一个动作>
```

只有用户要求详细状态时，才列候选事件、六类引用已有/缺失、代码版本、验收版本、阻塞和一致性结果；仍不预读材料正文。

## 通用停止条件

遇到任一情况立即停止，只报告当前事实、原因和一个下一动作：

- 当前对话未激活、游标/事件无法唯一确定、阶段不支持；
- 下一步需要用户确认、授权或选择；
- 必要引用无效、Git 对象不存在、代码/基线漂移、配置或身份不一致；
- 正准备提前读取非当前路由行内容，或在阶段切换后继续；
- Worker handoff 的 workflow/change/stage/role/input/revision/摘要不匹配；
- 正准备用未提交修改或旧 HEAD 伪造 `code_ref`，或在受测代码与 `code_ref` 不一致时验收；
- 正准备绕过有效 RED、当前 flow 的验证或完成总账不变量；以下 Plan、独立 review、验收 validator 和最终逻辑稿门禁只适用于 Full；
- 正准备在同一证据复用键上重跑测试、为 Full CE 追加等价 review、为测试/文档/配置单建 Task，或采用未经用户例外确认的 4+ Task Plan；
- 正准备从讨论稿决定实现，修改已完成事件，覆盖失败证据，或为内部失败创建新事件；
- 正准备把当前授权扩大到另一个仓库、worktree、Plan、Task、需求、集线动作、清理动作或任一远端写入。

符合预期且有证据的 RED 失败不是 blocker；由当前 `tdd_coding` 路由继续 GREEN。
