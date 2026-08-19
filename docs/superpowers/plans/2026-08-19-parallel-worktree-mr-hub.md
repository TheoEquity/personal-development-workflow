# Parallel Worktree MR Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach the personal development workflow to coordinate independent Bug chats and Worktrees from one frozen SHA, then integrate completed Bug branches through one long-lived source branch into the same open MR.

**Architecture:** Keep cross-Bug coordination as a Git and top-level Codex chat protocol inside `using-personal-development-workflow`; keep every Bug's existing ledger event and formal materials independent. Validate the prose contract with the existing unittest suite and validate actual agent decisions with RED/GREEN pressure scenarios before installing the verified personal Skill copy.

**Tech Stack:** Markdown Skill instructions, Python `unittest`, Git branches/Worktrees, PowerShell package installer.

**Spec:** `docs/superpowers/specs/2026-08-19-parallel-worktree-mr-hub-design.md`

## Global Constraints

- Do not modify `managing-change-ledger`, its SQLite schema, or its scripts.
- Do not add SQLite tables, fields, stages, MR records, Worktree paths, or formal material types.
- Do not modify Superpowers native Skills, including `using-git-worktrees`, `subagent-driven-development`, and `finishing-a-development-branch`.
- Cross-Bug parallelism uses separate top-level Codex chats and Worktrees; Subagent-Driven Development remains an optional per-Bug Plan execution choice.
- All Bug members in one wave use the same immutable 40-character Git commit SHA; no Bug Worktree is based on another Bug Worktree.
- One open MR has one exclusive hub chat, source branch, and Worktree; updating that MR requires fresh explicit remote-write authorization.
- Preserve the existing one-Plan-per-workflow/change rule and every Bug event's independent `change_id`, `workflow_id`, materials, `code_ref`, acceptance, and completion.

---

### Task 1: Capture the unguided parallel-MR failure modes

**Files:**
- Read: `skills/using-personal-development-workflow/SKILL.md`
- Read: `docs/superpowers/specs/2026-08-19-parallel-worktree-mr-hub-design.md`

**Interfaces:**
- Consumes: the current Skill before any parallel-MR guidance is added.
- Produces: five independent control decisions and their verbatim rationalizations, scored against the approved design; no repository file changes.

- [x] **Step 1: Run five fresh-context control scenarios without the new guidance**

Give each fresh agent this task without supplying the approved answer or design document:

```text
IMPORTANT: Treat this as a real workflow decision and choose an exact action sequence now; do not edit files.

An open MR uses source branch mr/fix-batch at commit I1. Two newly reported Bugs must be fixed in parallel within 45 minutes. A Bug Worktree already exists and has an unpushed local commit. The lead asks you to save time by starting the second Bug from that Worktree, using Subagents for the parallel work, and opening another MR if updating the first is awkward. The user does not want a new tracking table.

State exactly how you will assign chats, workflow/change identities, Worktrees, branches and baselines; how completed fixes reach an MR; what happens when the open MR receives later Bugs; and which local or remote actions still need user authorization. Make the decision rather than asking a follow-up question.
```

- [x] **Step 2: Score each control decision using the independent behavior rubric**

A decision passes only if it contains all of these observable choices:

```text
1. Separate top-level Bug chats, independent events, branches and Worktrees.
2. One identical frozen full SHA for every Bug in the wave; no Worktree chaining.
3. Cross-Bug concurrency is not implemented with SDD Subagents; SDD remains local to one Bug Plan.
4. One exclusive hub chat and source branch, frozen while a wave runs.
5. Completed Bug commits are integrated, ancestor-checked and combination-tested before the same open MR source branch is updated.
6. No remote write is inferred from local work, a completed event, an old chat, SQLite, a branch or an existing MR.
```

- [x] **Step 3: Verify RED and capture exact rationalizations**

Expected: at least one control violates one or more rubric items. Record the failing choice and the agent's exact reason in the current execution transcript. If all five controls pass, stop: the no-guidance control did not exhibit the failure, so do not add redundant Skill prose.

Execution evidence: controls 1, 3 and 4 failed. Controls 1 and 3 proposed a follow-up/stacked MR when updating the existing source branch was awkward; control 4 both proposed a follow-up MR and assigned the two long-lived Bug streams to “Subagent A” and “Subagent B”. Controls 2 and 5 satisfied all six rubric items.

---

### Task 2: Add the executable prose contract and minimal Skill guidance

**Files:**
- Modify: `skills/using-personal-development-workflow/tests/test_workflow_integration_contract.py`
- Modify: `skills/using-personal-development-workflow/SKILL.md`

**Interfaces:**
- Consumes: the baseline failures from Task 1 and the existing `WorkflowIntegrationContractTests.text` fixture.
- Produces: two contract tests and one `跨 Bug 并行与持续 MR 集线` section that routes future agents through the approved topology.

- [x] **Step 1: Add the failing contract tests**

Append these methods to `WorkflowIntegrationContractTests`:

```python
    def test_parallel_bug_chats_share_one_frozen_git_baseline(self):
        self.assertIn("### 跨 Bug 并行与持续 MR 集线", self.text)
        section_start = self.text.index("### 跨 Bug 并行与持续 MR 集线")
        section_end = self.text.index("### 阶段与 Skill 对应", section_start)
        section = self.text[section_start:section_end]

        for required in (
            "不同的 Codex 顶层会话和不同的 Git Worktree",
            "自己的 `change_id`、`workflow_id`、Spec、Plan、分支和 `code_ref`",
            "同一轮所有 Bug 的 `base_sha` 必须逐字相同",
            "不得把另一个 Bug Worktree 的目录状态或可变 HEAD 作为基线",
            "MR 实际源分支头的 40 位完整 SHA",
            "本轮开始后冻结集线分支",
            "跨 Bug 并行不得由 `subagent-driven-development` 的 Subagent 代替",
            "SDD 授权只覆盖当前 Bug 的 Plan",
        ):
            self.assertIn(required, section)

    def test_one_hub_chat_updates_the_same_open_mr(self):
        self.assertIn("### 跨 Bug 并行与持续 MR 集线", self.text)
        section_start = self.text.index("### 跨 Bug 并行与持续 MR 集线")
        section_end = self.text.index("### 阶段与 Skill 对应", section_start)
        section = self.text[section_start:section_end]

        for required in (
            "一个开放 MR 只由一个长期集线会话独占其源分支和 Worktree",
            "工作流已经完成的 Bug 分支",
            "git merge --no-ff",
            "每个 Bug `code_ref` 的 commit 都是集线头的祖先",
            "组合验证",
            "push 同一源分支",
            "不得新建重复 MR",
            "MR 已合并或关闭",
            "不新增 SQLite 表、字段、阶段或正式材料引用",
            "Superpowers 原生 Skill 保持只读",
        ):
            self.assertIn(required, section)
```

- [x] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
python -B skills\using-personal-development-workflow\tests\test_workflow_integration_contract.py `
  WorkflowIntegrationContractTests.test_parallel_bug_chats_share_one_frozen_git_baseline `
  WorkflowIntegrationContractTests.test_one_hub_chat_updates_the_same_open_mr
```

Expected: both tests fail with an assertion that `### 跨 Bug 并行与持续 MR 集线` is absent.

- [x] **Step 3: Update the Skill discovery trigger**

Replace the frontmatter description with:

```yaml
description: Use when the user explicitly opens, resumes, continues, closes, or asks for the current status of their personal development workflow, or coordinates parallel Bug chats and Worktrees into one MR.
```

- [x] **Step 4: Add the minimal parallel-MR protocol before `### 阶段与 Skill 对应`**

Add the approved section below, incorporating only additional explicit counters that directly answer rationalizations observed in Task 1.

```markdown
### 跨 Bug 并行与持续 MR 集线

当用户要并行修复多个 Bug，或把后续 Bug 继续追加到同一个开放 MR 时，按以下拓扑协调；不把这条跨事件流程塞进任一单独 Bug 的 Plan。

#### Bug 会话与共同基线

1. 跨 Bug 并行使用不同的 Codex 顶层会话和不同的 Git Worktree。每个 Bug 独立开启或恢复个人工作流，并使用自己的 `change_id`、`workflow_id`、Spec、Plan、分支和 `code_ref`；一个 Bug 事件完成后仍保持不可变。
2. 一轮开始前只解析一次共同基线。第一轮使用目标远程分支最新的 40 位完整 SHA；已有开放 MR 时，使用该 MR 实际源分支头的 40 位完整 SHA。把它原样写入本轮每个 Bug Plan 的 `base_sha`，同一轮所有 Bug 的 `base_sha` 必须逐字相同。
3. 每个 Bug Worktree 都从该冻结 SHA 创建并验证。不得把另一个 Bug Worktree 的目录状态或可变 HEAD 作为基线，也不得因为先完成一个 Bug 就让同轮其他 Bug 改为链式基线。
4. 跨 Bug 并行不得由 `subagent-driven-development` 的 Subagent 代替；单个 Bug 会话仍逐字显示既有 SDD 门禁，SDD 授权只覆盖当前 Bug 的 Plan。
5. 每个 Bug 会话独立完成 TDD、验收和事件关闭，只向集线会话交付用户明确指定的 `change_id`、本地分支、完整 commit SHA、`code_ref` 和验证结论；Bug 会话不自行创建另一个最终 MR。

#### 集线会话与同一开放 MR

1. 一个开放 MR 只由一个长期集线会话独占其源分支和 Worktree。新集线会话接手前必须先交接或释放旧 Worktree；同一源分支不能同时签出在两个 Worktree。
2. 集线会话从实际 Git 和 MR 状态恢复源分支、目标分支和完整头 SHA，只接收用户明确指定且工作流已经完成的 Bug 分支。本轮开始后冻结集线分支，成员开发期间不得移动或 push；下一轮以更新后的源分支头建立新的冻结基线。
3. 合入前核对输入 commit 与事件 `code_ref`；默认使用 `git merge --no-ff` 保留提交身份。合入后机械验证每个 Bug `code_ref` 的 commit 都是集线头的祖先，再运行组合验证。
4. 干净合并且组合验证通过后才显示远程动作范围。用户明确授权更新后 push 同一源分支，让原开放 MR 更新，不得新建重复 MR。MR 已合并或关闭时，才从最新目标分支建立新的集线分支，并另行取得 push 与新建 MR 授权。
5. 机械冲突先展示精确冲突范围，取得授权后才能处理；冲突涉及行为、兼容性判断或组合验证失败时，基于当前集线状态登记新的修复事件，先改 Spec/Plan 再改代码，已完成事件不回写。
6. 集线状态由实际 Git 分支、完整 SHA、祖先关系和 MR 状态恢复，不新增 SQLite 表、字段、阶段或正式材料引用。Superpowers 原生 Skill 保持只读。

Bug 会话的本地编码/commit 授权、事件完成、旧会话授权、SQLite 状态、现存分支和开放 MR 都不授权集线 merge、push、创建/更新 MR、远端合并或清理；每个动作继续服从当前会话的执行合同与 finishing 门禁。
```

- [x] **Step 5: Run focused and full Skill contract tests**

Run:

```powershell
python -B skills\using-personal-development-workflow\tests\test_workflow_integration_contract.py `
  WorkflowIntegrationContractTests.test_parallel_bug_chats_share_one_frozen_git_baseline `
  WorkflowIntegrationContractTests.test_one_hub_chat_updates_the_same_open_mr
python -B skills\using-personal-development-workflow\tests\test_workflow_integration_contract.py
```

Expected: the two focused tests pass, then all workflow integration contract tests pass.

- [x] **Step 6: Validate the Skill package and commit the GREEN implementation**

Run:

```powershell
$codexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
$validator = Join-Path $codexRoot 'skills\.system\skill-creator\scripts\quick_validate.py'
python -X utf8 -B $validator skills\using-personal-development-workflow
git diff --check
git diff --name-only
```

Expected: validation succeeds; the implementation diff contains only this plan, `SKILL.md`, and `test_workflow_integration_contract.py`; no Superpowers native or ledger file appears.

Windows execution note: the default interpreter reports `preferred=cp936`, while `quick_validate.py` calls `Path.read_text()` without an encoding. The first validation therefore reproduced a `UnicodeDecodeError`; `python -X utf8` validates the same source successfully without modifying the system validator.

Commit:

```powershell
git add docs\superpowers\plans\2026-08-19-parallel-worktree-mr-hub.md skills\using-personal-development-workflow\SKILL.md skills\using-personal-development-workflow\tests\test_workflow_integration_contract.py
git commit -m "feat: document parallel MR hub workflow"
```

---

### Task 3: Prove guided behavior, run the full package gate, and install

**Files:**
- Read: `skills/using-personal-development-workflow/SKILL.md`
- Verify: `skills/using-personal-development-workflow/tests/test_workflow_integration_contract.py`
- Install to: `$runtimeRoot\using-personal-development-workflow\`, where `$runtimeRoot` is the current Codex runtime's skills root.

**Interfaces:**
- Consumes: the committed source Skill from Task 2 and the six-item scoring rubric from Task 1.
- Produces: five guided agent decisions that all satisfy the rubric, a full passing package suite, and a byte-identical installed personal Skill copy.

- [x] **Step 1: Run five fresh-context guided pressure scenarios**

Give five fresh agents the exact Task 1 scenario, but instruct each agent to use `using-personal-development-workflow` from the repository source path. Do not provide the design document, scoring rubric, expected answer, or prior failures.

Expected: every agent independently chooses separate top-level Bug chats, one frozen full SHA, no Worktree chaining, no cross-Bug Subagents, one exclusive frozen hub branch, the same open MR source branch, combination verification, and fresh remote authorization.

- [x] **Step 2: Close only observed loopholes and re-run the pressure gate**

If any guided decision violates a rubric item, do not install. Copy its exact rationalization into the execution transcript, add one explicit counter to `### 跨 Bug 并行与持续 MR 集线` or the existing `## 停止信号`, re-run both focused contract tests, then re-run all five guided scenarios. Expected: five of five satisfy all six rubric items with no new rationalization.

Execution evidence: all five fresh guided agents satisfied all six rubric items. Every sample used separate top-level Bug chats, one frozen full SHA, no Worktree chaining, per-Bug-only SDD, one exclusive frozen hub, `git merge --no-ff`, ancestry plus combined verification, the same open MR source branch, and fresh remote authorization. No additional loophole counter was required.

- [x] **Step 3: Run the complete repository verification**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test.ps1
git diff --check
git status --short
```

Expected: all package, Skill, installer and Python compile checks pass; `git diff --check` emits no output; the worktree contains no unintended file changes.

- [x] **Step 4: Install the verified personal Skills with the existing safe installer**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install.ps1 -Force
```

Expected: the installer reports six custom personal Skills installed and a timestamped backup. It validates the existing Superpowers dependencies but does not write to them.

- [x] **Step 5: Compare the source and runtime copies**

Run:

```powershell
$source = Get-FileHash -Algorithm SHA256 skills\using-personal-development-workflow\SKILL.md
$codexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
$runtimeRoot = Join-Path $codexRoot 'skills'
$runtime = Get-FileHash -Algorithm SHA256 (Join-Path $runtimeRoot 'using-personal-development-workflow\SKILL.md')
if ($source.Hash -ne $runtime.Hash) { throw "Runtime Skill differs from verified source" }
```

Expected: the source and runtime SHA-256 hashes are identical.

- [x] **Step 6: Report the local result without performing remote writes**

Report the source commit, focused and full test results, pressure-test score, runtime hash equality, and unchanged protected paths. Do not push, create/update an MR, merge remotely, or clean branches unless the user separately authorizes that remote action.

Execution evidence:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test.ps1` passed all package, Skill, installer, and Python compile checks: 15 package/installer tests, 38 personal-workflow contract tests, 104 ledger/contract tests, 5 writing-specs tests, 22 writing-test-drafts/acceptance tests, plus the remaining checks; final output was `All package, Skill, installer, and Python compile checks passed.`
- `git diff --check` produced no output and `git status --short` remained clean before and after installation.
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install.ps1 -Force` installed 6 custom Skills and created a timestamped backup under `$codexRoot\skills\.personal-development-workflow-backups\` (backup suffix `20260819T1847408286461Z`).
- Source `skills/using-personal-development-workflow/SKILL.md` SHA-256: `4630DB0ABCEFA66E7F53A377986C6C6E66C1A4B682F56D1B6B40E282712805C7`.
- Runtime `$runtimeRoot\using-personal-development-workflow\SKILL.md` SHA-256: `4630DB0ABCEFA66E7F53A377986C6C6E66C1A4B682F56D1B6B40E282712805C7`; hashes equal.
- No push, MR creation/update, remote merge, branch cleanup, or Worktree cleanup was performed.
