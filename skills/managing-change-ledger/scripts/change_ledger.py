#!/usr/bin/env python3
"""Small SQLite ledger for the personal development workflow."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


FLOWS = ("direct", "light", "full")
STAGES = ("define", "implement", "verify", "done")
REFERENCE_FIELDS = ("spec_ref", "change_ref", "code_ref", "evidence_ref")
CHANGE_ID_PATTERN = re.compile(r"^CE-(\d{4,})$")
WORKFLOW_ID_PATTERN = re.compile(r"^WF-(\d{4,})$")
CODE_REF_PATTERN = re.compile(r"^(?P<repository>[A-Za-z0-9][A-Za-z0-9._-]*)@(?P<sha>[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")


class LedgerError(Exception):
    pass


@dataclass(frozen=True)
class RuntimeConfig:
    database: Path
    repositories: dict[str, Path]


def emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def load_config(args: argparse.Namespace) -> RuntimeConfig:
    if args.db:
        return RuntimeConfig(Path(args.db).expanduser().resolve(), {})
    if not args.config:
        raise LedgerError("provide --config or --db")
    path = Path(args.config).expanduser().resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LedgerError(f"cannot read workflow config: {error}") from error
    if not isinstance(payload, dict):
        raise LedgerError("workflow config must be a JSON object")
    database_value = payload.get("database")
    if not isinstance(database_value, str) or not database_value.strip():
        raise LedgerError("workflow config requires database")
    database = Path(database_value).expanduser()
    if not database.is_absolute():
        raise LedgerError("database must be an absolute path")
    raw_repositories = payload.get("repositories", {})
    if not isinstance(raw_repositories, dict):
        raise LedgerError("repositories must be an object")
    repositories: dict[str, Path] = {}
    for name, value in raw_repositories.items():
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", str(name)):
            raise LedgerError(f"invalid repository name: {name}")
        repository = Path(str(value)).expanduser()
        if not repository.is_absolute():
            raise LedgerError(f"repository path must be absolute: {name}")
        repositories[str(name)] = repository.resolve()
    return RuntimeConfig(database.resolve(), repositories)


@contextmanager
def database(path: Path, *, readonly: bool = False):
    if readonly:
        if not path.exists():
            raise LedgerError("ledger database does not exist; run init first")
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def transaction(connection: sqlite3.Connection):
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def columns(connection: sqlite3.Connection, name: str) -> set[str]:
    return {row["name"] for row in connection.execute(f"PRAGMA table_info({name})")}


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS change_ledger (
            change_id TEXT PRIMARY KEY,
            flow TEXT NOT NULL CHECK (flow IN ('direct', 'light', 'full')),
            source_ce TEXT,
            summary TEXT NOT NULL,
            spec_ref TEXT,
            change_ref TEXT,
            plan_ref TEXT,
            test_ref TEXT,
            code_ref TEXT,
            evidence_ref TEXT,
            status TEXT NOT NULL CHECK (status IN ('in_progress', 'completed'))
        );

        CREATE TABLE IF NOT EXISTS workflow_state (
            workflow_id TEXT PRIMARY KEY,
            change_id TEXT,
            current_stage TEXT NOT NULL CHECK (current_stage IN ('define', 'implement', 'verify', 'done')),
            flow TEXT NOT NULL CHECK (flow IN ('direct', 'light', 'full')),
            state TEXT NOT NULL CHECK (state IN ('active', 'closed')),
            repository TEXT,
            worktree_root TEXT,
            git_common_dir TEXT,
            base_sha TEXT,
            FOREIGN KEY (change_id) REFERENCES change_ledger(change_id),
            CHECK (
                (state = 'active' AND current_stage != 'done') OR
                (state = 'closed' AND current_stage = 'done')
            )
        );
        """
    )
    connection.executescript(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS one_active_workflow_per_change
            ON workflow_state(change_id)
            WHERE state = 'active' AND change_id IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS one_active_writer_per_worktree
            ON workflow_state(worktree_root)
            WHERE state = 'active' AND worktree_root IS NOT NULL;

        CREATE TRIGGER IF NOT EXISTS completed_change_is_immutable
        BEFORE UPDATE ON change_ledger WHEN OLD.status = 'completed'
        BEGIN SELECT RAISE(ABORT, 'completed change is immutable'); END;

        CREATE TRIGGER IF NOT EXISTS closed_workflow_is_immutable
        BEFORE UPDATE ON workflow_state WHEN OLD.state = 'closed'
        BEGIN SELECT RAISE(ABORT, 'closed workflow is immutable'); END;
        """
    )


def migrate_legacy(connection: sqlite3.Connection) -> None:
    change_rows = [dict(row) for row in connection.execute("SELECT * FROM change_ledger")]
    workflow_rows = (
        [dict(row) for row in connection.execute("SELECT * FROM workflow_state")]
        if table_exists(connection, "workflow_state")
        else []
    )
    flow_by_change = {
        row.get("change_id"): row.get("flow")
        for row in workflow_rows
        if row.get("change_id") and row.get("flow") in FLOWS
    }
    connection.executescript(
        """
        DROP TRIGGER IF EXISTS completed_change_is_immutable;
        DROP TRIGGER IF EXISTS completed_change_cannot_be_deleted;
        DROP TRIGGER IF EXISTS closed_workflow_is_immutable;
        DROP TRIGGER IF EXISTS closed_workflow_cannot_be_deleted;
        DROP INDEX IF EXISTS one_active_workflow_per_change;
        DROP INDEX IF EXISTS one_active_writer_per_worktree;
        """
    )
    if table_exists(connection, "workflow_state"):
        connection.execute("DROP TABLE workflow_state")
    connection.execute("DROP TABLE change_ledger")
    create_schema(connection)

    for row in change_rows:
        flow = row.get("flow") or flow_by_change.get(row["change_id"]) or "full"
        connection.execute(
            """
            INSERT INTO change_ledger (
                change_id, flow, source_ce, summary, spec_ref, change_ref,
                plan_ref, test_ref, code_ref, evidence_ref, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["change_id"],
                flow if flow in FLOWS else "full",
                row.get("source_ce"),
                row.get("summary") or "已迁移的历史变更",
                row.get("spec_ref"),
                row.get("change_ref"),
                row.get("plan_ref") or row.get("implementation_ref"),
                row.get("test_ref"),
                row.get("code_ref"),
                row.get("evidence_ref"),
                row.get("status", "in_progress"),
            ),
        )

    stage_map = {
        "requirement_discussion": "define",
        "research": "define",
        "prototype": "define",
        "register_change": "define",
        "writing_spec": "define",
        "writing_plan": "define",
        "tdd_coding": "implement",
        "writing_test": "verify",
        "acceptance": "verify",
        "completed": "done",
    }
    for row in workflow_rows:
        stage = stage_map.get(row.get("current_stage"), row.get("current_stage"))
        if stage not in STAGES:
            stage = "define"
        state = "closed" if row.get("state") == "closed" or stage == "done" else "active"
        if state == "closed":
            stage = "done"
        flow = row.get("flow") if row.get("flow") in FLOWS else "full"
        connection.execute(
            """
            INSERT INTO workflow_state (
                workflow_id, change_id, current_stage, flow, state,
                repository, worktree_root, git_common_dir, base_sha
            ) VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
            """,
            (row["workflow_id"], row.get("change_id"), stage, flow, state),
        )


def initialize(connection: sqlite3.Connection) -> None:
    if not table_exists(connection, "change_ledger"):
        create_schema(connection)
        return
    current_change = {"flow", "source_ce", "summary"}.issubset(columns(connection, "change_ledger"))
    current_workflow = table_exists(connection, "workflow_state") and {
        "repository",
        "worktree_root",
        "git_common_dir",
        "base_sha",
    }.issubset(columns(connection, "workflow_state"))
    if current_change and current_workflow:
        create_schema(connection)
    else:
        migrate_legacy(connection)


def require_initialized(connection: sqlite3.Connection) -> None:
    if not table_exists(connection, "change_ledger") or not table_exists(connection, "workflow_state"):
        raise LedgerError("ledger is not initialized")


def next_identifier(connection: sqlite3.Connection, table: str, field: str, prefix: str) -> str:
    highest = 0
    for row in connection.execute(f"SELECT {field} FROM {table}"):
        value = row[field]
        match = re.fullmatch(rf"{prefix}-(\d+)", value)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"{prefix}-{highest + 1:04d}"


def get_change(connection: sqlite3.Connection, change_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM change_ledger WHERE change_id=?", (change_id,)
    ).fetchone()
    if row is None:
        raise LedgerError(f"unknown change: {change_id}")
    return row


def get_workflow(connection: sqlite3.Connection, workflow_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM workflow_state WHERE workflow_id=?", (workflow_id,)
    ).fetchone()
    if row is None:
        raise LedgerError(f"unknown workflow: {workflow_id}")
    return row


def run_git(path: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *arguments],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise LedgerError(f"Git check failed: {detail.strip()}") from error
    return result.stdout.strip()


def resolve_git_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def inspect_worktree(path: Path, config: RuntimeConfig) -> dict[str, str | bool]:
    requested = path.expanduser().resolve()
    root = Path(run_git(requested, "rev-parse", "--show-toplevel")).resolve()
    if requested != root:
        raise LedgerError(f"worktree path must be its Git root: {root}")
    git_dir = resolve_git_path(root, run_git(root, "rev-parse", "--git-dir"))
    common = resolve_git_path(root, run_git(root, "rev-parse", "--git-common-dir"))
    if git_dir == common:
        raise LedgerError("path is the primary checkout, not a linked worktree")
    if run_git(root, "rev-parse", "--show-superproject-working-tree"):
        raise LedgerError("submodule checkout is not a workflow worktree")
    matches = []
    for name, repository in config.repositories.items():
        repository_root = Path(run_git(repository, "rev-parse", "--show-toplevel")).resolve()
        repository_common = resolve_git_path(
            repository_root,
            run_git(repository_root, "rev-parse", "--git-common-dir"),
        )
        if repository_common == common:
            matches.append(name)
    if len(matches) > 1:
        raise LedgerError("worktree matches multiple configured repository names")
    repository_name = matches[0] if matches else common.parent.name
    return {
        "repository": repository_name,
        "worktree_root": str(root),
        "git_common_dir": str(common),
        "head": run_git(root, "rev-parse", "HEAD").lower(),
        "dirty": bool(run_git(root, "status", "--porcelain")),
    }


def assert_worktree_binding(row: sqlite3.Row, config: RuntimeConfig, path: Path) -> dict[str, object]:
    if not row["worktree_root"]:
        raise LedgerError("workflow has no worktree binding")
    actual = inspect_worktree(path, config)
    for field in ("repository", "worktree_root", "git_common_dir"):
        if actual[field] != row[field]:
            raise LedgerError(f"worktree binding mismatch: {field}")
    return actual


def command_init(config: RuntimeConfig) -> dict[str, object]:
    with database(config.database) as connection, transaction(connection):
        initialize(connection)
    return {"database": str(config.database), "status": "initialized"}


def command_next_id(config: RuntimeConfig) -> dict[str, str]:
    with database(config.database, readonly=True) as connection:
        require_initialized(connection)
        return {"change_id": next_identifier(connection, "change_ledger", "change_id", "CE")}


def command_create(config: RuntimeConfig, args: argparse.Namespace) -> dict[str, object]:
    with database(config.database) as connection, transaction(connection):
        require_initialized(connection)
        change_id = args.change_id or next_identifier(connection, "change_ledger", "change_id", "CE")
        if not CHANGE_ID_PATTERN.fullmatch(change_id):
            raise LedgerError("change_id must look like CE-0001")
        if args.source_ce:
            source = get_change(connection, args.source_ce)
            if source["status"] != "completed":
                raise LedgerError("source_ce must reference a completed change")
        connection.execute(
            "INSERT INTO change_ledger (change_id, flow, source_ce, summary, status) VALUES (?, ?, ?, ?, 'in_progress')",
            (change_id, args.flow, args.source_ce, args.summary.strip()),
        )
        return dict(get_change(connection, change_id))


def command_set_ref(config: RuntimeConfig, args: argparse.Namespace) -> dict[str, object]:
    if args.field not in REFERENCE_FIELDS:
        raise LedgerError(f"unsupported reference field: {args.field}")
    value = args.value.strip()
    if not value:
        raise LedgerError("reference value cannot be empty")
    with database(config.database) as connection, transaction(connection):
        change = get_change(connection, args.change_id)
        if change["status"] == "completed":
            raise LedgerError("completed change is immutable")
        if args.field == "code_ref":
            match = CODE_REF_PATTERN.fullmatch(value)
            if not match:
                raise LedgerError("code_ref must be repository@full-git-sha")
            workflow = connection.execute(
                "SELECT * FROM workflow_state WHERE change_id=? AND state='active'",
                (args.change_id,),
            ).fetchone()
            if workflow is None or workflow["current_stage"] != "implement":
                raise LedgerError("code_ref can only be set during implement")
            actual = assert_worktree_binding(workflow, config, Path(workflow["worktree_root"]))
            if match.group("repository") != actual["repository"] or match.group("sha").lower() != actual["head"]:
                raise LedgerError("code_ref does not match the bound worktree HEAD")
            if actual["dirty"]:
                raise LedgerError("bound worktree has uncommitted changes")
        connection.execute(
            f"UPDATE change_ledger SET {args.field}=? WHERE change_id=?",
            (value, args.change_id),
        )
        return dict(get_change(connection, args.change_id))


def command_complete(config: RuntimeConfig, args: argparse.Namespace) -> dict[str, object]:
    with database(config.database) as connection, transaction(connection):
        change = get_change(connection, args.change_id)
        if change["status"] == "completed":
            return dict(change)
        workflow = connection.execute(
            "SELECT * FROM workflow_state WHERE change_id=? AND state='active'",
            (args.change_id,),
        ).fetchone()
        if workflow is None or workflow["current_stage"] != "verify":
            raise LedgerError("change can only complete from verify")
        if not change["code_ref"]:
            raise LedgerError("code_ref is required before completion")
        actual = assert_worktree_binding(workflow, config, Path(workflow["worktree_root"]))
        match = CODE_REF_PATTERN.fullmatch(change["code_ref"])
        if match is None or match.group("sha").lower() != actual["head"] or actual["dirty"]:
            raise LedgerError("completion requires a clean bound worktree at code_ref")
        connection.execute(
            "UPDATE change_ledger SET status='completed', summary=? WHERE change_id=?",
            (args.summary.strip(), args.change_id),
        )
        connection.execute(
            "UPDATE workflow_state SET current_stage='done', state='closed' WHERE workflow_id=?",
            (workflow["workflow_id"],),
        )
        payload = dict(get_change(connection, args.change_id))
        payload["current_stage"] = "done"
        return payload


def command_show(config: RuntimeConfig, change_id: str) -> dict[str, object]:
    with database(config.database, readonly=True) as connection:
        return dict(get_change(connection, change_id))


def command_list(config: RuntimeConfig, status: str | None) -> list[dict[str, object]]:
    with database(config.database, readonly=True) as connection:
        require_initialized(connection)
        if status:
            rows = connection.execute(
                "SELECT * FROM change_ledger WHERE status=? ORDER BY change_id", (status,)
            )
        else:
            rows = connection.execute("SELECT * FROM change_ledger ORDER BY change_id")
        return [dict(row) for row in rows]


def command_workflow_create(config: RuntimeConfig, flow: str) -> dict[str, object]:
    with database(config.database) as connection, transaction(connection):
        require_initialized(connection)
        workflow_id = next_identifier(connection, "workflow_state", "workflow_id", "WF")
        connection.execute(
            "INSERT INTO workflow_state (workflow_id, current_stage, flow, state) VALUES (?, 'define', ?, 'active')",
            (workflow_id, flow),
        )
        return dict(get_workflow(connection, workflow_id))


def command_workflow_bind(config: RuntimeConfig, workflow_id: str, change_id: str) -> dict[str, object]:
    with database(config.database) as connection, transaction(connection):
        workflow = get_workflow(connection, workflow_id)
        change = get_change(connection, change_id)
        if workflow["state"] != "active" or workflow["current_stage"] != "define":
            raise LedgerError("workflow must be active in define")
        if workflow["change_id"] and workflow["change_id"] != change_id:
            raise LedgerError("workflow is already bound to another change")
        if change["status"] != "in_progress" or change["flow"] != workflow["flow"]:
            raise LedgerError("change must be in progress with the same flow")
        connection.execute(
            "UPDATE workflow_state SET change_id=? WHERE workflow_id=?",
            (change_id, workflow_id),
        )
        return dict(get_workflow(connection, workflow_id))


def command_workflow_bind_worktree(config: RuntimeConfig, args: argparse.Namespace) -> dict[str, object]:
    actual = inspect_worktree(Path(args.worktree), config)
    with database(config.database) as connection, transaction(connection):
        workflow = get_workflow(connection, args.workflow_id)
        if workflow["state"] != "active" or workflow["current_stage"] != "define" or not workflow["change_id"]:
            raise LedgerError("bind a change to an active define workflow first")
        duplicate = connection.execute(
            "SELECT workflow_id FROM workflow_state WHERE state='active' AND worktree_root=? AND workflow_id!=?",
            (actual["worktree_root"], args.workflow_id),
        ).fetchone()
        if duplicate:
            raise LedgerError(f"worktree already has an active writer: {duplicate['workflow_id']}")
        if workflow["worktree_root"] and workflow["worktree_root"] != actual["worktree_root"]:
            raise LedgerError("workflow is already bound to another worktree")
        connection.execute(
            """
            UPDATE workflow_state
            SET repository=?, worktree_root=?, git_common_dir=?, base_sha=?
            WHERE workflow_id=?
            """,
            (
                actual["repository"],
                actual["worktree_root"],
                actual["git_common_dir"],
                actual["head"],
                args.workflow_id,
            ),
        )
        return dict(get_workflow(connection, args.workflow_id))


def command_workflow_assert(config: RuntimeConfig, args: argparse.Namespace) -> dict[str, object]:
    with database(config.database, readonly=True) as connection:
        workflow = get_workflow(connection, args.workflow_id)
        if workflow["state"] != "active":
            raise LedgerError("workflow is not active")
        actual = assert_worktree_binding(workflow, config, Path(args.worktree))
        return {**dict(workflow), **actual, "binding_status": "valid"}


def command_workflow_stage(config: RuntimeConfig, workflow_id: str, stage: str) -> dict[str, object]:
    with database(config.database) as connection, transaction(connection):
        workflow = get_workflow(connection, workflow_id)
        if workflow["state"] != "active" or not workflow["change_id"]:
            raise LedgerError("workflow must be active and bound")
        current = workflow["current_stage"]
        allowed = {
            "define": {"implement"},
            "implement": {"define", "verify"},
            "verify": {"define", "implement"},
        }
        if stage not in allowed.get(current, set()):
            raise LedgerError(f"invalid stage transition: {current} -> {stage}")
        change = get_change(connection, workflow["change_id"])
        if stage == "implement":
            if not workflow["worktree_root"]:
                raise LedgerError("bind a worktree before implementation")
            assert_worktree_binding(workflow, config, Path(workflow["worktree_root"]))
            if workflow["flow"] in ("light", "full") and not change["spec_ref"]:
                raise LedgerError("light/full requires spec_ref before implementation")
        if stage == "verify":
            if not change["code_ref"]:
                raise LedgerError("code_ref is required before verify")
            actual = assert_worktree_binding(workflow, config, Path(workflow["worktree_root"]))
            if actual["dirty"]:
                raise LedgerError("bound worktree must be clean before verify")
        connection.execute(
            "UPDATE workflow_state SET current_stage=? WHERE workflow_id=?",
            (stage, workflow_id),
        )
        return dict(get_workflow(connection, workflow_id))


def command_workflow_show(config: RuntimeConfig, workflow_id: str) -> dict[str, object]:
    with database(config.database, readonly=True) as connection:
        return dict(get_workflow(connection, workflow_id))


def command_workflow_list(config: RuntimeConfig, state: str | None) -> list[dict[str, object]]:
    with database(config.database, readonly=True) as connection:
        require_initialized(connection)
        if state:
            rows = connection.execute(
                "SELECT * FROM workflow_state WHERE state=? ORDER BY workflow_id", (state,)
            )
        else:
            rows = connection.execute("SELECT * FROM workflow_state ORDER BY workflow_id")
        return [dict(row) for row in rows]


def command_workflow_status(config: RuntimeConfig, workflow_id: str) -> dict[str, object]:
    with database(config.database, readonly=True) as connection:
        workflow = dict(get_workflow(connection, workflow_id))
        change = dict(get_change(connection, workflow["change_id"])) if workflow["change_id"] else None
        return {"workflow": workflow, "change": change}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config")
    source.add_argument("--db")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    commands.add_parser("next-id")

    create = commands.add_parser("create")
    create.add_argument("--change-id")
    create.add_argument("--flow", choices=FLOWS, required=True)
    create.add_argument("--summary", required=True)
    create.add_argument("--source-ce")

    set_ref = commands.add_parser("set-ref")
    set_ref.add_argument("change_id")
    set_ref.add_argument("--field", required=True)
    set_ref.add_argument("--value", required=True)

    complete = commands.add_parser("complete")
    complete.add_argument("change_id")
    complete.add_argument("--summary", required=True)

    show = commands.add_parser("show")
    show.add_argument("change_id")
    listing = commands.add_parser("list")
    listing.add_argument("--status", choices=("in_progress", "completed"))

    workflow_create = commands.add_parser("workflow-create")
    workflow_create.add_argument("--flow", choices=FLOWS, required=True)
    workflow_bind = commands.add_parser("workflow-bind-change")
    workflow_bind.add_argument("workflow_id")
    workflow_bind.add_argument("change_id")
    bind_worktree = commands.add_parser("workflow-bind-worktree")
    bind_worktree.add_argument("workflow_id")
    bind_worktree.add_argument("--worktree", required=True)
    assert_worktree = commands.add_parser("workflow-assert-worktree")
    assert_worktree.add_argument("workflow_id")
    assert_worktree.add_argument("--worktree", required=True)
    workflow_stage = commands.add_parser("workflow-set-stage")
    workflow_stage.add_argument("workflow_id")
    workflow_stage.add_argument("stage", choices=("define", "implement", "verify"))
    workflow_show = commands.add_parser("workflow-show")
    workflow_show.add_argument("workflow_id")
    workflow_list = commands.add_parser("workflow-list")
    workflow_list.add_argument("--state", choices=("active", "closed"))
    workflow_status = commands.add_parser("workflow-status")
    workflow_status.add_argument("workflow_id")
    return parser


def dispatch(config: RuntimeConfig, args: argparse.Namespace) -> object:
    if args.command == "init":
        return command_init(config)
    if args.command == "next-id":
        return command_next_id(config)
    if args.command == "create":
        return command_create(config, args)
    if args.command == "set-ref":
        return command_set_ref(config, args)
    if args.command == "complete":
        return command_complete(config, args)
    if args.command == "show":
        return command_show(config, args.change_id)
    if args.command == "list":
        return command_list(config, args.status)
    if args.command == "workflow-create":
        return command_workflow_create(config, args.flow)
    if args.command == "workflow-bind-change":
        return command_workflow_bind(config, args.workflow_id, args.change_id)
    if args.command == "workflow-bind-worktree":
        return command_workflow_bind_worktree(config, args)
    if args.command == "workflow-assert-worktree":
        return command_workflow_assert(config, args)
    if args.command == "workflow-set-stage":
        return command_workflow_stage(config, args.workflow_id, args.stage)
    if args.command == "workflow-show":
        return command_workflow_show(config, args.workflow_id)
    if args.command == "workflow-list":
        return command_workflow_list(config, args.state)
    if args.command == "workflow-status":
        return command_workflow_status(config, args.workflow_id)
    raise LedgerError(f"unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args)
        emit(dispatch(config, args))
    except (LedgerError, sqlite3.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
