from pathlib import Path
import unittest


SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"


class ManagingChangeLedgerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")

    def test_bug_registration_does_not_reuse_another_change_spec_path(self):
        self.assertIn("不得把其他事件的 Spec 路径塞入当前事件", self.text)
        self.assertIn("`specs/<change_id>.md`", self.text)
        self.assertNotIn("--spec-ref <path>.md@<sha>", self.text)

    def test_code_ref_is_atomically_persisted_from_worktree(self):
        self.assertIn("set-code-ref", self.text)
        self.assertIn("实际 worktree", self.text)
        self.assertIn("原子", self.text)
        self.assertIn("稳定仓库名只能使用", self.text)
        self.assertIn("`tdd_coding`", self.text)

    def test_impact_contracts_are_forward_only_stage_gates(self):
        self.assertIn("进入 `writing_plan`", self.text)
        self.assertIn("`## 既有功能与流程影响`", self.text)
        self.assertIn("每次新的 `adopt-plan`", self.text)
        self.assertIn("`## 实现兼容性分析`", self.text)
        self.assertIn("不追溯阻断", self.text)

    def test_plan_adoption_impact_validation_is_atomic(self):
        self.assertIn("全部 Spec `impact_id`", self.text)
        self.assertIn("Task N", self.text)
        self.assertIn("`阻塞`", self.text)
        self.assertIn("标为 `明确改变`", self.text)
        self.assertIn("编号唯一的 `Task N`", self.text)
        self.assertIn("保持事务无写入", self.text)

    def test_change_document_has_exactly_registration_and_completion_writes(self):
        self.assertIn("`change.md` 严格只写两次", self.text)
        self.assertIn("第一次：事件登记", self.text)
        self.assertIn("第二次：事件完成", self.text)
        self.assertIn("中间阶段不得编辑 `change.md`", self.text)
        self.assertIn("中间阶段不得更新 `change_ref`", self.text)

    def test_plan_adoption_does_not_use_an_intermediate_change_document(self):
        self.assertIn("Plan adoption 不创建或修改 `change.md`", self.text)
        self.assertIn("只原子更新 `plan_ref`", self.text)
        self.assertNotIn("--adoption-change-ref", self.text)
        self.assertNotIn("plan-adoption-proof", self.text)

    def test_completion_atomically_installs_the_final_change_reference(self):
        self.assertIn("complete CE-0001 --change-ref", self.text)
        self.assertIn("同时写入最终 `change_ref` 和 `status=completed`", self.text)
        self.assertIn("`set-ref --field change_ref` 必须拒绝", self.text)
        self.assertIn(
            "没有绑定活动工作流时，完成门重新校验 Spec 与 Plan 的实现兼容性覆盖",
            self.text,
        )

    def test_completion_derives_the_final_logic_draft_from_change_ref(self):
        for required in (
            "`logic/<change_id>.md`",
            "`## 功能逻辑`",
            "最终 `change_ref`",
            "不增加 `logic_ref`",
        ):
            self.assertIn(required, self.text)

    def test_runtime_commands_require_the_current_project_config(self):
        removed_user_default = "~/" + ".codex/personal-development-workflow/config.json"
        self.assertIn("当前项目配置", self.text)
        self.assertIn("--config <project-config>", self.text)
        self.assertNotIn(removed_user_default, self.text)

    def test_one_change_tracks_one_current_plan_with_multiple_tasks(self):
        for required in (
            "每个 `change_id` 只维护一份当前采用的正式 Plan",
            "一个 `plan_ref`",
            "多个实现 `Task N`",
            "实现 Task 不是总账身份",
            "重新规划仍写入 `plans/<change_id>.md`",
        ):
            self.assertIn(required, self.text)

    def test_completion_reliability_gates_are_flow_specific(self):
        self.assertIn("Full 的 `complete` 必须确认", self.text)
        self.assertIn("direct/light 只执行各自 flow", self.text)
        self.assertIn("Full 正准备在没有最终通过报告", self.text)
        self.assertIn("以下验收报告、validator 和最终逻辑稿错误只适用于 Full", self.text)

    def test_implementation_bug_uses_spec_handling_instead_of_discovery_spec(self):
        self.assertNotIn("discovery_spec", self.text)
        self.assertIn("在 `## Spec 处理` 说明中记录当前行为依据", self.text)
        self.assertIn("没有适用 Spec 时记录相关 CE 或 `source_ce`", self.text)


if __name__ == "__main__":
    unittest.main()
