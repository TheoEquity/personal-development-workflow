# Plan 基线选择

本文件定义个人开发工作流在创建或重写正式 Plan 前如何发现、展示、选择并验证代码基线。选择针对当前这一次 Plan，不自动沿用到下一次重写。

## 触发时机

- 每次新建正式 Plan，或材料评估确认后需要修改现有 Plan，都必须重新执行本门禁。任何会产生新 `plan_ref` 的 Plan 修改，无论称为定点修改、局部更新、重写或重建，都必须重新选择基线；内容不变但重新锚定到新的 Git SHA、重新提交或重新采用也不能沿用旧选择。
- 门禁必须发生在代码调查、Plan 写作和 Plan reviewer 之前。基线确定前不得创建或重写 Plan，也不得让 reviewer 使用尚未确认的代码树。
- 仅修改 Spec 而结论明确为“Plan 无需修改”时，不重写 Plan，因此不触发本门禁；该结论仍受材料变更评估的逐次确认约束。

## 发现本地候选

1. 在配置中的实现仓库运行 `git worktree list --porcelain`，枚举与当前事件直接相关的本地 worktree、分支和 detached HEAD；不得只看当前工作目录。
2. 对每个相关候选重新解析 40 位完整 HEAD SHA，并报告：绝对 worktree 路径、branch 或 detached、完整 SHA、`clean/dirty` 状态。只有通过明确的远程 ref 查询证明可达时才写 pushed；不能仅因 `L != R` 推断“尚未推送”，证据不足时写“未确认”。
3. 只展示与本次 Plan 有直接关系的候选。名称相似、同项目但无关的 worktree 不得自动纳入。
4. 本地候选可以尚未推送，也不要求等于远程最新 SHA。它表示用户明确选择从该 Git commit 继续，而不是宣称它已经存在于远程。
5. dirty worktree 的 HEAD commit 仍可作为候选，但必须明确写出“未提交修改不属于任何 SHA”。选中该 SHA 后，代码调查、Plan 和实现不得混入当前脏工作区。若用户要把这些修改纳入基线，必须先按下面的预 Plan 捕获合同取得范围明确的本地 commit 授权，提交后重新展示候选。

### 预 Plan 基线捕获合同

正式 Plan 尚未存在或尚未产生本轮 `Task N` 时，允许使用 `execution_contract` 的 `plan_or_tasks` 身份 `baseline-capture:<change_id>` 表示一次受限快照。实例化时必须绑定配置仓库、精确绝对 worktree/branch，并且只包含用户点名纳入基线的 diff；尚未存在 `Task N` 不能用未来任务占位。

- 请求 commit 授权前，先按 [execution-contract.md](execution-contract.md) 授权前只读生成 `baseline_snapshot`：绑定捕获前完整 HEAD，并把用户点名范围展开成按仓库相对路径排序且无重复的 path/state/mode/content OID 清单。untracked 文件必须逐文件列出，rename 按 deleted + present 两项表示；不能用目录名、自然语言“当前 diff”或未来暂存区代替清单。
- 该授权只允许检查、暂存并提交已经存在的点名 diff，不允许编辑任何文件，不能授权后续实现 commit，也不更新 `code_ref`。暂存前与 commit 前都必须确认范围仍精确等于用户点名的既有 diff；内容发生变化时旧授权失效。
- 暂存前只比较当前 worktree manifest 与授权清单，并确认相对 `head_sha` 的 staged delta 不含清单外路径；不能把包含所有 tracked 文件的原始 Git index 当成待提交 delta。然后只暂存 manifest 路径。暂存后与 commit 前再次逐字段核对当前 manifest，以及相对 `head_sha` 的 staged delta 的 path、mode、content OID；索引不得包含清单外条目。任何不一致都停止，不替用户清理或重写现有 index，必须重新展示新 manifest 并取得新授权。
- 使用正常 hooks 创建一次 commit；禁止 `--no-verify`。提交后验证新 HEAD 的唯一 parent 等于 `head_sha`，已提交 delta manifest 与授权清单逐字段相同，新 HEAD 相对 index 无 staged delta，且捕获路径没有 hook 遗留的新 worktree 修改。无关的未暂存路径继续按 dirty 排除。任一 post-commit 检查失败时授权已经耗尽：不得 amend、reset、重试、更新 `code_ref`，也不得把该 SHA 放入候选卡；报告实际 commit 并等待用户另行明确处理。
- baseline capture 是既有 diff 快照，不是新的实现声明。无论快照是代码、测试还是非代码，都在合同内使用 `tdd_required=false` 和 `tdd_exemption_reason: pre-existing-diff-snapshot-only`；它解决的是无法追溯制造实现前 RED 的快照问题，不构成 TDD 或实现完成证据，不能用来宣称代码正确、测试充分或任务已完成。
- 该例外只覆盖这一次原样快照 commit；后续实现任务仍必须执行 TDD，不能继承本次豁免、提交授权或证据。若要编辑、拆分、补测或修正快照内容，立即退出 capture，按正式任务重新取得相应材料、TDD 与执行授权。
- 若已有正式材料且 dirty 事实可能使其失效，先完成材料变更评估；不得用捕获 commit 绕过材料门禁。
- 提交形成新 SHA 后，本次捕获授权即耗尽；重新运行本地/远程发现、展示候选卡并等待选择，不能把旧选择或本授权带入规划和实现。

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
- 选择只绑定候选卡中明确选中的来源和定位对象。等待期间只有选中的候选移动才使该选择失效；未选候选的移动不允许静默改变已选基线，也不单独使其失效。

### 跨 Bug 共同基线候选卡

同一轮多个 Bug 并行开发时，本节专门规则只把通用基线选择的范围提升到整轮，并增加跨 Plan 一致性约束；它不改变本地/远程候选、默认选择或来源验证的通用语义。

1. 协调入口只建立一张共同基线候选卡并等待一次选择。卡片仍按本文件展示全部直接相关的本地候选和一个实际远程候选；第一轮以目标远程分支为远程候选，已有开放 MR 时以 MR 实际源分支头为远程候选。
2. 用户在该卡片后只回复“继续”时选择唯一远程候选；明确选择一个本地候选时选择本地。本地共同基线可以尚未推送，不要求与远程候选相等。
3. 选择结果原样传给本轮所有 Bug Plan。每份 Plan 记录相同的 `base_source`、`base_locator` 和 40 位完整 `base_sha`；远程来源的 `base_remote`、`base_branch` 也相同，本地来源的 `base_worktree`、`base_local_branch`、`base_detached_sha`、pushed 状态和 dirty 排除说明也相同。`base_locator` 只作共同基线的可读来源标签，不是各 Bug 后续独立开发 worktree 的路径，也不得代替结构化本地字段参与机械验证。
4. 每个 Bug 仍创建自己的隔离 worktree，但都使用选定的同一个 `base_sha` 作为强制起点。本地来源不执行远程 fetch 或远程相等性比较；远程来源继续执行对应的远程门禁。
5. 选中候选在所有 Plan 完成选择验证前移动时，整轮选择失效，重新生成一张共同基线候选卡；不得只替换某一个 Bug 的基线。未选候选移动不改变已经选定的共同基线。

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
base_locator: <可读来源标签，不作机械解析>
base_sha: <40 位完整 Git commit SHA>
```

- `base_source=remote` 时，额外记录可机械解析的 `base_remote` 与 `base_branch`。
- `base_source=local` 时，额外逐行记录 `base_worktree`（选择时的绝对来源 worktree）、`base_local_branch`（branch 名；detached 时为 `null`）和 `base_detached_sha`（detached 时为选择的完整 SHA；有 branch 时为 `null`），并记录 pushed 状态和 dirty 修改排除说明。`base_locator` 仅供人读，机械验证只使用这些结构化字段，不从 `absolute-worktree@branch` 之类字符串猜测分隔位置。
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
| 同轮多个 Bug | 整轮共用一张候选卡、一次选择和同一个来源/SHA |

## 常见错误与停止信号

| 错误想法 | 正确处理 |
| --- | --- |
| “远程通常是默认，所以直接写 Plan” | 默认只在候选卡展示后的“继续”生效。 |
| “当前分支 HEAD 就是本地基线” | 枚举相关 worktree，并让用户选择完整 SHA。 |
| “dirty 文件也在 HEAD 里” | 未提交修改不属于任何 SHA，必须排除或先形成获授权 commit。 |
| “本地 SHA 没推送，开发前再对齐远程” | 明确选择的本地 SHA 是有效基线，不执行远程相等性门禁。 |
| “候选移动一点没关系” | 基线身份已经变化，必须重新展示候选并等待选择。 |
| “跨 Bug 规则要求开放 MR 时强制远程” | MR 源分支头只是远程候选；整轮也允许明确选择本地候选。 |
