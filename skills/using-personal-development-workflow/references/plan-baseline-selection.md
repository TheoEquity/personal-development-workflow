# Plan 基线选择

本文件定义个人开发工作流在创建或重写正式 Plan 前如何发现、展示、选择并验证稳定代码基线。选择同时绑定一个交付轮次：同轮单需求或并发需求共享冻结 `base_sha`；新的轮次重新选择。

## 交付轮次与启动时机

- 需求讨论阶段不读取本文件。新需求完成登记并进入首次 `writing_plan` 时，才把“新需求启动的稳定基线候选”展示给用户；这样不会在需求讨论提前加载 Plan、worktree 或收尾规则。
- 一轮可以只有一个需求，也可以有多个并发需求。每个需求仍有独立 `change_id`、分支、worktree、正式材料和 `code_ref`，但同一轮默认共享已经冻结的 `base_source`、`base_locator` 和 `base_sha`。
- 当前轮已经有共同基线时，优先推荐该 SHA。用户手动选择不同于当前共同基线的稳定候选时，该需求进入新一轮；不得在原轮次混合基线，也不得静默改变其他需求的 Plan。
- 轮次身份不新增 SQLite stage、表、字段或正式材料类型。总控从当前会话的轮次选择、实际 Git、已完成事件总账和集线绿色 HEAD 恢复；无法唯一恢复时重新展示候选并等待选择。

## 触发时机

- 每次新建正式 Plan，或材料评估确认后需要修改现有 Plan，都必须重新执行本门禁。任何会产生新 `plan_ref` 的 Plan 修改，无论称为定点修改、局部更新、重写或重建，都必须重新选择基线；内容不变但重新锚定到新的 Git SHA、重新提交或重新采用也不能沿用旧选择。
- 门禁必须发生在代码调查、Plan 写作和 Plan reviewer 之前。基线确定前不得创建或重写 Plan，也不得让 reviewer 使用尚未确认的代码树。
- 仅修改 Spec 而结论明确为“Plan 无需修改”时，不重写 Plan，因此不触发本门禁；该结论仍受材料变更评估的逐次确认约束。

## 发现本地候选

候选来源只允许以下四类稳定身份；不属于四类的本地 HEAD 即使存在也不能展示为可选基线：

1. **本轮共同基线**：当前轮已经由用户选择并冻结的完整 SHA。
2. **集线绿色 HEAD**：当前交付周期实际集线分支上最近一次组合验证通过的完整 SHA。
3. **已完成事件 `code_ref`**：completed 总账的原始代码 commit，且 Git 对象、仓库身份和完成状态机械校验通过。
4. **远端目标分支 HEAD**：按下节实时查询的目标远程分支完整 SHA。

在配置仓库运行 `git worktree list --porcelain` 只是定位上述稳定身份、绝对 worktree 和 clean/dirty 状态，不会把任意 worktree HEAD 自动升级为候选。禁止仍在开发中的需求分支、其可变 HEAD 或 worktree 状态；也禁止用另一个进行中需求的分支作为链式基线。

对每个允许的本地候选重新解析 40 位完整 SHA，并报告来源类别、绝对 worktree（若有）、branch/detached、`clean/dirty` 和 pushed 状态。只有明确 remote ref 证明可达才写 pushed；证据不足写“未确认”。本地稳定候选可以尚未推送，也不要求等于远程最新 SHA。

dirty worktree 的 HEAD 只有在其 commit 已经属于上述允许类别时才可作为该稳定 commit 的定位对象，并必须明确“未提交修改不属于任何 SHA”。代码调查、Plan 和实现不得混入 dirty 内容。若用户要捕获既有 diff，先执行下面的预 Plan 捕获合同；捕获后仍必须把新 commit 明确冻结为**新一轮的本轮共同基线**，重新展示候选卡并等待选择，不能把捕获 SHA 自动塞进原轮次。

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
轮次：<current-round-id 或“新一轮”>
本轮共同基线：<40-char-sha 或“尚未建立”>
集线绿色 HEAD：<branch> | <40-char-sha 或“不存在”> | <组合验证证据>
已完成事件 code_ref：<change_id> | <40-char-sha> | <仓库与完成校验>
远端目标分支 HEAD：<base_remote>/<base_branch> | <40-char-sha> | 实际 ls-remote
排除：<仍在开发中的需求分支与其他非稳定 HEAD>
推荐：<四类允许候选之一> | <依据>
请选择：接受推荐，或明确指定一个已展示的稳定候选
```

- 推荐顺序为：仍有效的本轮共同基线 → 集线绿色 HEAD → 与本需求直接相关的已完成事件 `code_ref` → 远端目标分支 HEAD。更高优先级不存在、无效或与交付目标不相容时才推荐下一类，并逐条说明。
- 候选卡展示后必须等待用户选择。用户只回复“继续”或“接受推荐”时采用仍可验证的推荐候选；不再无条件把远端当默认。
- 用户明确指定已展示的其他稳定候选时选择该项；不同于当前共同基线时明确标记“进入新一轮”，不能把它写入原轮其他 Plan。
- 用户在候选卡出现前说过“继续”、笼统说“开始”，或保持沉默，都不能替代本次选择。
- 选择只绑定候选卡中明确选中的来源和定位对象。等待期间只有选中的候选移动才使该选择失效；未选候选的移动不允许静默改变已选基线，也不单独使其失效。

### 并发需求共同基线候选卡

同一轮多个需求或变更事件并发开发时，本节专门规则只把通用基线选择的范围提升到整轮，并增加跨 Plan 一致性约束；它不改变本地/远程候选、默认选择或来源验证的通用语义。

1. 协调入口只建立一张共同基线候选卡并等待一次选择。卡片只展示本轮共同基线、集线绿色 HEAD、已完成事件 `code_ref` 和实际远端目标分支 HEAD；第一轮没有共同基线或集线时通常推荐远端目标分支。
2. 用户在该卡片后只回复“继续”时接受推荐；明确选择另一个已展示稳定候选时使用该项。本地共同基线可以尚未推送，不要求与远程候选相等。
3. 选择结果原样传给本轮所有对应 Plan。每份 Plan 记录相同的 `base_source`、`base_locator` 和 40 位完整 `base_sha`；远程来源的 `base_remote`、`base_branch` 也相同，本地来源的 `base_worktree`、`base_local_branch`、`base_detached_sha`、pushed 状态和 dirty 排除说明也相同。`base_locator` 只作共同基线的可读来源标签，不是各需求后续独立开发 worktree 的路径，也不得代替结构化本地字段参与机械验证。
4. 每个需求仍创建自己的隔离 worktree，但都使用选定的同一个 `base_sha` 作为强制起点。本地来源不执行远程 fetch 或远程相等性比较；远程来源继续执行对应的远程门禁。
5. 选中候选在所有 Plan 完成选择验证前移动时，整轮选择失效，重新生成一张共同基线候选卡；不得只替换某一个需求的基线。未选候选移动不改变已经选定的共同基线。
6. 新加入需求接受当前共同基线时进入本轮；选择不同候选时进入新一轮。任何情况下都禁止让一个 Plan 在原轮次使用不同 `base_sha`。

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
| 用户在候选卡后只说“继续” | 接受仍可验证的推荐候选 |
| 用户选未推送本地 commit | 记录 `base_source=local`，不要求远程相等 |
| 本地 worktree dirty | HEAD 可列候选，但明确未提交修改被排除 |
| 用户要把 dirty 修改算进基线 | 先单独授权并形成 commit，再重新列候选 |
| 远程或本地定位对象移动 | 使选择失效，重新执行门禁 |
| Plan 重写 | 重新发现、展示并确认候选 |
| 同轮多个并发需求或变更事件 | 整轮共用一张候选卡、一次选择和同一个来源/SHA |
| 当前轮已有共同基线 | 默认推荐共同基线；新需求接受后加入本轮 |
| 用户选择不同稳定 SHA | 该需求进入新一轮，不混入原轮次 |
| 进行中需求分支 | 不展示为候选，也不作链式基线 |

## 常见错误与停止信号

| 错误想法 | 正确处理 |
| --- | --- |
| “远程通常是默认，所以直接写 Plan” | 默认只在候选卡展示后的“继续”生效。 |
| “当前分支 HEAD 就是本地基线” | 枚举相关 worktree，并让用户选择完整 SHA。 |
| “dirty 文件也在 HEAD 里” | 未提交修改不属于任何 SHA，必须排除或先形成获授权 commit。 |
| “本地 SHA 没推送，开发前再对齐远程” | 明确选择的本地 SHA 是有效基线，不执行远程相等性门禁。 |
| “候选移动一点没关系” | 基线身份已经变化，必须重新展示候选并等待选择。 |
| “并发需求规则要求开放 MR 时强制远程” | MR 源分支头只是远程候选；整轮也允许明确选择本地候选。 |
