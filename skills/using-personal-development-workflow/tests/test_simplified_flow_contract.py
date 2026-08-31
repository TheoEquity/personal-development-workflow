from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SimplifiedFlowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        cls.requirements = (ROOT / "references" / "requirement-discussion.md").read_text(
            encoding="utf-8"
        )
        cls.registration = (ROOT / "references" / "change-registration.md").read_text(
            encoding="utf-8"
        )
        cls.spec_stage = (ROOT / "references" / "spec-stage.md").read_text(
            encoding="utf-8"
        )
        cls.implementation = (ROOT / "references" / "implementation-stage.md").read_text(
            encoding="utf-8"
        )
        cls.acceptance = (ROOT / "references" / "acceptance-stage.md").read_text(
            encoding="utf-8"
        )
        cls.integration = (ROOT / "references" / "integration-and-cleanup.md").read_text(
            encoding="utf-8"
        )
        cls.all_text = "\n".join(
            (
                cls.workflow,
                cls.requirements,
                cls.registration,
                cls.spec_stage,
                cls.implementation,
                cls.acceptance,
                cls.integration,
            )
        )

    def test_one_router_has_three_flows_without_three_workflows(self):
        for required in (
            "`flow: direct | light | full`",
            "同一个状态机",
            "不新增阶段",
            "`review_mode: manual | auto`",
        ):
            self.assertIn(required, self.all_text)

    def test_bug_and_ce_ownership_are_result_based(self):
        for required in (
            "独立验收",
            "已完成的旧 CE 保持不可变",
            "`source_ce`",
            "恢复已有行为",
            "新增或改变正式行为",
            "先判行为、再判本次修改风险；风险门覆盖行为分类",
            "Bug 的现象涉及错误数据不自动升级 Full",
        ):
            self.assertIn(required, self.all_text)

    def test_flow_and_source_ce_have_one_durable_owner(self):
        self.assertIn("`flow` 只写入 `workflow_state`", self.all_text)
        self.assertIn("`source_ce` 固定落在 `change.md`", self.all_text)

    def test_personal_workflow_does_not_fall_back_to_in_place_development(self):
        self.assertIn("拒绝创建或使用 Worktree 时保持 `tdd_coding` 并停止", self.all_text)
        self.assertIn("不得在原 checkout 降级开发", self.all_text)

    def test_light_spec_has_no_full_material_gate(self):
        for required in (
            "`light` profile",
            "不强制既有功能影响表",
            "不强制代码 SHA 扫描",
            "不生成正式 `test_ref`",
            "不生成正式 `plan_ref`",
        ):
            self.assertIn(required, self.all_text)

    def test_project_constitution_is_optional_and_loader_is_separate(self):
        for required in (
            "没有项目宪法不得阻塞普通开发",
            "Loader 只服务项目宪法接入",
            "项目特有规则不得写入全局工作流 Skill",
            "Disclosure Set",
        ):
            self.assertIn(required, self.all_text)

    def test_loop_and_code_review_are_ephemeral(self):
        for required in (
            "`code_review: skip | run`",
            "`loop_mode: off | on`",
            "不进入总账",
            "复杂任务不能进入 Loop",
            "只能在 `direct` 与 `light` 之间切换",
            "systematic-debugging",
        ):
            self.assertIn(required, self.all_text)

    def test_full_review_reuses_sdd_final_and_batch_review_is_explicit(self):
        for required in (
            "SDD 最终整体 review 同时满足 Full CE 级代码 review",
            "不得追加等价代码 review",
            "用户明确要求跨 CE 批次 review",
        ):
            self.assertIn(required, self.all_text)

    def test_review_range_is_derived_from_ce_or_batch_git_facts(self):
        for required in (
            "`reviewed_worker_head`",
            "`review_head` 记录受审的 Worker SHA",
            "`code_ref` 记录 Delivery merge SHA",
            "Worker SHA 是 merge SHA 的祖先",
            "没有改写该 CE 的已审 diff",
            "`review_base` 取该 CE 的 `delivery_before_sha`",
            "按 Delivery 祖先顺序排列、不得重复",
            "`review_base=freeze_base`",
            "`review_head=freeze_head`",
            "跨 CE 批次 review",
            "只审查跨 CE 交互",
        ):
            self.assertIn(required, self.all_text)

    def test_full_plan_and_worker_shape_are_bounded(self):
        for required in (
            "所有正式 Plan 始终采用 Lean",
            "默认 1–3 个执行 Task",
            "一个实现 Worker",
            "不得把测试、文档或配置拆成独立 Task",
            "超过 3 个 Task",
            "用户例外确认",
        ):
            self.assertIn(required, self.all_text)

    def test_automation_evidence_has_one_execution_owner_and_exact_reuse_key(self):
        for required in (
            "`code_sha + command + environment_fingerprint + input_fingerprint`",
            "同一证据只执行和记录一次",
            "Reviewer 使用已有测试证据审查，不默认重跑",
            "Root 只验证引用、SHA、范围和证据",
            "Delivery 在最终候选合并版本上执行一次 CE 完整自动化验证",
            "Acceptance 复用绑定同一 `code_ref` 的自动化证据",
            "任一维度变化",
            "`environment_fingerprint`",
            "`input_fingerprint`",
            "`produced_by`",
        ):
            self.assertIn(required, self.all_text)

    def test_light_path_does_not_inherit_full_only_gates(self):
        for required in (
            "Direct/light 只加载本节、`test-driven-development`、`using-git-worktrees` 与 `verification-before-completion`",
            "只有 Full 加载 `execution-contract.md`、stage Worker 与 SDD",
            "Light 不加载 `material-change-assessment.md`",
            "按 flow 核对当前 CE 的既有行为或短 Spec 与 diff",
            "以下 Plan、独立 review、验收 validator 和最终逻辑稿门禁只适用于 Full",
            "以下报告、validator、最终逻辑稿和六类引用信号只适用于 Full",
            "以下 Worker、handoff 和完整候选展示信号只适用于 Full",
            "以下 Plan、SDD offer、Coordinator、独立 reviewer 和材料变更评估信号只适用于 Full",
        ):
            self.assertIn(required, self.all_text)

    def test_delivery_worker_rolls_until_user_freezes_batch(self):
        for required in (
            "Delivery Worktree",
            "Worker Worktree",
            "开发可以并发，集成必须串行",
            "`integrated_commit`",
            "批次边界由用户",
            "不自动 Push",
            "不自动删除 Worktree",
        ):
            self.assertIn(required, self.all_text)

    def test_history_is_searchable_but_not_current_behavior_contract(self):
        for required in (
            "修改与验证摘要",
            "历史摘要不是当前行为合同",
            "当前有效 Spec",
            "Worker 不直接修改 `change.md`",
        ):
            self.assertIn(required, self.all_text)


if __name__ == "__main__":
    unittest.main()
