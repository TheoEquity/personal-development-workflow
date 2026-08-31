# Personal Workflow Cost Reduction Implementation Plan

> **Plan profile:** lean

**Goal:** 降低 Full 个人开发工作流在 Plan、模型、Task/Worker、测试与 review 编排上的固定成本，同时保留既有授权、身份、TDD、SDD review、精确 SHA 与失败证据边界。

**Architecture:** 仓库中的六个自定义技能保持为唯一规范源；安装器负责替换并校验安装树。Full CE 用一个实现 Worker 在一个 worktree 中串行执行 1–3 个垂直 SDD Task。验证证据以代码 SHA、命令、环境与输入四元组判定复用或失效，各阶段只承担自己的验证职责。

**Tech Stack:** Markdown skill contracts, Python `unittest`, Python CLI contracts, PowerShell installer

**Spec:** 本轮用户已确认的“最终总体方案（需求层）”，2026-08-31

**Acceptance:** 源码规则只允许 Lean Plan、无固定角色模型表、Full 默认一个 Worker 和 1–3 Task；同一验证四元组不会跨 Coordinator/Root/Delivery/Acceptance 重跑；临时安装后的运行时树与源码规范树一致；既有 `full + auto` 仍停在最终验收确认门及外部授权边界前。

## Global Constraints

- 保留当前 dirty worktree 中用户已有修改，不覆盖、不回退无关变化。
- 不压缩 handoff、authorization offer、execution contract、revision 或远端授权边界。
- 不新增工作流阶段、ledger 数据库字段或正式材料类型。
- 不执行 Push、MR、Delivery 合入或 Worktree 清理。
- 所有代码/脚本修改遵循测试先行；安装副本只在源码测试通过后更新。

## 开发基线

- `base_source`: `local`
- `base_sha`: `620361c54b07bc4fcdba5c5e9035aaacc13dd1be`
- 工作区状态：已有与本需求相关及不相关的未提交修改；以实际 working tree 为实施输入并逐文件保留。

## 实现兼容性分析

| 来源影响项 | 现有代码或方法 | 新方案交点 | 技术影响 | 处理方式 | 对应任务 |
|---|---|---|---|---|---|
| I-001 | `scripts/install.ps1` 全树复制 | 安装树包含缓存、备份及独立演化文件 | 明确改变 | 定义规范文件集，增加只读一致性检查并用替换安装消除额外文件 | Task 1 |
| I-002 | Full Plan/模型/Worker 编排 | 固定 high/xhigh、微 Task 与多 Worker 增加串行成本 | 明确改变 | 固定 Lean、动态最低合理档位、一个 Full Worker、默认 1–3 垂直 Task | Task 2 |
| I-003 | Coordinator/Delivery/Acceptance 验证 | 同一 SHA 的等价测试与 review 被不同角色重复执行 | 明确改变 | 定义证据四元组与阶段责任，复用有效证据，只在四元组变化时重验 | Task 3 |

---

### Task 1: Canonical source and installation parity

**Outcome:** 仓库是唯一规范源，安装器可安全替换六个自定义技能并机械判定安装树与规范文件集一致或不一致。

**Files:**
- Modify: `tests/test_install_script.py`
- Modify: `scripts/install.ps1`
- Modify: `README.md`
- Modify: `DEPENDENCIES.md`

**Interfaces:**
- Consumes: repository `skills/<custom-skill>` trees and an installed destination root
- Produces: deterministic installed trees plus a read-only parity result

**Implementation notes:**

- 规范文件集排除 `__pycache__`、`.pytest_cache`、编译产物、SQLite 与手工备份；安装目标出现任何额外文件也判为不一致。
- 一致性检查不得修改或静默选择源码/安装副本；替换安装继续保留既有备份行为。

**Test goal:** 临时目标的首次安装、强制替换、缓存排除、额外文件检测、内容漂移检测和一致性检查全部可重复验证。

- [ ] **Step 1: 写入缓存、额外文件与内容漂移的失败测试并确认 RED**
- [ ] **Step 2: 实现规范文件枚举、替换安装和只读一致性检查**
- [ ] **Step 3: 运行 installer tests 并核对错误输出保留差异**

---

### Task 2: Lean planning and one-Worker execution

**Outcome:** 正式 Plan 只有 Lean；个人工作流不再固定模型/推理档位；Full CE 使用一个实现 Worker，Plan 默认只能采用 1–3 个垂直 Task，超过上限必须携带逐项理由和用户确认例外。

**Files:**
- Modify: `skills/managing-change-ledger/scripts/change_ledger.py`
- Modify: `skills/managing-change-ledger/tests/test_change_ledger.py`
- Modify: `skills/managing-change-ledger/SKILL.md`
- Modify: `skills/managing-change-ledger/tests/test_skill_contract.py`
- Modify: `skills/using-personal-development-workflow/SKILL.md`
- Modify: `skills/using-personal-development-workflow/references/plan-stage.md`
- Modify: `skills/using-personal-development-workflow/references/plan-worker-prompt.md`
- Modify: `skills/using-personal-development-workflow/references/plan-review-contract.md`
- Modify: `skills/using-personal-development-workflow/references/stage-worker-contract.md`
- Modify: `skills/using-personal-development-workflow/references/implementation-stage.md`
- Modify: `skills/using-personal-development-workflow/references/implementation-worker-prompt.md`
- Modify: `skills/using-personal-development-workflow/tests/test_model_assignment_contract.py`
- Create: `skills/using-personal-development-workflow/tests/test_full_auto_to_acceptance_contract.py`
- Modify: `skills/using-personal-development-workflow/tests/test_simplified_flow_contract.py`
- Modify: `skills/using-personal-development-workflow/tests/test_stage_worker_contract.py`
- Modify: `skills/using-personal-development-workflow/tests/test_workflow_integration_contract.py`

**Interfaces:**
- Consumes: confirmed Full Spec, current effective model configuration, exact `plan_ref`, SDD task contracts
- Produces: one Lean Plan, one Full implementation Worker/worktree, and 1–3 SDD review boundaries

**Implementation notes:**

- `adopt-plan` 机械拒绝无例外授权的 4+ Task；例外只改变 Task 数量门，不改变 Plan、身份或授权合同。
- Spec/Plan Worker 继承当前有效配置；Coordinator 按 SDD 复杂度选择足够完成任务的最低合理档位，个人工作流不保存角色模型表。
- 保留并合并安装副本中已有 `full + auto` 语义，仍停在最终验收确认、Delivery 合入、远端动作和清理之前。

**Test goal:** 4+ Task 无确认被拒、确认但缺逐项理由被拒、完整例外可采用；文本契约不存在固定模型表并明确一个 Worker/1–3 Task/full+auto 边界。

- [ ] **Step 1: 写入任务上限、动态模型、单 Worker 与 full+auto 契约测试并确认 RED**
- [ ] **Step 2: 最小修改 ledger 与工作流路由/提示合同使测试通过**
- [ ] **Step 3: 运行 ledger 和 personal-workflow 定向测试**

---

### Task 3: Single-owner review and reusable verification evidence

**Outcome:** TDD、SDD Task review 与最终整体 review 保留，但 Coordinator、Root、Delivery 和 Acceptance 不再对同一证据四元组追加等价测试或 review；最终候选版本只由 Delivery 执行一次完整自动化验证。

**Files:**
- Modify: `skills/using-personal-development-workflow/references/implementation-stage.md`
- Modify: `skills/using-personal-development-workflow/references/integration-and-cleanup.md`
- Modify: `skills/using-personal-development-workflow/references/acceptance-stage.md`
- Modify: `skills/using-personal-development-workflow/references/execution-contract.md`
- Modify: `skills/using-personal-development-workflow/references/stage-worker-contract.md`
- Modify: `skills/using-personal-development-workflow/tests/test_simplified_flow_contract.py`
- Modify: `skills/using-personal-development-workflow/tests/test_workflow_integration_contract.py`

**Interfaces:**
- Consumes: Task-focused test evidence, SDD final review, exact candidate SHA, command, environment fingerprint, input fingerprint
- Produces: reusable evidence bound to `code_ref`, one final-candidate automated validation, and uncovered-only Acceptance work

**Implementation notes:**

- Implementer 负责 TDD/聚焦测试，Reviewer 消费已有证据，Coordinator 汇总，Root 只核对引用/SHA/范围/证据，Delivery 在最终候选 merge SHA 执行完整自动化验证。
- Full SDD 最终 review 同时满足 CE review；只有用户明确要求跨 CE 批次 review 才新增 review。
- 任一 SHA、命令、环境或输入变化都会使对应证据失效；新 SHA 或跨 CE 组合状态不视为重复。

**Test goal:** 文本契约能机械证明验证四元组、失效条件、阶段唯一责任和 Acceptance 的自动证据复用，同时不删除 TDD/SDD review 与授权门。

- [ ] **Step 1: 写入重复测试/review 的失败契约并确认 RED**
- [ ] **Step 2: 收敛各阶段责任并保留必要的新 SHA/新组合验证**
- [ ] **Step 3: 运行全量测试、临时安装 parity、实际安装更新和安装后 parity**
