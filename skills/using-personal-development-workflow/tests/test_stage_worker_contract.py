from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "SKILL.md"
EXECUTION_CONTRACT = ROOT / "references" / "execution-contract.md"
STAGE_CONTRACT = ROOT / "references" / "stage-worker-contract.md"
SPEC_PROMPT = ROOT / "references" / "spec-worker-prompt.md"
PLAN_PROMPT = ROOT / "references" / "plan-worker-prompt.md"
IMPLEMENTATION_PROMPT = ROOT / "references" / "implementation-worker-prompt.md"
SPEC_STAGE = ROOT / "references" / "spec-stage.md"
PLAN_STAGE = ROOT / "references" / "plan-stage.md"
IMPLEMENTATION_STAGE = ROOT / "references" / "implementation-stage.md"


class StageWorkerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.execution_contract = EXECUTION_CONTRACT.read_text(encoding="utf-8")
        cls.spec_stage = SPEC_STAGE.read_text(encoding="utf-8")
        cls.plan_stage = PLAN_STAGE.read_text(encoding="utf-8")
        cls.implementation_stage = IMPLEMENTATION_STAGE.read_text(encoding="utf-8")

    def test_stage_worker_resources_exist(self):
        for path in (
            STAGE_CONTRACT,
            SPEC_PROMPT,
            PLAN_PROMPT,
            IMPLEMENTATION_PROMPT,
        ):
            self.assertTrue(path.is_file(), path)

    def test_shared_contract_uses_fresh_workers_and_file_handoffs(self):
        text = STAGE_CONTRACT.read_text(encoding="utf-8")
        for required in (
            "fork_turns=none",
            ".local/stage-workers/<workflow_id>/<change_id>/<stage>/",
            "handoff.json",
            "不得继承完整主会话",
            "完整内容写入文件",
            "只返回短交接",
            "不得修改 SQLite",
        ):
            self.assertIn(required, text)

    def test_contract_defines_stage_inputs_candidate_semantics_and_fresh_review(self):
        contract = STAGE_CONTRACT.read_text(encoding="utf-8")
        plan_prompt = PLAN_PROMPT.read_text(encoding="utf-8")
        for required in (
            "阶段必填输入",
            "baseline_details",
            "Plan 的 `candidate.md` 是候选清单",
            "待采用候选",
            "非阻塞建议",
            "规划用只读 worktree",
            "candidate_sha256",
            "expected_revision",
            "authorization-offer.json",
            "当前配置路径",
        ):
            self.assertIn(required, contract)
        for required in (
            "`fork_turns=none`",
            "不继承 writer 的聊天历史",
            "非阻塞建议",
        ):
            self.assertIn(required, plan_prompt)

        spec_prompt = SPEC_PROMPT.read_text(encoding="utf-8")
        implementation_prompt = IMPLEMENTATION_PROMPT.read_text(encoding="utf-8")
        for required in (
            "候选 SHA-256",
            "confirmed_candidate_sha256",
            "当前 revision",
        ):
            self.assertIn(required, spec_prompt)
        for required in (
            "authorization-offer.json",
            "execution-contract.json",
            "逐字节与 SHA-256",
        ):
            self.assertIn(required, implementation_prompt)

    def test_spec_worker_keeps_confirmation_and_publication_with_controller(self):
        prompt = SPEC_PROMPT.read_text(encoding="utf-8")
        for required in (
            "writing-specs",
            "spec_worker",
            "candidate.md",
            "用户确认前不得写入 `specs/<change_id>.md`",
            "主 Agent 完整展示",
            "spec_ref",
            "test_ref",
        ):
            self.assertIn(required, prompt)

        for required in (
            "Spec Worker",
            "spec-worker-prompt.md",
            "用户确认后",
            "`spec_ref` 与 `test_ref`",
        ):
            self.assertIn(required, self.spec_stage)

    def test_plan_worker_requires_review_then_controller_and_user_approval(self):
        prompt = PLAN_PROMPT.read_text(encoding="utf-8")
        for required in (
            "plan_worker",
            "writing-lean-plans",
            "writing-plans",
            "独立 reviewer",
            "Approved",
            "主 Agent",
            "用户确认",
            "不得调用 `adopt-plan`",
        ):
            self.assertIn(required, prompt)

        planning = self.plan_stage.split("## 固定采用顺序", 1)[1].split("```", 2)[1]
        review_index = planning.index("独立语义 reviewer Approved")
        controller_index = planning.index("主 Agent 审核")
        user_index = planning.index("用户确认")
        adopt_index = planning.index("managing-change-ledger adopt-plan")
        self.assertLess(review_index, controller_index)
        self.assertLess(controller_index, user_index)
        self.assertLess(user_index, adopt_index)

    def test_implementation_coordinator_runs_sdd_and_returns_without_finishing(self):
        prompt = IMPLEMENTATION_PROMPT.read_text(encoding="utf-8")
        for required in (
            "implementation_coordinator",
            "subagent-driven-development",
            "authorization_offer",
            "execution_contract",
            "Task Implementer",
            "完整报告写入文件",
            "不得调用 `finishing-a-development-branch`",
            "返回主 Agent",
        ):
            self.assertIn(required, prompt)

        for required in (
            "Implementation Coordinator",
            "implementation-worker-prompt.md",
            "启动 `subagent-driven-development`",
            "返回本入口",
        ):
            self.assertIn(required, self.implementation_stage)

        self.assertIn("implementation coordinator", self.execution_contract)

    def test_controller_owns_identity_confirmation_ledger_and_stage(self):
        contract = STAGE_CONTRACT.read_text(encoding="utf-8")
        for required in (
            "`workflow_id`",
            "`change_id`",
            "用户确认",
            "正式材料采用",
            "总账写入",
            "阶段推进",
        ):
            self.assertIn(required, contract)


if __name__ == "__main__":
    unittest.main()
