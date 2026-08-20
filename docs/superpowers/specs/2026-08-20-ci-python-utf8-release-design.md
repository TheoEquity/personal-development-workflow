# CI Python UTF-8 Release Design

## Context

The `v1.1.0` release candidate passed `scripts/test.ps1` locally but failed on
GitHub's Windows runner. The runner exposed Python standard streams through the
`cp1252` console encoding. Commands that emit Chinese JSON then raised
`UnicodeEncodeError`, causing 26 cascading ledger-test failures. The business
logic and assertions were not the source of the failure.

The `v1.1.0` tag is already public and must not be moved or overwritten. No
GitHub Release was created for it.

## Decision

Make the repository's canonical test entry point explicitly enable Python UTF-8
mode. `scripts/test.ps1` will set `PYTHONUTF8=1` before invoking any Python
process. This keeps local and GitHub Windows executions on the same encoding
contract without changing the ledger CLI's JSON format or runtime behavior.

Add a package-contract regression test that reads the real test entry point and
requires the UTF-8 setting. The test must fail before the script change and pass
after it.

## Alternatives Considered

- Setting UTF-8 only in `.github/workflows/tests.yml` would repair GitHub
  Actions but leave direct Windows invocations of `scripts/test.ps1`
  locale-dependent.
- Escaping all non-ASCII CLI output or reconfiguring the ledger CLI would alter
  runtime output behavior to solve a test-runner configuration defect.
- Moving the public `v1.1.0` tag would rewrite a published Git reference.

## Scope and Verification

Only `tests/test_package_contract.py` and `scripts/test.ps1` are implementation
inputs. After the RED/GREEN cycle, run the complete `scripts/test.ps1` suite and
Python compilation checks. Then fast-forward `main`, create the annotated
`v1.1.1` tag, atomically push `main` and that tag, and wait for the corresponding
GitHub Actions run before creating the `v1.1.1` Release.

The existing `v1.1.0` tag remains unchanged and has no Release entry.
