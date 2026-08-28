#!/usr/bin/env python3
"""Maintain the personal-development change ledger and workflow cursor."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


PRE_EVENT_STAGES = (
    "requirement_discussion",
    "research",
    "prototype",
    "register_change",
)
FORMAL_STAGES = (
    "writing_spec",
    "writing_plan",
    "tdd_coding",
    "writing_test",
    "acceptance",
)
WORKFLOW_STAGES = PRE_EVENT_STAGES + FORMAL_STAGES
FLOWS = ("direct", "light", "full")
REVIEW_MODES = ("manual", "auto")
REFERENCE_FIELDS = (
    "spec_ref",
    "change_ref",
    "plan_ref",
    "test_ref",
    "code_ref",
    "evidence_ref",
)
SHA_PATTERN = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
CHANGE_ID_PATTERN = re.compile(r"^CE-(\d{4,})$")
WORKFLOW_ID_PATTERN = re.compile(r"^WF-(\d{4,})$")
REPOSITORY_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
PLACEHOLDER_PATTERN = re.compile(r"(?:<[^>]+>|placeholder|\btodo\b|待填写)", re.I)
PLAN_PLACEHOLDER_PATTERN = re.compile(
    r"(?:<[^>]+>|placeholder|\btbd\b|\btodo\b|implement later|fill in details|待填写)",
    re.I,
)
VAULT_ROLE_PREFIXES = {
    "spec_ref": "specs/",
    "plan_ref": "plans/",
    "test_ref": "tests/",
    "evidence_ref": "acceptance/",
}
FULL_STAGE_PREREQUISITES = {
    "writing_plan": ("spec_ref", "test_ref"),
    "tdd_coding": ("spec_ref", "plan_ref", "test_ref"),
    "writing_test": ("spec_ref", "plan_ref", "code_ref"),
    "acceptance": ("spec_ref", "plan_ref", "test_ref", "code_ref"),
}
class LedgerError(Exception):
    """A user-correctable ledger operation error."""


def formal_stages_for_flow(flow: str) -> tuple[str, ...]:
    if flow == "direct":
        return ("tdd_coding", "acceptance")
    if flow == "light":
        return ("writing_spec", "tdd_coding", "acceptance")
    if flow == "full":
        return FORMAL_STAGES
    raise LedgerError(f"unknown workflow flow: {flow}")


def initial_bound_stage(flow: str) -> str:
    return "tdd_coding" if flow == "direct" else "writing_spec"


@dataclass(frozen=True)
class RuntimeConfig:
    database: Path
    spec_vault: Path | None
    repositories: dict[str, Path]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(action: str, status: str, change_id=None, workflow_id=None) -> None:
    identifiers = ""
    if workflow_id:
        identifiers += f" workflow_id={workflow_id}"
    if change_id:
        identifiers += f" change_id={change_id}"
    print(f"[{utc_timestamp()}] action={action}{identifiers} status={status}", file=sys.stderr)


def emit(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def load_acceptance_report_contract():
    """Load the executable grammar owned by writing-test-drafts."""

    module_name = "_codex_writing_test_acceptance_report"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    script = (
        Path(__file__).resolve().parents[2]
        / "writing-test-drafts"
        / "scripts"
        / "acceptance_report.py"
    )
    if not script.is_file():
        raise LedgerError(f"writing-test-drafts acceptance validator is missing: {script}")
    spec = importlib.util.spec_from_file_location(module_name, script)
    if spec is None or spec.loader is None:
        raise LedgerError("cannot load writing-test-drafts acceptance validator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as error:
        sys.modules.pop(module_name, None)
        raise LedgerError(
            f"cannot initialize writing-test-drafts acceptance validator: {error}"
        ) from error
    if not hasattr(module, "parse_test_draft") or not hasattr(
        module, "validate_acceptance_report"
    ):
        sys.modules.pop(module_name, None)
        raise LedgerError("writing-test-drafts acceptance validator has an invalid interface")
    return module


def validate_test_draft_contract(test_text: str) -> list[dict[str, object]]:
    contract = load_acceptance_report_contract()
    try:
        return contract.parse_test_draft(test_text)
    except contract.AcceptanceReportError as error:
        raise LedgerError(f"test draft invalid: {error}") from error


def validate_acceptance_report_contract(
    test_text: str,
    evidence_text: str,
    expected_change_id: str,
    expected_test_ref: str,
    expected_code_ref: str,
    *,
    require_passed: bool,
) -> dict[str, object]:
    contract = load_acceptance_report_contract()
    try:
        result = contract.validate_acceptance_report(
            test_text,
            evidence_text,
            expected_change_id,
            expected_test_ref,
            expected_code_ref,
            require_passed=require_passed,
        )
    except contract.AcceptanceReportError as error:
        raise LedgerError(f"acceptance report invalid: {error}") from error
    if not isinstance(result, dict):
        raise LedgerError("writing-test-drafts acceptance validator returned an invalid result")
    return result


def run_git(repo: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *arguments],
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise LedgerError(f"Git validation failed: {detail.strip()}") from error
    return result.stdout.strip()


def validate_git_vault(vault: Path, database: Path) -> None:
    if not vault.is_dir():
        raise LedgerError(f"spec_vault is not a directory: {vault}")
    root = Path(run_git(vault, "rev-parse", "--show-toplevel")).resolve()
    if root != vault.resolve():
        raise LedgerError("spec_vault must be the root of a Git repository")
    ignored = subprocess.run(
        ["git", "-C", str(vault), "check-ignore", "-q", "--", ".local"],
        capture_output=True,
    )
    if ignored.returncode != 0:
        raise LedgerError("Spec Vault .local must be excluded by Git ignore rules")
    tracked = run_git(vault, "ls-files", "--", ".local")
    if tracked:
        raise LedgerError("Spec Vault .local or its SQLite database is tracked by Git")
    try:
        database.resolve().relative_to((vault / ".local").resolve())
    except ValueError as error:
        raise LedgerError("database must be inside spec_vault/.local") from error


def load_runtime_config(args: argparse.Namespace) -> RuntimeConfig:
    if args.db:
        database = Path(args.db).expanduser()
        if not database.is_absolute():
            raise LedgerError("--db path must be absolute")
        return RuntimeConfig(database.resolve(), None, {})

    config_path = Path(args.config).expanduser()
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise LedgerError(f"workflow config not found: {config_path}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise LedgerError(f"cannot read workflow config: {error}") from error
    if not isinstance(payload, dict):
        raise LedgerError("workflow config must be a JSON object")
    vault_value = payload.get("spec_vault")
    database_value = payload.get("database")
    if not isinstance(vault_value, str) or not vault_value.strip():
        raise LedgerError("workflow config must contain a non-empty spec_vault")
    if not isinstance(database_value, str) or not database_value.strip():
        raise LedgerError("workflow config must contain a non-empty database")
    if PLACEHOLDER_PATTERN.search(vault_value) or PLACEHOLDER_PATTERN.search(database_value):
        raise LedgerError("workflow config contains a placeholder path")
    vault = Path(vault_value).expanduser()
    database = Path(database_value).expanduser()
    if not vault.is_absolute() or not database.is_absolute():
        raise LedgerError("spec_vault and database paths must be absolute")
    vault = vault.resolve()
    database = database.resolve()
    validate_git_vault(vault, database)

    repositories_value = payload.get("repositories", {})
    if not isinstance(repositories_value, dict):
        raise LedgerError("workflow config repositories must be an object")
    repositories: dict[str, Path] = {}
    for name, value in repositories_value.items():
        if not isinstance(name, str) or not name or not isinstance(value, str):
            raise LedgerError("repository mappings must use non-empty string names and paths")
        if not REPOSITORY_NAME_PATTERN.fullmatch(name):
            raise LedgerError(
                "repository mapping names must be stable identifiers using letters, digits, dot, underscore, or hyphen"
            )
        path = Path(value).expanduser()
        if not path.is_absolute() or PLACEHOLDER_PATTERN.search(value):
            raise LedgerError(f"repository path must be absolute and confirmed: {name}")
        repositories[name] = path.resolve()
    return RuntimeConfig(database, vault, repositories)


@contextmanager
def open_database(path: Path, *, readonly: bool = False):
    if readonly:
        if not path.exists():
            raise LedgerError("ledger database does not exist; run init first")
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=15)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def immediate_transaction(connection: sqlite3.Connection):
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def change_table_sql(name: str) -> str:
    return f"""
    CREATE TABLE {name} (
        change_id TEXT PRIMARY KEY,
        spec_ref TEXT,
        change_ref TEXT NOT NULL,
        plan_ref TEXT,
        test_ref TEXT,
        code_ref TEXT,
        evidence_ref TEXT,
        status TEXT NOT NULL CHECK (status IN ('in_progress', 'completed'))
    )
    """


def workflow_table_sql(name: str, change_table: str) -> str:
    pre = ", ".join(f"'{stage}'" for stage in PRE_EVENT_STAGES)
    formal = ", ".join(f"'{stage}'" for stage in FORMAL_STAGES)
    all_stages = ", ".join(f"'{stage}'" for stage in (*WORKFLOW_STAGES, "completed"))
    return f"""
    CREATE TABLE {name} (
        workflow_id TEXT PRIMARY KEY,
        change_id TEXT,
        current_stage TEXT NOT NULL CHECK (current_stage IN ({all_stages})),
        flow TEXT NOT NULL CHECK (flow IN ('direct', 'light', 'full')),
        review_mode TEXT NOT NULL CHECK (review_mode IN ('manual', 'auto')),
        state TEXT NOT NULL CHECK (state IN ('active', 'closed')),
        FOREIGN KEY (change_id) REFERENCES {change_table}(change_id),
        CHECK (
            (state = 'active' AND change_id IS NULL AND current_stage IN ({pre})) OR
            (state = 'active' AND change_id IS NOT NULL AND current_stage IN ({formal})) OR
            (state = 'closed' AND change_id IS NOT NULL AND current_stage = 'completed')
        )
    )
    """


def create_guards(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE UNIQUE INDEX one_active_workflow_per_change ON workflow_state(change_id) "
        "WHERE state = 'active' AND change_id IS NOT NULL"
    )
    connection.executescript(
        """
        CREATE TRIGGER completed_change_is_immutable
        BEFORE UPDATE ON change_ledger WHEN OLD.status = 'completed'
        BEGIN SELECT RAISE(ABORT, 'completed change is immutable'); END;
        CREATE TRIGGER completed_change_cannot_be_deleted
        BEFORE DELETE ON change_ledger WHEN OLD.status = 'completed'
        BEGIN SELECT RAISE(ABORT, 'completed change is immutable'); END;
        CREATE TRIGGER closed_workflow_is_immutable
        BEFORE UPDATE ON workflow_state WHEN OLD.state = 'closed'
        BEGIN SELECT RAISE(ABORT, 'closed workflow is immutable'); END;
        CREATE TRIGGER closed_workflow_cannot_be_deleted
        BEFORE DELETE ON workflow_state WHEN OLD.state = 'closed'
        BEGIN SELECT RAISE(ABORT, 'closed workflow is immutable'); END;
        """
    )


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def table_columns(connection: sqlite3.Connection, name: str) -> list[str]:
    return [row["name"] for row in connection.execute(f"PRAGMA table_info({name})")]


def preflight_migration(connection: sqlite3.Connection):
    required_change = {"change_id", "spec_ref", "change_ref", "test_ref", "code_ref", "evidence_ref", "status"}
    columns = set(table_columns(connection, "change_ledger"))
    if not required_change.issubset(columns) or not ({"plan_ref", "implementation_ref"} & columns):
        raise LedgerError("change_ledger schema cannot be migrated safely")
    change_rows = []
    for raw in connection.execute("SELECT * FROM change_ledger"):
        item = dict(raw)
        plan = item.get("plan_ref")
        implementation = item.get("implementation_ref")
        if plan and implementation and plan != implementation:
            raise LedgerError(
                f"migration conflict for {item['change_id']}: plan_ref and implementation_ref differ"
            )
        if item["status"] not in ("in_progress", "completed"):
            raise LedgerError(f"invalid change status during migration: {item['change_id']}")
        if not CHANGE_ID_PATTERN.fullmatch(item["change_id"]):
            raise LedgerError(f"invalid change_id during migration: {item['change_id']}")
        change_rows.append(
            {
                "change_id": item["change_id"],
                "spec_ref": item["spec_ref"],
                "change_ref": item["change_ref"],
                "plan_ref": plan or implementation,
                "test_ref": item["test_ref"],
                "code_ref": item["code_ref"],
                "evidence_ref": item["evidence_ref"],
                "status": item["status"],
            }
        )
    change_ids = {item["change_id"] for item in change_rows}
    change_statuses = {item["change_id"]: item["status"] for item in change_rows}

    workflow_rows = []
    if table_exists(connection, "workflow_state"):
        workflow_columns = table_columns(connection, "workflow_state")
        if workflow_columns not in (
            ["workflow_id", "change_id", "current_stage", "state"],
            ["workflow_id", "change_id", "current_stage", "flow", "review_mode", "state"],
        ):
            raise LedgerError("workflow_state schema cannot be migrated safely")
        active_bindings: set[str] = set()
        for raw in connection.execute("SELECT * FROM workflow_state"):
            item = dict(raw)
            stage = "writing_plan" if item["current_stage"] == "writing_implementation" else item["current_stage"]
            flow = item.get("flow", "full")
            review_mode = item.get("review_mode", "manual")
            if flow not in FLOWS:
                raise LedgerError(f"invalid workflow flow during migration: {item['workflow_id']}")
            if review_mode not in REVIEW_MODES:
                raise LedgerError(
                    f"invalid workflow review_mode during migration: {item['workflow_id']}"
                )
            if stage not in (*WORKFLOW_STAGES, "completed"):
                raise LedgerError(f"unknown stage during migration: {item['current_stage']}")
            if item["state"] not in ("active", "closed"):
                raise LedgerError(f"invalid workflow state during migration: {item['workflow_id']}")
            if item["change_id"] is not None and item["change_id"] not in change_ids:
                raise LedgerError(f"orphan workflow change_id during migration: {item['workflow_id']}")
            if item["state"] == "active" and item["change_id"] is not None:
                if item["change_id"] in active_bindings:
                    raise LedgerError(f"duplicate active workflow binding: {item['change_id']}")
                active_bindings.add(item["change_id"])
            structurally_valid = (
                item["state"] == "active" and item["change_id"] is None and stage in PRE_EVENT_STAGES
            ) or (
                item["state"] == "active" and item["change_id"] is not None and stage in FORMAL_STAGES
            ) or (
                item["state"] == "closed" and item["change_id"] is not None and stage == "completed"
            )
            if not structurally_valid:
                raise LedgerError(f"workflow binding/stage invariant violation: {item['workflow_id']}")
            if (
                item["state"] == "active"
                and item["change_id"] is not None
                and stage not in formal_stages_for_flow(flow)
            ):
                raise LedgerError(
                    f"workflow flow/stage invariant violation: {item['workflow_id']}"
                )
            if item["change_id"] is not None:
                change_status = change_statuses[item["change_id"]]
                if item["state"] == "active" and change_status != "in_progress":
                    raise LedgerError(
                        f"active workflow must bind an in-progress change: {item['workflow_id']}"
                    )
                if item["state"] == "closed" and change_status != "completed":
                    raise LedgerError(
                        f"closed workflow must bind a completed change: {item['workflow_id']}"
                    )
            workflow_rows.append(
                {
                    **item,
                    "current_stage": stage,
                    "flow": flow,
                    "review_mode": review_mode,
                }
            )
    completed_flows = {
        item["change_id"]: item["flow"]
        for item in workflow_rows
        if item["state"] == "closed" and item["change_id"] is not None
    }
    for item in change_rows:
        if item["status"] != "completed":
            continue
        flow = completed_flows.get(item["change_id"], "full")
        required = {
            "direct": ("change_ref", "code_ref"),
            "light": ("spec_ref", "change_ref", "code_ref"),
            "full": REFERENCE_FIELDS,
        }[flow]
        missing = [field for field in required if not item.get(field)]
        if missing:
            raise LedgerError(
                f"completed change has missing references during migration: {item['change_id']}: "
                + ", ".join(missing)
            )
    return change_rows, workflow_rows


def rebuild_canonical_schema(connection: sqlite3.Connection) -> None:
    if not table_exists(connection, "change_ledger"):
        connection.execute(change_table_sql("change_ledger"))
        connection.execute(workflow_table_sql("workflow_state", "change_ledger"))
        create_guards(connection)
        return

    change_rows, workflow_rows = preflight_migration(connection)
    connection.execute("DROP TABLE IF EXISTS workflow_state_new")
    connection.execute("DROP TABLE IF EXISTS change_ledger_new")
    connection.execute(change_table_sql("change_ledger_new"))
    connection.execute(workflow_table_sql("workflow_state_new", "change_ledger_new"))
    for item in change_rows:
        connection.execute(
            "INSERT INTO change_ledger_new VALUES (?,?,?,?,?,?,?,?)",
            tuple(item[field] for field in ("change_id", "spec_ref", "change_ref", "plan_ref", "test_ref", "code_ref", "evidence_ref", "status")),
        )
    for item in workflow_rows:
        connection.execute(
            "INSERT INTO workflow_state_new VALUES (?,?,?,?,?,?)",
            (
                item["workflow_id"],
                item["change_id"],
                item["current_stage"],
                item["flow"],
                item["review_mode"],
                item["state"],
            ),
        )
    if connection.execute("SELECT COUNT(*) FROM change_ledger_new").fetchone()[0] != len(change_rows):
        raise LedgerError("migration row-count verification failed for change_ledger")
    if connection.execute("SELECT COUNT(*) FROM workflow_state_new").fetchone()[0] != len(workflow_rows):
        raise LedgerError("migration row-count verification failed for workflow_state")
    if list(connection.execute("PRAGMA foreign_key_check(workflow_state_new)")):
        raise LedgerError("migration foreign-key validation failed")
    for trigger in (
        "completed_change_is_immutable",
        "completed_change_cannot_be_deleted",
        "closed_workflow_is_immutable",
        "closed_workflow_cannot_be_deleted",
    ):
        connection.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    connection.execute("DROP INDEX IF EXISTS one_active_workflow_per_change")
    if table_exists(connection, "workflow_state"):
        connection.execute("DROP TABLE workflow_state")
    connection.execute("DROP TABLE change_ledger")
    connection.execute("ALTER TABLE change_ledger_new RENAME TO change_ledger")
    connection.execute("ALTER TABLE workflow_state_new RENAME TO workflow_state")
    create_guards(connection)
    if list(connection.execute("PRAGMA foreign_key_check")):
        raise LedgerError("migration final foreign-key validation failed")


def require_schema(connection: sqlite3.Connection, *, workflow=False) -> None:
    if not table_exists(connection, "change_ledger"):
        raise LedgerError("ledger is not initialized; run init first")
    if workflow and not table_exists(connection, "workflow_state"):
        raise LedgerError("workflow state is not initialized; run init first")


def get_change(connection: sqlite3.Connection, change_id: str) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM change_ledger WHERE change_id=?", (change_id,)).fetchone()
    if row is None:
        raise LedgerError(f"change not found: {change_id}")
    return row


def get_workflow(connection: sqlite3.Connection, workflow_id: str) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM workflow_state WHERE workflow_id=?", (workflow_id,)).fetchone()
    if row is None:
        raise LedgerError(f"workflow not found: {workflow_id}")
    return row


def next_identifier(connection: sqlite3.Connection, table: str, column: str, prefix: str) -> str:
    pattern = CHANGE_ID_PATTERN if prefix == "CE" else WORKFLOW_ID_PATTERN
    maximum = 0
    for row in connection.execute(f"SELECT {column} FROM {table}"):
        match = pattern.fullmatch(row[0])
        if match:
            maximum = max(maximum, int(match.group(1)))
    return f"{prefix}-{maximum + 1:04d}"


def split_reference(value: str, expected: str) -> tuple[str, str]:
    locator, separator, sha = value.rpartition("@")
    if not separator or not locator or not SHA_PATTERN.fullmatch(sha):
        raise LedgerError(f"{expected} reference must use {expected}@git-sha")
    return locator, sha.lower()


def resolve_exact_commit(repo: Path, sha: str) -> str:
    resolved = run_git(repo, "rev-parse", "--verify", f"{sha}^{{commit}}").lower()
    if resolved != sha.lower():
        raise LedgerError("formal references must use the full exact Git commit SHA")
    return resolved


def validate_vault_role(field: str, normalized: str, change_id: str | None) -> None:
    if change_id is None:
        raise LedgerError(f"{field} requires a controller-provided change_id")
    if field == "change_ref":
        if normalized != f"changes/{change_id}/change.md":
            raise LedgerError("change_ref must use changes/<change_id>/change.md@<full-git-sha>")
        return
    canonical = {
        "spec_ref": f"specs/{change_id}.md",
        "plan_ref": f"plans/{change_id}.md",
        "test_ref": f"tests/{change_id}.md",
    }
    if field in canonical:
        if normalized != canonical[field]:
            role = {
                "spec_ref": "specs/<change_id>.md",
                "plan_ref": "plans/<change_id>.md",
                "test_ref": "tests/<change_id>.md",
            }[field]
            raise LedgerError(f"{field} must use {role}@<full-git-sha>")
        return
    if field == "evidence_ref":
        if not normalized.startswith(f"acceptance/{change_id}/"):
            raise LedgerError(
                "evidence_ref must use acceptance/<change_id>/<run>.md@<full-git-sha>"
            )
        return
    raise LedgerError(f"unknown Vault material role: {field}")


def validate_vault_reference(
    config: RuntimeConfig,
    field: str,
    value: str,
    change_id: str | None = None,
) -> None:
    if config.spec_vault is None:
        raise LedgerError("spec_vault is required to validate vault references")
    locator, sha = split_reference(value, "vault-relative-path")
    normalized = locator.replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized.endswith(".md") or normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized) or ".." in path.parts:
        raise LedgerError("vault reference must use a safe vault-relative-path.md@git-sha")
    validate_vault_role(field, normalized, change_id)
    resolve_exact_commit(config.spec_vault, sha)
    run_git(config.spec_vault, "cat-file", "-e", f"{sha}:{normalized}")


def resolve_code_repository(config: RuntimeConfig, locator: str) -> Path:
    if locator not in config.repositories:
        raise LedgerError(f"code repository is not configured: {locator}")
    repository = config.repositories[locator]
    root = Path(run_git(repository, "rev-parse", "--show-toplevel")).resolve()
    if root != repository.resolve():
        raise LedgerError(f"code repository locator is not a Git root: {locator}")
    return repository


def validate_code_reference(config: RuntimeConfig, value: str) -> None:
    locator, sha = split_reference(value, "repository")
    repository = resolve_code_repository(config, locator)
    resolve_exact_commit(repository, sha)


def git_common_directory(repository: Path) -> Path:
    raw = Path(run_git(repository, "rev-parse", "--git-common-dir"))
    if not raw.is_absolute():
        raw = repository / raw
    return raw.resolve()


def resolve_code_ref_from_worktree(
    config: RuntimeConfig, worktree_value: str
) -> dict[str, object]:
    candidate = Path(worktree_value).expanduser()
    if not candidate.is_absolute() or not candidate.is_dir():
        raise LedgerError("--worktree must be an existing absolute Git worktree root")
    worktree = candidate.resolve()
    root = Path(run_git(worktree, "rev-parse", "--show-toplevel")).resolve()
    if root != worktree:
        raise LedgerError("--worktree must point to the Git worktree root")

    common = git_common_directory(worktree)
    matches: list[str] = []
    for name in config.repositories:
        repository = resolve_code_repository(config, name)
        if git_common_directory(repository) == common:
            matches.append(name)
    if not matches:
        raise LedgerError(
            "worktree Git common directory does not match a configured repository"
        )
    if len(matches) != 1:
        raise LedgerError(
            "worktree Git common directory matches multiple configured repositories: "
            + ", ".join(sorted(matches))
        )
    commit_sha = run_git(worktree, "rev-parse", "HEAD").lower()
    if not SHA_PATTERN.fullmatch(commit_sha):
        raise LedgerError("worktree HEAD is not a full Git commit object ID")
    resolve_exact_commit(worktree, commit_sha)
    branch = run_git(worktree, "branch", "--show-current") or None
    dirty = bool(run_git(worktree, "status", "--porcelain", "--untracked-files=all"))
    repository_name = matches[0]
    return {
        "branch": branch,
        "code_ref": f"{repository_name}@{commit_sha}",
        "commit_sha": commit_sha,
        "detached": branch is None,
        "dirty": dirty,
        "repository": repository_name,
        "worktree": str(worktree),
    }


def validate_reference(
    config: RuntimeConfig,
    field: str,
    value: str,
    change_id: str | None = None,
) -> None:
    if field == "code_ref":
        validate_code_reference(config, value)
    else:
        validate_vault_reference(config, field, value, change_id)


def read_vault_blob(config: RuntimeConfig, field: str, value: str, change_id: str) -> str:
    validate_vault_reference(config, field, value, change_id)
    locator, sha = split_reference(value, "vault-relative-path")
    normalized = locator.replace("\\", "/")
    try:
        result = subprocess.run(
            ["git", "-C", str(config.spec_vault), "show", f"{sha}:{normalized}"],
            capture_output=True,
            check=True,
        )
        return result.stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError) as error:
        detail_bytes = getattr(error, "stderr", b"")
        detail = (
            detail_bytes.decode("utf-8", errors="replace")
            if isinstance(detail_bytes, bytes)
            else str(detail_bytes or error)
        )
        raise LedgerError(f"cannot read exact UTF-8 Vault blob: {detail.strip()}") from error


def read_vault_path_at_commit(
    config: RuntimeConfig,
    sha: str,
    relative_path: str,
    document: str,
) -> str:
    if config.spec_vault is None:
        raise LedgerError("spec_vault is required to read Vault documents")
    normalized = relative_path.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized.endswith(".md")
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized)
        or ".." in path.parts
    ):
        raise LedgerError(f"{document} must use a safe Vault-relative Markdown path")
    resolve_exact_commit(config.spec_vault, sha)
    try:
        result = subprocess.run(
            ["git", "-C", str(config.spec_vault), "show", f"{sha}:{normalized}"],
            capture_output=True,
            check=True,
        )
        return result.stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError) as error:
        detail_bytes = getattr(error, "stderr", b"")
        detail = (
            detail_bytes.decode("utf-8", errors="replace")
            if isinstance(detail_bytes, bytes)
            else str(detail_bytes or error)
        )
        raise LedgerError(
            f"cannot read {document} at {normalized}@{sha}: {detail.strip()}"
        ) from error


def strip_fenced_blocks(text: str) -> str:
    visible: list[str] = []
    fence: tuple[str, int] | None = None
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = (token[0], len(token))
            elif token[0] == fence[0] and len(token) >= fence[1]:
                fence = None
            continue
        if fence is None:
            visible.append(line)
    return "\n".join(visible)


def parse_frontmatter(text: str, document: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise LedgerError(f"{document} must start with YAML frontmatter")
    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration as error:
        raise LedgerError(f"{document} frontmatter is not closed") from error
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*?)\s*", line)
        if not match:
            raise LedgerError(f"{document} frontmatter must use scalar key: value fields")
        key, value = match.groups()
        if key in fields:
            raise LedgerError(f"duplicate {document} frontmatter field: {key}")
        fields[key] = value
    return fields, "\n".join(lines[end + 1 :])


def normalized_block(lines: list[str]) -> tuple[str, ...]:
    return tuple(line.strip() for line in lines if line.strip())


def require_meaningful(lines: list[str], label: str, *, allow_none: bool = False) -> None:
    normalized = normalized_block(lines)
    plain = " ".join(re.sub(r"^[-*+]\s*", "", line) for line in normalized).strip()
    empty_values = {"", "-", "—", "n/a", "none"}
    if not allow_none:
        empty_values.add("无")
    if plain.lower() in empty_values or PLACEHOLDER_PATTERN.search(plain):
        raise LedgerError(f"{label} must contain a concrete value")


def validate_change_document(
    text: str,
    change_id: str,
    *,
    final: bool,
    expected_source_ce: str | None = None,
    require_source_ce: bool = False,
) -> dict[str, str]:
    fields, _ = parse_frontmatter(text, "change document")
    if fields.get("change_id") != change_id:
        raise LedgerError("change document change_id does not match ledger change_id")
    if require_source_ce and "source_ce" not in fields:
        raise LedgerError("change document must declare source_ce as null or CE-0001")
    source_ce = fields.get("source_ce", "null")
    if source_ce != "null":
        if not CHANGE_ID_PATTERN.fullmatch(source_ce):
            raise LedgerError("change document source_ce must be null or use CE-0001 format")
        if source_ce == change_id:
            raise LedgerError("change document source_ce cannot reference itself")
    if expected_source_ce is not None and source_ce != expected_source_ce:
        raise LedgerError("change document source_ce does not match --source-ce")
    fields["source_ce"] = source_ce
    expected_status = "completed" if final else "in_progress"
    if fields.get("status") != expected_status:
        raise LedgerError("change document status does not match its ledger lifecycle")
    return fields


def validate_final_change_logic_link(text: str, change_id: str) -> None:
    body = normalized_block(
        single_section_body(text, "## 最终逻辑稿", "final change document")
    )
    expected = f"- logic/{change_id}.md"
    if body != (expected,):
        raise LedgerError(
            "final change document 最终逻辑稿 must contain exactly " + expected
        )


def validate_final_logic_document(text: str, change_id: str) -> None:
    visible = strip_fenced_blocks(text)
    lines = visible.splitlines()
    expected_h1 = f"# {change_id} 最终逻辑稿"
    h1_headings = [
        line.strip() for line in lines if re.fullmatch(r"#\s+.+", line.strip())
    ]
    if h1_headings != [expected_h1]:
        raise LedgerError(
            "final logic draft identity heading must be exactly " + expected_h1
        )

    h2_headings = [
        line.strip() for line in lines if re.fullmatch(r"##\s+.+", line.strip())
    ]
    if h2_headings not in (["## 功能逻辑"], ["## 功能逻辑", "## 注意事项"]):
        raise LedgerError(
            "final logic draft must contain one ## 功能逻辑 and at most one later ## 注意事项"
        )

    function_logic = single_section_body(
        visible,
        "## 功能逻辑",
        "final logic draft",
    )
    require_meaningful(function_logic, "final logic draft ## 功能逻辑")
    if "## 注意事项" in h2_headings:
        attention = single_section_body(
            visible,
            "## 注意事项",
            "final logic draft",
        )
        require_meaningful(attention, "final logic draft ## 注意事项")


def validate_history_summary(text: str, *, expected_source_ce: str) -> None:
    lines = single_section_body(text, "## 修改与验证摘要", "final change document")
    values: dict[str, str] = {}
    for raw in lines:
        line = re.sub(r"^[-*+]\s*", "", raw.strip())
        if not line:
            continue
        match = re.fullmatch(r"(类型|模块|问题|修改|验证|来源)[：:]\s*(.+)", line)
        if match:
            key, value = match.groups()
            if key in values:
                raise LedgerError(f"duplicate history summary field: {key}")
            require_meaningful([value], f"history summary {key}")
            values[key] = value
    missing = [key for key in ("类型", "模块", "问题", "修改", "验证") if key not in values]
    if missing:
        raise LedgerError("history summary missing fields: " + ", ".join(missing))
    if values["类型"] not in ("Bug", "小需求"):
        raise LedgerError("history summary 类型 must be Bug or 小需求")
    if expected_source_ce == "null":
        if "来源" in values:
            raise LedgerError("history summary 来源 must be omitted when source_ce is null")
    elif values.get("来源") != expected_source_ce:
        raise LedgerError("history summary 来源 must exactly match source_ce")


def ordered_section_bodies(
    text: str,
    headings: tuple[str, ...],
    document: str,
) -> dict[str, list[str]]:
    lines = strip_fenced_blocks(text).splitlines()
    positions: dict[str, int] = {}
    for heading in headings:
        matches = [index for index, line in enumerate(lines) if line.strip() == heading]
        if len(matches) != 1:
            raise LedgerError(f"{document} must contain one {heading} section")
        positions[heading] = matches[0]
    ordered = [positions[heading] for heading in headings]
    if ordered != sorted(ordered):
        raise LedgerError(f"{document} sections must use the canonical order")
    bodies: dict[str, list[str]] = {}
    for heading in headings:
        start = positions[heading] + 1
        end = next(
            (
                index
                for index in range(start, len(lines))
                if re.fullmatch(r"##\s+.+", lines[index].strip())
            ),
            len(lines),
        )
        bodies[heading] = lines[start:end]
    return bodies


def single_section_body(
    text: str,
    heading: str,
    document: str,
    *,
    additional_stop_pattern: str | None = None,
) -> list[str]:
    lines = strip_fenced_blocks(text).splitlines()
    matches = [index for index, line in enumerate(lines) if line.strip() == heading]
    if len(matches) != 1:
        raise LedgerError(f"{document} must contain one {heading} section")
    start = matches[0] + 1
    end = next(
        (
            index
            for index in range(start, len(lines))
            if re.fullmatch(r"##\s+.+", lines[index].strip())
            or (
                additional_stop_pattern is not None
                and re.fullmatch(additional_stop_pattern, lines[index].strip())
            )
        ),
        len(lines),
    )
    return lines[start:end]


def parse_contract_table(
    lines: list[str],
    headers: tuple[str, ...],
    label: str,
) -> list[dict[str, str]]:
    meaningful = [line.strip() for line in lines if line.strip()]
    if not meaningful or any(
        not (line.startswith("|") and line.endswith("|")) for line in meaningful
    ):
        raise LedgerError(f"{label} must use the canonical Markdown table")
    rows = [tuple(cell.strip() for cell in line[1:-1].split("|")) for line in meaningful]
    if len(rows) < 3 or rows[0] != headers:
        raise LedgerError(f"{label} table headers must use the canonical order")
    if len(rows[1]) != len(headers) or any(
        re.fullmatch(r":?-{3,}:?", cell) is None for cell in rows[1]
    ):
        raise LedgerError(f"{label} table separator is invalid")
    parsed: list[dict[str, str]] = []
    for row in rows[2:]:
        if len(row) != len(headers):
            raise LedgerError(f"{label} table rows must contain {len(headers)} cells")
        if any(not cell or PLACEHOLDER_PATTERN.search(cell) for cell in row):
            raise LedgerError(f"{label} table cells must contain concrete values")
        parsed.append(dict(zip(headers, row)))
    if not parsed:
        raise LedgerError(f"{label} table must contain at least one data row")
    return parsed


def validate_spec_document(text: str) -> str:
    visible = strip_fenced_blocks(text)
    lines = visible.splitlines()
    if not any(re.fullmatch(r"# Spec[：:].+", line.strip()) for line in lines):
        raise LedgerError("spec must start with a named # Spec heading")
    headings = (
        "## 功能目标",
        "## 输入与触发条件",
        "## 行为规则",
        "## 输出与状态变化",
        "## 边界",
        "## 可能的影响范围（非行为契约）",
    )
    bodies = ordered_section_bodies(visible, headings, "spec")
    for heading in headings:
        if heading != "## 行为规则":
            require_meaningful(bodies[heading], f"spec {heading}")

    behavior_lines = bodies["## 行为规则"]
    rule_positions = [
        index
        for index, line in enumerate(behavior_lines)
        if re.fullmatch(r"### 规则[：:].+", line.strip())
    ]
    if not rule_positions:
        raise LedgerError("spec must contain at least one named behavior rule")
    for index, start in enumerate(rule_positions):
        end = rule_positions[index + 1] if index + 1 < len(rule_positions) else len(behavior_lines)
        rule_lines = behavior_lines[start + 1 : end]
        markers = ("当：", "系统必须：", "结果：")
        marker_positions: list[int] = []
        for marker in markers:
            matches = [position for position, line in enumerate(rule_lines) if line.strip() == marker]
            if len(matches) != 1:
                raise LedgerError(f"spec rule must contain one non-empty {marker} field")
            marker_positions.append(matches[0])
        if marker_positions != sorted(marker_positions):
            raise LedgerError("spec rule fields must use the canonical order")
        for marker_index, marker in enumerate(markers):
            field_start = marker_positions[marker_index] + 1
            field_end = (
                marker_positions[marker_index + 1]
                if marker_index + 1 < len(markers)
                else len(rule_lines)
            )
            require_meaningful(rule_lines[field_start:field_end], f"spec rule {marker}")

    impact_lines = bodies["## 可能的影响范围（非行为契约）"]
    baseline_matches = [
        re.fullmatch(r"\s*-\s*代码基线：`([^`]+)`\s*", line)
        for line in impact_lines
    ]
    baselines = [match.group(1) for match in baseline_matches if match]
    if len(baselines) != 1:
        raise LedgerError("spec impact range must contain one parseable code baseline")
    split_reference(baselines[0], "repository")
    table_rows = []
    for line in impact_lines:
        if line.strip().startswith("|") and line.strip().endswith("|"):
            table_rows.append([cell.strip() for cell in line.strip()[1:-1].split("|")])
    candidates = [
        row
        for row in table_rows[2:]
        if len(row) == 4
        and all(cell and not re.fullmatch(r"-+", cell) for cell in row)
        and not any(PLACEHOLDER_PATTERN.search(cell) for cell in row)
    ]
    if not candidates:
        raise LedgerError("spec impact range must contain at least one concrete candidate")
    return baselines[0]


def validate_light_spec_document(text: str) -> None:
    visible = strip_fenced_blocks(text)
    lines = visible.splitlines()
    if not any(re.fullmatch(r"# Spec[：:].+", line.strip()) for line in lines):
        raise LedgerError("light spec must start with a named # Spec heading")
    required = (
        "## 要解决的问题",
        "## 触发条件",
        "## 期望行为",
        "## 本次范围",
        "## 完成条件",
    )
    bodies = ordered_section_bodies(visible, required, "light spec")
    for heading in required:
        require_meaningful(bodies[heading], f"light spec {heading}")
    optional = [line for line in lines if line.strip() == "## 必须保持不变"]
    if len(optional) > 1:
        raise LedgerError("light spec may contain at most one ## 必须保持不变 section")
    if optional:
        require_meaningful(
            single_section_body(visible, "## 必须保持不变", "light spec"),
            "light spec ## 必须保持不变",
        )
    if "## 既有功能与流程影响" in visible or "## 可能的影响范围（非行为契约）" in visible:
        raise LedgerError("light spec must not include full-profile impact sections")


def validate_spec_impact_contract(text: str) -> dict[str, str]:
    heading = "## 既有功能与流程影响"
    lines = single_section_body(text, heading, "spec")
    visible_lines = strip_fenced_blocks(text).splitlines()
    boundary_position = next(
        index for index, line in enumerate(visible_lines) if line.strip() == "## 边界"
    )
    impact_position = next(
        index for index, line in enumerate(visible_lines) if line.strip() == heading
    )
    code_impact_position = next(
        index
        for index, line in enumerate(visible_lines)
        if line.strip() == "## 可能的影响范围（非行为契约）"
    )
    if not boundary_position < impact_position < code_impact_position:
        raise LedgerError("spec impact sections must use the canonical order")
    meaningful = [line.strip() for line in lines if line.strip()]
    no_impact = "- 结论：未发现与本需求直接关联的既有功能或流程。"
    if meaningful == [no_impact]:
        return {}
    if no_impact in meaningful:
        raise LedgerError(
            "spec 既有功能与流程影响 cannot combine the no-impact conclusion with a table"
        )
    headers = (
        "impact_id",
        "既有功能或流程",
        "当前行为",
        "与新需求的交点",
        "影响结论",
        "Spec 处理",
    )
    rows = parse_contract_table(lines, headers, "spec 既有功能与流程影响")
    impact_conclusions: dict[str, str] = {}
    for row in rows:
        impact_id = row["impact_id"]
        if re.fullmatch(r"I-[0-9]{3,}", impact_id) is None:
            raise LedgerError("spec impact_id must use stable I-001 format")
        if impact_id in impact_conclusions:
            raise LedgerError(f"duplicate spec impact_id: {impact_id}")
        if row["影响结论"] not in ("保持不变", "兼容扩展", "明确改变"):
            raise LedgerError(f"spec {impact_id} 影响结论 is invalid")
        impact_conclusions[impact_id] = row["影响结论"]
        if row["Spec 处理"] not in ("无需修改", "已写入规则或边界"):
            raise LedgerError(f"spec {impact_id} Spec 处理 is invalid")
        if row["影响结论"] == "明确改变" and row["Spec 处理"] != "已写入规则或边界":
            raise LedgerError(
                f"spec {impact_id} 明确改变 must be 已写入规则或边界"
            )
    return impact_conclusions


def validate_plan_document(text: str) -> tuple[str, ...]:
    visible = strip_fenced_blocks(text)
    if PLAN_PLACEHOLDER_PATTERN.search(visible):
        raise LedgerError("plan must not contain placeholders")
    lines = visible.splitlines()
    h1 = [line for line in lines if re.fullmatch(r"# .+ Implementation Plan", line.strip())]
    if len(h1) != 1:
        raise LedgerError("plan must contain one named # ... Implementation Plan heading")
    field_positions: list[int] = []
    for field in ("Goal", "Architecture", "Tech Stack"):
        matches = [
            (index, match.group(1))
            for index, line in enumerate(lines)
            if (match := re.fullmatch(rf"\*\*{re.escape(field)}:\*\*\s*(.+?)\s*", line))
        ]
        if len(matches) != 1:
            raise LedgerError(f"plan must contain one non-empty {field} field")
        require_meaningful([matches[0][1]], f"plan {field}")
        field_positions.append(matches[0][0])
    global_matches = [index for index, line in enumerate(lines) if line.strip() == "## Global Constraints"]
    if len(global_matches) != 1 or field_positions != sorted(field_positions):
        raise LedgerError("plan header fields must use the canonical order")
    task_matches = [
        (index, match.group(1))
        for index, line in enumerate(lines)
        if (match := re.fullmatch(r"### Task (\d+):\s*.+", line.strip()))
    ]
    if not task_matches:
        raise LedgerError("plan must contain at least one named Task N")
    task_numbers = [task_number for _, task_number in task_matches]
    if any(
        int(task_number) < 1 or task_number != str(int(task_number))
        for task_number in task_numbers
    ):
        raise LedgerError("plan Task N numbers must use canonical decimal integers from 1")
    if len(task_numbers) != len(set(task_numbers)):
        raise LedgerError("plan must not contain duplicate Task N numbers")
    if global_matches[0] >= task_matches[0][0]:
        raise LedgerError("plan Global Constraints must precede tasks")
    global_end = next(
        (
            index
            for index in range(global_matches[0] + 1, task_matches[0][0] + 1)
            if re.fullmatch(r"(?:##\s+.+|### Task [0-9]+:\s*.+)", lines[index].strip())
        ),
        task_matches[0][0],
    )
    require_meaningful(
        lines[global_matches[0] + 1 : global_end],
        "plan Global Constraints",
    )
    target_paths: list[str] = []
    for task_index, (start, _) in enumerate(task_matches):
        end = task_matches[task_index + 1][0] if task_index + 1 < len(task_matches) else len(lines)
        task_lines = lines[start + 1 : end]
        files = [index for index, line in enumerate(task_lines) if line.strip() == "**Files:**"]
        interfaces = [
            index for index, line in enumerate(task_lines) if line.strip() == "**Interfaces:**"
        ]
        if len(files) != 1 or len(interfaces) != 1 or files[0] >= interfaces[0]:
            raise LedgerError("each plan task must contain ordered Files and Interfaces blocks")
        file_entries = [
            match.group(1)
            for line in task_lines[files[0] + 1 : interfaces[0]]
            if (match := re.fullmatch(
                r"\s*-\s*(?:Create|Modify|Test):\s*`([^`]+)`\s*", line
            ))
        ]
        if not file_entries:
            raise LedgerError("each plan task must name at least one exact file")
        target_paths.extend(file_entries)
        interface_text = task_lines[interfaces[0] + 1 :]
        consumes = [
            match.group(1)
            for line in interface_text
            if (match := re.fullmatch(
                r"\s*-\s*Consumes:\s*(\S(?:.*\S)?)\s*",
                line,
            ))
        ]
        produces = [
            match.group(1)
            for line in interface_text
            if (match := re.fullmatch(
                r"\s*-\s*Produces:\s*(\S(?:.*\S)?)\s*",
                line,
            ))
        ]
        checkboxes = [
            line
            for line in task_lines
            if re.fullmatch(r"\s*- \[ \] \*\*Step \d+:\s*.+\*\*\s*", line)
        ]
        if len(consumes) != 1 or len(produces) != 1 or not checkboxes:
            raise LedgerError(
                "each plan task must contain exactly one non-empty Consumes and Produces interface and at least one checkbox step"
            )
    return tuple(target_paths)


def validate_plan_compatibility_contract(
    spec_text: str,
    plan_text: str,
) -> None:
    spec_impacts = validate_spec_impact_contract(spec_text)
    spec_impact_ids = tuple(spec_impacts)
    heading = "## 实现兼容性分析"
    lines = single_section_body(
        plan_text,
        heading,
        "plan",
        additional_stop_pattern=r"(?:---|### Task [0-9]+:\s*.+)",
    )
    visible_lines = strip_fenced_blocks(plan_text).splitlines()
    global_position = next(
        index
        for index, line in enumerate(visible_lines)
        if line.strip() == "## Global Constraints"
    )
    compatibility_position = next(
        index for index, line in enumerate(visible_lines) if line.strip() == heading
    )
    first_task_position = next(
        index
        for index, line in enumerate(visible_lines)
        if re.fullmatch(r"### Task [0-9]+:\s*.+", line.strip())
    )
    if not global_position < compatibility_position < first_task_position:
        raise LedgerError("plan compatibility analysis must precede plan tasks")
    meaningful = [line.strip() for line in lines if line.strip()]
    evidence_prefix = "- 无交点代码证据："
    evidence_lines = [line for line in meaningful if line.startswith(evidence_prefix)]
    if evidence_lines:
        if len(meaningful) != 1 or len(evidence_lines) != 1:
            raise LedgerError(
                "plan 实现兼容性分析 cannot combine no-intersection evidence with a table"
            )
        evidence = evidence_lines[0][len(evidence_prefix) :].strip()
        evidence_parts = tuple(part.strip() for part in evidence.split("|"))
        expected_baseline = validate_spec_document(spec_text)
        if (
            len(evidence_parts) != 3
            or evidence_parts[0] != expected_baseline
            or re.fullmatch(r"`[^`]+`", evidence_parts[1]) is None
        ):
            raise LedgerError(
                "plan no-intersection code evidence must use baseline | `path-or-symbol` | reason"
            )
        require_meaningful(
            [evidence_parts[2]],
            "plan no-intersection code evidence reason",
        )
        if spec_impact_ids:
            raise LedgerError(
                "plan no-intersection evidence cannot replace Spec impact_id coverage"
            )
        return

    headers = (
        "来源影响项",
        "现有代码或方法",
        "新方案交点",
        "技术影响",
        "处理方式",
        "对应任务",
    )
    rows = parse_contract_table(lines, headers, "plan 实现兼容性分析")
    task_ids = {
        match.group(1)
        for line in strip_fenced_blocks(plan_text).splitlines()
        if (match := re.fullmatch(r"### Task ([0-9]+):\s*.+", line.strip()))
    }
    allowed_sources = set(spec_impact_ids) | {"implementation-only"}
    covered: set[str] = set()
    technical_impacts: dict[str, set[str]] = {}
    for row in rows:
        source = row["来源影响项"]
        if source not in allowed_sources:
            if re.fullmatch(r"I-[0-9]{3,}", source):
                raise LedgerError(f"plan references unknown Spec impact_id {source}")
            raise LedgerError(
                "plan 来源影响项 must be a Spec impact_id or implementation-only"
            )
        if source != "implementation-only":
            covered.add(source)
        technical_impact = row["技术影响"]
        if technical_impact not in ("无影响", "需要适配", "需要迁移", "阻塞"):
            raise LedgerError(f"plan {source} 技术影响 is invalid")
        technical_impacts.setdefault(source, set()).add(technical_impact)
        require_meaningful([row["处理方式"]], f"plan {source} 处理方式")
        task = row["对应任务"]
        if technical_impact == "阻塞":
            raise LedgerError(f"plan {source} 技术影响 is 阻塞")
        if technical_impact == "无影响":
            if task != "无需任务":
                raise LedgerError(f"plan {source} 无影响 must use 对应任务 无需任务")
            continue
        task_match = re.fullmatch(r"Task ([0-9]+)", task)
        if task_match is None:
            raise LedgerError(
                f"plan {source} {technical_impact} must map to an existing Task N"
            )
        if task_match.group(1) not in task_ids:
            raise LedgerError(f"plan {source} references missing {task}")

    missing = [impact_id for impact_id in spec_impact_ids if impact_id not in covered]
    if missing:
        raise LedgerError(
            "plan does not cover Spec impact_id: " + ", ".join(missing)
        )
    for impact_id, conclusion in spec_impacts.items():
        if conclusion == "明确改变" and not technical_impacts.get(
            impact_id, set()
        ).intersection(("需要适配", "需要迁移")):
            raise LedgerError(
                f"plan {impact_id} explicit behavior change requires adaptation or migration Task N"
            )


def validate_plan_baseline_contract(
    config: RuntimeConfig,
    spec_text: str,
    plan_text: str,
) -> None:
    heading = "## 开发基线"
    lines = single_section_body(plan_text, heading, "plan")
    known_fields = {
        "base_source",
        "base_locator",
        "base_sha",
        "base_remote",
        "base_branch",
        "base_worktree",
        "base_local_branch",
        "base_detached_sha",
    }
    fields: dict[str, str] = {}
    for line in lines:
        match = re.fullmatch(
            r"\s*(?:-\s*)?`?(base_[a-z_]+)`?\s*:\s*(.+?)\s*",
            line,
        )
        if match is None or match.group(1) not in known_fields:
            continue
        key, value = match.groups()
        value = value.strip()
        if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
            value = value[1:-1].strip()
        if key in fields:
            raise LedgerError(f"plan 开发基线 contains duplicate {key}")
        require_meaningful([value], f"plan 开发基线 {key}")
        fields[key] = value

    required = ("base_source", "base_locator", "base_sha")
    missing = [field for field in required if field not in fields]
    if missing:
        raise LedgerError("plan 开发基线 is missing " + ", ".join(missing))
    if fields["base_source"] not in ("remote", "local"):
        raise LedgerError("plan base_source must be remote or local")
    if re.fullmatch(r"[0-9a-fA-F]{40}", fields["base_sha"]) is None:
        raise LedgerError("plan base_sha must be a full 40-character Git commit SHA")

    visible_lines = strip_fenced_blocks(plan_text).splitlines()
    global_position = next(
        index
        for index, line in enumerate(visible_lines)
        if line.strip() == "## Global Constraints"
    )
    baseline_position = next(
        index for index, line in enumerate(visible_lines) if line.strip() == heading
    )
    compatibility_position = next(
        index
        for index, line in enumerate(visible_lines)
        if line.strip() == "## 实现兼容性分析"
    )
    first_task_position = next(
        index
        for index, line in enumerate(visible_lines)
        if re.fullmatch(r"### Task [0-9]+:\s*.+", line.strip())
    )
    if not global_position < baseline_position < compatibility_position < first_task_position:
        raise LedgerError(
            "plan 开发基线 must follow Global Constraints and precede compatibility analysis and tasks"
        )

    source = fields["base_source"]
    if source == "remote":
        missing_remote = [
            field for field in ("base_remote", "base_branch") if field not in fields
        ]
        if missing_remote:
            raise LedgerError(
                "remote plan 开发基线 is missing " + ", ".join(missing_remote)
            )
    else:
        missing_local = [
            field
            for field in ("base_worktree", "base_local_branch", "base_detached_sha")
            if field not in fields
        ]
        if missing_local:
            raise LedgerError(
                "local plan 开发基线 is missing " + ", ".join(missing_local)
            )
        if not Path(fields["base_worktree"]).is_absolute():
            raise LedgerError("plan base_worktree must be an absolute path")
        local_branch = fields["base_local_branch"]
        detached_sha = fields["base_detached_sha"]
        if (local_branch == "null") == (detached_sha == "null"):
            raise LedgerError(
                "local plan baseline must identify exactly one branch or detached SHA"
            )
        if detached_sha != "null" and detached_sha.lower() != fields["base_sha"].lower():
            raise LedgerError("plan base_detached_sha must equal base_sha")

    spec_baseline = validate_spec_document(spec_text)
    repository_name, _ = split_reference(spec_baseline, "repository")
    validate_code_reference(
        config,
        f"{repository_name}@{fields['base_sha'].lower()}",
    )


def resolve_plan_targets(code_repository: Path, plan_paths: tuple[str, ...]) -> tuple[Path, ...]:
    targets: list[Path] = []
    repository = code_repository.resolve()
    for raw_path in plan_paths:
        without_lines = re.sub(r":\d+(?:-\d+)?$", "", raw_path.strip())
        path = Path(without_lines)
        candidate = path.resolve() if path.is_absolute() else (repository / path).resolve()
        try:
            candidate.relative_to(repository)
        except ValueError as error:
            raise LedgerError(f"plan file path escapes code repository: {raw_path}") from error
        targets.append(candidate)
    return tuple(targets)


def discover_applicable_agents(
    workspace_root: Path,
    code_repository: Path,
    targets: tuple[Path, ...],
) -> set[Path]:
    workspace = workspace_root.resolve()
    repository = code_repository.resolve()
    try:
        repository.relative_to(workspace)
    except ValueError as error:
        raise LedgerError("code repository must be inside workspace_root") from error
    discovered: set[Path] = set()
    for target in targets:
        try:
            relative_parent = target.parent.relative_to(workspace)
        except ValueError as error:
            raise LedgerError("plan target must be inside workspace_root") from error
        directory = workspace
        candidates = [directory]
        for part in relative_parent.parts:
            directory = directory / part
            candidates.append(directory)
        for candidate_directory in candidates:
            agents_file = candidate_directory / "AGENTS.md"
            if agents_file.is_file():
                discovered.add(agents_file.resolve())
    return discovered


def snapshot_agents_inventory(paths: set[Path]) -> list[str]:
    inventory: list[str] = []
    for path in sorted(paths, key=lambda item: str(item).lower()):
        try:
            content = path.read_bytes()
        except OSError as error:
            raise LedgerError(f"cannot fully read AGENTS file: {path}") from error
        inventory.append(f"{path}@{hashlib.sha256(content).hexdigest()}")
    return inventory


def validate_plan_execution_context(
    config: RuntimeConfig,
    change_id: str,
    spec_ref: str,
    plan_ref: str,
) -> list[str]:
    if config.spec_vault is None:
        raise LedgerError("spec_vault is required to validate Plan execution context")
    spec_text = read_vault_blob(config, "spec_ref", spec_ref, change_id)
    code_baseline = validate_spec_document(spec_text)
    validate_code_reference(config, code_baseline)
    repository_name, _ = split_reference(code_baseline, "repository")
    code_repository = resolve_code_repository(config, repository_name)
    plan_text = read_vault_blob(config, "plan_ref", plan_ref, change_id)
    plan_paths = validate_plan_document(plan_text)
    targets = resolve_plan_targets(code_repository, plan_paths)
    workspace_root = Path(
        os.path.commonpath((str(config.spec_vault.resolve()), str(code_repository)))
    ).resolve()
    agents = discover_applicable_agents(workspace_root, code_repository, targets)
    return snapshot_agents_inventory(agents)


def validate_stage_prerequisites(
    config: RuntimeConfig,
    change: sqlite3.Row,
    target_stage: str,
    *,
    flow: str = "full",
    enforce_impact_contract: bool = True,
) -> None:
    if flow == "direct":
        required = {"acceptance": ("code_ref",)}.get(target_stage, ())
    elif flow == "light":
        required = {
            "tdd_coding": ("spec_ref",),
            "acceptance": ("spec_ref", "code_ref"),
        }.get(target_stage, ())
    elif flow == "full":
        required = FULL_STAGE_PREREQUISITES.get(target_stage, ())
    else:
        raise LedgerError(f"unknown workflow flow: {flow}")
    missing = [field for field in required if not change[field]]
    if missing:
        raise LedgerError(
            f"cannot enter {target_stage}; missing prerequisite references: " + ", ".join(missing)
        )
    for field in required:
        validate_reference(config, field, change[field], change["change_id"])
    if "spec_ref" in required:
        spec_text = read_vault_blob(
            config, "spec_ref", change["spec_ref"], change["change_id"]
        )
        if flow == "light":
            validate_light_spec_document(spec_text)
        else:
            spec_baseline = validate_spec_document(spec_text)
            validate_code_reference(config, spec_baseline)
            if target_stage == "writing_plan" and enforce_impact_contract:
                validate_spec_impact_contract(spec_text)
    if "plan_ref" in required:
        validate_plan_document(
            read_vault_blob(config, "plan_ref", change["plan_ref"], change["change_id"])
        )
    if "test_ref" in required:
        validate_test_draft_contract(
            read_vault_blob(config, "test_ref", change["test_ref"], change["change_id"])
        )
    if flow == "full" and target_stage in ("tdd_coding", "writing_test", "acceptance"):
        validate_plan_execution_context(
            config,
            change["change_id"],
            change["spec_ref"],
            change["plan_ref"],
        )


def command_init(args, config):
    with open_database(config.database) as connection:
        with immediate_transaction(connection):
            rebuild_canonical_schema(connection)
    log("init", "ok")
    emit({"database": str(config.database), "status": "ok"})


def command_create(args, config):
    with open_database(config.database) as connection:
        require_schema(connection)
        with immediate_transaction(connection):
            expected = next_identifier(connection, "change_ledger", "change_id", "CE")
            change_id = args.change_id or expected
            if not CHANGE_ID_PATTERN.fullmatch(change_id):
                raise LedgerError("change_id must use CE-0001 format")
            if change_id != expected:
                raise LedgerError(f"next available change_id is {expected}")
            validate_reference(config, "change_ref", args.change_ref, change_id)
            validate_change_document(
                read_vault_blob(config, "change_ref", args.change_ref, change_id),
                change_id,
                final=False,
                expected_source_ce=args.source_ce,
                require_source_ce=True,
            )
            if args.spec_ref:
                validate_reference(config, "spec_ref", args.spec_ref, change_id)
            connection.execute(
                "INSERT INTO change_ledger VALUES (?,?,?,NULL,NULL,NULL,NULL,'in_progress')",
                (change_id, args.spec_ref, args.change_ref),
            )
    log("create", "in_progress", change_id)
    emit({"change_id": change_id, "status": "in_progress"})


def command_next_id(args, config):
    with open_database(config.database, readonly=True) as connection:
        require_schema(connection)
        change_id = next_identifier(connection, "change_ledger", "change_id", "CE")
    log("next-id", "ok", change_id)
    emit({"change_id": change_id})


def command_resolve_code_ref(args, config):
    payload = resolve_code_ref_from_worktree(config, args.worktree)
    log("resolve-code-ref", "ok")
    emit(payload)


def command_set_code_ref(args, config):
    with open_database(config.database) as connection:
        require_schema(connection, workflow=True)
        with immediate_transaction(connection):
            row = get_change(connection, args.change_id)
            if row["status"] != "in_progress":
                raise LedgerError("completed change is immutable")
            workflow = connection.execute(
                "SELECT workflow_id,current_stage FROM workflow_state "
                "WHERE change_id=? AND state='active'",
                (args.change_id,),
            ).fetchone()
            if workflow is not None and workflow["current_stage"] != "tdd_coding":
                raise LedgerError(
                    "active workflow must be at tdd_coding before setting code_ref"
                )
            payload = resolve_code_ref_from_worktree(config, args.worktree)
            updated = connection.execute(
                "UPDATE change_ledger SET code_ref=? WHERE change_id=? AND status='in_progress'",
                (payload["code_ref"], args.change_id),
            )
            if updated.rowcount != 1:
                raise LedgerError("change changed concurrently")
            confirmation = resolve_code_ref_from_worktree(config, args.worktree)
            if confirmation["code_ref"] != payload["code_ref"]:
                raise LedgerError("worktree HEAD changed while setting code_ref")
            payload = confirmation
    payload.update(
        {
            "change_id": args.change_id,
            "field": "code_ref",
            "status": "in_progress",
        }
    )
    log("set-code-ref", "in_progress", args.change_id)
    emit(payload)


def command_set_ref(args, config):
    if args.field == "change_ref":
        raise LedgerError(
            "change_ref is written only at event registration and completion"
        )
    if args.field == "code_ref":
        raise LedgerError(
            "code_ref must be derived and persisted atomically with set-code-ref --worktree"
        )
    report_validation = None
    with open_database(config.database) as connection:
        require_schema(connection)
        with immediate_transaction(connection):
            row = get_change(connection, args.change_id)
            if row["status"] != "in_progress":
                raise LedgerError("completed change is immutable")
            workflow = None
            if args.field in ("spec_ref", "plan_ref"):
                workflow = connection.execute(
                    "SELECT workflow_id,current_stage FROM workflow_state "
                    "WHERE change_id=? AND state='active'",
                    (args.change_id,),
                ).fetchone()
            if args.field == "spec_ref" and workflow is not None:
                if workflow["current_stage"] != "writing_spec":
                    raise LedgerError(
                        "active workflow must return to writing_spec before replacing spec_ref"
                    )
            elif args.field == "plan_ref" and workflow is not None:
                raise LedgerError(
                    "active workflow Plan refs are adopted only by the atomic adopt-plan command"
                )
            validate_reference(config, args.field, args.value, args.change_id)
            if args.field == "test_ref":
                validate_test_draft_contract(
                    read_vault_blob(config, args.field, args.value, args.change_id)
                )
            elif args.field == "evidence_ref":
                if not row["test_ref"] or not row["code_ref"]:
                    raise LedgerError(
                        "test_ref and code_ref must exist before setting evidence_ref"
                    )
                test_text = read_vault_blob(
                    config, "test_ref", row["test_ref"], args.change_id
                )
                evidence_text = read_vault_blob(
                    config, "evidence_ref", args.value, args.change_id
                )
                report_validation = validate_acceptance_report_contract(
                    test_text,
                    evidence_text,
                    args.change_id,
                    row["test_ref"],
                    row["code_ref"],
                    require_passed=False,
                )
            updated = connection.execute(
                f"UPDATE change_ledger SET {args.field}=? WHERE change_id=? AND status='in_progress'",
                (args.value, args.change_id),
            )
            if updated.rowcount != 1:
                raise LedgerError("change changed concurrently")
    log("set-ref", "in_progress", args.change_id)
    payload = {
        "change_id": args.change_id,
        "field": args.field,
        "status": "in_progress",
        "value": args.value,
    }
    if report_validation is not None:
        payload["report_validation"] = report_validation
    emit(payload)


def command_plan_adoption_contract(args, config):
    emit(
        {
            "contract_version": 4,
            "command": "adopt-plan",
            "arguments": {
                "change_id": {"format": "^CE-[0-9]{4,}$", "required": True},
                "workflow_id": {"format": "^WF-[0-9]{4,}$", "required": True},
                "plan_ref": {
                    "format": "plans/<change_id>.md@<full-vault-commit-sha>",
                    "required": True,
                },
                "dry_run": {"required": False, "writes": False},
            },
            "preconditions": [
                "workflow is active and bound to change_id",
                "workflow current_stage is writing_plan",
                "change status is in_progress",
                "spec_ref contains a valid existing-flow impact contract",
                "candidate plan passes deterministic title, header, Task, Files, Interfaces, checkbox, and placeholder grammar",
                "candidate plan covers all Spec impact_id values with no blocking rows",
                "explicit Spec behavior changes map to adaptation or migration tasks",
                "Spec code baseline is a full exact configured repository commit",
                "candidate plan declares the same source-specific baseline with a full 40-character base_sha",
                "all applicable AGENTS.md files for Plan targets are readable and inventoried",
            ],
            "atomic_writes": [
                "change_ledger.plan_ref",
                "workflow_state.current_stage",
            ],
        }
    )


def validate_plan_adoption(connection, args, config):
    require_schema(connection, workflow=True)
    change = get_change(connection, args.change_id)
    workflow = get_workflow(connection, args.workflow_id)
    if change["status"] != "in_progress":
        raise LedgerError("completed change is immutable")
    if workflow["state"] != "active" or workflow["change_id"] != args.change_id:
        raise LedgerError("adopt-plan requires the active workflow bound to change_id")
    if workflow["flow"] != "full":
        raise LedgerError("adopt-plan is available only for full workflows")

    exact_repeat = (
        workflow["current_stage"] == "tdd_coding"
        and change["plan_ref"] == args.plan_ref
    )
    if workflow["current_stage"] != "writing_plan" and not exact_repeat:
        raise LedgerError("adopt-plan requires workflow current_stage writing_plan")

    validate_stage_prerequisites(
        config,
        change,
        "writing_plan",
        flow="full",
        enforce_impact_contract=not exact_repeat,
    )
    validate_reference(config, "plan_ref", args.plan_ref, args.change_id)
    plan_text = read_vault_blob(config, "plan_ref", args.plan_ref, args.change_id)
    validate_plan_document(plan_text)
    if not exact_repeat:
        spec_text = read_vault_blob(
            config, "spec_ref", change["spec_ref"], args.change_id
        )
        validate_plan_compatibility_contract(spec_text, plan_text)
        validate_plan_baseline_contract(config, spec_text, plan_text)
    agents = validate_plan_execution_context(
        config,
        args.change_id,
        change["spec_ref"],
        args.plan_ref,
    )
    return change, workflow, exact_repeat, agents


def command_adopt_plan(args, config):
    if args.dry_run:
        with open_database(config.database, readonly=True) as connection:
            change, workflow, _, agents = validate_plan_adoption(
                connection, args, config
            )
        payload = {
            "status": "validated",
            "dry_run": True,
            "candidate_plan_ref": args.plan_ref,
            "change": dict(change),
            "workflow": dict(workflow),
            "agents": agents,
            "would_write": {
                "change_ledger.plan_ref": args.plan_ref,
                "workflow_state.current_stage": "tdd_coding",
            },
        }
    else:
        with open_database(config.database) as connection:
            with immediate_transaction(connection):
                change, workflow, exact_repeat, agents = validate_plan_adoption(
                    connection, args, config
                )
                if exact_repeat:
                    payload = {
                        "status": "adopted",
                        "change": dict(change),
                        "workflow": dict(workflow),
                        "agents": agents,
                    }
                else:
                    updated_change = connection.execute(
                        "UPDATE change_ledger SET plan_ref=? "
                        "WHERE change_id=? AND status='in_progress' AND change_ref=?",
                        (
                            args.plan_ref,
                            args.change_id,
                            change["change_ref"],
                        ),
                    )
                    if updated_change.rowcount != 1:
                        raise LedgerError("change changed concurrently")
                    updated_workflow = connection.execute(
                        "UPDATE workflow_state SET current_stage='tdd_coding' "
                        "WHERE workflow_id=? AND change_id=? AND state='active' "
                        "AND current_stage='writing_plan'",
                        (args.workflow_id, args.change_id),
                    )
                    if updated_workflow.rowcount != 1:
                        raise LedgerError("workflow changed concurrently")
                    payload = {
                        "status": "adopted",
                        "change": dict(get_change(connection, args.change_id)),
                        "workflow": dict(get_workflow(connection, args.workflow_id)),
                        "agents": agents,
                    }
    log(
        "adopt-plan",
        "validated" if args.dry_run else "adopted",
        args.change_id,
        args.workflow_id,
    )
    emit(payload)


def command_complete(args, config):
    with open_database(config.database) as connection:
        require_schema(connection, workflow=True)
        with immediate_transaction(connection):
            row = get_change(connection, args.change_id)
            if row["status"] == "completed":
                if args.change_ref is not None and args.change_ref != row["change_ref"]:
                    raise LedgerError(
                        "provided final change_ref does not match the completed event"
                    )
                payload = {
                    "change_id": args.change_id,
                    "change_ref": row["change_ref"],
                    "status": "completed",
                }
            else:
                if args.change_ref is None:
                    raise LedgerError(
                        "in_progress completion requires final --change-ref"
                    )
                active_workflows = connection.execute(
                    "SELECT workflow_id,current_stage,flow,review_mode FROM workflow_state "
                    "WHERE change_id=? AND state='active'",
                    (args.change_id,),
                ).fetchall()
                if any(workflow["current_stage"] != "acceptance" for workflow in active_workflows):
                    raise LedgerError(
                        "active workflow must be at acceptance before completing its change"
                    )
                flow = active_workflows[0]["flow"] if active_workflows else "full"
                final_fields = {
                    "direct": ("code_ref",),
                    "light": ("spec_ref", "code_ref"),
                    "full": (
                        "spec_ref",
                        "plan_ref",
                        "test_ref",
                        "code_ref",
                        "evidence_ref",
                    ),
                }[flow]
                missing = [field for field in final_fields if not row[field]]
                if missing:
                    raise LedgerError("missing required references: " + ", ".join(missing))
                for field in final_fields:
                    validate_reference(config, field, row[field], args.change_id)
                validate_reference(config, "change_ref", args.change_ref, args.change_id)
                registration_text = read_vault_blob(
                    config, "change_ref", row["change_ref"], args.change_id
                )
                registration_fields = validate_change_document(
                    registration_text,
                    args.change_id,
                    final=False,
                )
                change_text = read_vault_blob(
                    config, "change_ref", args.change_ref, args.change_id
                )
                change_fields = validate_change_document(
                    change_text,
                    args.change_id,
                    final=True,
                )
                if change_fields["source_ce"] != registration_fields["source_ce"]:
                    raise LedgerError(
                        "final change document source_ce must match registration source_ce"
                    )
                for field in final_fields:
                    if change_fields.get(field) != row[field]:
                        raise LedgerError(
                            f"final change document {field} does not exactly match the ledger"
                        )
                if flow == "light":
                    validate_light_spec_document(
                        read_vault_blob(
                            config, "spec_ref", row["spec_ref"], args.change_id
                        )
                    )
                    validate_history_summary(
                        change_text,
                        expected_source_ce=change_fields["source_ce"],
                    )
                elif flow == "direct":
                    validate_history_summary(
                        change_text,
                        expected_source_ce=change_fields["source_ce"],
                    )
                else:
                    spec_text = read_vault_blob(
                        config, "spec_ref", row["spec_ref"], args.change_id
                    )
                    spec_baseline = validate_spec_document(spec_text)
                    validate_code_reference(config, spec_baseline)
                    plan_text = read_vault_blob(
                        config, "plan_ref", row["plan_ref"], args.change_id
                    )
                    validate_plan_document(plan_text)
                    if not active_workflows:
                        validate_plan_compatibility_contract(spec_text, plan_text)
                    test_text = read_vault_blob(
                        config, "test_ref", row["test_ref"], args.change_id
                    )
                    evidence_text = read_vault_blob(
                        config, "evidence_ref", row["evidence_ref"], args.change_id
                    )
                    validate_acceptance_report_contract(
                        test_text,
                        evidence_text,
                        args.change_id,
                        row["test_ref"],
                        row["code_ref"],
                        require_passed=True,
                    )
                    validate_plan_execution_context(
                        config,
                        args.change_id,
                        row["spec_ref"],
                        row["plan_ref"],
                    )
                    validate_final_change_logic_link(change_text, args.change_id)
                    _, final_change_sha = split_reference(
                        args.change_ref,
                        "vault-relative-path",
                    )
                    logic_path = f"logic/{args.change_id}.md"
                    logic_text = read_vault_path_at_commit(
                        config,
                        final_change_sha,
                        logic_path,
                        "final logic draft",
                    )
                    validate_final_logic_document(logic_text, args.change_id)
                updated = connection.execute(
                    "UPDATE change_ledger SET change_ref=?,status='completed' "
                    "WHERE change_id=? AND status='in_progress' AND change_ref=?",
                    (args.change_ref, args.change_id, row["change_ref"]),
                )
                if updated.rowcount != 1:
                    raise LedgerError("change changed concurrently")
                connection.execute(
                    "UPDATE workflow_state SET current_stage='completed',"
                    "review_mode='manual',state='closed' "
                    "WHERE change_id=? AND state='active'",
                    (args.change_id,),
                )
                payload = {
                    "change_id": args.change_id,
                    "change_ref": args.change_ref,
                    "status": "completed",
                }
    log("complete", "completed", args.change_id)
    emit(payload)


def command_show(args, config):
    with open_database(config.database, readonly=True) as connection:
        require_schema(connection)
        payload = dict(get_change(connection, args.change_id))
    log("show", payload["status"], args.change_id)
    emit(payload)


def command_list(args, config):
    with open_database(config.database, readonly=True) as connection:
        require_schema(connection)
        sql = "SELECT * FROM change_ledger"
        parameters = ()
        if args.status != "all":
            sql += " WHERE status=?"
            parameters = (args.status,)
        sql += " ORDER BY CAST(SUBSTR(change_id,4) AS INTEGER), change_id"
        payload = [dict(row) for row in connection.execute(sql, parameters)]
    log("list", args.status)
    emit(payload)


def command_workflow_create(args, config):
    with open_database(config.database) as connection:
        require_schema(connection, workflow=True)
        with immediate_transaction(connection):
            workflow_id = args.workflow_id or next_identifier(connection, "workflow_state", "workflow_id", "WF")
            expected = next_identifier(connection, "workflow_state", "workflow_id", "WF")
            if not WORKFLOW_ID_PATTERN.fullmatch(workflow_id):
                raise LedgerError("workflow_id must use WF-0001 format")
            if workflow_id != expected:
                raise LedgerError(f"next available workflow_id is {expected}")
            stage = args.stage
            if args.change_id:
                change = get_change(connection, args.change_id)
                if change["status"] != "in_progress":
                    raise LedgerError("workflow can bind only to an in-progress change")
                expected_stage = initial_bound_stage(args.flow)
                stage = stage or expected_stage
                if stage != expected_stage:
                    raise LedgerError(
                        f"a newly bound {args.flow} workflow must start at {expected_stage}"
                    )
                validate_stage_prerequisites(config, change, stage, flow=args.flow)
            else:
                stage = stage or "requirement_discussion"
            if not args.change_id and stage not in PRE_EVENT_STAGES:
                raise LedgerError("unbound workflow must use a pre-event stage")
            connection.execute(
                "INSERT INTO workflow_state VALUES (?,?,?,?,?,'active')",
                (workflow_id, args.change_id, stage, args.flow, args.review_mode),
            )
    log("workflow-create", "active", args.change_id, workflow_id)
    emit(
        {
            "workflow_id": workflow_id,
            "change_id": args.change_id,
            "current_stage": stage,
            "flow": args.flow,
            "review_mode": args.review_mode,
            "state": "active",
        }
    )


def command_workflow_bind(args, config):
    with open_database(config.database) as connection:
        require_schema(connection, workflow=True)
        with immediate_transaction(connection):
            workflow = get_workflow(connection, args.workflow_id)
            change = get_change(connection, args.change_id)
            if workflow["state"] != "active":
                raise LedgerError("closed workflow is immutable")
            if change["status"] != "in_progress":
                raise LedgerError("workflow can bind only to an in-progress change")
            if workflow["change_id"] == args.change_id:
                pass
            elif workflow["change_id"] is not None:
                raise LedgerError(f"workflow is already bound to {workflow['change_id']}")
            else:
                updated = connection.execute(
                    "UPDATE workflow_state SET change_id=?,current_stage=? "
                    "WHERE workflow_id=? AND state='active' AND change_id IS NULL",
                    (args.change_id, initial_bound_stage(workflow["flow"]), args.workflow_id),
                )
                if updated.rowcount != 1:
                    raise LedgerError("workflow changed concurrently")
    log("workflow-bind-change", "active", args.change_id, args.workflow_id)
    emit({"workflow_id": args.workflow_id, "change_id": args.change_id, "state": "active"})


def command_workflow_set_stage(args, config):
    with open_database(config.database) as connection:
        require_schema(connection, workflow=True)
        with immediate_transaction(connection):
            workflow = get_workflow(connection, args.workflow_id)
            if workflow["state"] != "active":
                raise LedgerError("closed workflow is immutable")
            allowed = (
                PRE_EVENT_STAGES
                if workflow["change_id"] is None
                else formal_stages_for_flow(workflow["flow"])
            )
            if args.stage not in allowed:
                raise LedgerError("stage violates workflow binding invariant")
            if workflow["change_id"] is not None:
                current_index = allowed.index(workflow["current_stage"])
                target_index = allowed.index(args.stage)
                tdd_index = allowed.index("tdd_coding")
                if workflow["flow"] == "full" and current_index < tdd_index <= target_index:
                    raise LedgerError(
                        "entering or skipping over tdd_coding requires the atomic adopt-plan command"
                    )
                if target_index > current_index:
                    validate_stage_prerequisites(
                        config,
                        get_change(connection, workflow["change_id"]),
                        args.stage,
                        flow=workflow["flow"],
                    )
            updated = connection.execute(
                "UPDATE workflow_state SET current_stage=? WHERE workflow_id=? AND state='active'",
                (args.stage, args.workflow_id),
            )
            if updated.rowcount != 1:
                raise LedgerError("workflow changed concurrently")
            payload = dict(get_workflow(connection, args.workflow_id))
    log("workflow-set-stage", "active", payload["change_id"], args.workflow_id)
    emit(payload)


def command_workflow_set_controls(args, config):
    if args.flow is None and args.review_mode is None:
        raise LedgerError("workflow-set-controls requires --flow or --review-mode")
    with open_database(config.database) as connection:
        require_schema(connection, workflow=True)
        with immediate_transaction(connection):
            workflow = get_workflow(connection, args.workflow_id)
            if workflow["state"] != "active":
                raise LedgerError("closed workflow is immutable")
            flow = args.flow or workflow["flow"]
            review_mode = args.review_mode or workflow["review_mode"]
            stage = workflow["current_stage"]
            if args.flow is not None and args.flow != workflow["flow"] and workflow["change_id"]:
                if args.flow == "direct":
                    stage = "acceptance" if stage == "acceptance" else "tdd_coding"
                elif args.flow == "light":
                    stage = "acceptance" if stage == "acceptance" else "writing_spec"
                else:
                    stage = "writing_spec"
            updated = connection.execute(
                "UPDATE workflow_state SET current_stage=?,flow=?,review_mode=? "
                "WHERE workflow_id=? AND state='active'",
                (stage, flow, review_mode, args.workflow_id),
            )
            if updated.rowcount != 1:
                raise LedgerError("workflow changed concurrently")
            payload = dict(get_workflow(connection, args.workflow_id))
    log("workflow-set-controls", "active", payload["change_id"], args.workflow_id)
    emit(payload)


def command_workflow_close(args, config):
    with open_database(config.database) as connection:
        require_schema(connection, workflow=True)
        with immediate_transaction(connection):
            workflow = get_workflow(connection, args.workflow_id)
            if workflow["state"] == "closed":
                payload = dict(workflow)
            else:
                if not workflow["change_id"]:
                    raise LedgerError("workflow must be bound to a completed change before closing")
                if get_change(connection, workflow["change_id"])["status"] != "completed":
                    raise LedgerError("change must be completed before closing workflow")
                updated = connection.execute(
                    "UPDATE workflow_state SET current_stage='completed',review_mode='manual',state='closed' "
                    "WHERE workflow_id=? AND state='active'",
                    (args.workflow_id,),
                )
                if updated.rowcount != 1:
                    raise LedgerError("workflow changed concurrently")
                payload = dict(get_workflow(connection, args.workflow_id))
    log("workflow-close", "closed", payload["change_id"], args.workflow_id)
    emit(payload)


def command_workflow_show(args, config):
    with open_database(config.database, readonly=True) as connection:
        require_schema(connection, workflow=True)
        payload = dict(get_workflow(connection, args.workflow_id))
    log("workflow-show", payload["state"], payload["change_id"], args.workflow_id)
    emit(payload)


def command_workflow_list(args, config):
    with open_database(config.database, readonly=True) as connection:
        require_schema(connection, workflow=True)
        sql = "SELECT * FROM workflow_state"
        parameters = ()
        if args.state != "all":
            sql += " WHERE state=?"
            parameters = (args.state,)
        sql += " ORDER BY CAST(SUBSTR(workflow_id,4) AS INTEGER), workflow_id"
        payload = [dict(row) for row in connection.execute(sql, parameters)]
    log("workflow-list", args.state)
    emit(payload)


def command_workflow_status(args, config):
    with open_database(config.database, readonly=True) as connection:
        require_schema(connection, workflow=True)
        workflow = get_workflow(connection, args.workflow_id)
        change = dict(get_change(connection, workflow["change_id"])) if workflow["change_id"] else None
        payload = {"workflow": dict(workflow), "change": change}
    log("workflow-status", workflow["state"], workflow["change_id"], args.workflow_id)
    emit(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Maintain change-event references and workflow state")
    parser.add_argument("--config", help="absolute current-project workflow config path")
    parser.add_argument("--db")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    create = commands.add_parser("create")
    create.add_argument("--change-id")
    create.add_argument("--change-ref", required=True)
    create.add_argument("--source-ce", required=True)
    create.add_argument("--spec-ref")
    commands.add_parser("next-id")
    resolve_code_ref = commands.add_parser("resolve-code-ref")
    resolve_code_ref.add_argument("--worktree", required=True)
    set_code_ref = commands.add_parser("set-code-ref")
    set_code_ref.add_argument("change_id")
    set_code_ref.add_argument("--worktree", required=True)
    set_ref = commands.add_parser("set-ref")
    set_ref.add_argument("change_id")
    set_ref.add_argument("--field", required=True, choices=REFERENCE_FIELDS)
    set_ref.add_argument("--value", required=True)
    commands.add_parser("plan-adoption-contract")
    adopt_plan = commands.add_parser("adopt-plan")
    adopt_plan.add_argument("change_id")
    adopt_plan.add_argument("--workflow-id", required=True)
    adopt_plan.add_argument("--plan-ref", required=True)
    adopt_plan.add_argument("--dry-run", action="store_true")
    show = commands.add_parser("show")
    show.add_argument("change_id")
    complete = commands.add_parser("complete")
    complete.add_argument("change_id")
    complete.add_argument("--change-ref")
    listing = commands.add_parser("list")
    listing.add_argument("--status", choices=("all", "in_progress", "completed"), default="all")
    workflow_create = commands.add_parser("workflow-create")
    workflow_create.add_argument("--workflow-id")
    workflow_create.add_argument("--change-id")
    workflow_create.add_argument("--stage", choices=WORKFLOW_STAGES)
    workflow_create.add_argument("--flow", choices=FLOWS, default="full")
    workflow_create.add_argument("--review-mode", choices=REVIEW_MODES, default="manual")
    workflow_bind = commands.add_parser("workflow-bind-change")
    workflow_bind.add_argument("workflow_id")
    workflow_bind.add_argument("change_id")
    workflow_stage = commands.add_parser("workflow-set-stage")
    workflow_stage.add_argument("workflow_id")
    workflow_stage.add_argument("--stage", required=True, choices=WORKFLOW_STAGES)
    workflow_controls = commands.add_parser("workflow-set-controls")
    workflow_controls.add_argument("workflow_id")
    workflow_controls.add_argument("--flow", choices=FLOWS)
    workflow_controls.add_argument("--review-mode", choices=REVIEW_MODES)
    for name in ("workflow-close", "workflow-show", "workflow-status"):
        command = commands.add_parser(name)
        command.add_argument("workflow_id")
    workflow_list = commands.add_parser("workflow-list")
    workflow_list.add_argument("--state", choices=("all", "active", "closed"), default="all")
    return parser


COMMANDS = {
    "init": command_init,
    "create": command_create,
    "next-id": command_next_id,
    "resolve-code-ref": command_resolve_code_ref,
    "set-code-ref": command_set_code_ref,
    "set-ref": command_set_ref,
    "plan-adoption-contract": command_plan_adoption_contract,
    "adopt-plan": command_adopt_plan,
    "show": command_show,
    "list": command_list,
    "complete": command_complete,
    "workflow-create": command_workflow_create,
    "workflow-bind-change": command_workflow_bind,
    "workflow-set-stage": command_workflow_set_stage,
    "workflow-set-controls": command_workflow_set_controls,
    "workflow-close": command_workflow_close,
    "workflow-show": command_workflow_show,
    "workflow-list": command_workflow_list,
    "workflow-status": command_workflow_status,
}


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "plan-adoption-contract":
            config = None
        else:
            if not args.config and not args.db:
                raise LedgerError("--config is required for project commands")
            config = load_runtime_config(args)
        COMMANDS[args.command](args, config)
    except (LedgerError, sqlite3.Error) as error:
        log(args.command, "error", getattr(args, "change_id", None), getattr(args, "workflow_id", None))
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
