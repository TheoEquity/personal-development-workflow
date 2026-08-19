# Remote Baseline Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a freshly fetched remote branch SHA the mandatory, immutable starting point for every personal-workflow implementation Worktree.

**Architecture:** Keep the behavior in the personal workflow controller and its personal execution contract. The Plan carries the reviewed remote/branch/SHA triple; the controller fetches and compares before delegating Worktree creation, while existing material-drift routing handles re-review. No Superpowers original is modified.

**Tech Stack:** Markdown Skill contracts, Python `unittest`, Git, PowerShell packaging tests.

**Spec:** `docs/superpowers/plans/2026-08-19-remote-baseline-gate-design.md`

## Global Constraints

- Superpowers original Skills and prompts are read-only.
- Fetch must not mutate the remote or merge/reset the user's main checkout.
- No Worktree, RED, test, production code, or local commit may precede successful latest-SHA verification.
- Published and runtime copies must express the same contract.

---

### Task 1: Add the failing remote-baseline contract

**Files:**
- Modify: `skills/using-personal-development-workflow/tests/test_workflow_integration_contract.py`
- Modify: `<runtime-skill-root>/using-personal-development-workflow/tests/test_workflow_integration_contract.py`

**Interfaces:**
- Consumes: existing workflow Skill and personal execution-contract Markdown.
- Produces: regression checks for Plan baseline fields, fetch-before-Worktree ordering, drift routing and forbidden pre-fetch side effects.

- [ ] **Step 1: Write the failing tests**

Add focused test methods requiring `base_remote` / `base_branch` / `base_sha`, a fetch-first sequence, exact full-SHA comparison, no `pull`/merge/reset, and Plan re-review on drift.

- [ ] **Step 2: Run the target test to verify RED**

Run: `python skills/using-personal-development-workflow/tests/test_workflow_integration_contract.py`

Expected: FAIL because the current Skill creates the Worktree before any mandatory remote fetch contract and the execution contract authorizes only the earlier three-item handoff.

### Task 2: Implement the personal workflow gate

**Files:**
- Modify: `skills/using-personal-development-workflow/SKILL.md`
- Modify: `skills/using-personal-development-workflow/references/execution-contract.md`
- Modify: `README.md`
- Modify: `<runtime-skill-root>/using-personal-development-workflow/SKILL.md`
- Modify: `<runtime-skill-root>/using-personal-development-workflow/references/execution-contract.md`

**Interfaces:**
- Consumes: adopted `plan_ref`, configured repository, Plan `base_remote`, `base_branch`, `base_sha`, and the user's affirmative SDD answer.
- Produces: fetched latest full SHA, either a verified Worktree handoff or a return to `writing_plan`.

- [ ] **Step 1: Add Plan baseline requirements**

Require the Plan and reviewer inputs to carry the remote name, branch name and reviewed 40-character SHA before adoption.

- [ ] **Step 2: Add the fetch-first development sequence**

Make the first post-authorization action a scoped fetch of the Plan remote/branch, resolve the remote tracking ref to a full commit SHA, and compare it before `using-git-worktrees`.

- [ ] **Step 3: Add deterministic outcomes**

If equal, create the Worktree from that SHA and re-verify `HEAD`; if different, keep code closed and return to targeted Plan impact review; if fetch/resolve fails, stop without development side effects.

- [ ] **Step 4: Align authorization and public documentation**

Allow only the local fetch needed to resolve the displayed base, retain the remote-write/finishing prohibitions, and show the new gate in README flow and prose.

- [ ] **Step 5: Run target tests to verify GREEN**

Run: `python skills/using-personal-development-workflow/tests/test_workflow_integration_contract.py`

Expected: all workflow integration contract tests PASS.

### Task 3: Synchronize, pressure-test and deploy

**Files:**
- Verify: runtime and published Skill, execution contract and tests.
- Verify: repository package tests and installer tests.

**Interfaces:**
- Consumes: completed Task 2 documents and tests.
- Produces: identical runtime/published behavior, fresh verification evidence, and a private GitHub update.

- [ ] **Step 1: Run skill behavior pressure tests**

Use fresh-context scenarios with deadline, authority and sunk-cost pressure. Every guided sample must fetch first and forbid Worktree/code side effects until the SHA gate passes.

- [ ] **Step 2: Run package verification**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test.ps1`

Expected: package, installer and bundled Skill tests PASS.

- [ ] **Step 3: Compare runtime and published copies**

Verify the Skill and execution-contract file hashes match; preserve the intentionally portable published test setup while keeping its new contract methods equivalent to the runtime test.

- [ ] **Step 4: Inspect scope and protected dependencies**

Run `git diff --check`, inspect `git diff`, and confirm no Superpowers original path changed.

- [ ] **Step 5: Commit and push the private workflow repository**

Commit only the planned published files and push `main` to the already configured private `origin`; do not touch any business repository or GitLab remote.
