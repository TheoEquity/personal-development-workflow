from pathlib import Path
import unittest


SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"


class WritingSpecsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")

    def test_spec_uses_controller_change_id_and_canonical_path(self):
        self.assertIn("总控提供的 `change_id`", self.text)
        self.assertIn("`specs/<change_id>.md`", self.text)

    def test_spec_phase_invokes_test_draft_child(self):
        self.assertIn("**REQUIRED SUB-SKILL:** 使用 `writing-test-drafts`", self.text)
        self.assertIn("`tests/<change_id>.md`", self.text)
        self.assertIn("用户提供的操作步骤、流程和预期结果", self.text)
        self.assertIn("用户未提供时", self.text)

    def test_spec_owns_the_existing_behavior_impact_contract(self):
        for required in (
            "## 既有功能与流程影响",
            "| impact_id | 既有功能或流程 | 当前行为 | 与新需求的交点 | 影响结论 | Spec 处理 |",
            "`I-001`",
            "保持不变",
            "兼容扩展",
            "明确改变",
            "无需修改",
            "已写入规则或边界",
        ):
            self.assertIn(required, self.text)

    def test_spec_impact_ids_are_stable_and_no_impact_has_one_canonical_form(self):
        self.assertIn("删除后不得复用", self.text)
        self.assertIn("不得因排序变化而重编号", self.text)
        self.assertIn("- 结论：未发现与本需求直接关联的既有功能或流程。", self.text)

    def test_behavior_uncertainty_stops_in_spec_and_is_not_code_impact_range(self):
        self.assertIn("必须停在 Spec 阶段", self.text)
        self.assertIn("不得交给 Plan 决定", self.text)
        self.assertIn("与“可能的影响范围”", self.text)


if __name__ == "__main__":
    unittest.main()
