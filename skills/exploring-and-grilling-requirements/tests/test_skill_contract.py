from pathlib import Path
import unittest


TEXT = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")


class RequirementExplorationSkillContractTests(unittest.TestCase):
    def test_skill_is_explicitly_optional(self):
        self.assertIn("按需", TEXT)
        self.assertIn("需求存在实质歧义", TEXT)
        self.assertIn("清晰任务不调用", TEXT)

    def test_exploration_returns_a_confirmable_decision(self):
        for required in ("目标", "关键选择", "边界", "成功条件", "未决项"):
            self.assertIn(required, TEXT)

    def test_does_not_force_ritual_for_every_request(self):
        for removed in ("强制轻量清晰度检查", "行为校验和", "反方压力检查"):
            self.assertNotIn(removed, TEXT)


if __name__ == "__main__":
    unittest.main()
