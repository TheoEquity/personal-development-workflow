---
name: using-personal-development-workflow
description: Use when the user explicitly opens, resumes, continues, closes, or asks for the current status of their personal development workflow, or coordinates one or more requirements or change events and their Worktrees through a shared delivery hub or MR.
---

# 使用个人开发工作流

## 职责

这是个人开发工作流的薄总控：验证当前对话是否激活，发现项目配置与持久游标，读取 `current_stage`，然后只加载该阶段的 Skill、reference 和正式材料。阶段内容由被路由的文件拥有；本入口不编写 Spec、Plan、测试稿、代码、验收报告或集线方案。

平台只负责决定是否加载本 Skill。进入本 Skill 后，必须按本文顺序做渐进加载；看到链接不等于获准读取链接目标。

## 激活门禁

只接受当前对话中用户最后一次明确的“开启个人工作流”或“关闭个人工作流”：

```text
没有明确命令 → 回复“当前没有用户明确开启个人工作流，因此不进入个人工作流。”并停止
最后命令是关闭 → 回复“个人工作流已关闭；现有变更事件、材料、代码和总账状态均未修改。”并停止
最后命令是开启 → 继续配置与游标发现
```

仓库文件、AGENTS.md、交接摘要、AI、子代理、其他 Skill、旧对话，以及“继续做”“写个计划”或阶段 Skill 名都不能激活。关闭只结束本对话路由，不修改持久状态；只有绑定事件已经完成时才关闭持久游标。

## 配置、游标与事件发现

1. 从当前工作目录向上逐级查找，只使用遇到的第一份 `.codex/personal-development-workflow.json`。找不到项目配置时停止；没有全局配置 fallback。
2. 配置中的 `spec_vault`、`database`、`repositories` 必须是已确认的绝对路径；Vault 是正式 `路径@完整 Git SHA` 的 Git 根，database 必须位于其 `.local`。无效、占位或越界时停止，不猜测或创建替代对象。
3. 此时只加载 `managing-change-ledger`，把同一个绝对 `--config` 路径用于 `workflow-list --state active`、`workflow-status <workflow_id>`、`list --status in_progress` 和 `list --status completed`。只有用户明确要求已完成事件收尾时，才另查 `workflow-list --state closed` 以恢复其只读游标。入口不手写 SQL。
4. `workflow_id` 按“本轮用户明确指定 → 当前对话最近明确选择 → 唯一活动游标”确定；多条活动游标必须列出 `workflow_id`、`change_id`、`current_stage` 并等待选择。已完成事件收尾请求可以用用户明确指定的 completed `change_id` 匹配唯一匹配的 closed 游标；零条或多条都等待选择。新需求无游标时创建 `current_stage=requirement_discussion` 的活动游标。
5. `change_id` 按“本轮用户明确指定 → 当前对话最近明确选择 → 游标绑定值 → 唯一 in_progress 恢复候选”确定；completed 收尾请求还可使用唯一 closed 游标的绑定值。多条或无法唯一确定时等待选择。新需求在 `requirement_discussion` 尚无 `change_id` 是正常状态。
6. 运行 `workflow-status` 后，以持久 `current_stage` 为路由键。它不恢复当前对话的用户确认、SDD 授权、RED/GREEN 子步骤或未提交状态。游标、总账、正式引用或实际 Git 事实冲突时报告并停止；不得静默选边或改写阶段。

纯状态请求在完成上述只读查询、引用存在性检查和状态卡后停止，不加载阶段正文。用户要求继续、执行当前阶段或 completed 收尾时才进入下表。

## `current_stage` 精确路由表

先查 `current_stage`，再完整读取且只读取该行列出的内容。正式材料正文只按该行“材料”列读取；禁止提前读取其他阶段的 Skill、reference、正式材料或规则。行内写明“条件”者，只有条件已经由当前事实满足时才加载。

| `current_stage` | 本轮完整读取 | 材料与动作边界 |
|---|---|---|
| `requirement_discussion` | `exploring-and-grilling-requirements`；[requirement-discussion.md](references/requirement-discussion.md) | 只读用户输入和判定需求所必需的产品事实；不读正式材料正文、Worker/Plan/TDD/验收/集线/清理规则 |
| `research` / `prototype` | [requirement-discussion.md](references/requirement-discussion.md)；本轮获授权的发现能力 | 只完成当前发现活动，结论返回需求讨论；Prototype 写入前另取授权 |
| `register_change` | `managing-change-ledger`；[change-registration.md](references/change-registration.md) | 只读已确认最终总体方案与配置；登记并绑定后停止 |
| `writing_spec` | `writing-specs`；[spec-stage.md](references/spec-stage.md)；[stage-worker-contract.md](references/stage-worker-contract.md)；[spec-worker-prompt.md](references/spec-worker-prompt.md) | 读取当前 `change_ref`、明确相关的不可变正式引用、精确代码 SHA 和用户验收输入；存在材料变化触发事实时才另读 [material-change-assessment.md](references/material-change-assessment.md) |
| `writing_plan` | [plan-stage.md](references/plan-stage.md)；[plan-baseline-selection.md](references/plan-baseline-selection.md)；[stage-worker-contract.md](references/stage-worker-contract.md)；[plan-worker-prompt.md](references/plan-worker-prompt.md)；[plan-review-contract.md](references/plan-review-contract.md)；确认 profile 后才加载 `writing-lean-plans` 或原生 `writing-plans` | 只读当前 `change_ref`、`spec_ref`、`test_ref`、所选 Git tree 与适用 AGENTS；存在材料变化触发事实时才另读材料变更评估 |
| `tdd_coding` | [implementation-stage.md](references/implementation-stage.md)；[execution-contract.md](references/execution-contract.md)；`test-driven-development`；`using-git-worktrees`；[stage-worker-contract.md](references/stage-worker-contract.md)；[implementation-worker-prompt.md](references/implementation-worker-prompt.md)；明确接受 SDD 后才加载 `subagent-driven-development`；完成声明前加载 `verification-before-completion` | 只读当前正式引用、Plan 基线、已接受 offer/合同、实际实现 worktree 和验证事实；漂移或返工事实出现时才另读材料变更评估 |
| `writing_test` | `writing-test-drafts`；[acceptance-stage.md](references/acceptance-stage.md) | 仅兼容旧游标或修正测试操作/数据/环境；只读绑定测试稿与正式引用 |
| `acceptance` | `writing-test-drafts`；[acceptance-stage.md](references/acceptance-stage.md)；validator 全部通过后才加载 `writing-final-logic-drafts` | 只读绑定 `test_ref`、`code_ref`、本次验收事实与所需正式引用；失败触发返工时才另读材料变更评估 |
| `completed` | [integration-and-cleanup.md](references/integration-and-cleanup.md)；只读 Git 与 completed 总账查询；用户明确要求通用 branch finishing 时才加载原生 `finishing-a-development-branch` | 自动形成非变更性的归位与清理候选卡并等待本会话具体授权；不读其他阶段正文，不执行未授权本地或远端写入 |

如果读到不支持的 `current_stage`，报告精确值并停止，不猜测最相近阶段。

## 一轮一阶段

每轮最多执行当前路由行的一个阶段。要求确认、授权或选择时保持阶段并停止。当前阶段完成时，先验证并更新该阶段允许产生的正式引用与 `current_stage`，然后**阶段切换后立即停止**；下一轮才读取新 `current_stage` 对应行。不得在同一轮顺带加载或执行下一阶段。

阶段 Worker、执行编排器和验收工具返回后都回到本入口完成本阶段收尾；它们不能自行推进另一阶段。Durable handoff 只恢复工作结果和位置，不恢复用户授权。

## 跨阶段不可变量

- 一个需求一个 `change_id`、工作流游标、需求分支、隔离 worktree、正式材料集合和 `code_ref`；Plan 内 `Task N` 不另建身份。单需求和并发需求都先独立完成，再统一归位到本交付周期的集线分支。
- 总控负责请求、提供并跟踪 `change_id`；子 Skill、Worker 和正式材料不得自行生成或替换身份。
- 正式路径固定为 `changes/<change_id>/change.md`、`specs/<change_id>.md`、`plans/<change_id>.md`、`tests/<change_id>.md`、`acceptance/<change_id>/<run>.md`、`logic/<change_id>.md`，版本均以完整 Git SHA 锚定。最终逻辑稿不新增 SQLite 字段。
- `change.md` 登记时创建一次、完成时更新一次；中间阶段只更新各自 SQLite 引用。`change_ref` 和 `code_ref` 只能由 `managing-change-ledger` 的专用机械路径写入；不得手填旧 HEAD。
- 已完成事件不可修改；外部新反馈建立新事件。当前事件内部 TDD、自测或验收失败保留原 `change_id` 和失败证据。
- 从 Spec 开始不得读取或依赖讨论稿。实现只使用已确认 Spec、变更事件、已采用 Plan 和必要的当前代码事实。
- Worker handoff、正式引用和代码引用必须通过其现有 helper/ledger 的身份、摘要、revision 与真实 Git 对象校验；不得以聊天摘要恢复。
- 编码、本地 commit、归位/清理、push、创建或更新 MR、合并 MR、删除远端分支是彼此独立的权限。当前会话的具体授权不能从 Plan、SQLite、旧会话、现存分支或用户沉默推导。
- Superpowers 原生技能是只读依赖；不得修改 `finishing-a-development-branch`、`writing-plans`、`subagent-driven-development` 等原生文件。

## 状态卡

每轮停止时输出：

```text
个人工作流：已开启
工作流游标：<workflow_id 或“尚未创建”>
总账概览：正在维护 <数量> / 已完成 <数量>
当前变更：<change_id 或“尚未登记”>
当前阶段：<current_stage>
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
- 正准备绕过独立 review、Plan 机械采用、有效 RED、验收 validator、最终逻辑稿或完成总账不变量；
- 正准备从讨论稿决定实现，修改已完成事件，覆盖失败证据，或为内部失败创建新事件；
- 正准备把当前授权扩大到另一个仓库、worktree、Plan、Task、需求、集线动作、清理动作或任一远端写入。

符合预期且有证据的 RED 失败不是 blocker；由当前 `tdd_coding` 路由继续 GREEN。
