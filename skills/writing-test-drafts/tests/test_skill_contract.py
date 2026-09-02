from pathlib import Path
import unittest


TEXT = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")


class WritingTestDraftContractTests(unittest.TestCase):
    def test_formal_acceptance_is_optional(self):
        self.assertIn("按需正式验收", TEXT)
        self.assertIn("Direct/Light 默认不调用", TEXT)

    def test_formal_acceptance_keeps_stable_ids_and_evidence_binding(self):
        self.assertIn("T-001", TEXT)
        self.assertIn("code_ref", TEXT)
        self.assertIn("passed", TEXT)
        self.assertIn("failed", TEXT)

    def test_validator_remains_an_optional_tool(self):
        self.assertIn("acceptance_report.py", TEXT)
        self.assertIn("可选", TEXT)


if __name__ == "__main__":
    unittest.main()
