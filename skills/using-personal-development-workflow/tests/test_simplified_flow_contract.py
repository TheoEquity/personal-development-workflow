from pathlib import Path
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL_TEXT = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")


class SimplifiedFlowContractTests(unittest.TestCase):
    def test_separates_task_depth_from_execution_topology(self):
        for required in (
            "direct | light | full",
            "单 Worktree 串行",
            "多 Worktree 并行",
            "一个 Worktree 同时只有一个写入者",
            "不得嵌套创建",
        ):
            self.assertIn(required, SKILL_TEXT)

    def test_supports_small_changes_and_zero_to_one_systems(self):
        self.assertIn("从零开发完整系统", SKILL_TEXT)
        self.assertIn("纵向 CE", SKILL_TEXT)

    def test_uses_four_recoverable_stages(self):
        for stage in ("define", "implement", "verify", "done"):
            self.assertIn(stage, SKILL_TEXT)

    def test_removed_or_optional_processes_are_not_hard_gates(self):
        for removed in (
            "review_mode",
            "code_review:",
            "loop_mode:",
            "Implementation Coordinator",
            "authorization_offer",
            "writing-final-logic-drafts",
            "stage-worker-contract.md",
        ):
            self.assertNotIn(removed, SKILL_TEXT)
        self.assertIn("TDD 是按风险选择的方法", SKILL_TEXT)
        self.assertIn("验证始终必需", SKILL_TEXT)

    def test_only_keeps_focused_references(self):
        references = {path.name for path in (SKILL_ROOT / "references").glob("*.md")}
        self.assertEqual(references, {"worktree-safety.md", "parallel-delivery.md"})


if __name__ == "__main__":
    unittest.main()
