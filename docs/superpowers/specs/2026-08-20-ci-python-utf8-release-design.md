# CI Python UTF-8 Release Design

## Context

The `v1.1.0` release candidate passed `scripts/test.ps1` locally but failed on
GitHub's Windows runner. The runner exposed Python standard streams through the
`cp1252` console encoding. Commands that emit Chinese JSON then raised
`UnicodeEncodeError`, causing 26 cascading ledger-test failures. The business
logic and assertions were not the source of the failure.

The `v1.1.0` tag is already public and must not be moved or overwritten. No
GitHub Release was created for it.

After the UTF-8 failures were removed, the Windows runner exposed one
independent test-portability mismatch: production inventories resolve
`AGENTS.md` paths, while the test expected the lexical temporary-directory
path. Windows represented those equivalent paths through long and 8.3 aliases.

## Decision

Make the repository's canonical test entry point explicitly enable Python UTF-8
mode. `scripts/test.ps1` will set `PYTHONUTF8=1` before invoking any Python
process. This keeps local and GitHub Windows executions on the same encoding
contract without changing the ledger CLI's JSON format or runtime behavior.

Add a package-contract regression test that reads the real test entry point and
requires the UTF-8 setting. The test must fail before the script change and pass
after it.

Keep the production AGENTS inventory contract unchanged. Make its existing test
derive expected path identities with the same `Path.resolve()` normalization
that the production inventory applies, so equivalent Windows long and 8.3 path
aliases do not create a false failure.

## Alternatives Considered

- Setting UTF-8 only in `.github/workflows/tests.yml` would repair GitHub
  Actions but leave direct Windows invocations of `scripts/test.ps1`
  locale-dependent.
- Escaping all non-ASCII CLI output or reconfiguring the ledger CLI would alter
  runtime output behavior to solve a test-runner configuration defect.
- Moving the public `v1.1.0` tag would rewrite a published Git reference.

## Scope and Verification

Implementation inputs are `tests/test_package_contract.py`, `scripts/test.ps1`,
and the existing Windows-portability expectation in
`skills/managing-change-ledger/tests/test_change_ledger.py`. After the RED/GREEN
cycle, run the complete `scripts/test.ps1` suite and Python compilation checks.
Then fast-forward `main`, create the next unused annotated patch tag, atomically
push `main` plus the tag, and wait for the corresponding GitHub Actions run
before creating the GitHub Release.

The existing failed-candidate tags remain unchanged and have no Release entry.
