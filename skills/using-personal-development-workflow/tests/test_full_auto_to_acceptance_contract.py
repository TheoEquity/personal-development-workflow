from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FullAutoToAcceptanceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        cls.spec_stage = (ROOT / "references" / "spec-stage.md").read_text(
            encoding="utf-8"
        )
        cls.spec_prompt = (ROOT / "references" / "spec-worker-prompt.md").read_text(
            encoding="utf-8"
        )
        cls.stage_contract = (
            ROOT / "references" / "stage-worker-contract.md"
        ).read_text(encoding="utf-8")
        cls.plan_stage = (ROOT / "references" / "plan-stage.md").read_text(
            encoding="utf-8"
        )
        cls.plan_prompt = (ROOT / "references" / "plan-worker-prompt.md").read_text(
            encoding="utf-8"
        )
        cls.implementation = (
            ROOT / "references" / "implementation-stage.md"
        ).read_text(encoding="utf-8")
        cls.execution_contract = (
            ROOT / "references" / "execution-contract.md"
        ).read_text(encoding="utf-8")
        cls.acceptance = (ROOT / "references" / "acceptance-stage.md").read_text(
            encoding="utf-8"
        )

    def test_auto_is_full_ce_autonomy_until_acceptance_confirmation(self):
        for required in (
            "`full + auto` 自动推进到验收确认门",
            "当前已绑定 CE",
            "不得扩展到另一个 CE、仓库或 Delivery",
            "最终验收确认门",
        ):
            self.assertIn(required, self.workflow)

    def test_auto_spec_adoption_keeps_digest_and_controller_review(self):
        combined = self.spec_stage + self.spec_prompt + self.stage_contract
        for required in (
            "自动采用当前 `candidate_sha256`",
            "主 Agent 审核通过",
            "`blockers` 为空",
            "confirmed_candidate_sha256",
            "不得修改候选",
        ):
            self.assertIn(required, combined)

    def test_auto_plan_adoption_still_requires_lint_review_and_controller(self):
        combined = self.plan_stage + self.plan_prompt
        for required in (
            "`review_mode=auto`",
            "dry-run `validated`",
            "reviewer `Approved`",
            "主 Agent 审核",
            "自动调用 `adopt-plan`",
        ):
            self.assertIn(required, combined)

    def test_auto_authorizes_exact_local_sdd_scope_without_extra_question(self):
        combined = self.implementation + self.execution_contract
        for required in (
            "`review_mode=auto`",
            "不再询问 SDD",
            "当前精确 `plan_ref`",
            "当前已绑定 CE",
            "本地 commits",
        ):
            self.assertIn(required, combined)

    def test_auto_still_stops_on_real_decisions_and_external_mutations(self):
        combined = self.workflow + self.implementation + self.acceptance
        for required in (
            "需求不清",
            "范围扩大",
            "基线漂移",
            "合入 Delivery",
            "Push",
            "删除 Worktree",
        ):
            self.assertIn(required, combined)

    def test_full_auto_stops_with_final_report_and_logic_for_human_confirmation(self):
        for required in (
            "验收报告",
            "最终逻辑稿",
            "完整展示候选并停止",
            "用户确认后才保存",
        ):
            self.assertIn(required, self.acceptance)

    def test_auto_resume_uses_persisted_control_not_chat_authority(self):
        combined = self.workflow + self.stage_contract
        for required in (
            "持久 `review_mode=auto`",
            "重新验证当前候选和正式引用",
            "不恢复其他 CE 或外部动作授权",
        ):
            self.assertIn(required, combined)


if __name__ == "__main__":
    unittest.main()
