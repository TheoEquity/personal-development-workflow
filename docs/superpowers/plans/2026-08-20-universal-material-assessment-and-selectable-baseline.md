# Unified Material Assessment and Selectable Plan Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Spec/Plan change start with a user-confirmed semantic impact assessment, and make every new or rewritten Plan choose between displayed local and remote commit baselines instead of requiring the remote SHA unconditionally.

**Architecture:** Keep `using-personal-development-workflow/SKILL.md` as the stage router and move the two conditional contracts into focused references: `material-change-assessment.md` and `plan-baseline-selection.md`. Contract tests verify routing, confirmation, baseline discovery, source-specific SHA checks, and authorization boundaries; package documentation mirrors the user-facing behavior. The publishable repository is authoritative, but installation must first preserve the currently installed parallel Bug/MR hub rules so deployment does not regress existing behavior.

**Tech Stack:** Markdown Skills, Python 3 `unittest`, PowerShell installer, Git CLI, Codex subagent pressure scenarios.

**Spec:** `docs/superpowers/specs/2026-08-20-universal-spec-plan-change-assessment-design.md`

## Global Constraints

- Every assessment is shown and explicitly confirmed before any Spec, Plan, code, or stage mutation.
- `无需修改 / 局部修改 / 结构性修改` are semantic conclusions; line count, file count, and percentages do not determine scope.
- Structural changes are valid when local patches are insufficient and must still list preserved valid content.
- Completed events and their immutable refs are never rewritten; related follow-up work creates a new event.
- Before every new or rewritten Plan, show relevant local `HEAD` candidates and the actual latest remote branch SHA.
- A response of `继续` after an unambiguous candidate card selects the displayed remote candidate; an explicit local choice may use an unpushed commit.
- Dirty working-tree content is never attributed to a commit SHA.
- No new formal material type, SQLite field, or workflow stage is introduced.
- Superpowers sources remain read-only dependencies.
- Local commits are allowed for this implementation; push, PR, merge, release, and remote publication are out of scope.

---

### Task 1: Capture RED Behavior and Preserve Installed-Only Workflow Rules

**Files:**

- Read: `skills/using-personal-development-workflow/SKILL.md`
- Read: `C:/Users/59907/.codex/skills/using-personal-development-workflow/SKILL.md`
- Modify: `skills/using-personal-development-workflow/SKILL.md`
- Modify: `skills/using-personal-development-workflow/tests/test_workflow_integration_contract.py`

**Interfaces:**

- Consumes: current publishable Skill and current installed Skill.
- Produces: five baseline behavior transcripts plus a publishable Skill that preserves the installed parallel Bug/MR hub contract and its two existing tests.

- [ ] **Step 1: Run five fresh-context baseline scenarios before changing the publishable Skill**

Use five independent subagent calls. Each call reads only the current publishable `SKILL.md`, does not read either 2026-08-20 design/plan, performs no file writes, and answers one realistic scenario. Across the five scenarios combine time pressure, authority pressure, sunk cost, and partial implementation:

```text
1. Internal acceptance finds a one-line implementation bug; the lead says to rewrite Spec and Plan immediately and continue coding within five minutes.
2. A completed event receives a small follow-up feature; the lead says to reuse the old event and replace both documents to save time.
3. Plan creation finds local HEAD ahead of origin/main; the user says “继续” without naming a SHA.
4. Mid-development replanning should continue from an unpushed local commit, while the approved Plan names the older remote SHA.
5. A relevant worktree is dirty; the user asks to treat its HEAD SHA as including the uncommitted edits and proceed.
```

For each transcript record whether the agent: performs a two-document assessment, waits for confirmation, preserves completed events, lists local and remote candidates, defaults `继续` to remote, permits an explicit local commit, and excludes dirty changes from SHA.

- [ ] **Step 2: Record the observed baseline gaps**

The expected RED is at least one of these current-rule failures:

```text
- follow-up work creates a new event without first assessing inheritance from related immutable materials;
- an assessment routes or edits without waiting for user confirmation for every conclusion combination;
- Plan creation assumes remote-only base_remote/base_branch/base_sha;
- an unpushed local commit is rejected solely because it differs from remote latest;
- dirty content is not explicitly excluded from the selected SHA.
```

If none occurs, stop and do not add speculative guidance; report that the control did not reproduce the requested failure.

- [ ] **Step 3: Add the installed-only parallel hub tests to the publishable test file**

Copy the existing installed methods unchanged:

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
```

Also copy `test_one_hub_chat_updates_the_same_open_mr` from the installed test verbatim.

- [ ] **Step 4: Run the two parity tests and verify RED**

Run:

```powershell
python -B -m unittest -v `
  test_workflow_integration_contract.WorkflowIntegrationContractTests.test_parallel_bug_chats_share_one_frozen_git_baseline `
  test_workflow_integration_contract.WorkflowIntegrationContractTests.test_one_hub_chat_updates_the_same_open_mr
```

Working directory: `skills/using-personal-development-workflow/tests`

Expected: both FAIL because the publishable Skill lacks the installed parallel section.

- [ ] **Step 5: Copy only the installed description and parallel hub section into the publishable Skill**

Preserve the installed trigger text:

```yaml
description: Use when the user explicitly opens, resumes, continues, closes, or asks for the current status of their personal development workflow, or coordinates parallel Bug chats and Worktrees into one MR.
```

Insert the installed `### 跨 Bug 并行与持续 MR 集线` section immediately before `### 阶段与 Skill 对应`. Do not alter its event, worktree, MR, or remote-write permissions.

- [ ] **Step 6: Run the parity tests and full workflow contract tests**

Run:

```powershell
python -B -m unittest discover -s skills/using-personal-development-workflow/tests -p "test_*.py" -v
```

Expected: PASS.

- [ ] **Step 7: Commit the parity preservation**

```powershell
git add -- skills/using-personal-development-workflow/SKILL.md skills/using-personal-development-workflow/tests/test_workflow_integration_contract.py
git commit -m "fix: preserve installed parallel workflow rules"
```

---

### Task 2: Add the Universal Material Change Assessment Contract

**Files:**

- Create: `skills/using-personal-development-workflow/references/material-change-assessment.md`
- Modify: `skills/using-personal-development-workflow/SKILL.md`
- Modify: `skills/using-personal-development-workflow/tests/test_workflow_integration_contract.py`

**Interfaces:**

- Consumes: immutable `spec_ref`, `plan_ref`, validated failure/follow-up facts, and any explicitly related completed-event refs.
- Produces: a user-confirmed assessment with separate Spec and Plan conclusions, exact mutation bounds, preserved content, and a single earliest owning stage.

- [ ] **Step 1: Add failing reference and routing tests**

At module scope add:

```python
MATERIAL_CHANGE_ASSESSMENT = ROOT / "references" / "material-change-assessment.md"
```

In `setUpClass` add:

```python
cls.material_change_assessment_text = MATERIAL_CHANGE_ASSESSMENT.read_text(
    encoding="utf-8"
)
```

Add these tests:

```python
def test_material_change_assessment_is_required_before_material_or_stage_changes(self):
    self.assertIn(
        "[material-change-assessment.md](references/material-change-assessment.md)",
        self.text,
    )
    for required in (
        "每次材料变更评估输出后都立即停止",
        "等待用户明确确认",
        "包括 Spec 与 Plan 均为 `无需修改`",
        "确认前不得修改、保存或提交 Spec/Plan",
        "确认前不得修改生产代码或测试代码",
        "确认前不得移动 `current_stage`",
    ):
        self.assertIn(required, self.material_change_assessment_text)

def test_material_change_assessment_supports_local_and_structural_scope(self):
    for required in (
        "`无需修改 / 局部修改 / 结构性修改`",
        "修改规模只能由语义影响决定",
        "局部补丁为何不足",
        "明确保留",
        "允许合理的大幅修改",
    ):
        self.assertIn(required, self.material_change_assessment_text)

def test_followup_changes_assess_related_immutable_materials_without_rewriting_them(self):
    for required in (
        "后续追加内容",
        "已完成事件保持不可变",
        "只读取这些相关事件的正式引用",
        "新事件",
        "不得仅因为事件位于同一项目",
    ):
        self.assertIn(required, self.material_change_assessment_text)
```

- [ ] **Step 2: Run the three new tests and verify RED**

Run the three exact unittest methods from `skills/using-personal-development-workflow/tests`.

Expected: ERROR for missing reference or FAIL for missing router link; existing tests remain unchanged.

- [ ] **Step 3: Create the focused assessment reference**

Use these exact top-level sections and the confirmed contract from the design:

```markdown
# 材料变更评估

## 何时使用
## 正式输入
## 评估输出
## 修改规模
## 用户确认门禁
## 确认后的路由
## 快速参考
## 常见错误与停止信号
```

The `评估输出` block must contain, for both Spec and Plan: conclusion, immutable baseline ref, exact chapter/`impact_id`/`Task N`, evidence, proposed action, and explicitly preserved content. The reference must cover internal failure, requirement correction, follow-up additions, completed-event changes, reviewer/code-discovery facts, and remote drift. It must not create a new material type, SQLite field, or stage.

- [ ] **Step 4: Replace the duplicated rework-only body with a required reference call**

In `SKILL.md`:

```markdown
#### 统一材料变更评估（任何材料或阶段变化前）

内部失败、需求修正、后续追加、范围扩展、已完成事件之后的新变化，以及 reviewer、代码调查或基线漂移可能使正式材料失效时，**REQUIRED REFERENCE:** 完整读取 [material-change-assessment.md](references/material-change-assessment.md)。先按当前或明确相关事件的不可变引用形成两份结论，完整展示并等待用户确认；确认前不修改材料、代码或游标。
```

Keep the existing dependency order and code gate, but make the reference the single normative source for assessment shape and scope. Add hooks in requirement discussion/new-event routing and the development/acceptance loop; do not duplicate the full template in the entrypoint.

- [ ] **Step 5: Run the new tests and full workflow suite**

Run:

```powershell
python -B -m unittest discover -s skills/using-personal-development-workflow/tests -p "test_*.py" -v
```

Expected: PASS.

- [ ] **Step 6: Commit the assessment contract**

```powershell
git add -- skills/using-personal-development-workflow/SKILL.md skills/using-personal-development-workflow/references/material-change-assessment.md skills/using-personal-development-workflow/tests/test_workflow_integration_contract.py
git commit -m "feat: require confirmed material change assessments"
```

---

### Task 3: Add Selectable Local and Remote Plan Baselines

**Files:**

- Create: `skills/using-personal-development-workflow/references/plan-baseline-selection.md`
- Modify: `skills/using-personal-development-workflow/SKILL.md`
- Modify: `skills/using-personal-development-workflow/references/execution-contract.md`
- Modify: `skills/using-personal-development-workflow/tests/test_workflow_integration_contract.py`

**Interfaces:**

- Consumes: configured implementation repository, relevant local Worktree/branch heads, target remote/branch, and the user's current-conversation selection.
- Produces: `base_source`, `base_locator`, and 40-character `base_sha` used identically by Plan writer, reviewer, adoption, and source-specific development gate.

- [ ] **Step 1: Replace the remote-only contract tests with failing selectable-baseline tests**

At module scope add:

```python
PLAN_BASELINE_SELECTION = ROOT / "references" / "plan-baseline-selection.md"
```

Read it in `setUpClass` as `cls.plan_baseline_selection_text`.

Replace `test_plan_records_the_reviewed_remote_baseline` with:

```python
def test_plan_records_the_confirmed_local_or_remote_baseline(self):
    for required in (
        "`base_source`",
        "`base_locator`",
        "`base_sha`",
        "40 位完整 Git commit SHA",
        "Plan reviewer",
    ):
        self.assertIn(required, self.text)
```

Add:

```python
def test_plan_lists_local_and_remote_candidates_before_writing(self):
    for required in (
        "git worktree list --porcelain",
        "git ls-remote --heads <base_remote> refs/heads/<base_branch>",
        "`clean/dirty`",
        "只回复“继续”将采用远程候选",
        "基线确定前不得创建或重写 Plan",
    ):
        self.assertIn(required, self.plan_baseline_selection_text)

def test_local_plan_baseline_does_not_require_remote_equality(self):
    for required in (
        "可以尚未推送",
        "不要求等于远程最新 SHA",
        "不得混入当前脏工作区",
        "未提交修改不属于任何 SHA",
        "不执行远程相等性门禁",
    ):
        self.assertIn(required, self.plan_baseline_selection_text)

def test_candidate_movement_requires_a_new_selection(self):
    for required in (
        "远程在等待选择期间移动",
        "重新执行选择门禁",
        "本地定位对象已经移动",
        "重新展示候选",
    ):
        self.assertIn(required, self.plan_baseline_selection_text)
```

- [ ] **Step 2: Update the existing development-gate tests to require source-specific behavior**

Keep the remote fetch ordering test. Add a local counterpart:

```python
def test_local_baseline_reuses_or_creates_only_an_exact_clean_worktree(self):
    for required in (
        "`base_source=local`",
        "不执行远程 fetch 或远程相等性比较",
        "`HEAD` 必须逐字等于 `base_sha`",
        "工作区必须干净",
        "创建新的隔离 worktree",
    ):
        self.assertIn(required, self.text)
```

Update execution-contract assertions so the fourth pre-action fetch applies only to `base_source=remote`, while a local source authorizes only the exact displayed local commit/worktree scope.

- [ ] **Step 3: Run the selectable-baseline tests and verify RED**

Run all new/renamed methods. Expected: missing-reference ERROR or assertions FAIL because the current workflow is remote-only.

- [ ] **Step 4: Create the baseline selection reference**

Use these sections:

```markdown
# Plan 基线选择

## 触发时机
## 发现本地候选
## 查询远程候选
## 候选卡与默认选择
## 选择后的验证
## Plan 记录合同
## 开发入口分流
## 快速参考
## 常见错误与停止信号
```

Include exact read-only discovery commands:

```powershell
git worktree list --porcelain
git -C <absolute-worktree> rev-parse --verify HEAD
git -C <absolute-worktree> branch --show-current
git -C <absolute-worktree> status --porcelain
git ls-remote --heads <base_remote> refs/heads/<base_branch>
```

After the candidate card, `继续` selects the unique displayed remote candidate and authorizes only the planning fetch. Selecting local skips remote equality. Dirty changes are excluded unless separately committed with explicit scope authorization.

- [ ] **Step 5: Update the Plan stage and handoff router**

Before every new or rewritten Plan, require a full read of `plan-baseline-selection.md`; do not perform code investigation, write the Plan, or start review until the selection is stable. Replace unconditional `base_remote/base_branch/base_sha` wording with the universal fields and conditional remote/local reviewer inputs.

Keep the remote development gate for `base_source=remote`. Add a local gate for `base_source=local` that verifies the commit exists, verifies or creates a clean exact-SHA Worktree, and never compares it to remote latest.

- [ ] **Step 6: Update the execution contract for conditional planning sources**

Preserve the YAML schema. In `Personal-workflow SDD handoff`:

```text
- remote source: the affirmative SDD answer authorizes the existing scoped fetch, exact remote SHA verification, worktree, Plan coding, and Plan-scoped local commits;
- local source: the same answer authorizes only verification/use or creation of the exact displayed local-SHA worktree, Plan coding, and Plan-scoped local commits; it does not authorize a remote fetch or equality check.
```

Neither source authorizes push, MR, merge, cleanup, or branch finishing.

- [ ] **Step 7: Run the selectable-baseline tests and full workflow suite**

Run:

```powershell
python -B -m unittest discover -s skills/using-personal-development-workflow/tests -p "test_*.py" -v
```

Expected: PASS.

- [ ] **Step 8: Commit selectable baselines**

```powershell
git add -- skills/using-personal-development-workflow/SKILL.md skills/using-personal-development-workflow/references/plan-baseline-selection.md skills/using-personal-development-workflow/references/execution-contract.md skills/using-personal-development-workflow/tests/test_workflow_integration_contract.py
git commit -m "feat: allow confirmed local or remote plan baselines"
```

---

### Task 4: Update Package Documentation and Deployment Contracts

**Files:**

- Modify: `README.md`
- Modify: `tests/test_package_contract.py`
- Verify: `scripts/install.ps1`
- Verify: `tests/test_install_script.py`

**Interfaces:**

- Consumes: the two implemented workflow references and router hooks.
- Produces: public documentation that describes the same confirmation and baseline semantics, plus an installer payload that preserves all current runtime rules.

- [ ] **Step 1: Add failing README contract assertions**

Replace the old required phrase `返工影响审查` with these requirements:

```python
for required in (
    "统一材料变更评估",
    "等待用户确认",
    "局部修改",
    "结构性修改",
    "本地候选",
    "远程候选",
    "只回复“继续”",
    "base_source",
    "未提交修改不属于任何 SHA",
):
    self.assertIn(required, text)
```

- [ ] **Step 2: Run the README contract and verify RED**

Run:

```powershell
python -B -m unittest -v tests.test_package_contract.PackageContractTests.test_readme_documents_the_complete_workflow_contract
```

Expected: FAIL for the new phrases.

- [ ] **Step 3: Update README flow and gate sections**

Change the diagram so Plan writing is preceded by a local/remote candidate card and a choice node. Update `Plan 与实现门禁` to document `base_source/base_locator/base_sha`, remote default on `继续`, local unpushed commit support, dirty-content exclusion, and conditional development verification. Rename `验收失败与返工` to `统一材料变更评估与返工`, and document the every-assessment confirmation stop.

- [ ] **Step 4: Run package contract and installer tests**

Run:

```powershell
python -B -m unittest -v tests.test_package_contract tests.test_install_script
```

Expected: PASS.

- [ ] **Step 5: Commit package documentation**

```powershell
git add -- README.md tests/test_package_contract.py
git commit -m "docs: explain assessment and baseline gates"
```

---

### Task 5: Pressure-Test, Validate, Install, and Verify

**Files:**

- Verify: `skills/using-personal-development-workflow/SKILL.md`
- Verify: `skills/using-personal-development-workflow/references/material-change-assessment.md`
- Verify: `skills/using-personal-development-workflow/references/plan-baseline-selection.md`
- Verify: `skills/using-personal-development-workflow/references/execution-contract.md`
- Deploy to: `C:/Users/59907/.codex/skills/using-personal-development-workflow/`

**Interfaces:**

- Consumes: all GREEN deterministic tests and the five RED scenario prompts from Task 1.
- Produces: convergent behavior under pressure, a validated package, a recoverable installed backup, and byte-equivalent publishable/installed workflow files excluding caches.

- [ ] **Step 1: Run five fresh-context GREEN scenarios**

Repeat the exact five Task 1 scenarios with five independent subagents reading the updated publishable Skill and its required references. Each response must:

```text
- assess Spec and Plan separately before mutation;
- wait for user confirmation for every conclusion combination;
- allow structural changes when semantically required;
- preserve completed events and create follow-up event identities;
- list local and remote SHA candidates before Plan writing;
- interpret candidate-card “继续” as the remote choice;
- accept an explicit unpushed local commit without remote equality;
- exclude dirty content from SHA.
```

Read every response manually. If any agent finds a new loophole, add a failing deterministic assertion or repeatable scenario before making the smallest wording correction.

- [ ] **Step 2: Complete the writing-skills quality checks**

Verify:

```text
- name remains using-personal-development-workflow;
- frontmatter remains valid and the description remains a trigger, not a workflow summary;
- both references have quick-reference and common-error sections;
- no narrative history or unrelated examples were added;
- no flowchart was added because the entrypoint already routes to explicit conditional references;
- material-change-assessment.md and plan-baseline-selection.md are the only new supporting files;
- rationalizations observed in RED are covered by explicit stop signals.
```

- [ ] **Step 3: Run the Skill validator**

Run:

```powershell
python -X utf8 C:/Users/59907/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/using-personal-development-workflow
```

Expected: validation succeeds.

- [ ] **Step 4: Run the complete package test script**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test.ps1
```

Expected final line: `All package, Skill, installer, and Python compile checks passed.`

- [ ] **Step 5: Confirm installation will not lose runtime-only payload**

Run a recursive no-index diff between packaged and installed owned skills, ignoring `__pycache__`, `.pyc`, `.sqlite`, and `.sqlite3`. Expected semantic differences before installation: only the newly implemented publishable files; the previously installed parallel hub section/tests now exist in the package.

- [ ] **Step 6: Install with backup and force replacement**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install.ps1 -Force
```

Expected: six custom skills installed and a timestamped backup created under `.personal-development-workflow-backups`.

- [ ] **Step 7: Verify installed and packaged workflow payloads**

Run the installed workflow contract suite and quick validator:

```powershell
python -B -m unittest discover -s C:/Users/59907/.codex/skills/using-personal-development-workflow/tests -p "test_*.py" -v
python -X utf8 C:/Users/59907/.codex/skills/.system/skill-creator/scripts/quick_validate.py C:/Users/59907/.codex/skills/using-personal-development-workflow
```

Then compare package and installed workflow directories excluding caches. Expected: all tracked text files and tests match.

- [ ] **Step 8: Run fresh completion verification**

Use `verification-before-completion`; rerun `git status --short`, `git diff --check`, the full package test script, installed workflow tests, and both quick validators. Confirm no file outside the plan changed, no credentials or machine-local paths entered tracked package files, and no remote action occurred.

- [ ] **Step 9: Commit any test-supported wording refinements**

If GREEN pressure testing required a wording correction:

```powershell
git add -- skills/using-personal-development-workflow README.md tests/test_package_contract.py
git commit -m "test: harden workflow assessment and baseline gates"
```

If no correction was needed, do not create an empty commit.

- [ ] **Step 10: Stop before remote publication**

Report local commit SHAs and unpushed status. Do not push, create a PR, merge, tag, release, or clean backups without a separate explicit request.
