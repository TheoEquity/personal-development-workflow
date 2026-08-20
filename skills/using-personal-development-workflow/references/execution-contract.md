# Execution Contract

This file is the canonical definition of `execution_contract`. Read it before
dispatching or reviewing implementation work. Callers reference this file;
they do not redefine the contract.

```yaml
execution_contract:
  tdd_required: <true | false>
  local_commit_authorized: <true | false>
  local_commit_scope:
    repositories: [<absolute repository roots>]
    workspace_or_branch: <absolute workspace and branch, or null when false>
    plan_or_tasks: [<bounded plan/task identifiers>]
  finish_after_execution: false
```

- Instantiate the contract for each task before implementation. Set
  `tdd_required=false` only for a controller-declared pure non-code task and
  record the concrete reason beside the contract. The implementer, fixer, and
  reviewer cannot create or broaden an exemption. The canonical definition of
  a valid RED and its evidence is in `test-driven-development/SKILL.md`.
- Set `local_commit_authorized=true` only from an explicit human authorization
  in the current conversation whose repository, workspace/branch, and
  plan/task bounds cover this task. Coding permission, a Plan `Commit` step,
  an earlier conversation, a ledger, or repository access is not authority.
  When false, every scope value is empty/null and no local commit may occur.
- `finish_after_execution` is always `false`. Execution ends by returning its
  implementation and verification state. Push, merge request, merge, branch
  cleanup, or any finishing workflow requires a later explicit request and
  its own authorization.

## Personal-workflow SDD handoff

个人工作流中的固定问题 `是否开启 Subagent-Driven Development 进行开发？`
是授权提示，不是进度通知。提问前，总控必须显示当前 `plan_ref`、配置中的代码仓库绝对路径，
Plan 显示的 `base_source`、`base_locator` 与评审时的完整 `base_sha`；`base_source=remote`
时还显示 `base_remote` 与 `base_branch`。同时说明所选来源的验证动作通过后，才由
`using-git-worktrees` 从该 SHA 创建或确认隔离工作区。
用户在当前对话中的明确肯定答复同时授权原有三件事：创建或进入
`using-git-worktrees` 实际返回的隔离 worktree、实现所显示的当前 Plan，以及在其中创建
当前 Plan 范围内的本地 commits。

当 `base_source=remote` 时，同一肯定答复还授权第四件本地前置动作：仅对 Plan 显示的 `base_remote` 与 `base_branch`
执行一次开发准备 fetch，只更新本地 remote-tracking ref 并解析最新完整
commit SHA。它在执行顺序中必须先于 worktree 创建或复用；不授权任何远程写入，也不允许
`pull`、merge 或 reset 主 checkout。fetch 失败或 SHA 漂移时，worktree、编码和 commit
授权尚不能落到实际执行范围；总控按个人工作流返回材料阶段。

当 `base_source=local` 时，同一答复只授权验证精确显示的本地 `base_sha`，以及复用或从该
SHA 创建干净隔离 worktree；它不授权远程 fetch 或远程相等性比较。定位对象移动、commit
不存在、HEAD 不相等或 worktree dirty 时，授权尚不能落到编码和 commit 范围，总控返回材料阶段。

所选来源验证通过且 worktree 建立后，把 `local_commit_authorized=true` 实例化为：配置中的代码仓库绝对路径、
实际返回的隔离 worktree 及其 branch、以及已显示的 Plan/Task 身份。范围不能包含其他仓库、
workspace、Plan 或 Task。普通“开始开发”、沉默、含糊回答、Plan 批准或持久游标都不是该授权。

该门禁不授权 push、MR、合并、清理或 branch finishing。即使 SDD 的全部 Task 和本地 commits
已经完成，这些操作仍需要之后单独明确授权。

Pass the exact serialized contract unchanged to every executor, implementer,
fixer, task reviewer, and uncommitted-change reviewer. A recipient must stop
when the contract is absent, altered, internally inconsistent, or too narrow
for discovered work. Reviewers independently fail the scope gate when a
change or commit falls outside the contract.

Durable progress may restore task position and evidence only. It never
restores authorization in a new conversation.
