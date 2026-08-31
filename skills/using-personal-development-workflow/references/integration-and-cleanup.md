# 滚动 Delivery、MR 与清理

本 reference 负责 Worker 集成、交付批次冻结、MR 反馈和清理；不新增 SQLite 阶段、表、字段或正式材料类型。Delivery/Worker 身份位于 Spec Vault `.local`，真实分支、SHA、祖先关系和 dirty 状态始终由 Git 复核。

## 拓扑

- 一个 Delivery Worktree/交付分支覆盖一次滚动交付周期，或一个开放 MR 的整个生命周期；开放 MR 只有一个集线会话独占其源分支。
- Full 的 Worker Worktree 只处理一个 `change_id + plan_ref`；同一 CE 只有一个实现 Worker，Plan 内 Task 不生成外层 Worker。Direct/light Worker 只绑定当前 CE 范围。一个 Worker 不得跨 CE 或复用做新 Plan。
- 新 Worker 从 Delivery 最新绿色 SHA 创建。依赖尚未集成的工作时先等待依赖进入 Delivery，不在 Worker 之间建立依赖网络。
- 开发可以并发，集成必须串行。用户可一次选择多个候选，但协调过程仍逐个处理，任一冲突或验证失败立即停止。

状态路径：

```text
.local/deliveries/<delivery_id>/delivery.json
.local/deliveries/<delivery_id>/workers/<worker_id>.json
.local/deliveries/<delivery_id>/changes/<change_id>/tasks.md
```

Delivery 至少记录路径、分支、当前 SHA、冻结 SHA、冻结状态和生命周期状态。Worker 至少记录 `worker_id`、`change_id`、Full 的 `plan_ref` 或 direct/light 的范围标识、路径、分支、基线 SHA、状态，并在集成后记录实际 `integrated_commit`。Light 的 `tasks.md` 不提交 Git，也不形成 `plan_ref`。

## 修改和集成前检查

每次修改或集成前，用真实 Git 状态核对：

- 当前目录、Git common directory、分支、HEAD；
- Worker 绑定的 CE/Plan 或轻量范围、基线和是否已集成；
- Delivery 当前绿色 SHA、冻结状态和是否存在其他集成操作；
- dirty/untracked 状态。

记录与 Git 不一致时停止，不自动猜测或覆盖。正在开发或已经集成的 Worker 不得承接新任务。

## 串行集成

Worker 完成、提交并验证后成为候选；展示精确 Worker、HEAD、目标 Delivery 和拟执行验证，等待用户确认本地合入。`review_mode=auto` 也不自动授权该动作。

授权后：

1. 记录 `delivery_before_sha` 并确认 Delivery 尚未冻结且仍绿色。
2. 确认 Worker HEAD 与 `delivery_before_sha` 后，在临时候选 ref/worktree 上执行 `git merge --no-ff <worker-head>`；不要求 Worker 对未变化的同一 SHA 重跑已有测试，也不直接移动正式 Delivery ref。
3. 冲突时只在临时候选中 abort，Delivery 不动；报告冲突，Worker 保留。
4. 合并成功后证明 Worker HEAD 是候选 HEAD 的祖先；该候选就是最终候选，在其精确 SHA 上执行一次 CE 完整自动化验证。
5. 验证通过后使用旧值校验的原子 compare-and-swap 提升 Delivery；并发移动或验证失败都不得提升。
6. 记录新 Delivery HEAD、本次 `integrated_commit` 和验证证据键，把 Worker 标为 `integrated`，禁止继续开发。

该过程保留提交身份；`--no-ff` 候选还必须证明 Worker SHA 是 merge SHA 的祖先，并比较 `delivery_before_sha..Worker SHA` 与该 merge 中该 CE 的变化，确认没有改写该 CE 的已审 diff。不得用 squash、patch 重放或不受控 rebase 替代可追踪的集成结果。

## CE 验证与 code_ref

一个 CE 的唯一 Worker 集成后，若 Delivery 当前 HEAD 与刚通过验证的最终候选 SHA 一致，直接复用该证据并把 HEAD 保存为该 CE 的单一 `code_ref`，不再追加一次内容相同的 CE 验证。证据键固定为 `code_sha + command + environment_fingerprint + input_fingerprint`，同一成功证据只执行和记录一次；任一维度变化时失效并重新执行。Worker 的 `integrated_commit` 留在本地状态中，用于归属、审查和 Bug 调查。后续 CE 推动 Delivery 不改变旧 `code_ref`。

完成版 `change.md` 由 CE 收尾过程统一写入，Worker 不直接修改 `change.md`。Bug 或小需求的修改与验证摘要用于检索，但历史摘要不是当前行为合同。

## 批次冻结与审核

Delivery 持续滚动接收已完成 Worker，批次边界由用户决定。用户说“这一批到这里”后：

- 固定 `freeze_base` 与当前 `freeze_head`，暂停接收普通任务；
- 对已集成内容核对批次组合证据；只有 `freeze_head`、命令、环境或输入形成新的组合状态时运行未覆盖验证，完全相同的证据键直接复用；
- 未集成 Worker 不进入本次 MR，保留到后续批次；
- 不自动 Push、不自动创建/更新 MR、不自动合并或部署，不自动删除 Worktree。

只有用户明确要求跨 CE 批次 review 时才新增一次审查，并固定：

```text
review_scope: CE | batch
review_base: <sha>
review_head: <sha>
reviewed_worker_head: <sha | null>
review_commits: [<integrated_commit>...]
```

- `review_scope=CE`：Full 的 `review_head` 和 `reviewed_worker_head` 记录已审 Worker SHA，`code_ref` 记录 Delivery merge SHA；祖先关系和未改写 diff 的证明把两者绑定。Full 不新增审查，直接复用该 SDD 最终整体 review；Direct/light 只有用户明确要求时执行一次范围化只读审查。
- `review_scope=batch`：严格映射为 `review_base=freeze_base`、`review_head=freeze_head`；`review_commits` 包含该冻结批次全部且仅限该批次的集成提交，并采用相同的顺序、去重和祖先校验。

批次审查使用一个只读 reviewer，只审查跨 CE 交互，并消费冻结 SHA 上已有的自动化证据；不得重做各 CE 的内部代码 review，不得派测试 Agent 重跑相同证据，也不得移动冻结 SHA。Coordinator、Root 和 Delivery 不得对 Full SDD 最终 review 追加等价代码 review。

## MR 反馈

冻结后只接收本次 MR 反馈：

- 原 CE 仍进行中且问题属于原验收范围：继续原 CE。
- 原 CE 已完成：新建 Bug CE，并在新 `change.md` 用 `source_ce` 指向引入问题的旧 CE；旧 CE 保持不可变。
- Bug 只是恢复已有约定行为：direct；实际新增行为：light 或 full。

确定 CE 后，从 Delivery 最新冻结状态另开修复 Worker。用户确认集成、验证通过后更新冻结 SHA，并重新执行批次级组合验证。与本次 MR 无关的普通任务继续等待。

开放 MR 更新时只 push 同一实际源分支，不得新建重复 MR。MR 已合并或关闭后不能复用旧周期。

## 清理候选卡

清理始终是独立授权。MR 提出后自动形成只读候选卡，至少列出：

- Delivery、已集成 Worker、未集成 Worker 的精确路径、分支、HEAD 与状态；
- Worker 的 `integrated_commit` 及其是 Delivery HEAD 祖先的证明；
- clean/dirty/untracked 摘要；
- 拟删除的精确 worktree registration、目录、状态文件和本地分支；
- 明确不包含的远端分支、其他 CE/Worker、Push、MR、合并与部署。

只有用户对这张精确卡确认后才执行：

- 已集成且 clean、无 untracked 的 Worker 可清理；本地分支先保留，或在 Git 能证明安全且卡片明确列出时用普通安全删除。
- 未集成 Worker 不清理，明确标记为未进入本次 MR。
- Delivery 保留到 MR 合并或关闭，用于反馈和验证。
- MR 合并或关闭后，先证明目标分支包含本批全部 `code_ref`；最终目标 SHA 或组合输入变化时运行相应组合验证，四元组完全相同时复用已有成功证据；之后才可候选清理 Delivery。
- 删除状态文件与删除 Worktree 同属清理授权；关闭对象标为 `closed/cleaned`，后续恢复默认忽略。

任何 dirty/untracked、分支被其他 worktree 使用、祖先证明失败、目标 ref 移动或卡片内容变化都停止清理。不得 force、reset、stash、宽泛 prune 或影响其他并发 Worktree。

## 远端权限

本地 Worker commit、Worker 合入 Delivery、Push、创建/更新 MR、合并 MR、部署、删除 Worktree和删除远端分支都是独立权限。即使 `review_mode=auto`，Push、MR、合并、部署和删除 Worktree 仍必须由用户手动确认。
