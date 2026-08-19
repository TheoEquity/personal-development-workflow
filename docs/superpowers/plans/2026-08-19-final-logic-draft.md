# Final Logic Draft Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require a concise, behavior-accurate final logic draft after passed acceptance and anchor it to the final change commit without adding a SQLite field.

**Architecture:** Add one focused personal writer Skill for the human-readable artifact, route passed acceptance through it, and make the ledger completion command derive and validate `logic/<change_id>.md` from the final `change_ref` commit. Package and runtime copies remain identical; Superpowers dependencies remain untouched.

**Tech Stack:** Markdown Skill contracts, Python 3 standard library, SQLite, Git CLI, Python `unittest`, PowerShell installer.

**Spec:** `docs/superpowers/plans/2026-08-19-final-logic-draft-design.md`

## Global Constraints

- The normal document granularity is the approved Tooltip visual-snapshot example: chronological and understandable, without code-level detail.
- `logic/<change_id>.md` is generated only after a passed, validated acceptance report.
- The final `change_ref` commit SHA anchors both final `change.md` and the canonical logic draft.
- SQLite retains exactly the existing two tables and eight/four fields; no `logic_ref` column or new stage is added.
- Superpowers original Skills and prompts are read-only.
- No remote push, pull request, merge, or release is part of this plan.

---

### Task 1: Prove the missing workflow behavior

**Files:**
- Test without edits: `skills/using-personal-development-workflow/SKILL.md`
- Test without edits: `skills/managing-change-ledger/SKILL.md`
- Record evidence in the task handoff, not in production files.

**Interfaces:**
- Consumes: current passed-acceptance and completion rules.
- Produces: verbatim RED evidence that an agent completes the event without creating a final logic draft.

- [ ] **Step 1: Run a no-guidance pressure scenario**

Give a fresh agent the current workflow and ledger Skills, a passed acceptance report, deadline pressure, a manager instruction to finish immediately, and an already prepared final `change.md`. Ask it to choose and act between immediate completion and creating an unmentioned logic draft.

- [ ] **Step 2: Verify RED**

Expected: the agent follows the current documented path directly from passed acceptance to final `change.md` and `complete`, proving the new artifact is not taught.

- [ ] **Step 3: Capture the exact omission and rationale**

Record whether the agent says the existing six references are sufficient, whether it treats the acceptance report as the only post-test artifact, and whether time pressure reinforces immediate completion.

### Task 2: Add executable completion tests first

**Files:**
- Modify: `skills/managing-change-ledger/tests/test_change_ledger.py`
- Modify: `skills/managing-change-ledger/tests/test_skill_contract.py`
- Modify: `skills/using-personal-development-workflow/tests/test_workflow_integration_contract.py`
- Modify: `tests/test_package_contract.py`
- Modify: `tests/test_install_script.py`

**Interfaces:**
- Consumes: existing `complete`, package installation, and workflow contracts.
- Produces: failing tests for canonical logic content, final-commit anchoring, routing, and distribution.

- [ ] **Step 1: Add the ledger behavior tests**

Add real Git-fixture tests proving `complete` rejects a missing `logic/<change_id>.md`, a wrong heading or empty `## 功能逻辑`, and a final `change.md` that does not contain its canonical logic path. Add a passing case where both files exist in the final commit and assert the database schema still has no `logic_ref` column.

- [ ] **Step 2: Add workflow and package contract tests**

Require the passed-acceptance route to invoke `writing-final-logic-drafts` before completion, require the fixed path and approved document shape, add the new owned Skill to package and installer expectations, and keep the Superpowers dependency list unchanged.

- [ ] **Step 3: Run focused tests to verify RED**

Run:

```powershell
python -B -m unittest -v tests.test_package_contract tests.test_install_script
python -B -m unittest -v skills.managing-change-ledger.tests.test_change_ledger skills.managing-change-ledger.tests.test_skill_contract
python -B -m unittest -v skills.using-personal-development-workflow.tests.test_workflow_integration_contract
```

Expected: FAIL because the package lacks the writer Skill, the workflow skips it, and `complete` accepts a final commit without the logic draft.

### Task 3: Add and pressure-test the final logic writer Skill

**Files:**
- Create: `skills/writing-final-logic-drafts/SKILL.md`
- Create: `skills/writing-final-logic-drafts/agents/openai.yaml`

**Interfaces:**
- Consumes: controller-provided `change_id`, current immutable `spec_ref`, `plan_ref`, `code_ref`, `test_ref`, and passed `evidence_ref`.
- Produces: user-confirmed `logic/<change_id>.md` with required `# <change_id> 最终逻辑稿` and `## 功能逻辑`, plus optional `## 注意事项`.

- [ ] **Step 1: Write the minimal Skill**

Define the chronological output recipe, the approved Tooltip-example granularity, the passed-acceptance prerequisite, conflict stop conditions, canonical path, confirmation gate, and exclusions from code-level or test-report content.

- [ ] **Step 2: Add discoverability metadata**

Use `name: writing-final-logic-drafts` and a third-person trigger-only description beginning with `Use when` for passed acceptance and final logic documentation.

- [ ] **Step 3: Verify GREEN with the original pressure scenario**

Provide the new Skill together with the current materials. Expected: the agent refuses immediate event completion, drafts the chronological logic document at the canonical path, and waits for confirmation.

- [ ] **Step 4: Run a shape variation scenario**

Use a different feature whose behavior has triggers, ordering, state and cleanup. Expected: the output remains readable at feature-flow level, uses no forced eight-section taxonomy, and does not collapse into a one-sentence summary.

### Task 4: Enforce the route and final-commit anchor

**Files:**
- Modify: `skills/using-personal-development-workflow/SKILL.md`
- Modify: `skills/managing-change-ledger/SKILL.md`
- Modify: `skills/managing-change-ledger/scripts/change_ledger.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: passed acceptance validator result and candidate final `change_ref`.
- Produces: a generated logic draft before completion and an atomic refusal when the candidate final commit lacks the required artifact.

- [ ] **Step 1: Route passed acceptance through the writer**

Keep `current_stage=acceptance`; after a passed report, call `writing-final-logic-drafts`, wait for user confirmation, save `logic/<change_id>.md`, and only then form final `change.md` and call `complete`.

- [ ] **Step 2: Add a derived-blob reader and validator**

In `change_ledger.py`, derive the final SHA from `change_ref`, read `logic/<change_id>.md` from that exact commit, require the exact H1 identity, one meaningful `## 功能逻辑`, and at most one optional meaningful `## 注意事项`.

- [ ] **Step 3: Bind final change.md to the canonical path**

Require one `## 最终逻辑稿` section whose meaningful body is exactly `- logic/<change_id>.md`; reject path aliases, placeholders and duplicate sections before the completion update.

- [ ] **Step 4: Preserve the database model**

Leave `REFERENCE_FIELDS`, table schemas, migration logic, `show`, and `list` unchanged. The logical version is derived as `logic/<change_id>.md@<final-change-ref-sha>` and is not persisted separately.

- [ ] **Step 5: Align public documentation**

Document the new post-acceptance step, its lightweight granularity, same-commit anchoring, and no-new-field rule in README and the ledger Skill.

### Task 5: Package, install, and verify

**Files:**
- Modify: `scripts/install.ps1`
- Modify: `scripts/test.ps1`
- Install through: `scripts/install.ps1 -Force`
- Verify: installer-managed runtime copies of all owned personal Skills.

**Interfaces:**
- Consumes: completed packaged Skill tree and tests.
- Produces: identical published/runtime personal Skills and fresh verification evidence.

- [ ] **Step 1: Add the new Skill to package lists**

Update installer and test-runner owned Skill arrays so installation, backup and test discovery treat `writing-final-logic-drafts` like the other personal Skills.

- [ ] **Step 2: Run focused GREEN tests**

Run the exact RED commands from Task 2. Expected: all pass.

- [ ] **Step 3: Run the full package suite**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test.ps1
```

Expected: all package, installer, bundled Skill, ledger, acceptance and Python compile checks pass.

- [ ] **Step 4: Install the verified package**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install.ps1 -Force
```

Expected: six owned personal Skills are installed and the script reports a timestamped backup of the previous five installed copies.

- [ ] **Step 5: Compare source and runtime copies**

Hash every owned Skill tree file and assert the packaged/runtime files match. Confirm no path under the Superpowers-owned dependency Skills changed.

- [ ] **Step 6: Inspect final scope**

Run `git diff --check`, inspect `git status --short` and `git diff`, and verify only this plan's source repository files plus installer-managed personal Skill copies changed.

- [ ] **Step 7: Commit only with separate authorization**

If the user explicitly authorizes a local commit, commit the planned source-repository files with a focused message. Without that authorization, leave the verified source diff uncommitted. Do not push.
