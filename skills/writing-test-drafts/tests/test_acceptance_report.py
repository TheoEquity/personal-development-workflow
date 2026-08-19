import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "acceptance_report.py"
if SCRIPT.exists():
    SPEC = importlib.util.spec_from_file_location("acceptance_report", SCRIPT)
    assert SPEC is not None and SPEC.loader is not None
    acceptance_report = importlib.util.module_from_spec(SPEC)
    sys.modules[SPEC.name] = acceptance_report
    SPEC.loader.exec_module(acceptance_report)
else:
    class _MissingAcceptanceReportError(ValueError):
        pass

    class _MissingAcceptanceReportModule:
        AcceptanceReportError = _MissingAcceptanceReportError

        @staticmethod
        def validate_acceptance_report(*args, **kwargs):
            raise AssertionError("production acceptance-report validator is missing")

    acceptance_report = _MissingAcceptanceReportModule()

CHANGE_ID = "CE-0001"
VAULT_SHA = "1" * 40
CODE_SHA = "2" * 40
TEST_REF = f"tests/CE-0001.md@{VAULT_SHA}"
CODE_REF = f"forentx-frontend@{CODE_SHA}"


def draft(*items: tuple[str, str, str]) -> str:
    blocks = ["# 测试稿：同步", "", "## 测试流程", ""]
    for test_id, title, expected in items:
        blocks.extend(
            [
                f"### {test_id} {title}",
                "",
                f"test_id: {test_id}",
                "",
                "操作：",
                "",
                f"1. 执行 {title}。",
                "",
                "预期结果：",
                "",
                f"- {expected}",
                "",
            ]
        )
    return "\n".join(blocks)


def report(
    *items: tuple[str, str, str, str, str, str],
    overall: str,
    change_id: str = CHANGE_ID,
    test_ref: str = TEST_REF,
    code_ref: str = CODE_REF,
    handoff_rows: list[tuple[str, str, str, str, str, str]] | None = None,
) -> str:
    human = {"passed": "通过", "failed": "失败", "incomplete": "未完成"}[overall]
    blocks = [
        "---",
        f"change_id: {change_id}",
        f"test_ref: {test_ref}",
        f"code_ref: {code_ref}",
        f"overall_status: {overall}",
        "---",
        "# 验收报告：同步",
        "",
        f"- 总体结果：{human}",
        "",
        "## 测试项结果",
        "",
    ]
    for test_id, title, status, expected, actual, evidence in items:
        blocks.extend(
            [
                f"### {test_id} {title}",
                "",
                f"test_id: {test_id}",
                f"status: {status}",
                "",
                "预期结果：",
                "",
                f"- {expected}",
                "",
                "实际结果：",
                "",
                f"- {actual}",
                "",
                "证据：",
                "",
                f"- {evidence}",
                "",
            ]
        )
    if handoff_rows is not None:
        blocks.extend(
            [
                "## 失败回传",
                "",
                "| test_id | 失败测试项 | 预期结果 | 实际结果 | 错误摘要 | 证据与日志 |",
                "|---|---|---|---|---|---|",
            ]
        )
        for row in handoff_rows:
            escaped = tuple(cell.replace("|", r"\|") for cell in row)
            blocks.append("| " + " | ".join(escaped) + " |")
        blocks.append("")
    return "\n".join(blocks)


PASS_ITEM = (
    "T-001",
    "创建批注",
    "passed",
    "页面显示批注。",
    "已观察到批注。",
    "2026-08-18T12:00:00Z | screenshot | acceptance/T-001.png",
)
FAIL_ITEM = (
    "T-002",
    "检查同步",
    "failed",
    "只创建一个 Issue。",
    "创建了两个 Issue。",
    "2026-08-18T12:01:00Z | url | GitLab Issue 列表",
)
NOT_RUN_ITEM = (
    "T-002",
    "检查同步",
    "not_executed",
    "只创建一个 Issue。",
    "前置环境不可用，未执行。",
    "无",
)
FAIL_ROW = (
    "T-002",
    "检查同步",
    "只创建一个 Issue。",
    "创建了两个 Issue。",
    "观察到重复 Issue。",
    "2026-08-18T12:01:00Z | url | GitLab Issue 列表",
)


class AcceptanceReportValidationTests(unittest.TestCase):
    def setUp(self):
        self.test_text = draft(
            ("T-001", "创建批注", "页面显示批注。"),
            ("T-002", "检查同步", "只创建一个 Issue。"),
        )

    def validate(self, report_text: str, *, require_passed: bool = False):
        return acceptance_report.validate_acceptance_report(
            self.test_text,
            report_text,
            CHANGE_ID,
            TEST_REF,
            CODE_REF,
            require_passed=require_passed,
        )

    def test_passed_report_returns_normalized_result(self):
        second = (
            "T-002",
            "检查同步",
            "passed",
            "只创建一个 Issue。",
            "已观察到一个 Issue。",
            "2026-08-18T12:01:00Z | url | GitLab Issue",
        )
        result = self.validate(report(PASS_ITEM, second, overall="passed"))
        self.assertEqual("passed", result["overall_status"])
        self.assertEqual([], result["failed_test_ids"])
        self.assertEqual([], result["not_executed_ids"])
        self.assertTrue(result["failure_handoff_valid"])

    def test_failed_report_requires_and_normalizes_exact_handoff(self):
        result = self.validate(
            report(PASS_ITEM, FAIL_ITEM, overall="failed", handoff_rows=[FAIL_ROW])
        )
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual(["T-002"], result["failed_test_ids"])
        self.assertEqual([], result["not_executed_ids"])
        self.assertTrue(result["failure_handoff_required"])
        self.assertTrue(result["failure_handoff_valid"])

    def test_failure_handoff_accepts_escaped_pipes_in_any_cell(self):
        self.test_text = draft(
            ("T-001", "创建批注", "页面显示批注。"),
            ("T-002", "检查同步", "只创建 A | B 两类映射。"),
        )
        failed_item = (
            "T-002",
            "检查同步",
            "failed",
            "只创建 A | B 两类映射。",
            "观察到 A | B | C 三类映射。",
            "2026-08-18T12:01:00Z | log | acceptance/T-002.log",
        )
        handoff = (
            "T-002",
            "检查同步",
            "只创建 A | B 两类映射。",
            "观察到 A | B | C 三类映射。",
            "映射集合包含额外分类。",
            "2026-08-18T12:01:00Z | log | acceptance/T-002.log",
        )
        valid = report(PASS_ITEM, failed_item, overall="failed", handoff_rows=[handoff])
        result = self.validate(valid)
        self.assertEqual("failed", result["overall_status"])
        self.assertIn("A | B", result["failure_handoff"][0]["expected"])
        unescaped = valid.replace(
            r"只创建 A \| B 两类映射。 | 观察到",
            "只创建 A | B 两类映射。 | 观察到",
            1,
        )
        self.assertNotEqual(valid, unescaped)
        with self.assertRaises(acceptance_report.AcceptanceReportError):
            self.validate(unescaped)

    def test_incomplete_report_is_not_failed(self):
        result = self.validate(report(PASS_ITEM, NOT_RUN_ITEM, overall="incomplete"))
        self.assertEqual("incomplete", result["overall_status"])
        self.assertEqual([], result["failed_test_ids"])
        self.assertEqual(["T-002"], result["not_executed_ids"])
        self.assertFalse(result["failure_handoff_required"])

    def test_frontmatter_bindings_must_match_exactly(self):
        valid = report(PASS_ITEM, NOT_RUN_ITEM, overall="incomplete")
        replacements = {
            f"change_id: {CHANGE_ID}": "change_id: CE-9999",
            f"test_ref: {TEST_REF}": f"test_ref: tests/other.md@{VAULT_SHA}",
            f"code_ref: {CODE_REF}": f"code_ref: other-repo@{CODE_SHA}",
        }
        for original, wrong in replacements.items():
            with self.subTest(field=original.split(":", 1)[0]):
                with self.assertRaises(acceptance_report.AcceptanceReportError):
                    self.validate(valid.replace(original, wrong))

    def test_empty_shell_and_fenced_pseudo_fields_are_rejected(self):
        fenced_shell = "\n".join(
            [
                "```markdown",
                "---",
                f"change_id: {CHANGE_ID}",
                f"test_ref: {TEST_REF}",
                f"code_ref: {CODE_REF}",
                "overall_status: passed",
                "---",
                "```",
            ]
        )
        with self.assertRaises(acceptance_report.AcceptanceReportError):
            self.validate(fenced_shell)

        fake_status = report(PASS_ITEM, NOT_RUN_ITEM, overall="incomplete").replace(
            "status: passed", "```yaml\nstatus: passed\n```", 1
        )
        with self.assertRaises(acceptance_report.AcceptanceReportError):
            self.validate(fake_status)

    def test_overall_status_must_be_derived_from_item_statuses(self):
        for text in (
            report(PASS_ITEM, NOT_RUN_ITEM, overall="failed", handoff_rows=[]),
            report(PASS_ITEM, FAIL_ITEM, overall="incomplete"),
        ):
            with self.subTest(text=text[:80]):
                with self.assertRaises(acceptance_report.AcceptanceReportError):
                    self.validate(text)

    def test_failed_handoff_rejects_missing_extra_and_wrong_rows(self):
        missing = report(PASS_ITEM, FAIL_ITEM, overall="failed")
        extra = report(
            PASS_ITEM,
            FAIL_ITEM,
            overall="failed",
            handoff_rows=[FAIL_ROW, ("T-999", "额外项", "x", "x", "x", "x")],
        )
        wrong = report(
            PASS_ITEM,
            FAIL_ITEM,
            overall="failed",
            handoff_rows=[FAIL_ROW[:2] + ("错误预期",) + FAIL_ROW[3:]],
        )
        for name, text in (("missing", missing), ("extra", extra), ("wrong", wrong)):
            with self.subTest(case=name):
                with self.assertRaises(acceptance_report.AcceptanceReportError):
                    self.validate(text)

    def test_nonfailed_report_must_not_contain_failure_handoff(self):
        incomplete_with_handoff = report(
            PASS_ITEM,
            NOT_RUN_ITEM,
            overall="incomplete",
            handoff_rows=[FAIL_ROW],
        )
        with self.assertRaises(acceptance_report.AcceptanceReportError):
            self.validate(incomplete_with_handoff)

    def test_require_passed_rejects_failed_and_incomplete(self):
        for text in (
            report(PASS_ITEM, FAIL_ITEM, overall="failed", handoff_rows=[FAIL_ROW]),
            report(PASS_ITEM, NOT_RUN_ITEM, overall="incomplete"),
        ):
            with self.subTest(text=text[:80]):
                with self.assertRaises(acceptance_report.AcceptanceReportError):
                    self.validate(text, require_passed=True)

    def test_id_title_expected_actual_and_evidence_are_strict(self):
        valid = report(PASS_ITEM, NOT_RUN_ITEM, overall="incomplete")
        mutations = (
            valid.replace("### T-001 创建批注", "### T-001 错误标题", 1),
            valid.replace("- 页面显示批注。", "- 错误预期。", 1),
            valid.replace("- 已观察到批注。", "- <真实结果>", 1),
            valid.replace(
                "- 2026-08-18T12:00:00Z | screenshot | acceptance/T-001.png",
                "- <证据>",
                1,
            ),
        )
        for text in mutations:
            with self.subTest(text=text[:100]):
                with self.assertRaises(acceptance_report.AcceptanceReportError):
                    self.validate(text)

    def test_cli_emits_json_and_reports_validation_errors_on_stderr(self):
        valid = report(PASS_ITEM, NOT_RUN_ITEM, overall="incomplete")
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            test_file = directory_path / "test.md"
            report_file = directory_path / "report.md"
            test_file.write_text(self.test_text, encoding="utf-8")
            report_file.write_text(valid, encoding="utf-8")
            command = [
                sys.executable,
                str(SCRIPT),
                "--test-file",
                str(test_file),
                "--report-file",
                str(report_file),
                "--change-id",
                CHANGE_ID,
                "--test-ref",
                TEST_REF,
                "--code-ref",
                CODE_REF,
            ]
            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual("incomplete", json.loads(completed.stdout)["overall_status"])
            self.assertEqual("", completed.stderr)

            failed = subprocess.run(
                command + ["--require-passed"], capture_output=True, text=True
            )
            self.assertNotEqual(0, failed.returncode)
            self.assertEqual("", failed.stdout)
            self.assertIn("acceptance report invalid", failed.stderr)

    def test_test_ref_path_is_derived_from_change_id(self):
        mismatched_ref = f"tests/CE-9999.md@{VAULT_SHA}"
        mismatched_report = report(
            PASS_ITEM,
            NOT_RUN_ITEM,
            overall="incomplete",
        ).replace(f"test_ref: {TEST_REF}", f"test_ref: {mismatched_ref}")
        with self.assertRaises(acceptance_report.AcceptanceReportError):
            acceptance_report.validate_acceptance_report(
                self.test_text,
                mismatched_report,
                CHANGE_ID,
                mismatched_ref,
                CODE_REF,
            )


if __name__ == "__main__":
    unittest.main()
