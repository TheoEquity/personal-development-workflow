import re
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"


class WritingTestDraftContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")

    def test_test_draft_defines_stable_test_id(self):
        self.assertIn("test_id: T-001", self.text)
        for rule in ("保留已有 ID", "不复用", "标题", "ID 不变"):
            self.assertIn(rule, self.text)

    def test_acceptance_report_has_machine_readable_frontmatter(self):
        self.assertRegex(
            self.text,
            re.compile(
                r"---\s+change_id: <CE-0001>\s+"
                r"test_ref: tests/<change_id>\.md@<full-vault-commit-sha>\s+"
                r"code_ref: <repository>@<full-code-commit-sha>\s+"
                r"overall_status: passed\s+---",
                re.MULTILINE,
            ),
        )

    def test_report_inherits_test_id_and_uses_canonical_status(self):
        self.assertIn("test_id: T-001", self.text)
        self.assertIn("status: passed", self.text)
        self.assertIn("`passed` / `failed` / `not_executed`", self.text)

    def test_overall_status_derivation_is_explicit(self):
        self.assertIn("`passed` / `failed` / `incomplete`", self.text)
        self.assertIn("全部测试项都是 `passed`", self.text)
        self.assertIn("任一测试项是 `failed`", self.text)
        self.assertIn("存在 `not_executed`", self.text)

    def test_spec_does_not_own_test_ids(self):
        self.assertIn("Spec 不定义 `test_id`", self.text)

    def test_skill_owns_one_executable_acceptance_report_grammar(self):
        for required in (
            "scripts/acceptance_report.py",
            "validate_acceptance_report",
            "唯一语义与 executable grammar 拥有者",
            "不得复制字段 grammar",
            "failure_handoff_valid",
        ):
            self.assertIn(required, self.text)

    def test_failure_handoff_rows_bind_test_id_and_exact_item_content(self):
        self.assertIn(
            "| test_id | 失败测试项 | 预期结果 | 实际结果 | 错误摘要 | 证据与日志 |",
            self.text,
        )
        for rule in ("全部且仅有", "逐项完全匹配", "`<br>`"):
            self.assertIn(rule, self.text)

    def test_initial_draft_uses_controller_identity_and_spec_fallback(self):
        for required in (
            "`tests/<change_id>.md`",
            "总控提供的 `change_id`",
            "用户提供的操作步骤、流程和预期结果优先",
            "用户未提供时",
            "根据已确认 Spec",
            "初次编写测试稿不依赖 Plan",
        ):
            self.assertIn(required, self.text)

    def test_cli_example_uses_canonical_test_ref(self):
        self.assertIn("--test-ref <tests/CE-0001.md@full-vault-sha>", self.text)
        self.assertNotIn("tests/path.md", self.text)


if __name__ == "__main__":
    unittest.main()
