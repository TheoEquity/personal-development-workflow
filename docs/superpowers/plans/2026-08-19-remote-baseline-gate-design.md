# Remote Baseline Gate Design

## Goal

个人工作流进入实现前，必须从已评审 Plan 指定的远程基线分支取得最新完整 Git SHA。开发 Worktree 只能从这个最新 SHA 创建，不能从可能过期的本地主分支或旧 Plan SHA 开始。

## Confirmed contract

- 每份 Plan 明确记录 `base_remote`、`base_branch` 和评审时的 `base_sha`。
- 用户明确开启 Subagent-Driven Development 后，总控先对该远程与分支执行 `git fetch`；不对主 checkout 执行 `pull`、merge 或 reset。
- fetch 后解析远程跟踪分支的完整 commit SHA，并与 Plan 的 `base_sha` 比较。
- SHA 一致时，才调用 `using-git-worktrees` 从该 SHA 创建或确认隔离 Worktree，并验证 Worktree `HEAD` 精确等于该 SHA、工作区干净、仓库与 AGENTS 范围仍匹配。
- SHA 不一致时，代码门保持关闭。总控只审查新提交相对 Plan 基线对 Spec、Plan 和实现范围的影响；不默认重写整份材料。Plan 至少更新 `base_sha`，重新评审、提交并由 `adopt-plan` 采用后，才能再次展示 SDD 门禁。
- fetch、远程或分支解析失败时停止，不创建 Worktree，不写 RED、测试、生产代码或本地 commit。
- SDD 肯定答复只额外允许为当前显示的远程与分支更新本地远程跟踪引用；仍不授权 push、MR、merge、清理或 branch finishing。

## Scope

修改个人总控 Skill、它的个人执行合同、发布仓库 README 与合同测试，并同步运行时副本。Superpowers 原生 `writing-plans`、`using-git-worktrees` 和 `subagent-driven-development` 保持只读。

## Example

Plan 记录 `base_remote: origin`、`base_branch: main`、`base_sha: aaaa...`。开发门禁开启后 fetch `origin main`：若 `origin/main` 仍是 `aaaa...`，从该完整 SHA 创建 Worktree；若已变成 `bbbb...`，停止实现，针对 `aaaa...bbbb...` 的差异更新并重审 Plan，不能先写代码再补材料。
