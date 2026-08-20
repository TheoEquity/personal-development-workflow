# Plan 基线选择

本文件定义个人开发工作流在创建或重写正式 Plan 前如何发现、展示、选择并验证代码基线。选择针对当前这一次 Plan，不自动沿用到下一次重写。

## 触发时机

- 每次新建正式 Plan，或材料评估确认后需要重写现有 Plan，都必须重新执行本门禁。
- 门禁必须发生在代码调查、Plan 写作和 Plan reviewer 之前。基线确定前不得创建或重写 Plan，也不得让 reviewer 使用尚未确认的代码树。
- 仅修改 Spec 而结论明确为“Plan 无需修改”时，不重写 Plan，因此不触发本门禁；该结论仍受材料变更评估的逐次确认约束。

## 发现本地候选

1. 在配置中的实现仓库运行 `git worktree list --porcelain`，枚举与当前事件直接相关的本地 worktree、分支和 detached HEAD；不得只看当前工作目录。
2. 对每个相关候选重新解析 40 位完整 HEAD SHA，并报告：绝对 worktree 路径、branch 或 detached、完整 SHA、`clean/dirty` 状态。
3. 只展示与本次 Plan 有直接关系的候选。名称相似、同项目但无关的 worktree 不得自动纳入。
4. 本地候选可以尚未推送，也不要求等于远程最新 SHA。它表示用户明确选择从该 Git commit 继续，而不是宣称它已经存在于远程。
5. dirty worktree 的 HEAD commit 仍可作为候选，但必须明确写出“未提交修改不属于任何 SHA”。选中该 SHA 后，代码调查、Plan 和实现不得混入当前脏工作区。若用户要把这些修改纳入基线，必须先取得范围明确的本地 commit 授权，提交后重新展示候选。

## 查询远程候选

1. 从项目配置和用户已经明确的目标确定 `<base_remote>` 与 `<base_branch>`。remote、branch 或目标仓库存在歧义时先询问，禁止猜 remote 默认分支。
2. 使用只读查询 `git ls-remote --heads <base_remote> refs/heads/<base_branch>` 获得实际远程分支当前的 40 位完整 SHA。不得把本地 remote-tracking ref 当成实际远程状态。
3. 远程不可访问、分支不存在或结果不唯一时，报告事实并停止；不得用旧 SHA 填补候选卡。

## 候选卡与默认选择

把本地候选和远程候选放在同一张候选卡中，至少显示：

```text
Plan 基线候选
本地：<absolute-worktree> | <branch-or-detached> | <40-char-sha> | clean/dirty | <pushed/未确认/尚未推送>
远程：<base_remote>/<base_branch> | <40-char-sha> | 实际 ls-remote
默认：只回复“继续”将采用远程候选
请选择：远程，或明确指定一个本地候选 SHA/定位对象
```

- 候选卡展示后必须等待用户选择。用户只回复“继续”将采用远程候选，但只有远程候选唯一且仍可验证时才生效。
- 用户明确指定本地候选、SHA 或定位对象时选择本地；不得因为“通常用远程”而覆盖该选择。
- 用户在候选卡出现前说过“继续”、笼统说“开始”，或保持沉默，都不能替代本次选择。

## 选择后的验证

### 远程来源

- 选择远程后，允许为本次规划执行一次限定到所选 remote/branch 的 fetch，并解析将用于代码调查的 commit。
- 若远程在等待选择期间移动，或 fetch 后解析的 SHA 与候选卡不同，所选候选失效；停止 Plan 写作，重新执行选择门禁并重新展示候选。
- 验证通过后，代码调查、writer 与 reviewer 必须使用所选 SHA 的同一 Git tree。后续进入开发时仍执行开发前远程漂移门禁。

### 本地来源

- 选择本地后重新解析该绝对 worktree、branch/detached 定位对象和 commit。若本地定位对象已经移动、commit 不存在或身份不再唯一，停止并重新展示候选。
- 本地基线不执行远程相等性门禁；它可以尚未推送，不要求等于远程最新 SHA。
- 代码调查和 Plan reviewer 只能读取精确选中的 Git tree。若已有 worktree 的 HEAD 等于所选 SHA 且干净，可以复用；否则从该 SHA 创建隔离的干净 worktree。不得混入当前脏工作区。

## Plan 记录合同

每份正式 Plan 的 `## 开发基线` 至少逐行记录：

```text
base_source: remote | local
base_locator: <remote/branch | absolute-worktree@branch-or-detached>
base_sha: <40 位完整 Git commit SHA>
```

- `base_source=remote` 时，额外记录可机械解析的 `base_remote` 与 `base_branch`。
- `base_source=local` 时，`base_locator` 必须包含选择时的绝对 worktree 与 branch/detached 身份，并记录 pushed 状态和 dirty 修改排除说明。
- Plan reviewer 必须收到这些字段、配置仓库绝对路径和精确 `base_sha` 的代码树；输入不一致时不能批准或采用 Plan。

## 开发入口分流

- `base_source=remote`：SDD 开始前重新 fetch Plan 指定分支并逐字比较最新完整 SHA；漂移时关闭代码门并返回材料评估。
- `base_source=local`：不执行远程 fetch 或远程相等性比较。验证 commit 仍存在，并只复用 HEAD 逐字等于 `base_sha` 且工作区干净的隔离 worktree；否则从该 SHA 创建新的隔离 worktree。
- 两种来源都只授权本地准备、实现和明确范围内的本地 commits；都不授权 push、MR、合并或清理。

## 快速参考

| 情况 | 动作 |
| --- | --- |
| 用户在候选卡后只说“继续” | 选择唯一的远程候选 |
| 用户选未推送本地 commit | 记录 `base_source=local`，不要求远程相等 |
| 本地 worktree dirty | HEAD 可列候选，但明确未提交修改被排除 |
| 用户要把 dirty 修改算进基线 | 先单独授权并形成 commit，再重新列候选 |
| 远程或本地定位对象移动 | 使选择失效，重新执行门禁 |
| Plan 重写 | 重新发现、展示并确认候选 |

## 常见错误与停止信号

| 错误想法 | 正确处理 |
| --- | --- |
| “远程通常是默认，所以直接写 Plan” | 默认只在候选卡展示后的“继续”生效。 |
| “当前分支 HEAD 就是本地基线” | 枚举相关 worktree，并让用户选择完整 SHA。 |
| “dirty 文件也在 HEAD 里” | 未提交修改不属于任何 SHA，必须排除或先形成获授权 commit。 |
| “本地 SHA 没推送，开发前再对齐远程” | 明确选择的本地 SHA 是有效基线，不执行远程相等性门禁。 |
| “候选移动一点没关系” | 基线身份已经变化，必须重新展示候选并等待选择。 |

