# 正式 TDD 编码阶段

只在 `current_stage=tdd_coding` 时完整读取。代码实现开始前，按 Plan 的 `base_source` 重新核对基线、正式引用和授权。授权对象和派生只由 [execution-contract.md](execution-contract.md) 定义；Worker 隔离与持久 handoff 只由 [stage-worker-contract.md](stage-worker-contract.md) 定义。

## SDD 专用门禁

Plan 刚采用或新对话恢复时，先从当前 `plan_ref`、配置仓库和 Plan 基线实例化并完整显示不可变 `authorization_offer`，然后逐字询问：**“是否开启 Subagent-Driven Development 进行开发？”** 阶段状态为“等待 SDD 选择”。offer 缺字段时不能提问。只回复“继续”不算明确开启 SDD。

只接受用户对该门禁明确表达“开启 / 使用 SDD”的肯定答复或明确“不启动”。“继续”“开始开发”、沉默、含糊回答、Plan 批准或旧对话都不是 SDD/commit 授权。展示 offer 后立即停止；同一轮不得 fetch、创建开发 worktree、修改代码或 commit。

用户明确回复“开启”后才进入 SDD 门禁并执行。用户明确回复“不启动”时，保持 `tdd_coding`，不创建 worktree、不修改代码、不创建本地 commit，并停止。用户之后另行明确选择非 SDD 执行方式时，才可使用带独立逐任务 reviewer 的 `executing-plans`；不启动本身不自动降级。

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

总控重新核对 `change_ref`、`spec_ref`、`plan_ref`、`test_ref` 和基线，初始化或验证 `implementation/implementation_coordinator` handoff。helper 将规范化 offer/contract 原样固化为当前 run 的 `authorization-offer.json`、`execution-contract.json` 和 SHA-256。使用 [implementation-worker-prompt.md](implementation-worker-prompt.md) 派发全新 Coordinator；它只读取 helper 文件，逐字节、摘要和逐字段验证后启动 `subagent-driven-development`。

Coordinator 是 SDD controller，不是 Task Implementer。它按正式 Plan 派发逐任务 Implementer、独立 Task Reviewer、必要 Fixer 和 Final Reviewer；Task 角色不得自行派发 reviewer 或辅助 Subagent。已接受 offer 与同一序列化内容原样传给所有角色，不能在 Task 间改写。全部任务结束后写完整报告，短返回有效 handoff 并返回本入口；不得调用 `finishing-a-development-branch` 或执行任何集成动作。

## TDD、验证与 code_ref

使用 `test-driven-development`；它是有效 RED 顺序、可复现实现前基线和结构化证据的唯一规范源。任务不满足有效 RED/豁免与证据定义时，不得进入 reviewer、报告 DONE 或开始下一 Task。

完成声明前加载 `verification-before-completion` 并取得当前代码版本的新鲜证据。更新 `code_ref` 前，本次相关测试和生产代码必须包含在一个获得明确授权的本地 commit 中；不得用仍指向旧内容的 `HEAD` 表示未提交修改。

合同不授权 commit 时，保留范围内未提交测试和代码，保持 `tdd_coding`、原 `code_ref` 和事件 `in_progress`，状态写“待授权提交”，不得误报 blocker。用户随后明确授权时，核对精确 Plan 和 diff，运行新鲜验证，只提交授权文件。

形成提交后，只读确认本次相关文件没有遗漏在 commit 之外，再从实际实现 worktree 调用：

```text
set-code-ref <change_id> --worktree <absolute-worktree-root>
```

`managing-change-ledger` 用 Git common directory 匹配配置仓库，从该 worktree 读取完整 `HEAD`，并在 SQLite 事务内原子写入 `code_ref`；提交事务前 HEAD 变化则回滚。通用 `set-ref` 不能写 `change_ref` 或 `code_ref`。返回的 worktree、branch、dirty 状态只供核对，不写进正式引用。

引用成功、`test_ref` 仍有效后，把阶段从 `tdd_coding` 直接进入 `acceptance` 并立即停止。不得在同一轮读取验收阶段或开始验收。

## 返工与停止信号

Spec、Plan、代码事实或 Git 引用冲突时停止，不通过代码补设计。新的用户可观察行为返回 `writing_spec`；纯实现兼容或 Plan 变化返回 `writing_plan`；出现这些事实时才加载材料变更评估。

- SDD offer 未被明确接受；
- 远程 fetch/解析失败、SHA 漂移、本地来源移动、worktree 不精确或 dirty；
- offer、最终合同或 handoff 被改写、扩大或摘要不匹配；
- 正准备跳过 Coordinator、独立 reviewer、TDD 或新鲜验证；
- 正准备把编码/commit 授权解释成 push、MR、合并、清理或 finishing；
- 阶段切换后正准备开始验收。
