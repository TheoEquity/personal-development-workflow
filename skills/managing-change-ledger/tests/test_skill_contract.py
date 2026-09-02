from pathlib import Path
import unittest


TEXT = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")


class ManagingChangeLedgerContractTests(unittest.TestCase):
    def test_contract_is_small_and_uses_four_stages(self):
        for required in ("define", "implement", "verify", "done", "worktree"):
            self.assertIn(required, TEXT)
        for removed in (
            "review_mode",
            "plan-adoption-contract",
            "adopt-plan",
            "最终逻辑稿",
            "只写两次",
            "六列表格",
        ):
            self.assertNotIn(removed, TEXT)

    def test_plan_and_test_drafts_are_not_ledger_gates(self):
        self.assertIn("Plan 和测试稿不是总账门禁", TEXT)


if __name__ == "__main__":
    unittest.main()
