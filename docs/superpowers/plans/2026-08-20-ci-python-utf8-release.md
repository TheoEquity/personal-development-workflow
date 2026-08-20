# CI Python UTF-8 Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the canonical PowerShell test entry point run every Python subprocess in UTF-8 mode so GitHub Windows runners can emit Chinese JSON safely.

**Architecture:** Preserve the ledger CLI and all runtime output contracts. Add one integration-style package test that invokes the real PowerShell entry point through a temporary Python command probe, then make the entry point establish `PYTHONUTF8=1` before any Python invocation.

**Tech Stack:** PowerShell 7, Python 3.12 `unittest`, Windows command shim, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-08-20-ci-python-utf8-release-design.md`

## Global Constraints

- Do not change the ledger CLI JSON format or runtime output behavior.
- Do not move or overwrite the public `v1.1.0` tag.
- Limit implementation changes to the UTF-8 entry point/tests and the existing AGENTS inventory test expectation.
- Do not rewrite failed-candidate tags; publish the verified fix under the next unused patch version.

---

### Task 1: Propagate UTF-8 Mode Through the Canonical Test Entry Point

**Files:**
- Modify: `tests/test_package_contract.py`
- Modify: `scripts/test.ps1`

**Interfaces:**
- Consumes: Windows `PATH` command resolution and the existing `scripts/test.ps1` entry point.
- Produces: Every `python` process started by `scripts/test.ps1` receives environment variable `PYTHONUTF8=1`.

- [ ] **Step 1: Write the failing integration test**

Add `os` and `tempfile` imports, then add this method to
`PackageContractTests`:

```python
@unittest.skipUnless(os.name == "nt", "PowerShell command shim is Windows-specific")
def test_test_entry_point_enables_utf8_for_every_python_process(self):
    with tempfile.TemporaryDirectory() as temp_dir:
        shim = Path(temp_dir) / "python.cmd"
        marker = Path(temp_dir) / "python-invocations.txt"
        shim.write_text(
            '@echo off\n'
            'echo invoked>>"%UTF8_PROBE_MARKER%"\n'
            'if "%PYTHONUTF8%"=="1" exit /b 0\n'
            'echo PYTHONUTF8=%PYTHONUTF8% 1>&2\n'
            'exit /b 97\n',
            encoding="ascii",
        )
        env = os.environ.copy()
        env.pop("PYTHONUTF8", None)
        env["UTF8_PROBE_MARKER"] = str(marker)
        env["PATH"] = f"{temp_dir}{os.pathsep}{env['PATH']}"
        result = subprocess.run(
            ["pwsh", "-NoProfile", "-File", str(REPO_ROOT / "scripts" / "test.ps1")],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertTrue(marker.is_file(), "test.ps1 did not invoke the Python probe")
        self.assertGreaterEqual(len(marker.read_text(encoding="ascii").splitlines()), 1)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
python -B -m unittest -v tests.test_package_contract.PackageContractTests.test_test_entry_point_enables_utf8_for_every_python_process
```

Expected: FAIL because the probe exits `97` and reports an empty
`PYTHONUTF8` value.

- [ ] **Step 3: Add the minimal UTF-8 environment contract**

In `scripts/test.ps1`, immediately after `$ErrorActionPreference = "Stop"`,
add:

```powershell
$env:PYTHONUTF8 = "1"
```

- [ ] **Step 4: Run focused and package tests to verify GREEN**

Run:

```powershell
python -B -m unittest -v tests.test_package_contract.PackageContractTests.test_test_entry_point_enables_utf8_for_every_python_process
python -B -m unittest -v tests.test_package_contract tests.test_install_script
```

Expected: the focused test passes, then all package and installer tests pass.

- [ ] **Step 5: Run the complete release verification**

Run:

```powershell
./scripts/test.ps1
```

Expected: package, Skill, installer, ledger, acceptance-report, and Python
compile checks all pass with exit code `0`.

- [ ] **Step 6: Commit the bounded implementation**

```powershell
git add -- tests/test_package_contract.py scripts/test.ps1 docs/superpowers/plans/2026-08-20-ci-python-utf8-release.md
git commit -m "fix: force utf8 for Windows test runs"
```

- [ ] **Step 7: Publish without rewriting a failed-candidate tag**

Fast-forward local `main` to the verified implementation commit, create
the next unused annotated patch tag, atomically push `main` plus the tag, wait
for GitHub Actions on the new commit, and create the matching GitHub Release
only after the run succeeds.

### Task 2: Normalize the Windows AGENTS Inventory Expectation

**Files:**
- Test: `skills/managing-change-ledger/tests/test_change_ledger.py`

**Interfaces:**
- Consumes: production AGENTS inventory entries formatted as `<resolved-path>@<sha256>`.
- Produces: a platform-portable expected inventory using the same resolved path identity.

- [ ] **Step 1: Record the target-environment RED**

Use the failed GitHub Windows run where production emitted the resolved
`<short-windows-temp-path>` identity while the test expected the equivalent
lexical `<long-windows-temp-path>` identity. The content hashes must be
identical.

- [ ] **Step 2: Normalize the expected paths**

Build each expected inventory entry with `path.resolve()` while retaining the
existing SHA-256 calculation:

```python
f"{path.resolve()}@{hashlib.sha256(path.read_bytes()).hexdigest()}"
```

- [ ] **Step 3: Run the focused ledger test**

```powershell
python -B -m unittest discover -s skills/managing-change-ledger/tests -p "test_change_ledger.py" -k "test_adopt_plan_keeps_registration_change_ref_and_reports_agents" -v
```

Expected: PASS locally; the next GitHub Windows run must also pass without a
long-path versus 8.3-alias mismatch.

- [ ] **Step 4: Re-run the complete release verification**

Run `./scripts/test.ps1`, commit only the documented files, create the next
unused annotated patch tag without moving `v1.1.0` or `v1.1.1`, and create the
GitHub Release only after CI succeeds.
