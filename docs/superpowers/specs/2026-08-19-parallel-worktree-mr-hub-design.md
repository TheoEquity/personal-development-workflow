# 并行 Worktree 与持续 MR 集线设计

## 状态

- 日期：2026-08-19
- 状态：用户已批准设计方向，等待书面设计复核
- 适用范围：个人开发工作流

## 背景

同一功能进入 MR 评审后，可能连续发现多个 Bug。用户希望把不同 Bug 分配到不同 Codex 顶层会话和不同 Git Worktree 中并行修复，再由一个专门的集线会话合并到同一个 MR；后续新发现的 Bug 也应继续追加到仍然打开的原 MR，而不是为每个 Bug 建立新的最终 MR。

现有个人工作流已经支持多个不同 `change_id` 各自拥有活动工作流游标，也已经要求开发前从远程分支核对不可变完整 SHA。它缺少的是跨 Bug 并行时的共同基线约定、顶层会话边界，以及持续更新同一 MR 源分支的集线规则。

## 目标

1. 每个 Bug 使用独立 `change_id`、工作流游标、Plan、顶层会话、Worktree 和本地分支。
2. 同一轮并行 Bug 从同一个不可变完整 Git SHA 开始，不能链式基于另一个 Bug Worktree。
3. 一个长期集线分支作为开放 MR 的唯一源分支。
4. 多个 Bug 分支完成后由集线会话统一合入、组合验证并更新同一个 MR。
5. 后续一轮 Bug 以当前 MR 源分支头的完整 SHA 为共同基线，再追加回原 MR。
6. 继续使用现有项目级 SQLite、事件和游标，不新增批次表、字段或阶段。
7. 不修改 Superpowers 原生 Skill。

## 非目标

- 不建立 MR 批次看板或在 SQLite 中复制 GitLab MR 状态。
- 不让 Subagent 代替另一个长期独立 Bug 会话。
- 不允许多个 Worktree 同时签出同一个集线分支。
- 不自动授权 push、创建或更新 MR、合并远端 MR 或清理分支。
- 不把 MR URL、临时 Worktree 路径或分支状态新增为正式材料引用。
- 不修改 `change.md` 的“两次写入”规则。

## 术语

- **Bug 会话**：用户为一个 Bug 单独开启的 Codex 顶层会话，绑定该 Bug 自己的工作流和 Worktree。
- **集线会话**：负责集成已完成 Bug 分支、运行组合验证并维护开放 MR 源分支的顶层会话。
- **集线分支**：开放 MR 的唯一源分支，例如 `mr/fix-batch`；具体名称由用户或仓库约定确定。
- **一轮并行修改**：共享同一冻结基线、可以同时运行的一组 Bug 会话。
- **轮次基线**：本轮所有成员 Plan 与 Worktree 共同使用的完整 Git commit SHA。

## 核心拓扑

第一轮从目标远程分支的最新完整 SHA 开始：

```text
origin/main@S0
├─ Bug A：会话 A / Worktree A / bug/CE-0002 → commit A
└─ Bug B：会话 B / Worktree B / bug/CE-0003 → commit B

集线会话：
S0 + merge(A) + merge(B) → I1
push 集线分支 → 创建 MR !100
```

后续一轮从当前 MR 源分支头开始：

```text
origin/mr/fix-batch@I1
├─ Bug C：会话 C / Worktree C / bug/CE-0004 → commit C
└─ Bug D：会话 D / Worktree D / bug/CE-0005 → commit D

集线会话：
I1 + merge(C) + merge(D) → I2
push 同一集线分支 → MR !100 自动更新
```

不存在以下链式关系：

```text
Worktree A → Worktree B → Worktree C
```

Worktree 的基线始终是一个已经明确记录的 Git commit SHA，而不是另一个 Worktree 的可变目录状态。

## 会话职责

### Bug 会话

每个 Bug 会话必须：

1. 由用户在该顶层会话中明确开启个人工作流并指定自己的 `change_id` 或新 Bug。
2. 只绑定该 Bug 的一个 `workflow_id` 和一个 Worktree。
3. 使用自己的 Spec、Plan、测试稿、代码提交、验收报告和最终逻辑稿。
4. 在 Plan 中记录本轮统一的 `base_remote`、`base_branch` 和 `base_sha`。
5. 开始编码前验证实际 Worktree `HEAD` 精确等于该 `base_sha`。
6. 只形成自己的本地 Bug 分支，不创建另一个最终 MR。
7. 按既有个人工作流完成 TDD、验收和事件完成；其 `code_ref` 保留为该 Bug 已验收的真实代码提交。
8. 把 `change_id`、本地分支、完整提交 SHA 和验证结论作为集线会话的输入。

不同 Bug 之间的并行边界位于顶层会话和 Worktree。单个 Bug 会话内部是否开启 Subagent-Driven Development，仍由该会话原有 SDD 门禁单独询问；肯定答复只覆盖当前 Bug Plan，不能扩展到其他 Bug 会话。

### 集线会话

一个开放 MR 默认保留一个长期集线会话。该会话必须：

1. 独占集线分支及其 Worktree。
2. 从实际 Git 和 MR 状态恢复当前源分支、目标分支与完整头 SHA，不依赖聊天记忆猜测。
3. 只接收用户明确指定、已经完成个人工作流的 Bug 分支。
4. 验证每个输入分支的提交与对应事件 `code_ref` 一致。
5. 从本轮冻结基线开始，按明确顺序合入成员分支。
6. 运行组合验证，确认修复之间没有互相破坏。
7. 在取得当前会话的远程写入授权后，首次创建 MR 或继续 push 同一源分支。

集线会话不是另一个 Bug 的实现者，不替 Bug 会话编写 Spec、Plan 或功能代码。它的正常改动只包括 Git 合并提交和不改变功能语义的集成操作。

如果用户希望使用新的集线会话，旧集线 Worktree 必须先交接、释放集线分支，或把新会话交给同一个永久 Worktree。不能让同一集线分支同时签出在两个 Worktree。

## 基线协议

### 第一轮

1. 集线协调入口对目标远程分支执行一次受限 fetch。
2. 解析最新完整 SHA `S0`。
3. 本轮每个 Bug 的 Plan 都记录相同的目标远程、目标分支和 `base_sha=S0`。
4. 每个 Bug Worktree 都从 `S0` 创建并验证。
5. 本轮完成前，不能把某个 Bug 的提交当成另一个 Bug 的基线。

### 已存在开放 MR 的后续轮次

1. 集线入口 fetch 当前 MR 的源分支。
2. 解析其完整头 SHA，例如 `I1`。
3. 把 `I1` 冻结为新一轮所有 Bug Plan 的共同 `base_sha`。
4. 本轮进行期间不移动或 push 集线分支。
5. 全部准备合入后，集线会话才让集线分支从 `I1` 前进到 `I2`。

### 基线漂移

- Bug 会话编码前发现所选基线分支头已改变时，沿用现有远程漂移门禁：停止编码，最小审查差异并更新受影响的 Plan；不得静默改用新 SHA。
- 集线分支在本轮成员开始后被外部移动时，集线会话停止合并，重新确认新的共同基线和每个成员的适用性。
- 目标分支在并行开发期间移动，不改变正在运行成员的冻结基线。集线会话在 push 或创建 MR 前检查目标分支变化、合并可行性和组合验证，不单独重写某一个成员的基线。

## 分支与合并规则

- Bug 分支建议使用包含 `change_id` 的稳定名称，例如 `bug/CE-0004`。
- 集线分支由用户或项目约定提供，且必须与开放 MR 的实际源分支一致。
- 集线会话默认使用保留提交身份的 merge，而不是把多个 Bug 伪装成一个未关联提交；推荐 `--no-ff`，以便通过祖先关系证明对应 Bug commit 已包含在集线头中。
- 合并前验证输入 commit 存在、分支没有未提交相关改动、事件已经完成且 `code_ref` 一致。
- 合并后验证每个 Bug `code_ref` 的 commit 都是集线头的祖先，并运行组合测试。

## 事件与总账边界

每个 Bug 仍是独立事件：

- 独立 `change_id` 和 `workflow_id`；
- 独立 Spec、Plan、测试稿、验收报告和最终逻辑稿；
- 独立不可变 `code_ref`；
- 独立完成和关闭。

集线不产生新的 `change_id`，也不修改已经完成的事件。Git 分支、commit 祖先关系和 GitLab MR 已经持久化集线状态，项目 SQLite 不重复保存以下信息：

- 集线分支头；
- MR URL 或状态；
- 临时 Worktree 路径；
- Bug 分支到 MR 的成员关系。

因此本设计不新增 SQLite 表、字段、阶段或正式材料类型。恢复集线时，用户提供或集线会话读取实际 MR，随后用 Git 和当前事件引用机械核对输入。

## MR 生命周期

### 首次创建

1. 集线会话合入首轮已完成 Bug 分支。
2. 组合验证通过。
3. 用户明确授权 push 和创建 MR。
4. push 集线分支并创建以该分支为源的 MR。

### 更新原 MR

当 MR 仍然打开时：

1. 后续 Bug 从当前 MR 源分支完整头 SHA 开始。
2. Bug 事件独立完成。
3. 集线会话恢复原集线分支并合入新 Bug。
4. 组合验证通过。
5. 用户明确授权更新。
6. push 同一源分支；不得新建重复 MR。

### MR 已关闭或合并

原 MR 已合并或关闭时不能继续追加。新的 Bug 轮次必须从最新目标远程分支建立新的集线分支，并在授权后创建新的 MR。

如果有人已经为 Bug 分支单独创建了 MR，不能把 MR 对象本身“拼接”进集线 MR。集线会话只能合入该 MR 源分支的实际 commit；是否关闭多余 MR 是另一个需要明确授权的远程动作。

## 冲突与失败处理

- **干净合并且组合验证通过**：允许进入 push/MR 授权门。
- **Git 冲突**：停止自动集成。不得在没有相应正式材料和授权时顺手重写功能代码。
- **冲突只涉及可证明的机械合并**：先展示精确冲突和拟处理范围，取得明确授权后才能形成集成提交。
- **冲突涉及行为、方案或兼容性判断**：为该集成问题建立新的 Bug/变更事件，基于当前集线分支走 Spec、Plan、TDD 和验收；已完成事件保持不可变。
- **组合测试失败**：不修改旧验收结论；登记新的修复事件，基于当前集线状态修复后再追加到同一个开放 MR。
- **输入分支或 SHA 无法证明**：停止，不猜测 Worktree、旧聊天或分支名。
- **集线分支被另一 Worktree 占用**：恢复原集线会话、执行 Handoff 或释放旧 Worktree，不能强制绕过 Git 的分支占用保护。

## 权限边界

- Bug 会话的编码和本地 commit 授权不授予集线操作。
- Bug 事件完成不授权 push、创建/更新 MR、远端合并或清理。
- 集线会话中的本地 merge commit、push、首次创建 MR、更新 MR、关闭重复 MR和远端合并分别服从现有执行合同与 finishing 授权。
- 新会话不能从旧会话、SQLite、Plan、分支存在或 MR 状态恢复远程写入授权。

## Skill 变更范围

实现只修改个人工作流拥有的文件：

1. `skills/using-personal-development-workflow/SKILL.md`
   - 增加跨 Bug 顶层会话并行规则；
   - 增加共同基线和轮次冻结规则；
   - 增加长期 MR 集线会话、源分支更新和冲突停止规则；
   - 澄清跨 Bug 并行不由 Subagent 承担，单 Bug 内部 SDD 门禁保持不变。
2. `skills/using-personal-development-workflow/tests/test_workflow_integration_contract.py`
   - 增加上述文字合同的自动测试。
3. 安装后同步该个人 Skill 的运行时副本。

不修改：

- `managing-change-ledger` 的 SQLite schema 或脚本；
- `change.md`、Spec、Plan、测试稿和最终逻辑稿格式；
- Superpowers 原生 `using-git-worktrees`、`subagent-driven-development`、`finishing-a-development-branch` 或其他原生 Skill；
- 其他个人 Skill。

## 验证策略

合同测试必须证明个人工作流明确要求：

1. 每个并行 Bug 使用独立顶层会话、事件、Worktree 和分支。
2. 同一轮所有 Bug 使用同一个完整基线 SHA。
3. 不允许 Worktree 链式作为基线。
4. 开放 MR 的后续轮次使用 MR 源分支头作为基线。
5. 集线分支在一轮期间冻结，并由一个集线会话独占。
6. Bug 会话不自行创建最终 MR。
7. 原 MR 打开时只更新同一源分支。
8. MR 已关闭或合并时才创建新的集线分支和 MR。
9. 组合验证、祖先关系和冲突停止规则存在。
10. 没有新增 SQLite 批次表、字段或阶段。
11. Superpowers 原生依赖保持只读。

## 完成判定

本设计完成后，用户可以：

1. 从一个冻结完整 SHA 同时启动多个 Bug 顶层会话和 Worktree；
2. 让每个 Bug 独立走完个人工作流；
3. 在长期集线会话中把它们合到同一 MR；
4. 以后从该 MR 源分支的新头启动下一轮并行 Bug；
5. 把新 Bug 继续追加到仍然打开的同一 MR；
6. 全程不增加数据库批次状态，也不修改 Superpowers 原生文件。
