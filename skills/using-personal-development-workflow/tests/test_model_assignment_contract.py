from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "references"


class ModelAssignmentContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stage_contract = (REFERENCES / "stage-worker-contract.md").read_text(
            encoding="utf-8"
        )
        cls.spec_stage = (REFERENCES / "spec-stage.md").read_text(encoding="utf-8")
        cls.plan_stage = (REFERENCES / "plan-stage.md").read_text(encoding="utf-8")
        cls.plan_prompt = (REFERENCES / "plan-worker-prompt.md").read_text(
            encoding="utf-8"
        )
        cls.implementation_prompt = (
            REFERENCES / "implementation-worker-prompt.md"
        ).read_text(encoding="utf-8")
        cls.dispatch_contracts = "\n".join(
            (
                cls.stage_contract,
                cls.spec_stage,
                cls.plan_stage,
                cls.plan_prompt,
                cls.implementation_prompt,
            )
        )

    def test_personal_workflow_has_no_fixed_model_or_reasoning_table(self):
        for forbidden in (
            "gpt-5.6-sol",
            "gpt-5.6-terra",
            "reasoning_effort=high",
            "reasoning_effort=xhigh",
            "固定模型与推理档位",
        ):
            self.assertNotIn(forbidden, self.dispatch_contracts)

    def test_stage_workers_inherit_current_effective_configuration(self):
        for required in (
            "当前有效配置",
            "不固定具体模型名称",
            "不固定 `high/xhigh`",
        ):
            self.assertIn(required, self.stage_contract)

    def test_sdd_uses_the_least_adequate_dynamic_assignment(self):
        for required in (
            "按任务复杂度",
            "足够完成任务的最低合理档位",
            "没有代表性结果证明收益",
            "不因 reviewer、返工或 Full 身份自动升级",
        ):
            self.assertIn(required, self.implementation_prompt)


if __name__ == "__main__":
    unittest.main()
