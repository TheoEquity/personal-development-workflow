from pathlib import Path
import re
import unittest


SKILL_DIRECTORY = Path(__file__).resolve().parents[1]
SKILL_FILE = SKILL_DIRECTORY / "SKILL.md"
OPENAI_METADATA_FILE = SKILL_DIRECTORY / "agents" / "openai.yaml"


def section(text, heading):
    match = re.search(
        rf"^{re.escape(heading)}\n(?P<body>.*?)(?=^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"Missing section: {heading}")
    return match.group("body")


class RequirementExplorationSkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL_FILE.read_text(encoding="utf-8")
        cls.metadata = OPENAI_METADATA_FILE.read_text(encoding="utf-8")

    def test_decision_pack_replaces_the_single_question_loop(self):
        decision_pack = section(self.skill, "## 决策包 Grill")
        self.assertIn("一个决策包", decision_pack)
        self.assertRegex(decision_pack, r"(?:1[–-]3 个|最多 3 个)")
        self.assertIn("紧密相关", decision_pack)
        self.assertIn("用户一次确认", decision_pack)

        for obsolete_rule in (
            "每个助手回合只问 frontier 中一个最高影响的问题",
            "仍一次问一个问题",
            "一个助手回合包含两个或更多问题",
        ):
            self.assertNotIn(obsolete_rule, self.skill)

    def test_behavior_checksum_is_a_required_confirmed_handoff(self):
        checksum = section(self.skill, "## 行为校验和")
        for required_field in (
            "核心不变量",
            "正例",
            "反例",
            "明确不依赖",
            "失败时用户看到什么",
        ):
            self.assertIn(required_field, checksum)

        self.assertIn("可证伪", checksum)
        self.assertIn("用户明确确认", checksum)
        self.assertRegex(checksum, r"进入.*Spec")
        self.assertRegex(checksum, r"不得使用.*Unconfirmed.*TBD")

    def test_final_overall_solution_is_printed_before_stage_completion(self):
        final_solution = section(self.skill, "## 最终总体方案确认")
        for required_part in (
            "功能目标",
            "用户场景与触发",
            "总体行为",
            "输出与状态变化",
            "边界和明确排除范围",
            "行为校验和",
            "完整打印",
            "阶段状态：等待确认",
        ):
            self.assertIn(required_part, final_solution)

        completion = section(self.skill, "## 结束需求讨论阶段")
        self.assertIn("用户明确确认“最终总体方案”", completion)
        self.assertIn("阶段状态：已完成", completion)
        self.assertIn("最终总体方案：", completion)

    def test_skill_does_not_embed_project_specific_checksum_examples(self):
        for project_specific_detail in (
            "CE-0005",
            "任意空白区域",
            "scrollTop",
            "屏幕 y",
            "下方 DOM",
            "框下 DOM",
            "selector",
        ):
            self.assertNotIn(project_specific_detail, self.skill)

    def test_interface_copy_describes_decision_packages_and_checksum(self):
        self.assertIn("决策包", self.metadata)
        self.assertIn("行为校验和", self.metadata)
        self.assertIn("最终总体方案", self.metadata)
        self.assertNotIn("逐个问透", self.metadata)


if __name__ == "__main__":
    unittest.main()
