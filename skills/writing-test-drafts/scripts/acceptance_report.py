#!/usr/bin/env python3
"""Validate a test draft and its bound acceptance report.

This module is the executable grammar owned by the writing-test-drafts skill.
It intentionally uses only the Python standard library so ledger and router
callers can import it without copying its Markdown grammar.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Sequence


TEST_ID_PATTERN = re.compile(r"T-\d{3}")
CHANGE_ID_PATTERN = re.compile(r"CE-\d{4}")
FULL_SHA_PATTERN = r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})"
TEST_REF_PATTERN = re.compile(rf"tests/(?!.*(?:^|/)\.\.(?:/|$))[^@\r\n]+\.md@{FULL_SHA_PATTERN}")
CODE_REF_PATTERN = re.compile(rf"[^@\s]+@{FULL_SHA_PATTERN}")
PLACEHOLDER_PATTERN = re.compile(
    r"(?:<[^>]+>|\b(?:todo|tbd|placeholder|xxx)\b|待填写|待补充|未提供)", re.IGNORECASE
)
CANONICAL_STATUSES = ("passed", "failed", "not_executed")
CANONICAL_OVERALL = ("passed", "failed", "incomplete")
HUMAN_OVERALL = {"passed": "通过", "failed": "失败", "incomplete": "未完成"}
FAILURE_HEADER = ("test_id", "失败测试项", "预期结果", "实际结果", "错误摘要", "证据与日志")
REUSED_EVIDENCE_PREFIX = "复用自动化证据："
REUSED_EVIDENCE_FIELDS = {
    "code_sha",
    "command",
    "environment_fingerprint",
    "input_fingerprint",
    "scope",
    "result",
    "produced_by",
}


class AcceptanceReportError(ValueError):
    """Raised when a test draft or acceptance report violates the grammar."""


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise AcceptanceReportError(f"JSON object contains duplicate key: {key}")
        result[key] = value
    return result


def strip_fenced_blocks(text: str) -> str:
    """Remove fenced code blocks so examples cannot satisfy mechanical fields."""

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
    if fence is not None:
        raise AcceptanceReportError("Markdown contains an unclosed fenced code block")
    return "\n".join(visible)


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise AcceptanceReportError("acceptance report must start with YAML frontmatter")
    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration as error:
        raise AcceptanceReportError("acceptance report frontmatter is not closed") from error

    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*?)\s*", line)
        if match is None:
            raise AcceptanceReportError(
                "acceptance report frontmatter must use scalar key: value fields"
            )
        key, value = match.groups()
        if key in fields:
            raise AcceptanceReportError(f"duplicate acceptance report frontmatter field: {key}")
        fields[key] = value
    return fields, "\n".join(lines[end + 1 :])


def _extract_h2(text: str, heading: str, document: str, *, required: bool = True) -> str | None:
    lines = text.splitlines()
    positions = [index for index, line in enumerate(lines) if line.strip() == heading]
    if not positions:
        if required:
            raise AcceptanceReportError(f"{document} must contain one {heading} section")
        return None
    if len(positions) != 1:
        raise AcceptanceReportError(f"{document} must contain one {heading} section")
    start = positions[0] + 1
    end = next(
        (index for index in range(start, len(lines)) if re.fullmatch(r"##\s+.+", lines[index].strip())),
        len(lines),
    )
    return "\n".join(lines[start:end])


def _test_sections(text: str, document: str) -> list[tuple[str, str, list[str]]]:
    lines = text.splitlines()
    headings: list[tuple[int, str, str]] = []
    for index, line in enumerate(lines):
        match = re.fullmatch(r"###\s+(T-\d{3})\s+(.+?)\s*", line)
        if match:
            headings.append((index, match.group(1), match.group(2).strip()))
    if not headings:
        raise AcceptanceReportError(f"{document} must contain canonical T-001 test items")

    sections: list[tuple[str, str, list[str]]] = []
    for position, (start, test_id, title) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        if not title or PLACEHOLDER_PATTERN.search(title):
            raise AcceptanceReportError(f"{document} item {test_id} must have a concrete title")
        sections.append((test_id, title, lines[start + 1 : end]))
    identifiers = [item[0] for item in sections]
    if len(identifiers) != len(set(identifiers)):
        raise AcceptanceReportError(f"{document} contains duplicate test IDs")
    return sections


def _normalized_block(lines: Sequence[str]) -> tuple[str, ...]:
    return tuple(line.strip() for line in lines if line.strip())


def _plain_block(lines: Sequence[str]) -> str:
    normalized = _normalized_block(lines)
    return " ".join(
        re.sub(r"^(?:[-*+]\s*|\d+[.)]\s*)", "", line).strip() for line in normalized
    ).strip()


def _require_meaningful(
    lines: Sequence[str], label: str, *, allow_none: bool = False, require_reason: bool = False
) -> None:
    plain = _plain_block(lines)
    empty_values = {"", "-", "—", "n/a", "none"}
    if not allow_none:
        empty_values.add("无")
    if plain.lower() in empty_values or PLACEHOLDER_PATTERN.search(plain):
        raise AcceptanceReportError(f"{label} must contain a concrete value")
    if require_reason and plain.rstrip("。.!！") == "未执行":
        raise AcceptanceReportError(f"{label} must explain why the test was not executed")


def _parse_labeled_sections(
    lines: Sequence[str], labels: tuple[str, ...], document: str
) -> dict[str, list[str]]:
    all_labels = ("操作", "预期结果", "实际结果", "证据")
    found: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = re.fullmatch(r"\s*(操作|预期结果|实际结果|证据)：\s*", line)
        if match:
            found.append((index, match.group(1)))
    names = [name for _, name in found]
    if names != list(labels):
        raise AcceptanceReportError(
            f"{document} must contain exactly these ordered sections: " + ", ".join(labels)
        )
    if any(name not in all_labels for name in names):
        raise AcceptanceReportError(f"{document} contains an unsupported labeled section")

    result: dict[str, list[str]] = {}
    for position, (start, label) in enumerate(found):
        end = found[position + 1][0] if position + 1 < len(found) else len(lines)
        result[label] = list(lines[start + 1 : end])
    return result


def parse_test_draft(test_text: str) -> list[dict[str, object]]:
    """Parse and validate the formal test-draft grammar."""

    visible = strip_fenced_blocks(test_text)
    flow = _extract_h2(visible, "## 测试流程", "test draft")
    assert flow is not None
    items: list[dict[str, object]] = []
    for heading_id, title, lines in _test_sections(flow, "test draft"):
        id_lines = [line for line in lines if re.match(r"\s*test_id\s*:", line)]
        if len(id_lines) != 1:
            raise AcceptanceReportError(f"test draft item {heading_id} must contain one test_id")
        match = re.fullmatch(r"\s*test_id\s*:\s*(T-\d{3})\s*", id_lines[0])
        if match is None or match.group(1) != heading_id or not TEST_ID_PATTERN.fullmatch(heading_id):
            raise AcceptanceReportError(
                f"test draft item {heading_id} has a noncanonical or mismatched test_id"
            )
        if any(re.match(r"\s*status\s*:", line) for line in lines):
            raise AcceptanceReportError(f"test draft item {heading_id} must not contain status")
        parts = _parse_labeled_sections(lines, ("操作", "预期结果"), f"test draft item {heading_id}")
        _require_meaningful(parts["操作"], f"test draft item {heading_id} 操作")
        _require_meaningful(parts["预期结果"], f"test draft item {heading_id} 预期结果")
        items.append(
            {
                "test_id": heading_id,
                "title": title,
                "expected": list(_normalized_block(parts["预期结果"])),
            }
        )
    return items


def parse_acceptance_items(report_body: str) -> list[dict[str, object]]:
    """Parse and validate report items from a frontmatter-free report body."""

    visible = strip_fenced_blocks(report_body)
    result_section = _extract_h2(visible, "## 测试项结果", "acceptance report")
    assert result_section is not None
    items: list[dict[str, object]] = []
    for heading_id, title, lines in _test_sections(result_section, "acceptance report"):
        id_lines = [line for line in lines if re.match(r"\s*test_id\s*:", line)]
        status_lines = [line for line in lines if re.match(r"\s*status\s*:", line)]
        if len(id_lines) != 1 or len(status_lines) != 1:
            raise AcceptanceReportError(
                f"acceptance item {heading_id} must contain one test_id and one status"
            )
        id_match = re.fullmatch(r"\s*test_id\s*:\s*(T-\d{3})\s*", id_lines[0])
        status_match = re.fullmatch(
            r"\s*status\s*:\s*(passed|failed|not_executed)\s*", status_lines[0]
        )
        if id_match is None or id_match.group(1) != heading_id:
            raise AcceptanceReportError(
                f"acceptance item {heading_id} has a noncanonical or mismatched test_id"
            )
        if status_match is None:
            raise AcceptanceReportError(
                f"acceptance item {heading_id} must use a canonical status"
            )
        status = status_match.group(1)
        parts = _parse_labeled_sections(
            lines, ("预期结果", "实际结果", "证据"), f"acceptance item {heading_id}"
        )
        _require_meaningful(parts["预期结果"], f"acceptance item {heading_id} 预期结果")
        _require_meaningful(
            parts["实际结果"],
            f"acceptance item {heading_id} 实际结果",
            require_reason=status == "not_executed",
        )
        _require_meaningful(
            parts["证据"],
            f"acceptance item {heading_id} 证据",
            allow_none=status == "not_executed",
        )
        items.append(
            {
                "test_id": heading_id,
                "title": title,
                "status": status,
                "expected": list(_normalized_block(parts["预期结果"])),
                "actual": list(_normalized_block(parts["实际结果"])),
                "evidence": list(_normalized_block(parts["证据"])),
            }
        )
    return items


def _summary_lines(lines: Sequence[str]) -> tuple[str, ...]:
    values: list[str] = []
    for line in lines:
        value = re.sub(r"^(?:[-*+]\s*|\d+[.)]\s*)", "", line.strip()).strip()
        if value:
            values.append(value)
    return tuple(values)


def _parse_table_row(line: str) -> tuple[str, ...]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        raise AcceptanceReportError("failure handoff must use a six-column Markdown table")
    cells: list[str] = []
    current: list[str] = []
    content = stripped[1:-1]
    index = 0
    while index < len(content):
        character = content[index]
        if character == "\\" and index + 1 < len(content) and content[index + 1] == "|":
            current.append("|")
            index += 2
            continue
        if character == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(character)
        index += 1
    cells.append("".join(current).strip())
    return tuple(cells)


def _cell_lines(cell: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in re.split(r"<br\s*/?>", cell, flags=re.IGNORECASE) if part.strip())


def _validate_failure_handoff(
    visible_body: str, failed_items: list[dict[str, object]], overall_status: str
) -> tuple[bool, list[dict[str, str]]]:
    handoff = _extract_h2(
        visible_body, "## 失败回传", "acceptance report", required=False
    )
    if overall_status != "failed":
        if handoff is not None:
            raise AcceptanceReportError(
                "passed or incomplete acceptance report must not contain failure handoff"
            )
        return True, []
    if handoff is None:
        raise AcceptanceReportError("failed acceptance report must contain failure handoff")

    table_lines = [line for line in handoff.splitlines() if line.strip().startswith("|")]
    if len(table_lines) < 2:
        raise AcceptanceReportError("failure handoff must contain its canonical table")
    if _parse_table_row(table_lines[0]) != FAILURE_HEADER:
        raise AcceptanceReportError("failure handoff table header is not canonical")
    separator = _parse_table_row(table_lines[1])
    if len(separator) != 6 or any(re.fullmatch(r":?-{3,}:?", cell) is None for cell in separator):
        raise AcceptanceReportError("failure handoff table separator is not canonical")
    rows = [_parse_table_row(line) for line in table_lines[2:]]
    if any(len(row) != 6 for row in rows):
        raise AcceptanceReportError("failure handoff row must contain six columns")
    if len(rows) != len(failed_items):
        raise AcceptanceReportError(
            "failure handoff rows must exactly match all and only failed test items"
        )

    normalized_rows: list[dict[str, str]] = []
    for failed, row in zip(failed_items, rows):
        test_id, title, expected, actual, error_summary, evidence = row
        expected_values = _summary_lines(failed["expected"])  # type: ignore[arg-type]
        actual_values = _summary_lines(failed["actual"])  # type: ignore[arg-type]
        evidence_values = _summary_lines(failed["evidence"])  # type: ignore[arg-type]
        if test_id != failed["test_id"] or title != failed["title"]:
            raise AcceptanceReportError(
                "failure handoff identity does not match failed item " + str(failed["test_id"])
            )
        if _cell_lines(expected) != expected_values:
            raise AcceptanceReportError(
                "failure handoff expected result does not match failed item " + test_id
            )
        if _cell_lines(actual) != actual_values:
            raise AcceptanceReportError(
                "failure handoff actual result does not match failed item " + test_id
            )
        if _cell_lines(evidence) != evidence_values:
            raise AcceptanceReportError(
                "failure handoff evidence does not match failed item " + test_id
            )
        _require_meaningful([error_summary], f"failure handoff {test_id} 错误摘要")
        normalized_rows.append(
            {
                "test_id": test_id,
                "title": title,
                "expected": expected,
                "actual": actual,
                "error_summary": error_summary,
                "evidence": evidence,
            }
        )
    return True, normalized_rows


def _validate_expected_bindings(change_id: str, test_ref: str, code_ref: str) -> None:
    if CHANGE_ID_PATTERN.fullmatch(change_id) is None:
        raise AcceptanceReportError("expected change_id must use CE-0001 format")
    if TEST_REF_PATTERN.fullmatch(test_ref) is None:
        raise AcceptanceReportError(
            "expected test_ref must use tests/<change_id>.md@<full-40-or-64-hex-sha>"
        )
    test_path = test_ref.split("@", 1)[0]
    if test_path != f"tests/{change_id}.md":
        raise AcceptanceReportError(
            "expected test_ref must use tests/<change_id>.md@<full-40-or-64-hex-sha>"
        )
    if CODE_REF_PATTERN.fullmatch(code_ref) is None:
        raise AcceptanceReportError(
            "expected code_ref must use <repository>@<full-40-or-64-hex-sha>"
        )


def _validate_reused_automation_evidence(
    items: Sequence[dict[str, object]], expected_code_ref: str
) -> list[dict[str, str]]:
    expected_code_sha = expected_code_ref.rsplit("@", 1)[1].lower()
    normalized: list[dict[str, str]] = []
    seen_keys: set[tuple[str, str, str, str]] = set()

    for item in items:
        for evidence_line in _summary_lines(item["evidence"]):  # type: ignore[arg-type]
            if not evidence_line.startswith(REUSED_EVIDENCE_PREFIX):
                continue
            if item["status"] != "passed":
                raise AcceptanceReportError(
                    "reused automation evidence is valid only for a passed acceptance item"
                )
            serialized = evidence_line[len(REUSED_EVIDENCE_PREFIX) :].strip()
            try:
                evidence = json.loads(serialized, object_pairs_hook=_unique_json_object)
            except json.JSONDecodeError as error:
                raise AcceptanceReportError(
                    "reused automation evidence must contain one compact JSON object"
                ) from error
            if not isinstance(evidence, Mapping) or set(evidence) != REUSED_EVIDENCE_FIELDS:
                raise AcceptanceReportError(
                    "reused automation evidence fields must exactly match the canonical schema"
                )

            values: dict[str, str] = {}
            for field in REUSED_EVIDENCE_FIELDS:
                value = evidence[field]
                if not isinstance(value, str) or not value.strip() or PLACEHOLDER_PATTERN.search(value):
                    raise AcceptanceReportError(
                        f"reused automation evidence {field} must be a concrete string"
                    )
                values[field] = value.strip()
            values["code_sha"] = values["code_sha"].lower()
            if re.fullmatch(FULL_SHA_PATTERN, values["code_sha"]) is None:
                raise AcceptanceReportError(
                    "reused automation evidence code_sha must be a full Git object ID"
                )
            if values["code_sha"] != expected_code_sha:
                raise AcceptanceReportError(
                    "reused automation evidence code_sha does not match acceptance code_ref"
                )
            if values["result"] != "passed" or values["produced_by"] != "delivery":
                raise AcceptanceReportError(
                    "reused automation evidence must be a passed result produced by delivery"
                )

            evidence_key = (
                values["code_sha"],
                values["command"],
                values["environment_fingerprint"],
                values["input_fingerprint"],
            )
            if evidence_key in seen_keys:
                raise AcceptanceReportError(
                    "reused automation evidence contains a duplicate exact evidence key"
                )
            seen_keys.add(evidence_key)
            normalized.append(values)
    return normalized


def validate_acceptance_report(
    test_text: str,
    report_text: str,
    expected_change_id: str,
    expected_test_ref: str,
    expected_code_ref: str,
    *,
    require_passed: bool = False,
) -> dict[str, object]:
    """Validate bindings and grammar, returning a normalized JSON-ready result."""

    _validate_expected_bindings(expected_change_id, expected_test_ref, expected_code_ref)
    fields, raw_body = _parse_frontmatter(report_text)
    for field, expected in (
        ("change_id", expected_change_id),
        ("test_ref", expected_test_ref),
        ("code_ref", expected_code_ref),
    ):
        if fields.get(field) != expected:
            raise AcceptanceReportError(
                f"acceptance report {field} does not exactly match the expected binding"
            )
    declared_overall = fields.get("overall_status")
    if declared_overall not in CANONICAL_OVERALL:
        raise AcceptanceReportError("acceptance report overall_status must be canonical")

    expected_items = parse_test_draft(test_text)
    actual_items = parse_acceptance_items(raw_body)
    expected_ids = [str(item["test_id"]) for item in expected_items]
    actual_ids = [str(item["test_id"]) for item in actual_items]
    if actual_ids != expected_ids:
        raise AcceptanceReportError(
            "acceptance report test IDs and order do not exactly match the test draft"
        )
    for expected, actual in zip(expected_items, actual_items):
        if actual["title"] != expected["title"]:
            raise AcceptanceReportError(
                f"acceptance title does not match test draft: {expected['test_id']}"
            )
        if actual["expected"] != expected["expected"]:
            raise AcceptanceReportError(
                f"acceptance expected result does not match test draft: {expected['test_id']}"
            )

    statuses = [str(item["status"]) for item in actual_items]
    derived = (
        "failed"
        if "failed" in statuses
        else "incomplete"
        if "not_executed" in statuses
        else "passed"
    )
    if declared_overall != derived:
        raise AcceptanceReportError(
            "acceptance report overall_status does not match item statuses"
        )

    visible_body = strip_fenced_blocks(raw_body)
    human_lines = [
        match.group(1)
        for line in visible_body.splitlines()
        if (match := re.fullmatch(r"\s*-\s*总体结果：\s*(通过|失败|未完成)\s*", line))
    ]
    if human_lines != [HUMAN_OVERALL[derived]]:
        raise AcceptanceReportError(
            "acceptance report must contain one human-readable overall result matching item statuses"
        )

    failed_items = [item for item in actual_items if item["status"] == "failed"]
    reused_automation_evidence = _validate_reused_automation_evidence(
        actual_items, expected_code_ref
    )
    handoff_valid, handoff_rows = _validate_failure_handoff(
        visible_body, failed_items, derived
    )
    if require_passed and derived != "passed":
        raise AcceptanceReportError(
            "require_passed accepts only an acceptance report whose every item passed"
        )

    return {
        "change_id": expected_change_id,
        "test_ref": expected_test_ref,
        "code_ref": expected_code_ref,
        "overall_status": derived,
        "test_count": len(actual_items),
        "passed_test_ids": [
            item["test_id"] for item in actual_items if item["status"] == "passed"
        ],
        "failed_test_ids": [item["test_id"] for item in failed_items],
        "not_executed_ids": [
            item["test_id"] for item in actual_items if item["status"] == "not_executed"
        ],
        "failure_handoff_required": derived == "failed",
        "failure_handoff_valid": handoff_valid,
        "failure_handoff": handoff_rows,
        "reused_automation_evidence": reused_automation_evidence,
        "items": actual_items,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-file", required=True, type=Path)
    parser.add_argument("--report-file", required=True, type=Path)
    parser.add_argument("--change-id", required=True)
    parser.add_argument("--test-ref", required=True)
    parser.add_argument("--code-ref", required=True)
    parser.add_argument("--require-passed", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        test_text = args.test_file.read_text(encoding="utf-8")
        report_text = args.report_file.read_text(encoding="utf-8")
        result = validate_acceptance_report(
            test_text,
            report_text,
            args.change_id,
            args.test_ref,
            args.code_ref,
            require_passed=args.require_passed,
        )
    except (AcceptanceReportError, OSError, UnicodeError) as error:
        print(f"acceptance report invalid: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
