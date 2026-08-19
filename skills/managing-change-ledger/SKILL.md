---
name: managing-change-ledger
description: Use when a requirement or bug must be registered, formal-material Git references change, a change ledger must be queried or completed, or a personal-workflow cursor must be created, read, advanced, bound, or closed in local SQLite.
---

# 管理变更事件与总账

## 核心原则

以变更事件为中心管理开发链路。一个 `in_progress` 事件包含该需求从规划、实现、内部验收到修正后的完整开发循环；内部 TDD 或内部验收失败不是新的变更事件。Markdown 与本地 Git 保存内容和全部历史；SQLite 保存每条变更当前采用的六类材料引用，以及个人工作流当前阶段的可变游标，不复制正文、不维护第二套版本历史。

`change.md` 严格只写两次：第一次是事件登记，第二次是事件完成。Spec、Plan、测试稿、代码和验收证据在中间阶段产生新版本时只更新 SQLite 当前引用；中间阶段不得编辑 `change.md`，中间阶段不得更新 `change_ref`。

只使用 `scripts/change_ledger.py` 操作数据库，不让用户手写 SQL。只提交本地 Spec Vault；除非用户明确授权，不推送远端、不操作真实 GitLab。

## 管理边界

`change_ledger` 只关联以下六类正式材料：

| 材料 | 保存位置 | 总账引用 |
|---|---|---|
| Spec | Spec Vault Markdown + 本地 Git | `spec_ref` |
| 变更事件 | Spec Vault `change.md` + 本地 Git | `change_ref` |
| Plan | Spec Vault Markdown + 本地 Git | `plan_ref` |
| 测试稿 | Spec Vault Markdown + 本地 Git | `test_ref` |
| 代码 | 真实代码仓库 | `code_ref` |
| 测试证据（验收报告） | Spec Vault Markdown + 本地 Git | `evidence_ref` |

验收全部通过后还形成 `logic/<change_id>.md` 最终逻辑稿。它是完成版 `change.md` 的伴随文档，由最终 `change_ref` 的同一 Git commit SHA 锁定，不增加 `logic_ref`，也不改变上述六类总账引用。讨论稿不属于规划或实现输入，不写入总账。Plan 是经过评审后实际采用并落盘维护的正式材料；评审过程或评审回复本身不新增材料类型。不要创建 `code.md`；代码只用真实仓库提交定位。`workflow_state` 是运行游标，不是第七类正式材料，不进入 Spec Vault Git，也不替代任何正式引用。

每个 `change_id` 只维护一份当前采用的正式 Plan 和一个 `plan_ref`；该 Plan 对应绑定该事件的个人工作流任务，并可在文档内部包含多个实现 `Task N`。实现 Task 不是总账身份，不产生独立的 `change_id`、`workflow_id` 或 `plan_ref`。分模块、并行执行、分别验证或逐 Task review 都仍属于同一事件。需要重新规划时，重新规划仍写入 `plans/<change_id>.md`，提交新版本并用新的完整 Git SHA 替换当前 `plan_ref`，不创建 Task 专属 Plan 路径。

引用格式与 Vault 材料角色固定为：

- `spec_ref`：`specs/<change_id>.md@<full-vault-commit-sha>`
- `change_ref`：`changes/<change_id>/change.md@<full-vault-commit-sha>`
- `plan_ref`：`plans/<change_id>.md@<full-vault-commit-sha>`
- `test_ref`：`tests/<change_id>.md@<full-vault-commit-sha>`
- `evidence_ref`：`acceptance/<change_id>/<run>.md@<full-vault-commit-sha>`
- `code_ref`：`<repository>@<full-code-commit-sha>`

最终逻辑稿没有独立数据库字段；完成后其派生定位固定为 `logic/<change_id>.md@<final-change-ref-sha>`。脚本从最终 `change_ref` 解析 SHA，再读取同一 commit tree 中的 canonical 文件。

SHA 必须是 Git 返回的完整、精确 commit object ID（当前常见 SHA-1 为 40 位，SHA-256 仓库为 64 位）；即使 Git 可以解析，7 位或其他缩写也不是正式引用。只有内容已经包含在所引用的 Git commit 中，且路径符合字段角色时，引用才有效：Vault 引用的 commit 必须包含该 Markdown 的对应版本；代码引用的 commit 必须包含准备验收或已经验收的测试与生产代码。未提交工作区、暂存区、笼统的“当前代码”或仍指向旧内容的 `HEAD` 都不能充当正式引用。仓库存在无关的用户改动不自动使引用失效，但必须通过只读检查确认本次变更相关文件没有遗漏在该 commit 之外；无法证明时停止更新引用。

SQLite 固定包含两张用途分离的表。`change_ledger` 保留以下八个字段：

| 字段 | 规则 |
|---|---|
| `change_id` | 主键，格式 `CE-0001` |
| `spec_ref` | 新需求登记时可空，完成时必填 |
| `change_ref` | 始终必填；进行中固定为登记版本，完成事务中替换为最终版本 |
| `plan_ref` | 进行中可空，完成时必填 |
| `test_ref` | 进行中可空，完成时必填 |
| `code_ref` | 进行中可空，完成时必填 |
| `evidence_ref` | 进行中可指向最近报告，完成时必须指向最终通过报告 |
| `status` | 只能是 `in_progress` 或 `completed` |

`workflow_state` 只保留四个字段：

| 字段 | 规则 |
|---|---|
| `workflow_id` | 主键，格式 `WF-0001` |
| `change_id` | 需求讨论期间可空；事件登记后绑定一条 `in_progress` 变更且不可改绑 |
| `current_stage` | 当前可恢复阶段；允许为内部返工向前回退，不表达状态转移矩阵 |
| `state` | 只能是 `active` 或 `closed` |

`current_stage` 的合法值固定为：`requirement_discussion`、`research`、`prototype`、`register_change`、`writing_spec`、`writing_plan`、`tdd_coding`、`writing_test`、`acceptance`、`completed`。`completed` 只由关闭命令写入。`writing_test` 仅为已有游标和旧回环兼容；新流程的初始测试稿在 `writing_spec` 子流程生成，编码完成后从 `tdd_coding` 直接进入 `acceptance`。

不要增加需求表、材料表、revision 表、baseline 表、时间字段、分类字段或数据库内的历史版本。旧引用由本地 Git 历史找回，不在 SQLite 中另存。不要把当前对话是否已激活、等待用户确认、TDD 的 RED/GREEN 子步骤或未提交文件状态写进 `workflow_state`。

## 事件边界与变更分类

以下输入必须建立新的变更事件：

- 新需求；
- 来自外部用户、客户、独立测试方、生产使用或已交付功能的 Bug 反馈；
- 已完成事件之后出现的需求变化或 Bug 反馈。

当前 `in_progress` 事件的 TDD 失败、开发者自测失败和内部验收失败留在原事件中处理。保留失败验收报告及日志证据，更新原事件的当前引用，并在同一事件内回到 Spec、Plan、代码或测试稿；不为失败项或内部发现的代码问题创建新事件。

需要建立事件时，分类必须明确选择以下一种，不使用“未知”“待定”或“暂时无法判断”：

| 分类 | 判断标准 | Spec 处理 |
|---|---|---|
| `新需求` | 正常进入、尚不依附现有 Spec 的需求 | 新建或补充 Spec |
| `实现 Bug` | Spec 契约正确，实际代码没有按契约表现 | Spec 正文不改，但事件必须关联发现时的 Spec 版本 |
| `Spec 功能缺陷` | 当前功能本应覆盖该行为，但 Spec 的行为契约缺失或错误 | 修改当前 Spec，并产生新 Spec Git 版本 |
| `关联新需求` | 新行为扩展现有 Spec 的范围，不属于原功能缺陷 | 建立关联的新需求或新 Spec，不把扩展伪装成 Bug |

外部反馈即使发生时另有事件正在开发，也单独建立事件。判断依据是反馈来源，不是当前是否恰好存在 `in_progress` 行。

## 工作流程

### 定位配置、Spec Vault 与数据库

总控或独立调用方必须从当前工作目录向上定位最近的项目配置，并把其绝对路径作为 `--config <project-config>` 显式传给每个访问项目数据的命令。找不到当前项目配置时停止，不猜测其他配置或材料仓库：

```json
{
  "spec_vault": "<absolute-spec-vault-path>",
  "database": "<absolute-spec-vault-path>/.local/personal-workflow.sqlite3",
  "repositories": {
    "<repository-name>": "<absolute-repository-root>"
  }
}
```

`spec_vault` 和 `database` 必须是已确认的绝对路径。`.local/` 必须加入 Spec Vault 的 `.gitignore`；SQLite 文件不得提交到 Git。`repositories` 把稳定仓库名映射为已确认的非 bare Git worktree 精确顶层（通常是主 checkout）；稳定仓库名只能使用字母、数字、点、下划线和连字符，且必须以字母或数字开头，不能把绝对路径伪装成名字。`resolve-code-ref --worktree` 与 `set-code-ref --worktree` 通过 Git common directory 将实际 linked worktree 反向匹配到唯一稳定名。配置不存在、字段为空、含占位符、路径无法确认、Vault 不是 Git 根目录、`.local/` 未被 Git 实际忽略或已经被跟踪时停止，不生成带占位符的真实配置，也不猜测另建 Vault。

路径确认后，统一通过当前项目配置调用脚本：

```powershell
python <skill-directory>/scripts/change_ledger.py `
  --config <project-config> init
```

除不读取项目数据的 `plan-adoption-contract` 外，省略 `--config` 的项目命令必须失败。直接 `--db <absolute-path>` 只保留给初始化、迁移、测试或已明确路径的维护操作，不能作为个人工作流的项目发现机制。

`init` 创建 `change_ledger` 与 `workflow_state`。再次运行时保留既有行；旧数据库的 `implementation_ref` 无损迁移为 `plan_ref`，旧游标的 `writing_implementation` 迁移为 `writing_plan`，旧的一表数据库则补建工作流表。迁移拒绝缺少任一最终引用的 `completed` 行、绑定 `completed` 事件的活动游标，以及绑定 `in_progress` 事件的关闭游标；不能把历史矛盾固化进 canonical 表。不得读取讨论稿作为规划或实现依据。

### 管理工作流游标

用户在已激活的个人工作流中开始新需求讨论、且没有可恢复游标时，创建游标：

```powershell
python <skill-directory>/scripts/change_ledger.py --config <config-path> workflow-create
```

需求讨论完成后，把阶段更新为 `register_change`。事件创建成功后绑定一次 `change_id`，再进入 `writing_spec`：

```powershell
python <skill-directory>/scripts/change_ledger.py --config <config-path> `
  workflow-set-stage WF-0001 --stage register_change
python <skill-directory>/scripts/change_ledger.py --config <config-path> `
  workflow-bind-change WF-0001 CE-0001
```

`workflow-bind-change` 原子写入 `change_id` 并把阶段设为 `writing_spec`，不得留下“已绑定但仍处于事件前阶段”的中间状态。重复绑定同一事件是幂等操作；改绑其他事件失败。

每个阶段只有在对应阶段 Skill 的门禁满足、正式写入或结果已经发生后才移动游标。等待确认、被阻塞或尚未执行时保持原阶段。内部验收失败时先保存失败报告并更新 `evidence_ref`，再把 `current_stage` 直接设为拥有问题的阶段；允许回退，不建立状态转移矩阵。

向后回退到任意较早责任阶段始终允许。只有向前进入目标阶段时检查该阶段的最低正式材料：`writing_plan` 需要 `spec_ref`、`test_ref`；`tdd_coding` 需要 `spec_ref`、`plan_ref`、`test_ref`；兼容阶段 `writing_test` 需要 `spec_ref`、`plan_ref`、`code_ref`；`acceptance` 需要 `spec_ref`、`plan_ref`、`test_ref`、`code_ref`。检查引用非空、完整 SHA、Git 对象、Vault canonical 路径和正式结构；测试稿缺失时不得进入 Plan。

每次向前进入 `writing_plan` 时，脚本还从不可变 `spec_ref` 读取 `## 既有功能与流程影响`。该章节必须是 `writing-specs` 定义的六列表格，或唯一的无直接影响结论；重复/非法 `impact_id`、未知枚举、无影响结论与表格并存，以及没有写入规范性规则的“明确改变”都拒绝推进。此门只约束新的前向动作，不把新格式塞进历史材料共用的基础结构校验。

新建并绑定事件的游标只能从 `writing_spec` 开始。普通 `workflow-set-stage` 不得进入 `tdd_coding`，也不得从更早阶段跳过它进入后续阶段；Plan adoption 边界只能由下面的原子 `adopt-plan` 跨越。回退到 `writing_plan` 后也必须重新评审并再次调用 `adopt-plan`，不能用旧证明直接跳回编码。

不要把 Plan adoption 拆成 `set-ref` 和 `workflow-set-stage`。先从脚本读取唯一机器合同；合同 JSON 定义参数、前置条件和原子写入集合，本 Skill 不复制这些易漂移的字段定义：

```powershell
python <skill-directory>/scripts/change_ledger.py plan-adoption-contract
```

评审通过且候选 Plan 已形成不可变正式引用后，在仍处于 `writing_plan` 时一次执行：

```powershell
python <skill-directory>/scripts/change_ledger.py --config <config-path> adopt-plan CE-0001 `
  --workflow-id WF-0001 `
  --plan-ref plans/CE-0001.md@<full-vault-commit-sha>
```

每次新的 `adopt-plan` 还要求候选 Plan 包含 `## 实现兼容性分析`。脚本在同一事务内读取不可变 Spec 与候选 Plan，要求全部 Spec `impact_id` 至少覆盖一次，只允许 Spec ID 或 `implementation-only` 来源；`无影响` 必须给出具体代码证据并写 `无需任务`，`需要适配` 或 `需要迁移` 必须给出处理方式并绑定候选 Plan 中真实存在、从 1 开始且无前导零、编号唯一的 `Task N`。Spec 标为 `明确改变` 的影响项至少要有一行 `需要适配` 或 `需要迁移`，不能只映射为 `无影响`；未知状态、未知 Spec ID、非法/重复 Task 编号或 `阻塞` 一律拒绝。Spec 使用无直接影响结论时，Plan 仍须给出至少一条 `implementation-only` 分析，或唯一的 ``- 无交点代码证据：<Spec 代码基线> | `<路径或符号>` | <具体理由>``；基线必须与该 Spec 的代码基线完全一致。

Plan adoption 不创建或修改 `change.md`，也不更新 `change_ref`。`adopt-plan` 直接从不可变 `spec_ref` 和候选 `plan_ref` 机械验证正式结构、影响覆盖、完整 SHA、角色路径、代码基线、Plan 目标位置和适用 AGENTS 清单；全部通过后在一个 `BEGIN IMMEDIATE` 事务内只原子更新 `plan_ref` 和工作流的 `tdd_coding` 阶段。任何影响合同或 adoption 校验失败都保持事务无写入；对同一已采纳 Plan 的重复或并发调用幂等。

新影响合同不追溯阻断已经采用旧 Plan、并已进入 `tdd_coding` 或 `acceptance` 的事件；它们可以继续原有验收和完成门。旧事件一旦回到 `writing_spec` 向前进入 Plan，或回到 `writing_plan` 重新采用 Plan，就必须满足当前合同。对已采用引用的精确幂等 `adopt-plan` 重试不重新要求历史文档补格式。

查询游标或连同已绑定总账行查询：

```powershell
python <skill-directory>/scripts/change_ledger.py --config <config-path> workflow-list --state active
python <skill-directory>/scripts/change_ledger.py --config <config-path> workflow-show WF-0001
python <skill-directory>/scripts/change_ledger.py --config <config-path> workflow-status WF-0001
```

只有绑定的变更已经 `completed` 时才运行 `workflow-close`。它原子写入 `current_stage=completed`、`state=closed`；关闭后的游标不可修改。用户仅说“关闭个人工作流”只关闭当前对话的路由，不调用此命令。

### 登记变更事件

这是 `change.md` 的第一次：事件登记。该版本固定记录需求或 Bug 背景、分类与理由、影响范围、Spec 处理和用户确认结论，并使用 `status: in_progress`。用户确认并提交后，进入完成边界以前不再编辑。

总控运行 `next-id` 请求下一个编号，并把返回的唯一 `change_id` 提供给全部子 Skill。脚本负责机械分配和查重；子 Skill 不得自行生成或更换材料身份：

```powershell
python <skill-directory>/scripts/change_ledger.py --config <config-path> next-id
```

根据已知事实完成分类、Spec 处理和影响范围，生成 `changes/<change_id>/change.md`。随后同一身份机械决定 `specs/<change_id>.md`、`plans/<change_id>.md`、`tests/<change_id>.md`、`acceptance/<change_id>/<run>.md` 和验收通过后使用的 `logic/<change_id>.md`。先在对话框完整展示拟落稿内容，用户确认后再保存和提交。

```markdown
---
change_id: CE-0001
classification: 新需求
status: in_progress
created_at: 2026-08-17T14:30:00Z
discovery_spec: null
---

# CE-0001 变更事件

## 现象与背景

[需求或 Bug 的可验证事实]

## 分类理由

[为什么属于四种分类中的这一种]

## Spec 处理

- 处理：新建 / 修改 / 不修改
- 说明：[具体原因]

## 影响范围

[受影响的功能、模块、共享资源和相邻流程]

## 当前结论

[当前已确定的处理结论]
```

不要另加 `Unconfirmed Items`、`Failure and Recovery`、`Acceptance Links`、`Current Implementation Gap` 或状态转移矩阵。

用户确认后保存 `change.md`，提交到本地 Spec Vault，取得 Vault Git SHA，再创建总账行：

```powershell
python <skill-directory>/scripts/change_ledger.py --config <config-path> create `
  --change-id CE-0001 `
  --change-ref changes/CE-0001/change.md@<full-vault-commit-sha>
```

登记新事件时 `spec_ref` 可以暂时为空。即使 Bug 来自已有 Spec，也不得把其他事件的 Spec 路径塞入当前事件；进入 `writing_spec` 后，由总控提供当前 `change_id`，将确认后的行为契约保存为 `specs/<change_id>.md`，再写入对应 `spec_ref`。

### 维护当前材料引用

每当 Spec、Plan、测试稿或验收报告产生已提交的新版本，验证 SHA 确实存在，再只更新 SQLite 中对应的当前引用。Vault 普通引用继续使用 `set-ref`；`code_ref` 只能使用后面的原子 `set-code-ref --worktree`，不得通过通用 `set-ref` 写入。`set-ref --field change_ref` 必须拒绝；`change_ref` 只能由 `create` 写入登记版本，再由 `complete --change-ref` 原子替换为最终版本。

```powershell
python <skill-directory>/scripts/change_ledger.py --config <config-path> set-ref CE-0001 `
  --field test_ref `
  --value tests/CE-0001.md@<full-vault-commit-sha>
```

运行 `set-ref` 前先确认 Vault 引用资格：解析目标 SHA，确认路径由同一 `change_id` 机械生成且本次内容存在于该 commit。写 `code_ref` 前确认本次变更相关测试和生产代码均已进入实际 worktree 的当前 `HEAD`，且没有会改变受测行为的未提交相关改动。需要创建本地 commit 但尚未获得相应 Git 授权时，保持原引用和 `in_progress` 状态并停止；不得把主 checkout、旧 `HEAD`、绝对仓库路径或手工猜测的仓库名写成新代码引用。本地 commit 不授权 push、创建 MR 或合并。

从实际 Git worktree 原子派生并写入正式引用：

```powershell
python <skill-directory>/scripts/change_ledger.py --config <config-path> set-code-ref CE-0001 `
  --worktree <absolute-worktree-root>
```

命令要求输入 worktree 根目录，通过 Git common directory 与配置中的仓库映射唯一匹配，读取该 worktree 的完整 `HEAD`，并在同一 SQLite 事务中写入 `code_ref=<repository>@<full-sha>`；存在活动游标时只允许在 `tdd_coding` 阶段写入。事务提交前脚本再次读取 `HEAD`，发生变化就回滚，但这不是跨 Git 与 SQLite 的全局锁。返回值同时包含 worktree、分支或 detached、dirty 等核对上下文；这些上下文不进入正式 `code_ref`，dirty 也不能一刀切拒绝，因为它可能来自无关用户改动，调用方仍必须只读确认本次变更相关文件没有遗漏在该 commit 外。`resolve-code-ref --worktree` 仅保留为不写总账的只读预览；未配置仓库、非法稳定名、绝对路径 locator 或同一 Git common directory 的重复稳定名都必须拒绝。

绑定活动工作流时，只在 `writing_spec` 直接更新 `spec_ref`，并在同一阶段由 `writing-specs` 的测试稿子节点更新初始 `test_ref`；两者都必须存在且 Spec 影响合同有效才能进入 `writing_plan`。候选 Plan 草稿只在 Spec Vault Git 中形成不可变候选引用；活动工作流的 `plan_ref` 只能由 `adopt-plan` 原子写入，任何阶段都不得用普通 `set-ref` 替换。工作流已经进入 `tdd_coding` 或更后阶段后若 Spec 或 Plan 变化，先显式回到各自责任阶段，Plan 重新评审、补齐实现兼容性分析后再通过 `adopt-plan` 正式采用。没有绑定活动工作流的普通总账事件保留普通材料的 `set-ref` 能力，但它不能据此绕过个人工作流的 adoption 边界，也不能改 `change_ref`。

设置 `evidence_ref` 前，总账必须已有当前 `test_ref` 与 `code_ref`。脚本从对应不可变 Git blob 读取测试稿和报告，直接调用 `writing-test-drafts/scripts/acceptance_report.py` 的唯一 validator；本 Skill 和总账脚本不复制报告字段、Markdown grammar、状态推导或失败回传表。validator 无效时事务不写入；有效时 `set-ref` 的 JSON 同时返回其规范化结果，供路由器消费。

内部验收失败时保留失败报告，可让 `evidence_ref` 指向最近一次已经通过上述 validator 的报告，但状态保持 `in_progress`。根据规范化失败事实回到对应阶段修正；不创建新事件。修复后重新运行适用的测试稿并生成新的验收报告，不覆盖旧报告。

### 完成变更

这是 `change.md` 的第二次：事件完成。验收报告通过唯一 validator 后，先由 `writing-final-logic-drafts` 根据当前不可变 Spec、Plan、代码和验收事实形成 `logic/<change_id>.md`，完整展示并取得用户确认。逻辑稿必须使用精确 `# <change_id> 最终逻辑稿`、一个有具体内容的 `## 功能逻辑`，以及至多一个有具体内容的可选 `## 注意事项`；不得用一句空泛总结、代码导读或测试证据替代。

逻辑稿确认后，基于 SQLite 中已经确定的五类当前材料引用生成最终 `change.md`，写入 `status: completed`、最终 `spec_ref`、`plan_ref`、`test_ref`、`code_ref`、`evidence_ref`、一个 `## 最终逻辑稿` 章节及唯一 `- logic/<change_id>.md`，以及最终结论。提交后的最终 `change_ref` 必须指向同时包含两份 canonical 文件的 commit tree。

验收报告的唯一文本和可执行合同由 `writing-test-drafts` 定义，本 Skill 不复制其字段或 grammar。`complete` 再次调用同一个 validator，并以 `require_passed` 门检查所引用的测试稿、最终报告和当前总账期望绑定；只有其规范化结果为全部通过才继续。旧测试稿报告、空壳、无效状态和代码块伪字段均不能完成。

`complete` 同时按 `writing-specs` 与 `writing-plans` 的正式结构拒绝 Spec/Plan 空壳，并重新验证正式引用、Spec 代码基线、Plan 目标路径和适用 AGENTS 清单；它不依赖中间版 `change.md` 或 adoption 历史。没有绑定活动工作流时，完成门重新校验 Spec 与 Plan 的实现兼容性覆盖，防止普通总账事件通过 `set-ref plan_ref` 绕过 `adopt-plan`；已有活动工作流的当前事件依赖 `adopt-plan` 门，已进入后续阶段的 legacy 事件保留不追溯兼容。

该脚本只机械证明已提交报告、证据结构及引用绑定满足合同，不声称能从 Markdown 独立证明现实操作确已发生；实际执行义务仍由 `writing-test-drafts` 和可信 runner/controller 履行。

最终 `change.md` frontmatter 把 `change_id`、`status: completed` 和 `spec_ref`、`plan_ref`、`test_ref`、`code_ref`、`evidence_ref` 写成总账的逐字值并提交；`change_ref` 由其自身的 canonical 路径与完整 commit SHA 机械证明，不能在同一次 Git 提交内容中自引用尚未产生的 commit SHA。对于 `in_progress` 事件，`complete` 必须接收这个最终 `change_ref`，从候选提交加载最终文档并校验身份、其余五类引用和 canonical 逻辑稿，再在同一事务中同时写入最终 `change_ref` 和 `status=completed`。逻辑稿正文与路径不写入 SQLite；`complete` 只从最终提交派生并验证。

完成前逐项检查：

- 六个引用全部存在且格式有效；
- 引用使用 Git 返回的完整 SHA 且精确解析为该 commit；
- 每个 Vault 引用的目标文件版本确实包含在对应 commit 中；
- 本次变更相关代码没有未纳入 `code_ref` 的工作区或暂存区改动；
- 最终验收报告总体结论为“通过”，测试稿的每个关键步骤均有通过结果；
- 验收报告通过 `writing-test-drafts` 唯一 validator 的期望绑定与 `require_passed` 校验；
- Spec、Plan、代码基线、目标路径与适用 AGENTS 清单通过上述结构和绑定校验；
- `logic/<change_id>.md` 已由用户确认，含正确身份、具体的 `## 功能逻辑` 和至多一个可选 `## 注意事项`；
- `change.md` 已更新为同一 `change_id`、`status: completed`、与总账逐字一致的其余五类最终引用，以及唯一的 canonical 最终逻辑稿路径；
- 最终提交 tree 同时包含完成版 `change.md` 和该逻辑稿；SQLite 继续只有既有字段；
- 最终候选 `change_ref` 指向该提交；完成事务成功前，总账仍保持登记版本；
- 若存在绑定该事件的活动工作流，其 `current_stage` 必须已经是 `acceptance`；没有绑定工作流的普通总账事件可直接完成。

如果任一条件不满足，保持 `in_progress` 并处理对应缺口；满足后运行：

```powershell
python <skill-directory>/scripts/change_ledger.py --config <config-path> `
  complete CE-0001 --change-ref changes/CE-0001/change.md@<full-vault-commit-sha>
```

完成行不可再改；对已完成行重复运行 `complete CE-0001` 是幂等查询，不重开门禁。已完成时若仍提供 `--change-ref`，它必须与总账已存最终值逐字一致。若该事件绑定了活动工作流，必须先在 `acceptance` 完成事件，再运行 `workflow-close <workflow_id>` 关闭游标，顺序不可颠倒。完成后的外部 Bug 反馈或需求变化必须新建变更事件，并关联发现时采用的 Spec 版本。

## 查询与日志

查询单条总账：

```powershell
python <skill-directory>/scripts/change_ledger.py --config <config-path> show CE-0001
```

查询全部、正在维护或已完成的事件：

```powershell
python <skill-directory>/scripts/change_ledger.py --config <config-path> list
python <skill-directory>/scripts/change_ledger.py --config <config-path> list --status in_progress
python <skill-directory>/scripts/change_ledger.py --config <config-path> list --status completed
```

`list` 只读返回按 `change_id` 排序的 JSON 数组。每行保留八个既有字段；调用方根据 `status` 和六类引用是否为空判断哪些事件正在维护、哪些已经完成以及当前材料缺口。`workflow-list` 返回工作流游标，`workflow-status` 一次返回游标和它绑定的总账行。阶段以 `workflow_state.current_stage` 为主，并用正式引用、失败报告和代码事实校验；两者冲突时停止，不静默改写任一方。

脚本把机器可读 JSON 输出到标准输出，把普通操作日志输出到标准错误。日志时间统一使用 UTC、精确到秒：

```text
[2026-08-17T14:30:00Z] action=set-ref change_id=CE-0001 status=in_progress
```

## 常见错误

| 错误 | 修正 |
|---|---|
| 为追踪历史再建 revision/baseline 表 | 只覆盖当前引用；从本地 Git 取历史 |
| 只看六类引用猜测精确工作阶段 | 读取 `workflow_state`，再用正式材料校验游标 |
| 把 `workflow_state` 当第七类正式材料 | 它只保存运行游标，不进入 Git 或总账引用 |
| 用户关闭当前对话路由时关闭持久游标 | 只在绑定事件已经完成后运行 `workflow-close` |
| 把分类、正文、diff 或测试步骤写进 SQLite | 放回对应 Markdown |
| 每个阶段都重写 `change.md` 并推进 `change_ref` | 中间只更新 SQLite 材料引用；事件文档只在登记和完成时写 |
| 为 Plan adoption 追加一个中间 `change.md` | 直接调用 `adopt-plan` 校验不可变 Spec/Plan，保持登记 `change_ref` 不变 |
| 为 Plan 内每个实现 Task 新建 Plan、游标或事件 | Task 只在同一 `plans/<change_id>.md` 内拆分；总账继续维护该事件唯一的当前 `plan_ref` |
| 为当前事件的 TDD 或内部验收失败新建 Bug 事件 | 保留失败报告，在同一 `in_progress` 事件内修正并重新验收 |
| 把外部 Bug 反馈塞回已完成事件 | 新建事件，关联反馈发生时采用的 Spec 版本 |
| 普通代码 Bug 也频繁修改 Spec | 保留事件记录和发现时 Spec 引用，Spec 正文不改 |
| Spec 功能缺陷只改代码 | 同时修改当前 Spec 并更新 `spec_ref` |
| 用失败或旧验收报告完成事件 | 更新为同一 `code_ref` 的最终通过报告 |
| 验收通过后直接完成，或把一句总结当逻辑稿 | 先用 `writing-final-logic-drafts` 形成并确认 `logic/<change_id>.md`，再让最终提交同时包含它和完成版 `change.md` |
| 为最终逻辑稿新增数据库字段或阶段 | 从最终 `change_ref` 的 SHA 派生版本；不增加 `logic_ref` 或 SQLite 阶段 |
| 用旧 `HEAD` 引用尚未提交的新材料或代码 | 先形成包含实际内容的本地 commit，再更新引用 |
| 因仓库存在任意脏文件就阻塞 | 只读识别本次变更相关文件；无关用户改动保持不动 |
| 在相关代码仍有未提交改动时开始正式验收 | 重新验证并形成新的本地代码 commit，再用其 SHA 验收 |
| 修改已完成总账行 | 创建新的变更事件 |
| 把讨论稿加入规划、实现输入或总账 | 排除讨论稿，只使用确认后的正式材料 |

## 停止信号

出现以下任一情况时停止当前操作，回到对应处理项修正：

- 正准备新增已定义的两张表之外的表、额外字段、状态或数据库内的历史版本；
- 正准备在配置路径缺失或未确认时猜测创建 SQLite；
- 正准备把工作流改绑到另一个事件，或在绑定事件未完成时关闭游标；
- 正准备在登记与完成之间编辑 `change.md`，或用 `set-ref` 更新 `change_ref`；
- 正准备在没有最终通过报告或 `code_ref` 不一致时标记完成；
- 正准备在没有用户确认的 canonical 最终逻辑稿，或最终 `change_ref` 提交不包含该文件时标记完成；
- 正准备改写已完成行、覆盖旧验收报告或把讨论稿作为规划、实现输入；
- 正准备为当前 `in_progress` 事件的内部开发或验收失败创建新事件；
- 无法证明某个引用的 Git SHA 真实存在。
- 无法证明目标 commit 包含被引用的材料内容或实际受测代码；
- 本次变更相关文件仍有未纳入 `code_ref` 的改动。
## 可靠性门禁

脚本命令必须使用配置中的绝对 `spec_vault` 与位于 `spec_vault/.local` 的绝对数据库；该目录必须被 Vault 的 `.gitignore` 排除。除 `init` 外的查询对不存在数据库使用只读连接，不得创建文件。正式引用必须由 Git 证明完整 commit SHA 精确相等，Vault 引用还必须证明字段角色路径和 `commit:path` 存在，`code_ref` 必须指向可定位的代码仓库；`complete` 必须确认 final `change.md`、canonical 最终逻辑稿、测试稿与最终报告结构完整且互相绑定，总体通过、没有失败或未执行。

所有 read-check-write 操作都在 `BEGIN IMMEDIATE` 事务中，并以当前 `in_progress`、`active` 或 NULL 条件更新且检查影响行数。`adopt-plan` 把 Plan 引用和 `tdd_coding` 阶段作为一个不可分割写入且保持登记 `change_ref` 不变；`complete` 把最终 `change_ref` 与 `status=completed` 作为一个不可分割写入。数据库 CHECK 与终态 trigger 共同保护结构：未绑定游标只能位于 `requirement_discussion` 至 `register_change`；已绑定游标只能位于正式阶段；closed/completed 只能由规定命令产生且不可再改。迁移先预检冲突、未知阶段、孤儿外键和重复 active 绑定，再在同一事务中建立 canonical shadow tables、验证行数与 `foreign_key_check` 并原子替换；任一步失败都回滚。
