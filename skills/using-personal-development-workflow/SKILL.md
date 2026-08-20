---
name: using-personal-development-workflow
description: Use when the user explicitly opens, resumes, continues, closes, or asks for the current status of their personal development workflow, or coordinates parallel Bug chats and Worktrees into one MR.
---

# 使用个人开发工作流

## 核心原则

作为个人工作流的入口、状态监督器和阶段路由器。只判断当前阶段、展示状态并调用对应阶段 Skill；不替代阶段 Skill 编写 Spec、Plan、测试稿、代码或验收报告。

总控负责请求、提供并跟踪 `change_id`：需求讨论确认后，它调用 `managing-change-ledger next-id` 取得唯一身份，并把同一值原样传给所有材料 Skill。正式项目 Markdown 固定使用 `changes/<change_id>/change.md`、`specs/<change_id>.md`、`plans/<change_id>.md`、`tests/<change_id>.md`、`acceptance/<change_id>/<run>.md` 和 `logic/<change_id>.md`；版本继续由 `路径@完整 Git SHA` 定位。最终逻辑稿不增加 SQLite 字段，它的 SHA 由最终 `change_ref` 的同一 Git commit 派生。`managing-change-ledger` 是机械分配与持久化引擎，但不得替总控改变材料身份。

一份正式 Plan 对应一个个人工作流任务，也就是一个工作流游标绑定的一个变更事件；同一事件当前只维护一个 `plan_ref` 和一条 canonical Plan 路径。Plan 内部可以拆分为多个实现 `Task N`，每个 Task 可以分别执行 TDD、验证和独立 review，但它们共享该事件的 Spec、Plan、代码快照和完成边界。实现 Task 不是新的工作流或总账身份，不得为单个实现 Task 新建 Plan、工作流游标或变更事件。当前事件需要重新规划时，仍更新 `plans/<change_id>.md`，重新评审、提交，并用新的完整 Git SHA 更新 `plan_ref`；历史版本继续由同一路径的不同 SHA 区分。

`change.md` 登记时创建一次、完成时更新一次。登记版固定记录背景、分类、影响范围、Spec 处理和确认结论；Spec、测试稿、Plan、代码与证据推进时，中间阶段只更新各自的 SQLite 引用，不修改 `change.md` 或 `change_ref`；完成版记录 `status: completed`、最终材料引用、`logic/<change_id>.md` 的 canonical 路径和最终结论。

当前对话是否允许路由，只由用户最后一次明确的“开启/关闭个人工作流”指令决定。跨对话可恢复的当前阶段来自 SQLite 的 `workflow_state`；正式材料和事件完成状态来自 `change_ledger`、Spec Vault Git 引用和代码 Git 引用。入口必须读取游标并用正式材料校验，不能只靠对话记忆，也不能只看六类引用猜测精确阶段。一个 `in_progress` 事件覆盖开发、内部验收、修正和重新验收的完整 Loop；只有新需求或外部 Bug 反馈开启新的变更事件。

所有 SQLite 读写都使用 `managing-change-ledger` 的脚本。入口不手写 SQL，不把 `workflow_state` 当第七类正式材料，也不创建状态转移矩阵。

Superpowers 原生技能是只读依赖；本工作流不得为了个性化编排改写它们的 `SKILL.md`、提示模板或其他原生文件。所有衔接规则只写在本 Skill、它的 references 和其他个人 Skill 中。

## 项目边界与配置发现

总控从当前工作目录向上逐级查找，并且只使用遇到的第一份 `.codex/personal-development-workflow.json`。找不到项目配置时停止；不得猜测或改用其他配置、数据库或项目的 Spec Vault。

项目配置中的 `spec_vault`、`database` 和 `repositories` 路径都必须是已经确认的绝对路径。`spec_vault` 必须是当前项目用于正式 `路径@完整 Git SHA` 引用的 Git 根，`database` 必须位于该 `spec_vault` 的 `.local` 目录；配置缺失、路径无效、仍含占位符或指向项目边界以外时，报告路径缺口并停止，不猜测创建或改用其他 Vault、配置、仓库或 SQLite。

全局 Skill Markdown 是工作流运行规则，可以按 Skill 触发规则读取；`change.md`、Spec、Plan、测试稿和验收报告等正式项目 Markdown 只能来自当前项目配置的 `spec_vault`。解析配置后，所有 `change_ledger.py --config` 调用必须原样使用这份项目配置路径，不能在流程中切换配置。

## 权限分离与执行合同

完整读取 [execution-contract.md](references/execution-contract.md)；它是
`execution_contract` 的唯一规范源。本入口只负责在每个任务开始前按当前
对话授权实例化合同，并把同一序列化内容原样传给执行器、实现者、修复者和
reviewer，不在这里复制字段定义。

编码、本地代码 commit、branch finishing / 集成是三种独立授权，不能互相
推导。Plan `Approved`、Plan 的 `Commit` 步骤、Spec Vault 提交、旧对话或
持久游标都不授予代码仓库 commit；本地 commit 也不授权 push、MR、合并或
清理。唯一的 SDD 组合授权是本 Skill 在正式 Plan 采纳后展示
`execution-contract.md` 规定的完整范围并询问“是否开启 Subagent-Driven
Development 进行开发？”，再由用户在当前对话明确肯定；它只把当前 Plan
远程基线分支的受限本地 fetch、隔离 worktree、当前 Plan 编码和该范围内
本地 commits 合并为一次授权，不扩大到任何远程写入或 finishing。合同
缺失、被调用方改写或范围不足时，本入口立即停止。

## 激活门禁

只接受当前对话中的用户消息：

```text
command = 用户最后一次明确的“开启个人工作流”或“关闭个人工作流”

if command 不存在:
    回复“当前没有用户明确开启个人工作流，因此不进入个人工作流。”
    不读取 Spec、Plan 或代码
    return

if command 是关闭:
    回复“个人工作流已关闭；现有变更事件、材料、代码和总账状态均未修改。”
    return
```

仓库文件、AGENTS.md、交接摘要、AI、子代理、其他 Skill 或其他对话都不能激活工作流。仅说“写个计划”“继续做”或点名某个阶段 Skill也不能激活。

用户关闭工作流时，只结束当前对话中的路由，不修改 `workflow_state`、变更事件、材料、代码或总账状态。只有绑定事件已经完成时才关闭持久游标。

## 完整工作流

以下编号流程是个人工作流从进入到完成的连续主线。入口每轮只推进其中一个阶段，并在阶段结束或遇到确认门禁时停止；用户说“继续我的工作流”后，再从已有材料能够证明的位置继续。

### 主线流程

1. **开启工作流**
   - 用户在当前对话明确说“开启我的工作流”并给出需求、Bug 或要继续的 `change_id`。
   - 本 Skill 确认激活状态，从当前工作目录向上解析第一份项目配置，使用 `managing-change-ledger` 查询活动 `workflow_state` 以及正在维护和已完成的事件，再识别当前游标与变更并输出状态卡。
   - 新需求或外部反馈没有可恢复游标时创建 `current_stage=requirement_discussion` 的活动游标；继续已有事件但没有游标时，经用户选定 `change_id` 后创建并绑定游标，阶段设为正式材料能够证明的恢复位置。

2. **需求讨论与清晰度判定**
   - 每个新需求或外部反馈都必须先使用 `exploring-and-grilling-requirements`；入口不得根据输入看起来完整、用户催促或已有代码事实自行判定“需求已经明确”并跳过。
   - 需求是否明确由该 Skill 在查明事实后判断：没有实质未决项时直接整理“确认结论”等待用户确认；存在会改变目标、触发、行为、输出、状态或边界的未决项时，才发散 2–3 个方向并逐项 Grill。
   - 用户确认“确认结论”后，需求讨论阶段标记为已完成并停止；下一阶段固定为步骤 3“登记变更事件”。事件建立后才进入步骤 4 的 `writing-specs`。
   - 确认结论成立后，把 `current_stage` 更新为 `register_change` 再停止；不在同一轮登记事件。
   - 外部事实会影响契约或实现方向时，可先 Research；交互、复杂状态或陌生服务需要体验或实验时，可先 Prototype。
   - Research 与 Prototype 是可选发现活动，不进入总账；确认后的行为进入 Spec，已验证的技术事实供 Spec 的“可能的影响范围”和后续 Plan 使用。
   - 进入可选发现活动时分别把阶段设为 `research` 或 `prototype`；结论返回需求讨论继续确认，需求结论已经完整确认时则进入 `register_change`。
   - 只有该 Skill 输出已由用户确认的“确认结论”，新需求或外部 Bug 反馈才进入步骤 3。当前事件内部 TDD、自测或验收失败不进入本需求讨论阶段，而是进入“开发与验收回环”。

3. **登记变更事件**
   - 只有新需求，或来自外部用户、客户、独立测试方、生产使用、已交付功能的 Bug 反馈，才使用 `managing-change-ledger` 生成并确认新事件。
   - 正式分类为新需求、实现 Bug、Spec 功能缺陷或关联新需求。外部反馈发生时即使另有事件正在开发，也单独登记；当前事件内部发现的问题不登记新事件。
   - 总控先调用 `managing-change-ledger next-id` 请求下一个 `change_id`，再把该 ID 提供给 `change.md` 及后续全部材料；子 Skill 不得自行生成文件身份。
   - 保存并提交登记版 `changes/<change_id>/change.md` 后创建总账行，取得登记版 `change_ref`，并持续跟踪同一 `change_id`。直到完成事件前不再修改该文件或引用。
   - 把当前游标一次性绑定到该 `change_id`。新事件登记并绑定后固定把阶段设为 `writing_spec`，由该阶段形成或核对同一 `change_id` 的 Spec、当前代码影响范围和测试稿；只有 `spec_ref` 与 `test_ref` 都有效后才能进入 Plan，然后停止。

4. **建立验收基准**
   - 新需求、Spec 功能缺陷或需要扩展行为契约时，使用 `writing-specs` 创建或修改 `specs/<change_id>.md`；完整展示并经用户确认后保存。
   - `writing_spec` 需要修改当前材料，或新事件与需求讨论已经明确关联的既有正式事件存在继承、保持或改变关系时，先完整执行 [material-change-assessment.md](references/material-change-assessment.md) 并等待用户确认；确认前不得调用写作 Skill 或保存候选稿。没有直接相关正式材料的新需求不制造空评估。
   - Spec 必须包含 `## 既有功能与流程影响`：用稳定 `impact_id` 记录直接相关的既有行为和保持、兼容扩展或明确改变结论；没有直接关联项时使用 `writing-specs` 定义的唯一无影响结论。行为影响不确定时保持 `writing_spec`，不得下放给 Plan。
   - Spec 形成有效 `spec_ref` 后，`writing-specs` 调用 `writing-test-drafts` 作为同一 `writing_spec` 阶段的子节点，生成 `tests/<change_id>.md`。用户提供的操作步骤、流程和预期结果优先；用户未提供时由测试稿 Skill 根据已确认 Spec 和可验证系统入口生成。
   - 测试稿不因影响表自动扩展回归项；本工作流不修改 `writing-test-drafts`，其测试项仍只由用户步骤和已确认的规范性行为驱动。
   - `writing-specs` 是“可能的影响范围”的唯一规范源；本入口只把该章节传给 Plan，不在这里重述或扩大其含义。
   - Spec 与测试稿分别提交后，使用 `managing-change-ledger` 只更新 `spec_ref` 和 `test_ref`；登记版 `change_ref` 保持不变。
   - Spec 与测试稿引用都更新成功后把阶段设为 `writing_plan`，然后停止。测试稿子节点属于本阶段收尾，不算串行推进另一个阶段。

5. **编写、评审并维护 Plan**
   - 每次创建或重写正式 Plan 前，必须完整读取并执行 [plan-baseline-selection.md](references/plan-baseline-selection.md)：先发现并展示本地候选与实际远程候选，等待用户选定来源和完整 SHA，再让代码调查、writer 与 reviewer 使用同一 Git tree。基线选择只对本次 Plan 有效；基线确定前不得调查代码、调用 `writing-plans` 或开始评审。
   - **REQUIRED SUB-SKILL:** 使用原生 `writing-plans`，输入已确认的完整 Spec 和全部 `impact_id`、变更事件和当前代码事实；Plan 固定保存为 Spec Vault `plans/<change_id>.md`，不得调用已废弃的两个个人实现/计划 Skill，也不得因任务小或用户催促省略 `plan_ref`。
   - 本阶段以整个工作流任务及其绑定的变更事件为 Plan 边界；多个实现 `Task N` 是同一 Plan 内的执行拆分，不各自取得 Plan、游标或事件身份。并行执行、分模块实现或逐 Task review 都不改变这一边界。
   - 候选 Plan 必须在具体 Task 前包含 `## 开发基线`，逐行记录 `base_source`、`base_locator` 和 `base_sha`；`base_sha` 必须是本次代码调查与计划评审实际使用的 40 位完整 Git commit SHA。远程来源另记 `base_remote` 与 `base_branch`；本地来源记录绝对 worktree、branch/detached、pushed 状态和未提交修改排除说明。不得用缩写 SHA 或工作区文件状态代替。Plan reviewer 必须同时收到这些字段、对应仓库绝对路径和相同代码基线；任一字段缺失、引用不存在或评审输入不一致时保持 `writing_plan`，总控不得调用 `adopt-plan`。
   - 在本次 `writing-plans` 调用要求中附加：候选 Plan 必须在具体 Task 前包含 `## 实现兼容性分析`，逐项记录 Spec `impact_id` 或 `implementation-only`、现有代码或方法、新方案交点、技术影响、处理方式和对应任务。`无影响` 必须给出代码证据并写 `无需任务`；`需要适配`、`需要迁移` 必须映射到编号规范且唯一的真实 `Task N`；Spec 标为 `明确改变` 的每个影响项至少要有一条适配或迁移任务，不能反写成全部无影响；`阻塞` 或待确认项不能采用。Spec 无直接关联项时仍要给出实现层交点结论，或用 ``- 无交点代码证据：<Spec 代码基线> | `<路径或符号>` | <具体理由>`` 记录唯一证据行。该要求只作为调用输入，不改写原生 skill。
   - 完整执行 `writing-plans` 的 `Execution Handoff` 所规定的 Plan 保存与评审合同，并按 `plan-document-reviewer-prompt.md` 传入它要求的全部绝对定位、不可变引用、代码基线、工作区差异和独立 AGENTS 发现信息。把完整影响表以及覆盖、Task 映射和阻塞状态规则作为本次调用的 requirements 输入；该模板仍是 reviewer 字段和判定协议的唯一规范源，本入口不修改模板，只核对结果是否完整一致。原生 Handoff 的通用执行方式二选一提示在个人工作流中由下面的 SDD 专用门禁替代，不提前选择执行器。
   - `Issues Found` 时保持 `writing_plan`；调查或 review 发现用户可观察行为会变化时返回 `writing_spec`，不得由 Plan 自行决定；纯代码、方法或 AGENTS 问题留在 `writing_plan` 重新规划。
   - 只有 reviewer 精确返回 `Approved` 且候选 Plan 已形成有效 `plan_ref` 后，调用 `managing-change-ledger` 的原子命令 `adopt-plan <change_id> --workflow-id <workflow_id> --plan-ref <plan_ref>`。该命令机械解析 Spec 影响项、Plan 兼容性表、覆盖关系、技术状态与真实 Task 引用，不把空洞的 reviewer `Approved` 当作内容校验；成功时只写入 `plan_ref` 并把阶段改为 `tdd_coding`，`change_ref` 保持登记版不变。失败时保留原引用与 `writing_plan`，不得拆成若干 `set-ref` / `workflow-set-stage` 写入。
   - 只有 `adopt-plan` 成功后，才显示当前 `plan_ref`、配置中的实现仓库绝对路径、Plan 的 `base_source`、`base_locator`、`base_sha`，以及所选来源对应的验证和隔离 worktree 说明；同时显示本地 commit 范围和不含远程写入/finishing 的边界，然后逐字询问：**“是否开启 Subagent-Driven Development 进行开发？”** 显示后停止，不得在同一轮 fetch、创建 worktree 或开始编码。
   - reviewer 回复不是第七类正式材料。Plan 批准和 Spec Vault 提交都不授予代码仓库 commit 或集成权限。

6. **正式 TDD 编码**
   - 上一步专用门禁尚未得到明确回答时保持 `current_stage=tdd_coding`。普通“开始开发”“开始实现”“开始编码”不等于选择 SDD，也不授权 commit；只接受对该门禁明确表达“开启 / 使用 SDD”的肯定答复，或明确的“不启动”答复。
   - 用户明确回复“不启动”时保持 `current_stage=tdd_coding`，不创建 worktree、不修改代码、不创建本地 commit，说明当前未启动 SDD 后停止。含糊答复只重新要求在“开启 / 不启动”中明确选择，也不产生任何执行副作用。
   - 用户之后另行明确选择非 SDD 执行方式时，才可使用带独立逐任务 reviewer 的 `executing-plans`，并按该次授权重新实例化执行合同；“不启动 SDD”本身不会自动降级到 `executing-plans`。

   #### 开发前远程基线门禁
   - 当 Plan 为 `base_source=remote` 且用户明确回复“开启”时，该回复按 [execution-contract.md](references/execution-contract.md) 授权当前显示 Plan 的受限本地 fetch、隔离 worktree、编码和范围内本地 commits。开发准备的第一项动作是在配置中的实现仓库核对 Plan 的 `base_remote` 与 `base_branch`；缺失、歧义、remote 不存在或分支不能定位时返回 `writing_plan`，不得猜测 remote 默认分支。
   - 核对成功后先运行 `git fetch --no-tags <base_remote> +refs/heads/<base_branch>:refs/remotes/<base_remote>/<base_branch>`，只强制更新该本地 remote-tracking ref；再用 `git rev-parse --verify <base_remote>/<base_branch>^{commit}` 解析最新完整 SHA。fetch、认证、网络、ref 更新或解析失败时保持 `tdd_coding` 并停止；不得创建或复用开发 worktree、不得写 RED、测试或生产代码、不得创建本地 commit。总控不对主 checkout 执行 `git pull`、merge 或 reset。
   - 把最新完整 SHA 与 Plan 的 `base_sha` 逐字比较：
     - 完全一致：才把该 SHA 作为强制 `start_point` 传给 `using-git-worktrees`。创建或确认隔离 worktree 后重新读取其完整 `HEAD`；只有 `HEAD` 等于该 SHA、工作区干净、仓库映射和 AGENTS 清单仍与 Plan 评审输入一致时，远程基线门禁才通过。
     - 不一致：代码门保持关闭，记录 `<base_sha>..<最新 SHA>`，只审查这段远程差异对当前 Spec、Plan 兼容性分析、Task 和 AGENTS 的影响，不默认重写整份材料。至少返回 `writing_plan` 更新 `base_sha`；若差异改变用户可观察行为则先返回 `writing_spec`。候选材料必须按既有最小修改规则重新确认，Plan 重新评审、提交并由 `adopt-plan` 采用后，才能再次展示 SDD 门禁。
   - `using-git-worktrees` 或平台原生 worktree 工具无法保证从强制 `start_point` 创建，或实际 worktree `HEAD`、干净状态、仓库/AGENTS 校验不一致时立即停止。不得退回本地主 checkout、旧 `HEAD`、`FETCH_HEAD` 猜测或“先开发后 rebase”。

   #### 开发前本地基线门禁
   - 当 Plan 为 `base_source=local` 且用户明确回复“开启”时，不执行远程 fetch 或远程相等性比较；先验证 `base_sha` commit 仍存在，并重新核对 Plan 的绝对 worktree 与 branch/detached 定位对象。定位对象已经移动或 commit 不存在时返回 `writing_plan`，重新执行 Plan 基线选择。
   - 只有现有隔离 worktree 的 `HEAD` 必须逐字等于 `base_sha`、工作区必须干净，且仓库映射和 AGENTS 清单仍与 Plan reviewer 输入一致时才可复用。否则把该 SHA 作为强制 `start_point` 交给 `using-git-worktrees` 创建新的隔离 worktree，再重复相同验证。
   - 选中 worktree 内不得带入选择时排除的 dirty 修改。任何校验失败都关闭代码门；不得退回远程 SHA、当前主 checkout 或其他本地 HEAD 猜测继续。

   #### SDD 执行
   - 代码实现开始前，总控必须按 `base_source` 完成上述远程或本地基线门禁；只有对应门禁通过后，才使用 `using-git-worktrees` 完成项目设置和干净基线测试。取得实际绝对 worktree 与 branch 后，把它们填入每个 Task 的同一授权合同，重新核对 `spec_ref`、`plan_ref`、`test_ref` 与实现基线，然后启动 `subagent-driven-development`。这之后不再追加一次 fetch、worktree、编码或本地 commit 确认；SDD 按其连续执行规则完成全部 Task 并返回本入口。
   - 进入每个任务前按 [execution-contract.md](references/execution-contract.md) 实例化合同并原样传给所有角色。SDD 门禁的肯定答复使当前 Plan 在实际 worktree 内取得范围准确的本地 commit 授权；其他执行方式只有编码授权时采用未提交路径。合同始终不允许任何 finishing 动作。
   - 使用 `test-driven-development`；该 Skill 是有效 RED 顺序、可复现实现前基线和结构化证据的唯一规范源。路由器只核验其证据并在缺失/无效时停止，不重新定义 RED。
   - `subagent-driven-development` 只能由上述专用门禁的肯定答复启动，并且启动时合同必须允许当前 Plan 在实际 worktree 内 commit。非 SDD 路径仍必须带独立逐任务 reviewer；个人工作流不提供绕过逐任务独立 reviewer 的直接执行路径。所有任务结束后都按合同返回本路由器并停止。
   - 使用 `verification-before-completion` 取得新鲜验证证据。更新 `code_ref` 前，本次变更相关测试和生产代码必须已经包含在一个获得明确授权的本地 Git commit 中；不得用仍指向旧内容的 `HEAD` 表示未提交修改。
   - 合同不授权本地 commit 时，允许保留本次 Plan 范围内的相关未提交测试和代码，保持 `current_stage=tdd_coding`、原 `code_ref` 和事件 `in_progress`，说明“编码已执行但等待本地 commit 授权”后停止；不得写入 `code_ref`，也不得把正确的未提交状态误报为 blocker。
   - 用户之后在当前对话明确授权本地 commit 时，先验证授权范围覆盖本次精确 Plan，再核对相关未提交 diff、运行新鲜验证、只提交范围内相关文件并取得 SHA；不能沿用此前模糊授权或跳过范围核对。
   - 代码提交形成后，通过只读检查确认本次变更相关文件没有遗漏在该 commit 之外，再从实际实现 Git worktree 调用 `managing-change-ledger set-code-ref <change_id> --worktree <absolute-worktree-root>`。总账脚本在同一命令中通过 Git common directory 反向匹配配置仓库、读取该 worktree 的完整 `HEAD`，并在 SQLite 事务内把派生的 `code_ref` 写入当前 `tdd_coding` 事件；提交事务前再次读取 `HEAD`，发生变化则回滚。通用 `set-ref` 不能写 `change_ref` 或 `code_ref`，总控也不得从主 checkout、旧 `HEAD` 或手填 SHA 拼接引用。
   - `set-code-ref` 返回的 worktree 路径、分支和 dirty 状态只用于核对，不写入正式 `code_ref`；无关的用户工作区改动保持不动。命令成功后登记版 `change_ref` 仍保持不变。
   - 引用更新成功且既有 `test_ref` 仍有效后，从 `tdd_coding` 直接进入 `acceptance`，然后停止。

7. **兼容旧游标与修正测试稿**
   - 新事件不在编码后首次编写测试稿；初始测试稿已经在步骤 4 由 `writing-specs` 的子节点形成。
   - `writing_test` 只保留给已有持久游标兼容，或验收失败后仅需修正操作、数据或环境的旧回环。进入时使用 `writing-test-drafts` 修改 `tests/<change_id>.md`，不得改变正确的 Spec 行为契约。
   - 更新并提交测试稿后使用 `managing-change-ledger` 只更新 `test_ref`，再进入 `acceptance`；登记版 `change_ref` 保持不变。新流程不得把 `writing_test` 当作 TDD 编码后的默认下一阶段。

8. **实际验收并生成报告**
   - 用户要求验收后，使用 `writing-test-drafts` 的执行模式，按指定版本测试稿实际操作。
   - 执行第一个测试项前，确认实际运行内容与总账 `code_ref` 指向同一 Git commit，并确认本次变更相关文件没有会改变受测行为的未提交改动。无法证明一致时不开始验收，倒回 `tdd_coding` 重新验证并形成代码快照。
   - 按 `writing-test-drafts` 的唯一报告合同生成新报告；本入口不复制字段、Markdown grammar、状态推导或失败回传格式。
   - 报告提交后，先调用 `writing-test-drafts` 的唯一 validator，并把当前事件、测试稿和代码引用作为期望绑定。validator 无效时停止；有效时只消费其规范化结果，再使用 `managing-change-ledger` 只更新 `evidence_ref`；登记版 `change_ref` 保持不变。

9. **处理验收结果**
    - validator 规范化结果为全部通过：先校验报告、测试稿、完整 Git SHA、六类引用和实际受测代码，然后进入步骤 10。
    - validator 规范化结果包含失败：原事件保持 `in_progress`，消费其已校验的失败回传，进入“开发与验收回环”。
    - validator 规范化结果没有失败但存在未执行：总体未完成；说明原因并停在步骤 8，不得进入步骤 10。

10. **形成并确认最终逻辑稿**
   - **REQUIRED SUB-SKILL:** 使用 `writing-final-logic-drafts`，原样传入同一 `change_id`、当前不可变 `spec_ref`、`plan_ref`、`test_ref`、`code_ref` 和已经由唯一 validator 判定全部通过的 `evidence_ref`。
   - 逻辑稿固定保存为 `logic/<change_id>.md`。候选稿和保存稿都使用精确 `# <change_id> 最终逻辑稿`、必填 `## 功能逻辑` 和可选 `## 注意事项`；内容按验收通过后的真实顺序讲清核心机制、触发、处理、结果及理解流程所需的层级、重复触发或清理行为，不写代码导读或测试证据，也不强制拆成多个固定栏目。
   - 先在对话中完整展示候选稿并停止。用户确认后才保存 canonical 文件；未确认、材料冲突或无法从实际代码与验收事实证明正文时保持 `current_stage=acceptance`，不修改 `change.md`、SQLite 或代码，不完成事件。
   - 保存后仍保持 `acceptance`，不增加 SQLite 阶段或 `logic_ref`。本步骤只把控制权交回总控；下一次继续时进入步骤 11。

11. **完成变更事件**
   - 按 `managing-change-ledger` 的唯一完成合同形成并提交最终 `change.md`：同一 `change_id`、`status: completed`，与总账逐字一致的 `spec_ref`、`plan_ref`、`test_ref`、`code_ref`、`evidence_ref`，正文中的 `## 最终逻辑稿` 及唯一 `- logic/<change_id>.md`，以及最终结论。
   - 最终 `change_ref` 指向的同一 Git commit tree 必须同时包含 canonical 最终逻辑稿；其派生版本是 `logic/<change_id>.md@<final-sha>`，但不写入 SQLite 新字段。
   - 取得最终提交 SHA 后调用 `complete <change_id> --change-ref changes/<change_id>/change.md@<final-sha>`。只有脚本的材料角色、报告绑定、阶段和 Git 对象检查全部通过，命令才在一个事务内原子更新最终 `change_ref` 和 `status=completed`。
   - 总账完成后关闭该事件绑定的工作流游标，使其成为 `current_stage=completed`、`state=closed`。
   - 完成事件不授予集成权限。只有用户在完成事件后另行明确要求并授权其具体范围时，才可调用 `finishing-a-development-branch`。
   - 已完成行不可修改，已完成事件允许幂等查询；完成后收到的外部 Bug 反馈或需求变化创建新的变更事件。

### 开发与验收回环

内部 TDD、自测或验收失败始终在当前 `in_progress` 事件内循环，不建立新的 Bug 事件：

```text
Spec 与测试稿 → Plan → TDD 编码 → 内部验收 → 独立验收报告
                                             ├─ 通过 → 对齐引用 → 最终逻辑稿 → 完成事件
                                             └─ 失败 → 失败回传 → 倒回对应阶段 → 再次验收
```

1. 保留并提交失败验收报告，让当前事件的 `evidence_ref` 指向该报告；不得覆盖、删除或把失败改写成通过。
2. 使用 `writing-test-drafts` 的唯一 validator 读取报告；只消费其规范化绑定、测试项和失败回传结果。报告只提供事实，不决定路由；本入口不重新解析或列举报告字段。

#### 统一材料变更评估（任何材料或阶段变化前）

内部失败、需求修正、后续追加、范围扩展、已完成事件之后的新变化，以及 reviewer、代码调查或基线漂移可能使正式材料失效时，**REQUIRED REFERENCE:** 完整读取 [material-change-assessment.md](references/material-change-assessment.md)。总控只使用当前事件或需求讨论已经明确关联事件的不可变正式引用，先形成 Spec 与 Plan 两份结论，完整展示并等待用户确认；确认前不修改材料、代码或游标。

3. 用户确认评估后，只倒回该 reference 判定的最早责任阶段。Spec 需要变化时先进入 `writing_spec`；只有 Plan 需要变化时进入 `writing_plan`；两份材料均无需修改且事实属于实现偏差时回到 `tdd_coding`。测试操作、数据或环境有误时按既有测试稿/验收路径处理。
4. 把已确认的位置、预计动作和明确保留项原样传给对应写作 Skill。材料需要变化时，先完成 Spec 确认与引用更新，再完成 Plan 独立 review、提交和 `adopt-plan`；代码门和旧执行授权保持关闭，直到新材料采用完成。
5. 内部失败继续使用原 `change_id`；新增行为、范围扩展、已完成事件之后的变化和当前开发/内部验收以外的外部 Bug 反馈必须建立新事件。旧事件及其正式引用保持不可变。
6. 重复本 Loop，直到最新报告全部通过、六类引用有效且报告 `code_ref` 与总账一致，再进入主线步骤 10；逻辑稿确认后才进入步骤 11。

### 跨 Bug 并行与持续 MR 集线

当用户要并行修复多个 Bug，或把后续 Bug 继续追加到同一个开放 MR 时，按以下拓扑协调；不把这条跨事件流程塞进任一单独 Bug 的 Plan。

#### Bug 会话与共同基线

1. 跨 Bug 并行使用不同的 Codex 顶层会话和不同的 Git Worktree。每个 Bug 独立开启或恢复个人工作流，并使用自己的 `change_id`、`workflow_id`、Spec、Plan、分支和 `code_ref`；一个 Bug 事件完成后仍保持不可变。
2. 一轮开始前只解析一次共同基线。第一轮使用目标远程分支最新的 40 位完整 SHA；已有开放 MR 时，使用该 MR 实际源分支头的 40 位完整 SHA。把它原样写入本轮每个 Bug Plan 的 `base_sha`，同一轮所有 Bug 的 `base_sha` 必须逐字相同。
3. 每个 Bug Worktree 都从该冻结 SHA 创建并验证。不得把另一个 Bug Worktree 的目录状态或可变 HEAD 作为基线，也不得因为先完成一个 Bug 就让同轮其他 Bug 改为链式基线。
4. 跨 Bug 并行不得由 `subagent-driven-development` 的 Subagent 代替；单个 Bug 会话仍逐字显示既有 SDD 门禁，SDD 授权只覆盖当前 Bug 的 Plan。
5. 每个 Bug 会话独立完成 TDD、验收和事件关闭，只向集线会话交付用户明确指定的 `change_id`、本地分支、完整 commit SHA、`code_ref` 和验证结论；Bug 会话不自行创建另一个最终 MR。

#### 集线会话与同一开放 MR

1. 一个开放 MR 只由一个长期集线会话独占其源分支和 Worktree。新集线会话接手前必须先交接或释放旧 Worktree；同一源分支不能同时签出在两个 Worktree。
2. 集线会话从实际 Git 和 MR 状态恢复源分支、目标分支和完整头 SHA，只接收用户明确指定且工作流已经完成的 Bug 分支。本轮开始后冻结集线分支，成员开发期间不得移动或 push；下一轮以更新后的源分支头建立新的冻结基线。
3. 合入前核对输入 commit 与事件 `code_ref`；默认使用 `git merge --no-ff` 保留提交身份。合入后机械验证每个 Bug `code_ref` 的 commit 都是集线头的祖先，再运行组合验证。
4. 干净合并且组合验证通过后才显示远程动作范围。用户明确授权更新后 push 同一源分支，让原开放 MR 更新，不得新建重复 MR。MR 已合并或关闭时，才从最新目标分支建立新的集线分支，并另行取得 push 与新建 MR 授权。
5. 机械冲突先展示精确冲突范围，取得授权后才能处理；冲突涉及行为、兼容性判断或组合验证失败时，基于当前集线状态登记新的修复事件，先改 Spec/Plan 再改代码，已完成事件不回写。
6. 集线状态由实际 Git 分支、完整 SHA、祖先关系和 MR 状态恢复，不新增 SQLite 表、字段、阶段或正式材料引用。Superpowers 原生 Skill 保持只读。

Bug 会话的本地编码/commit 授权、事件完成、旧会话授权、SQLite 状态、现存分支和开放 MR 都不授权集线 merge、push、创建/更新 MR、远端合并或清理；每个动作继续服从当前会话的执行合同与 finishing 门禁。

### 阶段与 Skill 对应

| 阶段 | 使用的 Skill | 阶段产物或结果 |
|---|---|---|
| 开启、状态查看、继续、关闭 | `using-personal-development-workflow` | 当前阶段、门禁和下一动作 |
| 需求讨论 | `exploring-and-grilling-requirements` | 已确认的需求结论和“下一阶段：建立变更事件” |
| Research / Prototype | 按用户授权选择对应能力 | 确认结论，随后进入 Spec；不进总账 |
| 变更事件、SQLite 查询、引用更新、完成 | `managing-change-ledger` | `change.md`、事件列表、总账引用和状态 |
| Spec 与测试稿 | `writing-specs` 调用 `writing-test-drafts` | 已确认行为契约、既有功能与流程影响、非确定性的可能影响范围和可执行测试稿 |
| Plan | `writing-plans` | 含实现兼容性分析、保存到 Spec Vault、经独立 reviewer `Approved` 并由 `plan_ref` 维护的正式 Plan |
| 正式编码 | `test-driven-development`；按执行合同选择编排器 | 逐任务结构化 RED、GREEN、REFACTOR 证据，以及已授权 commit 或相关未提交代码 |
| 完成声明前验证 | `verification-before-completion` | 当前代码版本的新鲜验证证据 |
| 实际验收 | `writing-test-drafts` | 按既有测试稿生成独立验收报告和真实证据 |
| 验收通过后的最终逻辑稿 | `writing-final-logic-drafts` | `logic/<change_id>.md` 的用户确认候选与 canonical 文件 |

## 识别当前游标与变更

先查询 `workflow-list --state active`：

1. 用户本轮明确指定 `workflow_id` 时使用该游标；
2. 否则使用当前对话中用户最近明确选择的 `workflow_id`；
3. 只有一条活动游标时把它作为恢复候选；
4. 多条活动游标时列出 `workflow_id`、绑定的 `change_id` 和 `current_stage`，请用户选择；
5. 没有活动游标且输入是新需求时创建游标；没有游标但用户要继续已有事件时，先按下面规则确定 `change_id`，再创建并绑定游标。

确定游标后运行 `workflow-status <workflow_id>`，一次取得 `workflow_state` 和已绑定的 `change_ledger` 行。不得在多条活动游标之间自行选择。

按以下顺序确定当前 `change_id`：

1. 使用用户本轮明确指定的 `change_id`；
2. 否则使用当前对话中用户最近明确选择的 `change_id`；
3. 游标已经绑定 `change_id` 时使用该值；
4. 用户要求继续已有事件但游标尚未绑定时，查询 `list --status in_progress`；只有一条时把它作为恢复候选，多条时列出候选并请用户选择；
5. 无法唯一确定时，说明缺少 ID，只问用户选择哪一个并停止。

不得在多个进行中事件之间自行选择。新需求或外部 Bug 反馈尚无事件时必须先保持 `requirement_discussion`，由 `exploring-and-grilling-requirements` 完成清晰度判定和确认结论；之后才使用 `managing-change-ledger` 登记事件。当前事件内部失败继续使用原 `change_id`。

## SQLite 监控

按照“项目边界与配置发现”从当前工作目录向上定位最近的 `.codex/personal-development-workflow.json`，并把该绝对配置路径传给以下每个命令。找不到项目配置时停止；没有全局配置 fallback，也不读取其他项目的正式 Markdown。

工作流已激活后，在开启、继续、查看状态以及正式材料引用更新后，使用 `managing-change-ledger` 查询游标与总账：

```powershell
python <managing-change-ledger>/scripts/change_ledger.py --config <config-path> workflow-list --state active
python <managing-change-ledger>/scripts/change_ledger.py --config <config-path> workflow-status <workflow_id>
python <managing-change-ledger>/scripts/change_ledger.py --config <config-path> list --status in_progress
python <managing-change-ledger>/scripts/change_ledger.py --config <config-path> list --status completed
```

监控读取 `workflow_state` 的四个字段和 `change_ledger` 的八个字段。简短状态显示 `workflow_id`、`current_stage`、游标 `state`、绑定的 `change_id`、事件 `status` 和总账计数；详细状态再显示六类引用的“已有/缺失”、代码版本、最新报告和一致性检查。

- `workflow_state.current_stage` 是跨对话恢复的流程游标，不代表当前对话已经激活，也不保存等待确认、RED/GREEN 子步骤或未提交文件状态。
- `change_ledger.status=in_progress` 表示事件正在维护；六类引用说明正式材料是否就绪，不替代阶段游标。
- `completed` 表示已完成且不可修改；外部反馈必须创建新事件。
- `evidence_ref` 存在只证明已有报告，不证明报告通过。进入完成判断前必须用 `writing-test-drafts` 的唯一 validator 核对并消费规范化结果。
- `current_stage` 与正式材料、失败报告或代码事实冲突时，报告冲突并停止；不得静默相信游标或静默重写它。用户确认正确阶段后再调用 `workflow-set-stage` 修正。

## 状态监督

以持久化游标确定当前阶段，再用已有引用和证据校验：

| 已知事实 | 当前阶段或动作 |
|---|---|
| `requirement_discussion` 且尚未绑定事件 | 继续需求讨论；结论确认后写为 `register_change` |
| `research` 或 `prototype` | 完成已授权的发现活动；结果返回需求讨论，结论已完整确认时进入事件登记 |
| `register_change` 且尚未绑定事件 | 登记事件；绑定后固定进入 `writing_spec`，由该阶段形成或核对当前事件的 `spec_ref` 与 `test_ref` |
| `writing_spec` | 已有或明确相关正式材料时先完成并确认材料变更评估；随后读取/编写 Spec，确认既有功能与流程影响，扫描非确定性的可能影响范围，并由测试稿子节点生成或修正测试稿；`spec_ref` 与 `test_ref` 都更新后进入 Plan |
| `writing_plan` | 把 Spec 影响项传给原生 `writing-plans`，形成实现兼容性分析并取得独立 reviewer 的 `Approved`；由 `managing-change-ledger` 原子 `adopt-plan` 成功后进入 TDD 编码 |
| `tdd_coding` | 正式 Plan 刚采纳时显示 SDD 专用门禁；明确“开启”后先 fetch Plan 指定的远程基线并核对最新完整 SHA，一致后才建立或确认隔离 worktree 并连续执行 SDD；漂移时回到材料、明确“不启动”或尚未选择时不产生执行副作用 |
| `writing_test` | 仅兼容已有游标或旧回环；修正测试稿后进入验收，不作为新流程默认阶段 |
| `acceptance` | 实际验收；失败时按失败回传改写为责任阶段，通过后先形成并确认最终逻辑稿，再完成事件；等待逻辑稿确认时仍保持本阶段 |
| 外部 Bug 反馈且尚无确认结论 | 先进入需求讨论；结论确认后再登记新的变更事件并分类 |
| `current_stage=completed` 且 `state=closed` | 已完成；绑定总账必须同时为 `completed`。保持停止，不自动 branch finishing；只有用户另行明确要求并授权才进入集成动作 |

这张表只是游标含义与校验规则，不是状态转移矩阵；内部失败可以直接回到拥有问题的阶段。当前对话中的细粒度门禁，例如“Plan 正在等待独立 reviewer”，只显示在状态卡中，不写入 SQLite；新对话恢复后重新满足对应阶段 Skill 的门禁。

## 阶段路由

每轮最多推进一个工作流阶段。调用阶段 Skill 后遵守其确认、写入、安全和停止门禁。阶段完成时先更新该阶段产生的正式引用和 `current_stage`，再停止；这属于当前阶段收尾，不算串行执行下一阶段。要求用户确认、等待授权或被阻塞时不移动游标并立即停止。

执行编排器完成全部 Plan 任务时也受“一轮一阶段”约束：它必须把控制权返回本入口并停止。入口根据 `local_commit_authorized` 决定是验证 SDD 已形成的范围内授权 commits，或在尚未提交时按授权创建范围准确的本地 commit，再从实际 worktree 解析并更新 `code_ref` 后进入 `acceptance`；没有授权时保留相关未提交代码并停在 `tdd_coding`。执行结束后的禁止集成与停止信号以 [execution-contract.md](references/execution-contract.md) 为唯一规范源。

### 需求讨论

新需求或外部反馈进入个人工作流时，**REQUIRED SUB-SKILL:** 无条件先使用 `exploring-and-grilling-requirements`，由它查明事实并判断需求是否明确。输入看起来完整、用户要求跳过、时间紧或已有现成实现都不能让入口替代该 Skill 作出清晰度判定。用户不需要再次指定讨论 Skill；个人工作流中不得改用普通 `brainstorming`，也不得在事件与 Spec 尚未完成前提前调用 `writing-plans`。

需求讨论 Skill 输出“阶段状态：已完成”后，先使用 `managing-change-ledger` 把当前游标写为 `register_change`，然后停止；这次游标更新属于阶段收尾，不得顺带登记事件。下一次继续个人工作流时建立变更事件；只有事件已经建立并取得 `change_id`、`change_ref` 后，才路由到 `writing-specs`。不要把“阶段结束”描述成重新开启或返回入口；个人工作流在同一对话中始终保持开启。

外部事实未知且会影响契约或可能影响范围时，建议 Research；交互、复杂状态或陌生服务必须通过体验或实验才能决定时，建议 Prototype。两者都不是总账正式材料，确认结论必须进入 Spec。Prototype 修改任何文件前必须取得用户授权，并与正式实现隔离。

### 正式材料

- 新需求或外部 Bug 反馈已经由需求讨论 Skill 形成并经用户确认“确认结论”：使用 `managing-change-ledger` 登记事件。
- 当前事件内部验收失败：使用已有失败报告和原 `change_id` 路由，不登记事件。
- 本次需要创建或修改行为契约：已有或明确相关正式材料时，先按 [material-change-assessment.md](references/material-change-assessment.md) 展示并确认修改范围与保留项；然后使用 `writing-specs`，并由其测试稿子节点形成或更新同一 `change_id` 的测试稿。
- Spec 已确认且需要形成或维护正式 Plan：先执行并确认 [plan-baseline-selection.md](references/plan-baseline-selection.md)，再使用原生 `writing-plans`。
- 用户要求实际验收：使用 `writing-test-drafts` 的执行模式读取步骤 4 已形成的测试稿；已有 `writing_test` 游标只按兼容路径处理。
- 验收报告全部通过之后、完成变更事件之前：使用 `writing-final-logic-drafts` 形成并确认 `logic/<change_id>.md`；这不增加 SQLite 阶段或字段。
- 最终逻辑稿已确认且引用满足完成条件：让最终 `change_ref` 的同一提交包含逻辑稿和完成版 `change.md`，再使用 `managing-change-ledger` 完成事件。

从进入 Spec 后的规划与实现阶段开始，讨论稿不得作为输入；规划与实现只读取已确认 Spec、变更事件、已评审 Plan 和必要的当前代码事实。

### 正式 Plan

进入 `writing_plan` 后执行主线步骤 5。每次创建或重写 Plan 都先完整执行 [plan-baseline-selection.md](references/plan-baseline-selection.md)，再遵守 `writing-plans` 的 Plan 保存/评审合同与 `plan-document-reviewer-prompt.md`。本入口把已确认 Spec 的影响项、实现兼容性要求和已确认的 `base_source`、`base_locator`、`base_sha` 附加到本次 writer/reviewer 输入；`writing-plans` 仍负责候选 Plan 与独立 reviewer 合同，`managing-change-ledger` 的原子 `adopt-plan` 是 Plan 内容校验、`plan_ref` 持久化和阶段推进的唯一合同。本入口不复制两者的字段或判定，也不修改任何 Superpowers 原生文件。采纳成功后的执行选择只使用本 Skill 的 SDD 专用门禁，不显示原生 Handoff 的通用二选一。

### 正式编码

进入 `tdd_coding` 后执行主线步骤 6。若 SDD 门禁尚未回答，先显示或恢复“是否开启 Subagent-Driven Development 进行开发？”并停止。明确开启后按 Plan 的 `base_source` 执行对应基线门禁：远程来源重新 fetch 并验证最新完整 SHA，本地来源验证精确 commit 和干净隔离 worktree；门禁通过后才按实际返回的 worktree 实例化合同并启动 SDD。明确不启动时保持停止。授权字段、作用域和执行后停止要求只由 [execution-contract.md](references/execution-contract.md) 定义；有效 RED、豁免和结构化证据只由 `test-driven-development` 定义；实现完成声明只由 `verification-before-completion` 的新鲜证据支持。

返回本入口后，严格按主线步骤 6 判断：未获得范围准确的本地 commit 授权就保留相关未提交代码并停在 `tdd_coding`；形成并核验授权 commit 后，从实际 worktree 解析并更新 `code_ref`、从 `tdd_coding` 直接进入 `acceptance` 并停止。

如果 Spec、Plan、代码事实或 Git 引用冲突，报告冲突并停止，不得通过代码自行补设计。实现调查发现新的用户可观察行为变化时返回 `writing_spec`；纯实现兼容问题或 Plan 需要变更时回到 `writing_plan`，重新评审、提交并更新 `plan_ref`。

### 验收失败

执行主线“开发与验收回环”。事件边界以 `managing-change-ledger` 为唯一合同，报告保留和失败回传以 `writing-test-drafts` 为唯一合同；本入口只根据已提交报告选择一个责任阶段并移动游标，不复制二者的判断或报告格式。

## 状态卡

每个阶段结束时输出简短状态卡：

```text
个人工作流：已开启
工作流游标：<workflow_id 或“尚未创建”>
总账概览：正在维护 <数量> / 已完成 <数量>
当前变更：<change_id 或“尚未登记”>
当前阶段：<阶段>
阶段状态：<已完成 / 等待确认 / 被阻塞 / 待执行>
下一步：<一个动作>
```

简短状态只显示总账计数和当前事件。只有用户要求“详细状态”时，才列出候选事件、六类材料的已有/缺失、代码基线、验收版本、阻塞原因和引用一致性检查，避免每轮加载完整材料正文。

当当前阶段为 `tdd_coding` 时，状态卡还必须显示按 [execution-contract.md](references/execution-contract.md) 实例化的原样合同，以及 `test-driven-development` 证据门禁状态。合同不允许 commit 且存在相关未提交实现时，阶段状态写“待授权提交”，不能宣称已有 `code_ref`。

正式 Plan 刚采纳且 SDD 门禁尚未回答时，状态卡还显示 Plan 的 `base_source`、`base_locator`、`base_sha`；远程来源同时显示 `base_remote`、`base_branch`。阶段状态写“等待 SDD 选择”，下一步逐字写“是否开启 Subagent-Driven Development 进行开发？”。用户明确不启动后写“SDD 未启动”，不得暗示已经 fetch、创建 worktree 或开始实现。

## 停止信号

出现以下任一情况时停止路由：

- 工作流未由当前对话中的用户激活；
- 当前变更无法唯一确定；
- 下一阶段需要用户确认、授权或选择；
- 必要材料缺失、引用无效、代码漂移或上游契约冲突；
- 正准备把旧 `HEAD` 当作未提交新代码的 `code_ref`，或在本次变更相关改动未纳入代码快照时进入验收；
- 正准备违反 [execution-contract.md](references/execution-contract.md) 的权限来源、范围、原样透传或执行后停止要求；
- 合同不允许 commit 时正准备采用 commit-based `subagent-driven-development` 或执行 Plan 的 Commit 步骤；
- 任务不满足 `test-driven-development` 的有效 RED / 证据定义，却正准备报告 `DONE`、进入 reviewer、标记完成或开始下一任务；
- 执行编排完成后正准备不返回本路由器，或自动调用 `finishing-a-development-branch`；
- 事件完成后没有用户另行明确授权，却正准备 push、创建/更新 MR、合并、清理分支或执行 branch finishing；
- 项目配置、活动游标、总账引用与实际材料之间存在无法安全自动修复的不一致；
- 正准备从讨论稿决定实现；
- 正准备在需求讨论结论确认后跳过变更事件直接调用 `writing-specs`；
- 正准备把已存在的 `exploring-and-grilling-requirements` 报告成“没有专用讨论 Skill”；
- 正准备因需求看起来明确、时间紧或用户要求跳过而绕过 `exploring-and-grilling-requirements`；
- 正准备因任务小、单会话、用户沉默或用户要求跳过而省略正式 Plan；
- 正准备调用 `writing-implementation-drafts` 或 `writing-personal-workflow-execution-plans`；
- 正准备在 Plan 尚未进入可复现的 Spec Vault Git commit、`plan_ref` 尚未更新时进入编码；
- 正准备在独立计划 reviewer 尚未返回 `Approved`，或 `managing-change-ledger adopt-plan` 尚未原子成功时，把 `writing_plan` 改为 `tdd_coding`；
- 正准备在 SDD 专用门禁得到明确肯定答复前创建 worktree、启动 `subagent-driven-development`、修改代码或创建本地 commit；
- 正准备在 Plan 缺少 `base_source`、`base_locator` 或 40 位完整 `base_sha` 时猜测基线并开始开发；
- 正准备在创建或重写 Plan 前省略本地/远程候选卡、默认使用尚未展示的远程候选，或把 dirty 修改算入某个 SHA；
- 正准备在 fetch 和最新完整 SHA 核对完成前创建或复用开发 worktree、写 RED/测试/生产代码，或创建本地 commit；
- 远程最新 SHA 与 Plan `base_sha` 不一致，却正准备沿用旧批准、先开发后 rebase，或不经材料更新、重新评审与 `adopt-plan` 就继续；
- 正准备把普通“开始开发”、沉默、含糊答复或“不启动 SDD”解释成 SDD/commit 授权，或自动降级到 `executing-plans`；
- 正准备从工作区 Plan、旧 Plan ref、聊天记录或阶段名恢复 Plan 采纳；
- 正准备用计划编写者的自检代替独立 reviewer，或把 reviewer 结果写入总账、六类正式材料或新的 SQLite 阶段；
- 正准备为当前事件的 TDD、自测或内部验收失败创建新的 Bug 事件；
- 正准备覆盖失败证据、跳过真实验收或完成不满足条件的事件。
- 验收已经全部通过，但正准备跳过 `writing-final-logic-drafts`、用户确认或 `logic/<change_id>.md` 的最终提交锚定而直接完成事件。

正确且符合预期的 RED 失败不属于停止信号或 blocker；它必须被记录后继续 GREEN。停止时只说明当前事实、阻塞原因和一个下一动作，不自行绕过。
