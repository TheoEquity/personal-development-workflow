# Execution Contract

This file is the canonical definition of `authorization_offer` and
`execution_contract`. Read it before dispatching an implementation coordinator
or any implementation/review role. Callers reference this file; they do not
redefine either object.

`authorization_offer` is the immutable object displayed before the
personal-workflow SDD question in `review_mode=manual`, or instantiated and
validated without that question in `review_mode=auto`. It describes the exact
scope of local implementation authority; it never grants Delivery, remote, or
cleanup authority.

```yaml
authorization_offer:
  repository: <absolute repository root>
  plan_ref: <current immutable plan ref>
  plan_or_tasks: [<the same current immutable plan ref>]
  base_source: <remote | local>
  base_locator:
    kind: <remote | local>
    remote: <exact remote, or null for local>
    worktree: <absolute source worktree, or null for remote>
    branch: <exact source branch, or null when detached>
    detached_sha: <40-character SHA when detached, otherwise null>
  base_sha: <40-character Git commit SHA>
  remote_fetch_authorized: <true for the displayed remote source, otherwise false>
  worktree_creation_authorized: true
  tdd_required: <true | false>
  tdd_exemption_reason: <concrete pure-non-code reason, or null>
  baseline_snapshot: null
  local_commit_authorized: true
  finish_after_execution: false
```

The canonical post-preparation contract is:

```yaml
execution_contract:
  tdd_required: <true | false>
  tdd_exemption_reason: <concrete reason, or null>
  baseline_snapshot: <null or the manifest below>
  local_commit_authorized: <true | false>
  local_commit_scope:
    repositories: [<absolute repository roots>]
    workspace_or_branch:
      workspace: <actual absolute worktree path>
      branch: <actual branch name, or null when detached>
    plan_or_tasks: [<bounded plan/task identifiers>]
  finish_after_execution: false
```

The non-null `baseline_snapshot` shape is:

```yaml
  baseline_snapshot:
    head_sha: <40-character pre-capture HEAD SHA>
    entries:
      - path: <canonical repository-relative path>
        state: <present | deleted>
        mode: <Git mode to stage, or null for deleted>
        content_oid: <Git object id to stage, or null for deleted>
```

- Instantiate the contract before implementation. Set `tdd_required=false`
  only for a controller-declared pure non-code task or the exact pre-Plan
  baseline snapshot exception below, and put the concrete reason in
  `tdd_exemption_reason`; otherwise that field is `null`. The implementer,
  fixer, and reviewer cannot create or broaden an exemption. The canonical
  definition of a valid RED and its evidence for implementation work is in
  `test-driven-development/SKILL.md`.
- `baseline_snapshot` is `null` for ordinary implementation, review, and SDD
  contracts. Only `baseline-capture:<change_id>` may replace it with the
  structured manifest shown above.
- Set `local_commit_authorized=true` only from an explicit human authorization
  in the current conversation whose repository, workspace/branch, and
  plan/task bounds cover this task. Coding permission, a Plan `Commit` step,
  an earlier conversation, a ledger, or repository access is not authority.
  When false, every scope value is empty/null and no local commit may occur.
  When true, `workspace_or_branch` uses the structured workspace/branch object
  above; callers must not encode it as a delimiter-joined scalar.
- `finish_after_execution` is always `false`. Execution ends by returning its
  implementation and verification state. Push, merge request, merge, branch
  cleanup, or any finishing workflow requires a later explicit request and
  its own authorization.

Before a Plan has a current `Task N`, a separately confirmed baseline snapshot
uses `plan_or_tasks: [baseline-capture:<change_id>]`. This narrow identity may
authorize one local commit of the explicitly named existing diff in the exact
repository/worktree scope; it does not authorize file edits, later
implementation commits, `code_ref` updates, or any remote action. This is a
snapshot of a pre-existing diff, not a new implementation claim. Instantiate
it with `tdd_required=false` and record
`tdd_exemption_reason: pre-existing-diff-snapshot-only` in the contract even
when the named snapshot contains code. This exception applies only to the
unchanged pre-existing diff: it is not TDD evidence, does not prove the
implementation complete or correct, and cannot be reused by a later task.
Every later implementation task still follows TDD normally. The authorization
is consumed by that one snapshot commit. Before asking for this commit
authorization, the controller read-only builds `baseline_snapshot` from the
pre-capture `HEAD` and every explicitly named path. Paths are repository-relative,
slash-normalized, sorted, and unique. `content_oid` is the repository-format
Git object id of the exact content Git would stage after clean filters; symlinks
bind their link target and mode, submodules bind mode `160000` plus their commit,
and deletions use null mode/content. A rename is one deleted entry plus one
present entry. Immediately before staging, compare the current worktree
manifest with the authorized object and require that the staged delta relative
to `head_sha` has no path outside the manifest; do not compare the raw Git index,
which normally contains every tracked path. Stage exactly the manifest paths.
Immediately after staging and again before commit, require both the current
worktree manifest and the staged delta relative to `head_sha` to equal the
authorized entries field-for-field. Any difference consumes no commit authority
and requires a newly displayed manifest and new human authorization.

Create the snapshot commit with normal hooks enabled. After `git commit`
returns, verify that HEAD advanced by exactly one commit, that its only parent
is `baseline_snapshot.head_sha`, and that the committed delta's path, state,
mode, and content object id equal the authorized entries field-for-field. Also
require no staged delta relative to the new HEAD and no new worktree change on
the captured paths; unrelated unstaged paths remain dirty and are excluded by
the later candidate card. A hook-created commit, amend, merge parent, rewritten
entry, or leftover captured-path change makes the capture invalid. The commit
authorization is already consumed: do not amend, reset, retry, update `code_ref`,
or offer that SHA as a baseline without new explicit user direction.

## Personal-workflow SDD handoff

个人工作流 `review_mode=manual` 中的固定问题 `是否开启 Subagent-Driven Development 进行开发？`
是授权提示，不是进度通知。提问前只实例化并展示 `authorization_offer`；此时不得用
空范围或猜测的 worktree 提前实例化 `execution_contract`。offer 必须把当前 `plan_ref`、
配置中的代码仓库绝对路径、当前 Plan 范围、Plan 显示的 `base_source`、结构化
`base_locator` 与评审时的完整 `base_sha` 全部写入。远程来源把 Plan 的 `base_remote`、
`base_branch` 分别写入 locator 的 `remote`、`branch`，并把 `worktree`、`detached_sha`
写为 `null`；本地来源从 Plan 的 `base_worktree`、`base_local_branch`、
`base_detached_sha` 原样填充，`remote=null` 且不授权 fetch。不得从带分隔符的单个字符串反向解析
worktree 或 branch。Plan 中的 `base_remote`、`base_branch`、`base_worktree`、
`base_local_branch`、`base_detached_sha` 只是构造 locator 的输入，不是 offer 顶层字段；
offer 出现这些额外顶层 key 时无效。`worktree_creation_authorized: true` 表示肯定答复允许 `using-git-worktrees`
在来源验证通过后从该 SHA 创建或确认隔离工作区，offer 中不猜测尚不存在的开发
worktree 路径或 branch。

个人工作流的 SDD offer 固定使用 `plan_or_tasks: [plan_ref]`，表示本次问题授权整份当前
Plan；不得改成等价 Task 列表、重复项或未来 Task。只要当前 SDD Plan 含有代码任务，
`tdd_required=true` 且 `tdd_exemption_reason=null`；只有控制器在提问前证明整份 Plan 都是
纯非代码任务时才能写 `false` 和具体理由。混合 Plan 不能按单个非代码 Task 降低整份 offer。

`authorization_offer` 一经展示即不可变。缺失字段、无效引用或不完整 SHA 会阻止提问；
展示后 repository、Plan/Task、基线来源或任一权限字段发生变化时，旧 offer 失效，必须
重新评估并展示新的完整 offer 后再提问，不能就地改写。用户在当前对话中的明确肯定答复
只接受刚刚显示的完整序列化 offer；沉默、含糊回答或批准 Plan 都不接受它。展示 offer
和问题后必须停止，不得在同一轮验证来源、fetch、创建 worktree、编码或 commit。

`review_mode=auto` 不再询问 SDD。总控仍为当前已绑定 CE、当前精确 `plan_ref` 和当前代码仓库实例化同一完整 offer，并逐字段验证后才派生合同；持久 `review_mode=auto` 只授权这个范围内的隔离 worktree、SDD 和本地 commits。它不得扩展到另一个 CE、仓库或 Delivery，也不授权 Push、MR、部署或删除 Worktree。需求不清、范围扩大、基线漂移、引用/offer/contract 不一致或 Task 数量例外未获得用户确认时停止，不能用 auto 猜测决定。

不可变性按字段名与归一化值比较，不按 Markdown/YAML 字节比较。展示前把 SHA 规范为 40 位
小写十六进制、布尔值与 null 解析为原生类型、仓库路径解析为平台确认的绝对路径，并保持
`plan_ref`、来源定位和有序列表的精确值；列表不得含重复项。YAML 缩进、键顺序或引号样式不参与身份比较。
展示后冻结这棵类型化字段树；任何字段值变化都会使 offer 失效。

用户明确肯定后，offer 才授权原有三件事：创建或进入 `using-git-worktrees` 实际返回的隔离 worktree、
实现所显示的当前 Plan，以及在其中创建当前 Plan 范围内的本地 commits。

当 `base_source=remote` 时，同一肯定答复还授权第四件本地前置动作：仅对 Plan 显示的 `base_remote` 与 `base_branch`
执行受限的开发准备 fetch，只更新本地 remote-tracking ref 并解析最新完整
commit SHA。它在执行顺序中必须先于 worktree 创建或复用；不授权任何远程写入，也不允许
`pull`、merge 或 reset 主 checkout。认证、网络、fetch、ref 更新或解析失败时不产生合同或
worktree，保持 `tdd_coding` 并停止；只要仍在同一对话且 offer 字段未变，用户之后回复继续
可重试完全相同的受限 fetch，无需制造材料变更评估或重新询问 SDD。远程成功返回的 SHA
与 offer `base_sha` 不同时才属于基线漂移：旧 offer 立即失效，总控展示材料变更评估并等待
确认，确认后按个人工作流返回责任材料阶段。

当 `base_source=local` 时，同一答复只授权验证精确显示的本地 `base_sha`，以及复用或从该
SHA 创建干净隔离 worktree；它不授权远程 fetch 或远程相等性比较。定位对象移动、commit
不存在、HEAD 不相等或 worktree dirty 时，授权尚不能落到编码和 commit 范围。若 Plan 记录的本地来源定位对象移动或 commit 不存在，总控保持当前阶段，先展示材料变更评估并等待确认；确认后才返回责任材料阶段。仅目标开发 worktree 不匹配时，从精确 `base_sha` 创建新的干净隔离 worktree。

所选来源验证通过且 worktree 建立并复核为精确 `base_sha` 后，才从已接受的 offer 机械派生
最终 `execution_contract`：`tdd_required`、`tdd_exemption_reason`、`baseline_snapshot`、
`local_commit_authorized`、`plan_or_tasks` 和 `finish_after_execution` 原样复制，`repositories` 必须精确等于
`[authorization_offer.repository]`；`workspace_or_branch` 是派生时唯一新增的字段，
`workspace` 与 `branch` 只能分别取 `using-git-worktrees` 实际返回并已验证的绝对 worktree
和 branch，detached 时 branch 为 `null`。`plan_ref`、`base_source`、结构化 `base_locator`、
`base_sha` 以及 fetch/worktree 权限留在
不可变 offer 中作为派生和验证输入，不得被最终合同替代或遗失。

总控必须把已接受 offer 与派生合同并排逐字段比较；除补入实际 `workspace_or_branch` 外，
不得扩大或改写其他字段，也不得增加第二个仓库、换成更宽的 Plan/Task 或改变 TDD、commit、
finishing 边界。任何比较失败、来源验证失败或 worktree 创建失败都不产生最终
`execution_contract`，不得启动实现。普通“开始开发”、沉默、含糊回答、Plan 批准或持久
游标都不是该授权。

该门禁不授权 push、MR、合并、清理或 branch finishing。即使 SDD 的全部 Task 和本地 commits
已经完成，这些操作仍需要之后单独明确授权。

Pass the accepted normalized offer and exact serialized contract unchanged to
the personal-workflow implementation coordinator. The coordinator repeats the
field comparison before invoking SDD and passes both objects unchanged to every
executor, implementer, fixer, task reviewer, and uncommitted-change reviewer.
The coordinator is an orchestration role, not an additional authority source:
it cannot add a repository, widen the Plan/tasks, change TDD or commit scope, or
enable finishing. Every recipient repeats the comparison and must stop when
either object is absent, altered, internally inconsistent, or too narrow for
discovered work. Reviewers independently fail the scope gate when a change or
commit falls outside the contract.

Durable progress may restore task position and evidence. A new conversation
never restores a manual authorization; a persisted `review_mode=auto` may
resume only after revalidating the current candidate, formal references, and
exact bounded offer, and it still restores no authority for another CE or any
external action.
