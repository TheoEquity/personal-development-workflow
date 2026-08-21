# 完成后的集线归位与清理

只在 `current_stage=completed`，或用户对已完成事件明确提出归位、集成、清理、开放 MR 协调请求时完整读取。本流程不新增 SQLite 阶段、表、字段或正式材料类型；状态从实际 Git、completed 总账、当前会话已确认的交付周期事实恢复。

## 拓扑与生命周期

- 无论单需求还是并发需求，每个需求都保留自己的 `change_id`、工作流、需求分支、隔离 worktree、正式材料和 `code_ref`，完成后先归位到一个集线分支，再考虑目标分支或 MR。
- 一个集线分支/worktree 覆盖一次本地交付周期，或一个开放 MR 的整个生命周期。开放 MR 只有一个集线会话独占其源分支；接手前先恢复或明确交接，不能让同一分支同时签出到两个可写 worktree。
- MR 合并/关闭或本地交付完成后结束本周期。下一轮从目标分支最新稳定 SHA 新建，不沿用旧轮次的冻结基线。
- 集线状态只从实际分支、完整 SHA、Git 祖先关系、completed 事件 `code_ref`、MR 状态和当前会话授权恢复。旧授权、分支名称或 SQLite 完成状态都不能代替 Git 证明。

推荐集线分支时优先级为：现有开放 MR 的实际源分支 → 本交付周期已经存在且最近组合验证为绿色的集线分支 → 从目标分支最新稳定 SHA 推荐新的 `codex/hub-<cycle-id>`。名称必须先做只读冲突检查；缺少 target、cycle 或 MR 身份时在候选卡标为“待选择”，不猜测。

## 自动归位与清理候选卡

事件成为 `completed` 后的下一次路由，先做只读发现并自动展示非变更性的**归位与清理候选卡**。展示不是授权；用户催促、“继续”“都处理”“不要再问”、旧对话授权或已完成状态都不能替代针对这张精确卡的当前会话确认。

发现并机械核对：

1. completed 总账中的 `change_id` 与原 `code_ref`；`code_ref` 的 commit 必须存在并属于配置仓库。
2. 需求分支、需求 worktree、完整 HEAD、clean/dirty 与 untracked 状态，以及它们是否仍包含原 `code_ref`。分支已移动不能改写原 code_ref。
3. 推荐集线分支、专属/临时候选 worktree、当前集线 HEAD、最后一个组合验证绿色 SHA 和目标分支/MR 身份。
4. 其他仍在开发或已完成但未处理的并发需求 worktree；只用于隔离检查，不能纳入本次清理范围。

若同一 `change_id` 发现多个候选 worktree 或需求分支，必须全部列出并标为拓扑冲突；用户明确选择精确的需求容器前不得归位或清理，未选择对象始终在本次授权之外。选择只消除本次定位歧义，不代表其余对象可以删除或已被修复。

完整展示：

```text
归位与清理候选卡
change_id：<完成事件>
原 code_ref：<repository@40-char-sha>
需求分支：<branch 或缺失>
需求 worktree：<absolute path 或缺失> | <clean/dirty> | <untracked 摘要>
推荐集线分支：<existing-or-new branch，或待选择>
当前集线 HEAD：<40-char-sha，或尚未创建>
集线最后绿色 SHA：<40-char-sha>
目标分支 / 开放 MR：<实际身份>
拟执行归位：<临时候选 merge、祖先验证、组合验证、原子提升>
拟执行清理：<精确 worktree registration、需求 worktree、已归位本地需求分支；dirty 时不执行>
明确不包含：push、创建/更新 MR、合并 MR、删除远端分支、其他需求 worktree
请选择：仅授权归位 / 授权归位并在成功后执行上述精确清理 / 暂不处理
```

卡片中的任一分支、worktree、code_ref、集线 HEAD、目标或动作范围变化，旧卡与旧授权失效；重新只读发现并展示新卡。卡片缺字段时保持只读并等待选择，不能调用通用 finishing 补猜。

## 当前会话授权

归位授权只覆盖卡片中的一个 `change_id`、原 `code_ref`、配置仓库、候选集线分支和本地验证动作。清理授权只覆盖卡片逐项列出的本地需求 worktree registration、worktree 与需求分支，并以归位成功为前置。两者可以由用户对同一张卡分别或一次明确授权，但候选卡展示本身不等于授权。

本地归位与清理授权不包含 push、创建/更新 MR、合并 MR、删除远端分支。每一类远端写入都需要之后在当前会话展示精确 remote/ref/MR、拟写入 SHA 和结果后，另行明确授权；不得从“更新同一个 MR”或“完成收尾”推导。

## 保留 commit 身份的原子归位

目标是保留原 `code_ref` commit 身份，使它成为集线 HEAD 的祖先。禁止 squash、cherry-pick、patch 重放、rebase 后替代 SHA，或把需求分支当前可变 HEAD 当作 code_ref。

授权后使用临时候选 ref/worktree，不直接在集线绿色 ref 上试合并：

1. 记录并再次核对 `hub_before_green_sha`、原 `code_ref`、目标 ref 和所有卡片字段。集线 ref 已移动或不再绿色时不开始。
2. 从 `hub_before_green_sha` 创建本次专用的临时候选 ref/worktree。在其中执行 `git merge --no-ff <code_ref-sha>`；merge commit 必须实际包含原 commit，而不是重写它。
3. 发生冲突时只在临时候选中 `git merge --abort`；集线 ref 始终停在汇入前最后一个绿色 SHA。报告精确冲突，不修改需求分支/worktree，不清理。行为或兼容性冲突必须建立新的修复事件，不能回写已完成事件。
4. 合并成功后机械证明原 `code_ref` 是候选 HEAD 的祖先，并在该精确候选 commit 上运行卡片列明的组合验证。验证命令、结果和候选 SHA 都必须新鲜。
5. 任一祖先证明或组合验证失败，丢弃/隔离本次临时候选；集线仍在汇入前最后一个绿色 SHA，需求分支/worktree 完整保留，不执行任何清理。展示原因，并允许之后用同 `code_ref` 重新生成卡片和重试。
6. 仅当候选通过，才使用带旧值校验的原子 ref compare-and-swap，把集线分支从 `hub_before_green_sha` 提升到候选 HEAD。若平台或 Git 状态不能保证 compare-and-swap，停止而不提升。并发移动导致 CAS 失败时集线保持实际当前值，重新发现，不能覆盖。
7. 提升后重新解析集线完整 HEAD，再次机械证明 `code_ref` 是集线 HEAD 的祖先且 HEAD 等于已验证候选 SHA。只有两项都通过才报告归位成功；该 HEAD 成为新的“集线最后绿色 SHA”。

临时候选/ref/worktree 只能在卡片已授权范围内创建和回收。异常残留必须明确报告，不能扩大清理到其他 worktree。组合验证失败绝不能先更新集线再 reset；原子候选流程的目的就是让正式集线 ref 未经绿色验证不移动。

## 需求 worktree 与本地分支清理

只有归位成功、祖先证明和组合验证都通过，并且当前卡片已经得到具体清理授权时，才处理这个需求：

1. 对需求 worktree 运行只读状态检查，包含 untracked。任何 dirty/untracked 都阻止清理；完整列出相对路径与状态，等待用户处理。绝不自动 `--force`、reset、stash、删除或把文件移到别处。
2. 再次确认清理目标的 Git common directory 属于配置仓库、路径与卡片完全相同，且不是集线或其他并发需求 worktree。
3. 只移除这个需求的精确 worktree registration 和 worktree；不运行会波及其他登记的宽泛清理，不删除其他并发需求目录。
4. 验证该精确 registration 已消失后，用安全的普通本地分支删除（等价 `git branch -d`）删除已归位的本地需求分支。若 Git 不能证明已合入、分支被其他 worktree 使用或 ref 已移动，停止；禁止强制删除。
5. 清理后再次列出 worktree，证明其他并发需求 worktree 和集线 worktree 未变化。

子需求清理不得影响其他并发需求 worktree。清理成功只回收该需求的本地开发容器，不删除 completed 总账、正式材料、`code_ref` commit、远端分支或 Git 历史。

## 集线对目标分支的交付与最终回收

向目标分支 push、创建/更新 MR 或合并 MR 时，分别展示远端动作卡并取得对应明确授权。开放 MR 更新必须 push 同一实际源分支，不得新建重复 MR；MR 已合并或关闭后不能继续复用旧周期。

最终回收前，必须从当前会话已确认的交付周期范围、completed 总账、集线实际祖先关系和目标分支事实恢复**本轮成员清单（`change_id → code_ref`）**。不得仅凭分支名或“本轮全部”猜成员；无法唯一恢复时，先展示候选成员及证据并等待用户确认。最终清理候选卡必须逐项列出该清单、目标分支对每个原 commit 的祖先证明、组合验证命令/结果/目标 SHA，以及拟清理的精确集线 worktree registration 和本地集线分支。卡片展示不等于授权。

只有以下事实同时满足，才可展示集线 worktree/本地集线分支的最终清理候选：

- 实际最终目标分支包含本轮全部 completed `code_ref`，逐个祖先证明通过；
- 最终目标 SHA 上的组合验证新鲜且通过；
- 开放 MR 已实际合并/关闭，或本地交付完成事实已经明确；
- 集线 worktree clean 且无 untracked；
- 当前会话再次取得针对精确集线 worktree registration 和本地集线分支的清理授权。

任一缺失都保留集线。最终清理仍不删除远端分支，除非用户对远端分支另行明确授权。

## 快速失败边界

| 情况 | 结果 |
|---|---|
| merge 冲突 | 临时候选失败；集线绿色 SHA 不动；需求对象保留 |
| 组合验证失败 | 不提升集线；不清理；允许同 `code_ref` 重试 |
| 集线 ref 并发移动 | CAS 失败；重新生成候选卡，不覆盖 |
| 需求 worktree dirty/untracked | 已归位状态保留，但本地清理停止并列文件 |
| 另一个需求仍开发 | 只列为隔离对象，绝不清理或用作基线 |
| 只有本地授权 | 禁止 push、创建/更新 MR、合并 MR、删除远端分支 |
| 目标未包含全部 code_ref | 保留集线 worktree 与分支 |
