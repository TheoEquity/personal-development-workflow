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

    def test_one_skill_has_light_and_full_profiles(self):
        self.assertIn("`profile=light`", self.text)
        self.assertIn("`profile=full`", self.text)
        self.assertIn("direct 不调用本 Skill", self.text)

    def test_only_full_profile_invokes_test_draft_child(self):
        self.assertIn("只有 `full`", self.text)
        self.assertIn("**REQUIRED SUB-SKILL:** 使用 `writing-test-drafts`", self.text)
        self.assertIn("`tests/<change_id>.md`", self.text)

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

    def test_light_profile_is_short_and_does_not_reintroduce_full_gates(self):
        for required in (
            "要解决的问题",
            "输入、事件或状态",
            "期望行为",
            "本次范围",
            "完成条件",
            "必须保持不变的行为或关键兼容边界",
            "不强制既有功能影响表",
            "不扫描代码 SHA",
            "不生成正式测试稿",
            "不生成 `test_ref`",
        ):
            self.assertIn(required, self.text)


if __name__ == "__main__":
    unittest.main()
