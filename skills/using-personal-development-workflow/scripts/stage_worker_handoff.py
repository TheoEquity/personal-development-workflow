#!/usr/bin/env python3
"""Create, validate, and atomically update durable stage-worker handoffs."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = 2
ROLE_BY_STAGE = {
    "writing_spec": "spec_worker",
    "writing_plan": "plan_worker",
    "implementation": "implementation_coordinator",
}
VALID_STATUSES = {
    "initialized",
    "working",
    "candidate_ready",
    "waiting_user",
    "approved",
    "published",
    "blocked",
    "complete",
}
ALLOWED_TRANSITIONS = {
    "initialized": {"working", "candidate_ready", "approved", "blocked", "complete"},
    "working": {"working", "candidate_ready", "approved", "blocked", "complete"},
    "candidate_ready": {"working", "waiting_user", "published", "blocked"},
    "waiting_user": {"working", "published", "blocked"},
    "approved": {"working", "blocked"},
    "blocked": {"working", "blocked"},
    "published": set(),
    "complete": set(),
}
REQUIRED_INPUT_KEYS_BY_STAGE = {
    "writing_spec": {
        "change_ref",
        "repository_path",
        "code_sha",
        "related_formal_refs",
        "acceptance_steps_ref",
    },
    "writing_plan": {
        "change_ref",
        "spec_ref",
        "test_ref",
        "plan_profile",
        "repository_path",
        "base_source",
        "base_locator",
        "base_sha",
        "baseline_details",
        "agents_inventory",
        "workspace_differences",
    },
    "implementation": {
        "change_ref",
        "spec_ref",
        "plan_ref",
        "test_ref",
        "repository_path",
        "workspace_path",
        "authorization_offer",
        "execution_contract",
    },
}
TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
CANDIDATE_STATUSES = {"candidate_ready", "waiting_user", "approved", "published"}
OFFER_KEYS = {
    "repository",
    "plan_ref",
    "plan_or_tasks",
    "base_source",
    "base_locator",
    "base_sha",
    "remote_fetch_authorized",
    "worktree_creation_authorized",
    "tdd_required",
    "tdd_exemption_reason",
    "baseline_snapshot",
    "local_commit_authorized",
    "finish_after_execution",
}
CONTRACT_KEYS = {
    "tdd_required",
    "tdd_exemption_reason",
    "baseline_snapshot",
    "local_commit_authorized",
    "local_commit_scope",
    "finish_after_execution",
}


class ContractError(ValueError):
    """Raised when a handoff violates its workflow identity or safety contract."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_token(value: Any, field: str) -> str:
    if not isinstance(value, str) or not TOKEN_RE.fullmatch(value):
        raise ContractError(f"Invalid {field}: {value!r}")
    return value


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"Invalid {field}: expected a non-empty string")
    return value.strip()


def _require_bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise ContractError(f"Invalid {field}: expected boolean")
    return value


def _require_full_sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or not FULL_SHA_RE.fullmatch(value):
        raise ContractError(f"{field} must be a full 40-character Git SHA")
    return value.lower()


def _resolve_existing_directory(value: Any, field: str) -> Path:
    text = _require_string(value, field)
    path = Path(text)
    if not path.is_absolute() or not path.is_dir():
        raise ContractError(f"{field} must be an existing absolute directory: {text}")
    return path.resolve()


def _canonical_json(value: Any, field: str) -> tuple[Any, str]:
    text = _require_string(value, field)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ContractError(f"{field} must be valid JSON") from exc
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return payload, canonical


def _git(path: Path, *args: str, field: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = ""
        if isinstance(exc, subprocess.CalledProcessError):
            detail = (exc.stderr or exc.stdout or "").strip()
        suffix = f": {detail}" if detail else ""
        raise ContractError(f"Invalid Git {field}{suffix}") from exc
    return result.stdout.strip()


def _verify_git_root(path: Path, field: str) -> None:
    top = Path(_git(path, "rev-parse", "--show-toplevel", field=field)).resolve()
    if top != path.resolve():
        raise ContractError(f"{field} must be the Git worktree root: {path}")


def _git_common_directory(path: Path, field: str) -> Path:
    raw = Path(_git(path, "rev-parse", "--git-common-dir", field=field))
    if not raw.is_absolute():
        raw = path / raw
    return raw.resolve()


def _verify_same_git_repository(
    first: Path, second: Path, first_field: str, second_field: str
) -> None:
    _verify_git_root(first, first_field)
    _verify_git_root(second, second_field)
    if _git_common_directory(first, first_field) != _git_common_directory(
        second, second_field
    ):
        raise ContractError(f"{second_field} is not a worktree of {first_field}")


def _verify_commit(repository: Path, sha: str, field: str) -> None:
    _git(repository, "cat-file", "-e", f"{sha}^{{commit}}", field=field)


def _verify_formal_ref(vault: Path, value: str, field: str) -> None:
    path, sha = value.rsplit("@", 1)
    _git(vault, "cat-file", "-e", f"{sha}:{path}", field=field)


def _normalize_input_refs(input_refs: Mapping[str, str] | None) -> dict[str, str]:
    if input_refs is None:
        return {}
    if not isinstance(input_refs, Mapping):
        raise ContractError("input_refs must be a mapping")
    normalized: dict[str, str] = {}
    for key, value in input_refs.items():
        key = _require_token(key, "input_refs key")
        normalized[key] = _require_string(value, f"input_refs[{key}]")
    return dict(sorted(normalized.items()))


def _validate_stage_role(stage: Any, role: Any) -> None:
    expected_role = ROLE_BY_STAGE.get(stage)
    if expected_role is None:
        raise ContractError(f"Unsupported stage: {stage!r}")
    if role != expected_role:
        raise ContractError(
            f"Role {role!r} does not match stage {stage!r}; expected {expected_role!r}"
        )


def _load_config(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path)
    if not path.is_absolute() or not path.is_file():
        raise ContractError(f"Configuration must be an existing absolute file: {path}")
    path = path.resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"Invalid configuration: {path}") from exc
    if not isinstance(payload, dict):
        raise ContractError("Configuration root must be an object")

    try:
        vault_value = payload["spec_vault"]
        database_value = payload["database"]
        repositories_value = payload["repositories"]
    except KeyError as exc:
        raise ContractError(
            "Configuration must contain spec_vault, database, and repositories"
        ) from exc

    vault = _resolve_existing_directory(vault_value, "spec_vault")
    _verify_git_root(vault, "spec_vault")
    local_root = (vault / ".local").resolve()
    if not local_root.is_dir():
        raise ContractError(f"spec_vault/.local must exist: {local_root}")

    database = Path(_require_string(database_value, "database"))
    if not database.is_absolute() or not database.is_file():
        raise ContractError(f"database must be an existing absolute file: {database}")
    database = database.resolve()
    if not database.is_relative_to(local_root):
        raise ContractError("database must be inside spec_vault/.local")

    if not isinstance(repositories_value, Mapping) or not repositories_value:
        raise ContractError("repositories must be a non-empty mapping")
    repositories: dict[str, Path] = {}
    for name, value in repositories_value.items():
        name = _require_token(name, "repository name")
        repositories[name] = _resolve_existing_directory(
            value, f"repositories[{name}]"
        )
        _verify_git_root(repositories[name], f"repositories[{name}]")

    return {
        "path": path,
        "vault": vault,
        "local_root": local_root,
        "database": database,
        "repositories": repositories,
    }


def _formal_ref(change_id: str, value: str, kind: str) -> str:
    paths = {
        "change_ref": f"changes/{change_id}/change.md",
        "spec_ref": f"specs/{change_id}.md",
        "plan_ref": f"plans/{change_id}.md",
        "test_ref": f"tests/{change_id}.md",
    }
    expected_path = paths[kind]
    match = re.fullmatch(
        rf"{re.escape(expected_path)}@([0-9a-fA-F]{{40}})", value
    )
    if match is None:
        raise ContractError(
            f"{kind} must match {expected_path}@<40-character Git SHA>"
        )
    return f"{expected_path}@{match.group(1).lower()}"


def _normalize_tdd_fields(payload: dict[str, Any], prefix: str) -> None:
    required = _require_bool(payload.get("tdd_required"), f"{prefix}.tdd_required")
    reason = payload.get("tdd_exemption_reason")
    if required:
        if reason is not None:
            raise ContractError(f"{prefix}.tdd_exemption_reason must be null")
    else:
        payload["tdd_exemption_reason"] = _require_string(
            reason, f"{prefix}.tdd_exemption_reason"
        )


def _normalize_authority_objects(
    refs: dict[str, str], repository: Path, workspace: Path
) -> None:
    offer_value, _ = _canonical_json(refs["authorization_offer"], "authorization_offer")
    contract_value, _ = _canonical_json(
        refs["execution_contract"], "execution_contract"
    )
    if not isinstance(offer_value, dict) or set(offer_value) != OFFER_KEYS:
        raise ContractError("authorization_offer has an invalid field set")
    if not isinstance(contract_value, dict) or set(contract_value) != CONTRACT_KEYS:
        raise ContractError("execution_contract has an invalid field set")

    plan_ref = refs["plan_ref"]
    if Path(_require_string(offer_value["repository"], "authorization_offer.repository")).resolve() != repository:
        raise ContractError("authorization_offer.repository does not match repository_path")
    offer_value["repository"] = str(repository)
    if offer_value["plan_ref"] != plan_ref or offer_value["plan_or_tasks"] != [plan_ref]:
        raise ContractError("authorization_offer must bind the exact current plan_ref")
    source = offer_value["base_source"]
    if source not in {"local", "remote"}:
        raise ContractError("authorization_offer.base_source must be local or remote")
    offer_value["base_sha"] = _require_full_sha(
        offer_value["base_sha"], "authorization_offer.base_sha"
    )
    locator = offer_value["base_locator"]
    locator_keys = {"kind", "remote", "worktree", "branch", "detached_sha"}
    if not isinstance(locator, dict) or set(locator) != locator_keys:
        raise ContractError("authorization_offer.base_locator has an invalid field set")
    if locator["kind"] != source:
        raise ContractError("authorization_offer base locator kind mismatch")
    if source == "remote":
        locator["remote"] = _require_string(locator["remote"], "base_locator.remote")
        if locator["worktree"] is not None or locator["detached_sha"] is not None:
            raise ContractError("remote base locator cannot contain worktree/detached_sha")
        locator["branch"] = _require_string(locator["branch"], "base_locator.branch")
    else:
        if locator["remote"] is not None:
            raise ContractError("local base locator remote must be null")
        locator["worktree"] = str(
            _resolve_existing_directory(locator["worktree"], "base_locator.worktree")
        )
        branch = locator["branch"]
        detached = locator["detached_sha"]
        if branch is None:
            locator["detached_sha"] = _require_full_sha(
                detached, "base_locator.detached_sha"
            )
        else:
            locator["branch"] = _require_string(branch, "base_locator.branch")
            if detached is not None:
                raise ContractError("branch locator detached_sha must be null")

    if _require_bool(
        offer_value["remote_fetch_authorized"], "authorization_offer.remote_fetch_authorized"
    ) != (source == "remote"):
        raise ContractError("remote_fetch_authorized does not match base_source")
    if _require_bool(
        offer_value["worktree_creation_authorized"],
        "authorization_offer.worktree_creation_authorized",
    ) is not True:
        raise ContractError("worktree_creation_authorized must be true")
    _normalize_tdd_fields(offer_value, "authorization_offer")
    if offer_value["baseline_snapshot"] is not None:
        raise ContractError("personal-workflow SDD baseline_snapshot must be null")
    if _require_bool(
        offer_value["local_commit_authorized"],
        "authorization_offer.local_commit_authorized",
    ) is not True:
        raise ContractError("personal-workflow SDD must authorize scoped local commits")
    if _require_bool(
        offer_value["finish_after_execution"],
        "authorization_offer.finish_after_execution",
    ) is not False:
        raise ContractError("finish_after_execution must be false")

    _normalize_tdd_fields(contract_value, "execution_contract")
    if contract_value["baseline_snapshot"] is not None:
        raise ContractError("execution_contract.baseline_snapshot must be null")
    if _require_bool(
        contract_value["local_commit_authorized"],
        "execution_contract.local_commit_authorized",
    ) is not True:
        raise ContractError("execution_contract must authorize scoped local commits")
    if _require_bool(
        contract_value["finish_after_execution"],
        "execution_contract.finish_after_execution",
    ) is not False:
        raise ContractError("execution_contract.finish_after_execution must be false")
    scope = contract_value["local_commit_scope"]
    scope_keys = {"repositories", "workspace_or_branch", "plan_or_tasks"}
    if not isinstance(scope, dict) or set(scope) != scope_keys:
        raise ContractError("execution_contract.local_commit_scope has an invalid field set")
    if scope["repositories"] != [str(repository)]:
        raise ContractError("execution_contract must bind the configured repository")
    workspace_or_branch = scope["workspace_or_branch"]
    if not isinstance(workspace_or_branch, dict) or set(workspace_or_branch) != {"workspace", "branch"}:
        raise ContractError("workspace_or_branch has an invalid field set")
    if Path(_require_string(workspace_or_branch["workspace"], "workspace_or_branch.workspace")).resolve() != workspace:
        raise ContractError("execution_contract workspace does not match workspace_path")
    workspace_or_branch["workspace"] = str(workspace)
    branch = workspace_or_branch["branch"]
    if branch is not None:
        workspace_or_branch["branch"] = _require_string(branch, "workspace_or_branch.branch")
    if scope["plan_or_tasks"] != [plan_ref]:
        raise ContractError("execution_contract must bind the exact current plan_ref")

    for field in (
        "tdd_required",
        "tdd_exemption_reason",
        "baseline_snapshot",
        "local_commit_authorized",
        "finish_after_execution",
    ):
        if contract_value[field] != offer_value[field]:
            raise ContractError(f"execution_contract changed authorization field {field}")

    refs["authorization_offer"] = json.dumps(
        offer_value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    refs["execution_contract"] = json.dumps(
        contract_value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _prepare_stage_inputs(
    stage: str,
    input_refs: Mapping[str, str] | None,
    change_id: str,
    config: Mapping[str, Any],
) -> dict[str, str]:
    refs = _normalize_input_refs(input_refs)
    required = REQUIRED_INPUT_KEYS_BY_STAGE.get(stage)
    if required is None:
        raise ContractError(f"Unsupported stage: {stage!r}")
    missing = sorted(required - refs.keys())
    if missing:
        raise ContractError(
            f"Missing required input_refs for {stage}: {', '.join(missing)}"
        )

    repository = _resolve_existing_directory(refs["repository_path"], "repository_path")
    if repository not in config["repositories"].values():
        raise ContractError("repository_path is not declared in project configuration")
    refs["repository_path"] = str(repository)
    refs["change_ref"] = _formal_ref(change_id, refs["change_ref"], "change_ref")
    _verify_formal_ref(config["vault"], refs["change_ref"], "change_ref")

    if stage == "writing_spec":
        refs["code_sha"] = _require_full_sha(refs["code_sha"], "code_sha")
        _verify_commit(repository, refs["code_sha"], "code_sha")
        return dict(sorted(refs.items()))

    refs["spec_ref"] = _formal_ref(change_id, refs["spec_ref"], "spec_ref")
    refs["test_ref"] = _formal_ref(change_id, refs["test_ref"], "test_ref")
    _verify_formal_ref(config["vault"], refs["spec_ref"], "spec_ref")
    _verify_formal_ref(config["vault"], refs["test_ref"], "test_ref")
    if stage == "writing_plan":
        if refs["plan_profile"] not in {"lean", "full"}:
            raise ContractError("plan_profile must be lean or full")
        if refs["base_source"] not in {"local", "remote"}:
            raise ContractError("base_source must be local or remote")
        refs["base_sha"] = _require_full_sha(refs["base_sha"], "base_sha")
        _verify_commit(repository, refs["base_sha"], "base_sha")
        details, _ = _canonical_json(refs["baseline_details"], "baseline_details")
        if not isinstance(details, dict):
            raise ContractError("baseline_details must be a JSON object")
        required_details = (
            {"base_remote", "base_branch"}
            if refs["base_source"] == "remote"
            else {
                "base_worktree",
                "base_local_branch",
                "base_detached_sha",
                "pushed_status",
                "dirty_exclusions",
            }
        )
        missing_details = sorted(required_details - details.keys())
        if missing_details:
            raise ContractError(
                "Missing baseline_details fields: " + ", ".join(missing_details)
            )
        if refs["base_source"] == "remote":
            details["base_remote"] = _require_string(
                details["base_remote"], "baseline_details.base_remote"
            )
            details["base_branch"] = _require_string(
                details["base_branch"], "baseline_details.base_branch"
            )
        else:
            details["base_worktree"] = str(
                _resolve_existing_directory(
                    details["base_worktree"], "baseline_details.base_worktree"
                )
            )
            _verify_same_git_repository(
                repository,
                Path(details["base_worktree"]),
                "repository_path",
                "baseline_details.base_worktree",
            )
            branch = details["base_local_branch"]
            detached = details["base_detached_sha"]
            if branch is None:
                details["base_detached_sha"] = _require_full_sha(
                    detached, "baseline_details.base_detached_sha"
                )
            else:
                details["base_local_branch"] = _require_string(
                    branch, "baseline_details.base_local_branch"
                )
                if detached is not None:
                    raise ContractError(
                        "baseline_details.base_detached_sha must be null for a branch"
                    )
            details["pushed_status"] = _require_string(
                details["pushed_status"], "baseline_details.pushed_status"
            )
            details["dirty_exclusions"] = _require_string(
                details["dirty_exclusions"], "baseline_details.dirty_exclusions"
            )
        refs["baseline_details"] = json.dumps(
            details, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return dict(sorted(refs.items()))

    refs["plan_ref"] = _formal_ref(change_id, refs["plan_ref"], "plan_ref")
    _verify_formal_ref(config["vault"], refs["plan_ref"], "plan_ref")
    workspace = _resolve_existing_directory(refs["workspace_path"], "workspace_path")
    _verify_same_git_repository(
        repository, workspace, "repository_path", "workspace_path"
    )
    refs["workspace_path"] = str(workspace)
    _normalize_authority_objects(refs, repository, workspace)
    offer = json.loads(refs["authorization_offer"])
    _verify_commit(repository, offer["base_sha"], "authorization_offer.base_sha")
    if offer["base_source"] == "local":
        _verify_same_git_repository(
            repository,
            Path(offer["base_locator"]["worktree"]),
            "repository_path",
            "authorization_offer.base_locator.worktree",
        )
    return dict(sorted(refs.items()))


def _run_fingerprint(
    config: Mapping[str, Any],
    workflow_id: str,
    change_id: str,
    stage: str,
    role: str,
    input_refs: Mapping[str, str],
) -> str:
    identity = {
        "schema_version": SCHEMA_VERSION,
        "config_path": str(config["path"]),
        "spec_vault": str(config["vault"]),
        "workflow_id": workflow_id,
        "change_id": change_id,
        "stage": stage,
        "role": role,
        "input_refs": input_refs,
    }
    encoded = json.dumps(
        identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _workspace_paths(
    config: Mapping[str, Any],
    workflow_id: str,
    change_id: str,
    stage: str,
    role: str,
    input_refs: Mapping[str, str],
) -> dict[str, Path]:
    fingerprint = _run_fingerprint(
        config, workflow_id, change_id, stage, role, input_refs
    )
    workspace = (
        config["local_root"]
        / "stage-workers"
        / workflow_id
        / change_id
        / stage
        / f"run-{fingerprint}"
    )
    resolved_workspace = workspace.resolve()
    if not resolved_workspace.is_relative_to(config["local_root"]):
        raise ContractError("Stage-worker workspace escapes spec_vault/.local")
    return {
        "workspace": resolved_workspace,
        "handoff": resolved_workspace / "handoff.json",
        "candidate": resolved_workspace / "candidate.md",
        "report": resolved_workspace / "report.md",
        "offer": resolved_workspace / "authorization-offer.json",
        "contract": resolved_workspace / "execution-contract.json",
    }


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_regular_file(path: Path, field: str, *, allow_empty: bool = False) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ContractError(f"{field} must be a regular file: {path}")
    data = path.read_bytes()
    if not allow_empty and not data:
        raise ContractError(f"{field} cannot be empty: {path}")
    return data


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_name = handle.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name and Path(temporary_name).exists():
            Path(temporary_name).unlink()


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    _atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _write_immutable_json(path: Path, canonical_json: str, field: str) -> str:
    expected = (canonical_json + "\n").encode("utf-8")
    if path.exists():
        actual = _read_regular_file(path, field)
        if actual != expected:
            raise ContractError(f"Immutable {field} content mismatch: {path}")
    else:
        _atomic_write_text(path, canonical_json + "\n")
    return _sha256_bytes(expected)


@contextmanager
def _handoff_lock(handoff_path: Path, timeout_seconds: float = 5.0):
    lock_path = handoff_path.with_name("handoff.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    deadline = time.monotonic() + timeout_seconds
    locked = False
    try:
        while not locked:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise ContractError(f"Timed out acquiring handoff lock: {lock_path}") from exc
                time.sleep(0.05)
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _require_declared_path(payload: Mapping[str, Any], field: str, expected: Path) -> None:
    value = payload.get(field)
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise ContractError(f"Invalid {field}")
    if Path(value).resolve() != expected.resolve():
        raise ContractError(f"{field} does not match the derived run path")


def _read_handoff(config_path: str | Path, handoff_path: str | Path) -> dict[str, Any]:
    config = _load_config(config_path)
    path = Path(handoff_path)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ContractError(f"Handoff must be an existing regular absolute file: {path}")
    path = path.resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"Invalid handoff JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ContractError("Handoff root must be a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("Unsupported handoff schema_version")

    workflow_id = _require_token(payload.get("workflow_id"), "workflow_id")
    change_id = _require_token(payload.get("change_id"), "change_id")
    stage = payload.get("stage")
    role = payload.get("role")
    _validate_stage_role(stage, role)
    refs = _prepare_stage_inputs(stage, payload.get("input_refs"), change_id, config)
    payload["input_refs"] = refs
    expected = _workspace_paths(
        config, workflow_id, change_id, stage, role, refs
    )
    if path != expected["handoff"]:
        raise ContractError("Handoff path does not match its derived run identity")
    if payload.get("config_path") != str(config["path"]):
        raise ContractError("Handoff config_path mismatch")
    if payload.get("spec_vault") != str(config["vault"]):
        raise ContractError("Handoff spec_vault mismatch")
    _require_declared_path(payload, "candidate_path", expected["candidate"])
    _require_declared_path(payload, "report_path", expected["report"])
    for field in ("candidate_path", "report_path"):
        declared = Path(payload[field])
        if declared.exists() and declared.is_symlink():
            raise ContractError(f"{field} cannot be a symlink")

    status = payload.get("status")
    if status not in VALID_STATUSES:
        raise ContractError(f"Unsupported handoff status: {status!r}")
    revision = payload.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise ContractError("Invalid handoff revision")

    candidate_sha = payload.get("candidate_sha256")
    if candidate_sha is not None and (
        not isinstance(candidate_sha, str) or not DIGEST_RE.fullmatch(candidate_sha)
    ):
        raise ContractError("Invalid candidate_sha256")
    if status in CANDIDATE_STATUSES:
        actual_sha = _sha256_bytes(
            _read_regular_file(expected["candidate"], "candidate_path")
        )
        if candidate_sha != actual_sha:
            raise ContractError("candidate.md does not match candidate_sha256")

    if stage == "implementation":
        _require_declared_path(
            payload, "authorization_offer_path", expected["offer"]
        )
        _require_declared_path(
            payload, "execution_contract_path", expected["contract"]
        )
        offer_data = _read_regular_file(expected["offer"], "authorization_offer_path")
        contract_data = _read_regular_file(
            expected["contract"], "execution_contract_path"
        )
        if offer_data != (refs["authorization_offer"] + "\n").encode("utf-8"):
            raise ContractError("authorization_offer file content mismatch")
        if contract_data != (refs["execution_contract"] + "\n").encode("utf-8"):
            raise ContractError("execution_contract file content mismatch")
        if payload.get("authorization_offer_sha256") != _sha256_bytes(offer_data):
            raise ContractError("authorization_offer digest mismatch")
        if payload.get("execution_contract_sha256") != _sha256_bytes(contract_data):
            raise ContractError("execution_contract digest mismatch")
    else:
        for field in (
            "authorization_offer_path",
            "execution_contract_path",
            "authorization_offer_sha256",
            "execution_contract_sha256",
        ):
            if payload.get(field) is not None:
                raise ContractError(f"{field} must be null outside implementation")
    return payload


def init_handoff(
    config_path: str | Path,
    *,
    workflow_id: str,
    change_id: str,
    stage: str,
    role: str,
    input_refs: Mapping[str, str] | None,
) -> dict[str, Any]:
    """Create or idempotently recover one identity-bound stage-worker run."""

    workflow_id = _require_token(workflow_id, "workflow_id")
    change_id = _require_token(change_id, "change_id")
    _validate_stage_role(stage, role)
    config = _load_config(config_path)
    refs = _prepare_stage_inputs(stage, input_refs, change_id, config)
    paths = _workspace_paths(config, workflow_id, change_id, stage, role, refs)
    paths["workspace"].mkdir(parents=True, exist_ok=True)

    offer_path: str | None = None
    contract_path: str | None = None
    offer_sha: str | None = None
    contract_sha: str | None = None
    if stage == "implementation":
        offer_sha = _write_immutable_json(
            paths["offer"], refs["authorization_offer"], "authorization_offer"
        )
        contract_sha = _write_immutable_json(
            paths["contract"], refs["execution_contract"], "execution_contract"
        )
        offer_path = str(paths["offer"])
        contract_path = str(paths["contract"])

    if paths["handoff"].exists():
        payload = validate_handoff(
            config["path"],
            paths["handoff"],
            workflow_id=workflow_id,
            change_id=change_id,
            stage=stage,
            role=role,
            input_refs=refs,
        )
    else:
        now = _utc_now()
        payload = {
            "schema_version": SCHEMA_VERSION,
            "config_path": str(config["path"]),
            "spec_vault": str(config["vault"]),
            "workflow_id": workflow_id,
            "change_id": change_id,
            "stage": stage,
            "role": role,
            "status": "initialized",
            "revision": 0,
            "input_refs": refs,
            "candidate_path": str(paths["candidate"]),
            "report_path": str(paths["report"]),
            "candidate_sha256": None,
            "authorization_offer_path": offer_path,
            "execution_contract_path": contract_path,
            "authorization_offer_sha256": offer_sha,
            "execution_contract_sha256": contract_sha,
            "artifact_ref": None,
            "review_status": None,
            "summary": [],
            "needs_user_decision": [],
            "blockers": [],
            "created_at": now,
            "updated_at": now,
        }
        _atomic_write_json(paths["handoff"], payload)

    return {
        "workspace": str(paths["workspace"]),
        "handoff_path": str(paths["handoff"]),
        "candidate_path": payload["candidate_path"],
        "report_path": payload["report_path"],
        "authorization_offer_path": payload["authorization_offer_path"],
        "execution_contract_path": payload["execution_contract_path"],
        "status": payload["status"],
        "revision": payload["revision"],
    }


def validate_handoff(
    config_path: str | Path,
    handoff_path: str | Path,
    *,
    workflow_id: str,
    change_id: str,
    stage: str,
    role: str,
    input_refs: Mapping[str, str] | None,
) -> dict[str, Any]:
    """Validate exact config, identity, inputs, paths, and immutable contents."""

    workflow_id = _require_token(workflow_id, "workflow_id")
    change_id = _require_token(change_id, "change_id")
    _validate_stage_role(stage, role)
    config = _load_config(config_path)
    expected_refs = _prepare_stage_inputs(stage, input_refs, change_id, config)
    payload = _read_handoff(config["path"], handoff_path)
    expected = {
        "workflow_id": workflow_id,
        "change_id": change_id,
        "stage": stage,
        "role": role,
        "input_refs": expected_refs,
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ContractError(
                f"Handoff {field} mismatch: expected {value!r}, got {payload.get(field)!r}"
            )
    return payload


def _normalize_text_list(values: Iterable[str] | None, field: str) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        raise ContractError(f"{field} must be a list of strings")
    result: list[str] = []
    for value in values:
        result.append(_require_string(value, f"{field} entry"))
    return result


def _normalize_optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, field)


def write_handoff(
    config_path: str | Path,
    handoff_path: str | Path,
    *,
    expected_revision: int,
    status: str,
    artifact_ref: str | None = None,
    review_status: str | None = None,
    summary: Iterable[str] | None = None,
    needs_user_decision: Iterable[str] | None = None,
    blockers: Iterable[str] | None = None,
    confirmed_candidate_sha256: str | None = None,
) -> dict[str, Any]:
    """Compare-and-swap one legal result transition while preserving identity."""

    if status not in VALID_STATUSES:
        raise ContractError(f"Unsupported handoff status: {status!r}")
    if not isinstance(expected_revision, int) or isinstance(expected_revision, bool) or expected_revision < 0:
        raise ContractError("expected_revision must be a non-negative integer")
    path = Path(handoff_path)
    if not path.is_absolute():
        raise ContractError("handoff_path must be absolute")

    with _handoff_lock(path):
        payload = _read_handoff(config_path, path)
        if payload["revision"] != expected_revision:
            raise ContractError(
                f"Stale handoff revision: expected {expected_revision}, current {payload['revision']}"
            )
        current_status = payload["status"]
        if status not in ALLOWED_TRANSITIONS[current_status]:
            raise ContractError(
                f"Illegal handoff transition: {current_status} -> {status}"
            )

        normalized_artifact = _normalize_optional_string(artifact_ref, "artifact_ref")
        normalized_review = _normalize_optional_string(review_status, "review_status")
        normalized_summary = _normalize_text_list(summary, "summary")
        normalized_decisions = _normalize_text_list(
            needs_user_decision, "needs_user_decision"
        )
        normalized_blockers = _normalize_text_list(blockers, "blockers")

        candidate_sha = payload.get("candidate_sha256")
        candidate_text: str | None = None
        if status in CANDIDATE_STATUSES:
            candidate_data = _read_regular_file(
                Path(payload["candidate_path"]), "candidate_path"
            )
            candidate_sha = _sha256_bytes(candidate_data)
            candidate_text = candidate_data.decode("utf-8")

        if payload["role"] == "plan_worker" and status == "approved":
            if normalized_artifact is None:
                raise ContractError(
                    "Approved Plan handoff requires the exact immutable candidate plan ref"
                )
            try:
                normalized_artifact = _formal_ref(
                    payload["change_id"], normalized_artifact, "plan_ref"
                )
            except ContractError as exc:
                raise ContractError(
                    "Approved Plan handoff requires the exact immutable candidate plan ref"
                ) from exc
            _verify_formal_ref(
                Path(payload["spec_vault"]), normalized_artifact, "artifact_ref"
            )
            if normalized_review != "Approved":
                raise ContractError(
                    "Approved Plan handoff requires review_status=Approved"
                )
            if normalized_blockers:
                raise ContractError("Approved Plan handoff cannot contain blockers")
            if candidate_text is None or normalized_artifact not in candidate_text:
                raise ContractError("Plan candidate.md must name the approved artifact_ref")

        if payload["role"] == "spec_worker" and status == "published":
            if normalized_artifact is None:
                raise ContractError("Published Spec requires the exact immutable spec_ref")
            try:
                normalized_artifact = _formal_ref(
                    payload["change_id"], normalized_artifact, "spec_ref"
                )
            except ContractError as exc:
                raise ContractError(
                    "Published Spec requires the exact immutable spec_ref"
                ) from exc
            _verify_formal_ref(
                Path(payload["spec_vault"]), normalized_artifact, "artifact_ref"
            )
            if (
                not isinstance(confirmed_candidate_sha256, str)
                or not DIGEST_RE.fullmatch(confirmed_candidate_sha256)
                or confirmed_candidate_sha256 != candidate_sha
            ):
                raise ContractError(
                    "Published Spec must match the exact user-confirmed candidate digest"
                )

        payload["status"] = status
        payload["revision"] = expected_revision + 1
        payload["candidate_sha256"] = candidate_sha
        payload["artifact_ref"] = normalized_artifact
        payload["review_status"] = normalized_review
        payload["summary"] = normalized_summary
        payload["needs_user_decision"] = normalized_decisions
        payload["blockers"] = normalized_blockers
        payload["updated_at"] = _utc_now()
        _atomic_write_json(path, payload)
        return payload


def _parse_key_values(values: Iterable[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in values:
        if not isinstance(item, str) or "=" not in item:
            raise ContractError(f"Expected KEY=VALUE, got {item!r}")
        key, value = item.split("=", 1)
        if key in result:
            raise ContractError(f"Duplicate input ref: {key}")
        result[key] = value
    return _normalize_input_refs(result)


def _identity_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--change-id", required=True)
    parser.add_argument("--stage", choices=sorted(ROLE_BY_STAGE), required=True)
    parser.add_argument("--role", choices=sorted(ROLE_BY_STAGE.values()), required=True)
    parser.add_argument("--input-ref", action="append", default=[], metavar="KEY=VALUE")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--config", required=True)
    _identity_arguments(init_parser)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--config", required=True)
    validate_parser.add_argument("--handoff", required=True)
    _identity_arguments(validate_parser)

    write_parser = subparsers.add_parser("write")
    write_parser.add_argument("--config", required=True)
    write_parser.add_argument("--handoff", required=True)
    write_parser.add_argument("--expected-revision", type=int, required=True)
    write_parser.add_argument("--status", choices=sorted(VALID_STATUSES), required=True)
    write_parser.add_argument("--artifact-ref")
    write_parser.add_argument("--review-status")
    write_parser.add_argument("--summary", action="append", default=[])
    write_parser.add_argument("--decision", action="append", default=[])
    write_parser.add_argument("--blocker", action="append", default=[])
    write_parser.add_argument("--confirmed-candidate-sha256")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = init_handoff(
                args.config,
                workflow_id=args.workflow_id,
                change_id=args.change_id,
                stage=args.stage,
                role=args.role,
                input_refs=_parse_key_values(args.input_ref),
            )
        elif args.command == "validate":
            result = validate_handoff(
                args.config,
                args.handoff,
                workflow_id=args.workflow_id,
                change_id=args.change_id,
                stage=args.stage,
                role=args.role,
                input_refs=_parse_key_values(args.input_ref),
            )
        else:
            result = write_handoff(
                args.config,
                args.handoff,
                expected_revision=args.expected_revision,
                status=args.status,
                artifact_ref=args.artifact_ref,
                review_status=args.review_status,
                summary=args.summary,
                needs_user_decision=args.decision,
                blockers=args.blocker,
                confirmed_candidate_sha256=args.confirmed_candidate_sha256,
            )
    except ContractError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
