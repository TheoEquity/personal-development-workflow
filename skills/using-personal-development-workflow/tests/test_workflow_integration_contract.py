import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT.parents[1]
WORKFLOW = ROOT / "SKILL.md"
EXECUTION_CONTRACT = ROOT / "references" / "execution-contract.md"
EXAMPLE_CONFIG = (
    PACKAGE_ROOT / "examples" / "personal-development-workflow.json.example"
)
LEDGER_SCRIPT = (
    PACKAGE_ROOT
    / "skills"
    / "managing-change-ledger"
    / "scripts"
    / "change_ledger.py"
)


class WorkflowIntegrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.execution_contract_text = EXECUTION_CONTRACT.read_text(encoding="utf-8")

    def test_plan_review_protocol_has_one_normative_source(self):
        self.assertIn("`writing-plans` 的 `Execution Handoff`", self.text)
        self.assertIn("`plan-document-reviewer-prompt.md`", self.text)
        self.assertNotIn("plan-adoption-proof:start", self.text)
        self.assertIn("`managing-change-ledger`", self.text)
        self.assertIn("`adopt-plan`", self.text)

    def test_change_document_is_written_only_at_registration_and_completion(self):
        self.assertIn("登记时创建一次、完成时更新一次", self.text)
        self.assertIn("中间阶段只更新各自的 SQLite 引用", self.text)
        self.assertIn("通用 `set-ref` 不能写 `change_ref`", self.text)
        self.assertNotIn("最新 `change_ref`", self.text)

    def test_plan_adoption_keeps_the_registration_change_reference(self):
        self.assertIn(
            "`adopt-plan <change_id> --workflow-id <workflow_id> --plan-ref <plan_ref>`",
            self.text,
        )
        self.assertIn("`change_ref` 保持登记版不变", self.text)
        for stale_phrase in (
            "adoption-only",
            "adoption_change_ref",
            "`plan-adoption-contract`",
            "plan-adoption-proof",
        ):
            self.assertNotIn(stale_phrase, self.text)

    def test_completion_atomically_installs_the_final_change_reference(self):
        self.assertIn(
            "`complete <change_id> --change-ref changes/<change_id>/change.md@<final-sha>`",
            self.text,
        )
        self.assertIn("原子更新最终 `change_ref` 和 `status=completed`", self.text)
        self.assertIn("已完成事件允许幂等查询", self.text)

    def test_acceptance_handoff_consumes_the_single_validator_result(self):
        self.assertNotIn("`change_id`、`test_ref`、`code_ref` 和 `overall_status`", self.text)
        self.assertIn("`writing-test-drafts` 的唯一 validator", self.text)
        self.assertIn("规范化结果", self.text)
        self.assertIn("`status: completed`", self.text)
        self.assertIn("`spec_ref`、`plan_ref`、`test_ref`、`code_ref`、`evidence_ref`", self.text)

    def test_impact_range_definition_is_not_duplicated(self):
        self.assertIn("`writing-specs` 是“可能的影响范围”的唯一规范源", self.text)
        self.assertNotIn("`可能修改 / 可能新增 / 需要核对`", self.text)

    def test_execution_contract_and_finishing_are_stop_signals_not_copies(self):
        self.assertNotIn("execution_contract:", self.text)
        self.assertNotIn("tdd_evidence:", self.text)
        self.assertLessEqual(self.text.count("`finishing-a-development-branch`"), 2)

    def test_plan_approval_has_a_preimplementation_drift_boundary(self):
        self.assertIn("代码实现开始前", self.text)
        self.assertIn("重新核对", self.text)

    def test_sdd_final_reviewer_receives_the_canonical_execution_contract(self):
        self.assertIn("同一序列化内容原样传给", self.text)
        self.assertIn("reviewer", self.text)

    def test_superpowers_originals_are_read_only_dependencies(self):
        self.assertIn("Superpowers 原生技能是只读依赖", self.text)

    def test_controller_discovers_the_nearest_project_configuration_only(self):
        removed_user_default = "~/" + ".codex/personal-development-workflow/config.json"
        self.assertIn("从当前工作目录向上", self.text)
        self.assertIn("第一份 `.codex/personal-development-workflow.json`", self.text)
        self.assertIn("找不到项目配置时停止", self.text)
        self.assertNotIn(removed_user_default, self.text)

    def test_user_level_default_configuration_is_removed(self):
        removed_user_default = "~/" + ".codex/personal-development-workflow/config.json"
        self.assertNotIn(removed_user_default, self.text)
        self.assertIn("没有全局配置 fallback", self.text)

    def test_current_project_configuration_binds_formal_materials_to_repository(self):
        self.assertTrue(EXAMPLE_CONFIG.is_file(), EXAMPLE_CONFIG)
        config = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))

        self.assertEqual(config["spec_vault"], "<absolute-project-spec-vault-path>")
        self.assertEqual(config["database"], "<absolute-project-spec-vault-path>/.local/personal-workflow.sqlite3")
        self.assertEqual(
            config["repositories"],
            {"example-repository": "<absolute-code-repository-path>"},
        )

    def test_project_configuration_initializes_the_git_ignored_local_ledger(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            vault = project_root / "spec-vault"
            repository = project_root / "code-repository"
            config_directory = project_root / ".codex"
            vault.mkdir()
            repository.mkdir()
            config_directory.mkdir()

            for git_root in (vault, repository):
                subprocess.run(
                    ["git", "-C", str(git_root), "init", "-q"],
                    check=True,
                    capture_output=True,
                    text=True,
                )

            (vault / ".gitignore").write_text("/.local\n", encoding="utf-8")
            database_path = vault / ".local" / "personal-workflow.sqlite3"
            project_config = config_directory / "personal-development-workflow.json"
            project_config.write_text(
                json.dumps(
                    {
                        "spec_vault": str(vault),
                        "database": str(database_path),
                        "repositories": {"example-repository": str(repository)},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(LEDGER_SCRIPT),
                    "--config",
                    str(project_config),
                    "init",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(
                result.returncode,
                0,
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            )
            self.assertTrue(database_path.is_file(), database_path)

    def test_register_change_always_enters_writing_spec(self):
        self.assertIn("新事件登记并绑定后固定把阶段设为 `writing_spec`", self.text)
        self.assertIn("只有 `spec_ref` 与 `test_ref` 都有效后才能进入 Plan", self.text)

    def test_personal_workflow_never_bypasses_independent_task_review(self):
        self.assertNotIn("当前会话直接 TDD", self.text)
        self.assertIn("用户之后另行明确选择非 SDD 执行方式", self.text)
        self.assertIn("带独立逐任务 reviewer 的 `executing-plans`", self.text)

    def test_adopted_plan_stops_at_the_explicit_sdd_handoff(self):
        for required in (
            "是否开启 Subagent-Driven Development 进行开发？",
            "只有 `adopt-plan` 成功后",
            "用户明确回复“开启”",
            "使用 `using-git-worktrees`",
            "启动 `subagent-driven-development`",
            "用户明确回复“不启动”",
            "不创建 worktree、不修改代码、不创建本地 commit",
        ):
            self.assertIn(required, self.text)

    def test_plan_records_the_reviewed_remote_baseline(self):
        for required in (
            "`base_remote`",
            "`base_branch`",
            "`base_sha`",
            "40 位完整 Git commit SHA",
            "Plan reviewer",
        ):
            self.assertIn(required, self.text)

    def test_sdd_fetches_and_resolves_the_plan_branch_before_worktree(self):
        self.assertIn("#### 开发前远程基线门禁", self.text)
        gate_start = self.text.index("#### 开发前远程基线门禁")
        gate_end = self.text.index("####", gate_start + 5)
        gate = self.text[gate_start:gate_end]

        for required in (
            "第一项动作",
            "git fetch --no-tags <base_remote> +refs/heads/<base_branch>:refs/remotes/<base_remote>/<base_branch>",
            "<base_remote>/<base_branch>^{commit}",
            "最新完整 SHA",
            "`using-git-worktrees`",
        ):
            self.assertIn(required, gate)
        self.assertLess(gate.index("git fetch"), gate.index("`using-git-worktrees`"))

    def test_remote_baseline_drift_closes_code_until_plan_readoption(self):
        for required in (
            "不得创建或复用开发 worktree",
            "不得写 RED、测试或生产代码",
            "不得创建本地 commit",
            "只审查这段远程差异",
            "重新评审、提交并由 `adopt-plan` 采用",
            "不对主 checkout 执行 `git pull`、merge 或 reset",
        ):
            self.assertIn(required, self.text)

    def test_sdd_authorization_covers_only_the_scoped_local_fetch(self):
        for required in (
            "第四件本地前置动作",
            "Plan 显示的 `base_remote` 与 `base_branch`",
            "只更新本地 remote-tracking ref",
            "不授权任何远程写入",
        ):
            self.assertIn(required, self.execution_contract_text)

    def test_sdd_handoff_authorizes_only_the_displayed_local_scope(self):
        for required in (
            "当前 `plan_ref`",
            "配置中的代码仓库绝对路径",
            "实际返回的隔离 worktree",
            "当前 Plan 范围内的本地 commits",
            "不授权 push、MR、合并、清理或 branch finishing",
        ):
            self.assertIn(required, self.execution_contract_text)

    def test_controller_owns_one_change_id_for_all_materials(self):
        for required in (
            "总控负责请求、提供并跟踪 `change_id`",
            "`specs/<change_id>.md`",
            "`plans/<change_id>.md`",
            "`tests/<change_id>.md`",
            "`acceptance/<change_id>/<run>.md`",
        ):
            self.assertIn(required, self.text)

    def test_one_plan_maps_to_one_workflow_change_and_can_hold_many_tasks(self):
        for required in (
            "一份正式 Plan 对应一个个人工作流任务",
            "一个工作流游标绑定的一个变更事件",
            "Plan 内部可以拆分为多个实现 `Task N`",
            "不得为单个实现 Task 新建 Plan、工作流游标或变更事件",
            "仍更新 `plans/<change_id>.md`",
            "新的完整 Git SHA",
        ):
            self.assertIn(required, self.text)

    def test_spec_phase_creates_test_draft_before_plan(self):
        self.assertIn("`writing-specs` 调用 `writing-test-drafts`", self.text)
        self.assertIn("Spec 与测试稿", self.text)
        self.assertIn("从 `tdd_coding` 直接进入 `acceptance`", self.text)

    def test_code_ref_is_resolved_from_actual_worktree(self):
        self.assertIn("set-code-ref <change_id> --worktree", self.text)
        self.assertIn("原子", self.text)
        self.assertIn("Git common directory", self.text)

    def test_spec_impacts_are_passed_into_plan_and_review_requirements(self):
        self.assertIn("完整 Spec 和全部 `impact_id`", self.text)
        self.assertIn("`## 实现兼容性分析`", self.text)
        self.assertIn("作为本次调用的 requirements 输入", self.text)
        self.assertIn("覆盖、Task 映射和阻塞状态", self.text)
        self.assertIn("Spec 标为 `明确改变`", self.text)
        self.assertIn("至少要有一条适配或迁移任务", self.text)

    def test_plan_behavior_change_returns_to_spec(self):
        self.assertIn("返回 `writing_spec`", self.text)
        self.assertIn("不得由 Plan 自行决定", self.text)

    def test_rework_impact_audit_reads_current_refs_before_routing(self):
        for required in (
            "返工影响审查",
            "移动游标前",
            "当前 `spec_ref` 与 `plan_ref`",
            "完整 Git SHA",
            "不可变内容",
            "`无需修改 / 局部修改 / 结构性修改`",
            "具体章节、`impact_id` 或 `Task N`",
        ):
            self.assertIn(required, self.text)

    def test_rework_routes_to_the_earliest_owning_stage(self):
        for required in (
            "Spec 与 Plan 均为 `无需修改`：回到 `tdd_coding`",
            "只有 Plan 需要修改：回到 `writing_plan`",
            "Spec 需要修改：回到 `writing_spec`",
            "只重新审查受新 Spec 影响的 Plan 部分",
        ):
            self.assertIn(required, self.text)

    def test_rework_rejects_unscoped_document_rewrites(self):
        for required in (
            "以当前正式引用为基线检查 Git diff",
            "审查范围外的大段删除、整份替换、Task 全部重建或无理由重编号",
            "局部补丁不足",
            "取得用户明确确认",
            "新增行为、范围扩展或已完成事件之后的变化必须新建事件",
        ):
            self.assertIn(required, self.text)

    def test_rework_material_changes_close_the_code_gate(self):
        for required in (
            "只要 Spec 或 Plan 不是 `无需修改`，代码门立即关闭",
            "不得修改生产代码或测试代码",
            "不得启动实现编排器",
            "不得创建新的代码 commit",
            "不得更新 `code_ref`",
        ):
            self.assertIn(required, self.text)

    def test_rework_reopens_code_gate_only_after_material_adoption(self):
        for required in (
            "先修改并确认 Spec、提交并更新 `spec_ref`",
            "再修改 Plan、完成独立 review",
            "`adopt-plan` 成功并安装新 `plan_ref`",
            "才允许进入 `tdd_coding`",
            "材料修改前的编码或 commit 授权立即失效",
            "Spec 与 Plan 均为 `无需修改` 时允许直接进入 `tdd_coding`",
        ):
            self.assertIn(required, self.text)

    def test_rework_freezes_preexisting_code_until_the_new_plan_is_adopted(self):
        for required in (
            "已经存在材料修改前产生的代码改动",
            "冻结",
            "不自动删除",
            "不得继续修改、提交或更新 `code_ref`",
            "新 `spec_ref`/`plan_ref`",
            "实际 worktree diff",
            "重新满足 TDD 与授权门禁",
        ):
            self.assertIn(required, self.text)

    def test_impact_assessment_does_not_expand_test_drafts(self):
        self.assertIn("测试稿不因影响表自动扩展回归项", self.text)
        self.assertIn("不修改 `writing-test-drafts`", self.text)


if __name__ == "__main__":
    unittest.main()
