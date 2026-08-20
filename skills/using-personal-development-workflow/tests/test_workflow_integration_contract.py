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
MATERIAL_CHANGE_ASSESSMENT = ROOT / "references" / "material-change-assessment.md"
PLAN_BASELINE_SELECTION = ROOT / "references" / "plan-baseline-selection.md"
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
        cls.material_change_assessment_text = MATERIAL_CHANGE_ASSESSMENT.read_text(
            encoding="utf-8"
        )

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

    def test_passed_acceptance_writes_final_logic_before_completion(self):
        for required in (
            "`writing-final-logic-drafts`",
            "`logic/<change_id>.md`",
            "`## 功能逻辑`",
            "验收报告全部通过之后",
            "完成变更事件之前",
            "不增加 SQLite 阶段",
        ):
            self.assertIn(required, self.text)

        writer = self.text.index("`writing-final-logic-drafts`")
        completion = self.text.index("**完成变更事件**")
        self.assertLess(writer, completion)

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
        self.assertIn("只回复“继续”不算明确开启 SDD", self.text)

    def test_plan_records_the_confirmed_local_or_remote_baseline(self):
        for required in (
            "`base_source`",
            "`base_locator`",
            "`base_sha`",
            "40 位完整 Git commit SHA",
            "Plan reviewer",
        ):
            self.assertIn(required, self.text)

    def test_plan_lists_local_and_remote_candidates_before_writing(self):
        self.assertTrue(PLAN_BASELINE_SELECTION.is_file())
        baseline = PLAN_BASELINE_SELECTION.read_text(encoding="utf-8")
        for required in (
            "git worktree list --porcelain",
            "git ls-remote --heads <base_remote> refs/heads/<base_branch>",
            "`clean/dirty`",
            "只回复“继续”将采用远程候选",
            "基线确定前不得创建或重写 Plan",
        ):
            self.assertIn(required, baseline)

    def test_local_plan_baseline_does_not_require_remote_equality(self):
        self.assertTrue(PLAN_BASELINE_SELECTION.is_file())
        baseline = PLAN_BASELINE_SELECTION.read_text(encoding="utf-8")
        for required in (
            "可以尚未推送",
            "不要求等于远程最新 SHA",
            "不得混入当前脏工作区",
            "未提交修改不属于任何 SHA",
            "不执行远程相等性门禁",
        ):
            self.assertIn(required, baseline)

    def test_dirty_baseline_capture_has_a_bounded_preplan_commit_scope(self):
        baseline = PLAN_BASELINE_SELECTION.read_text(encoding="utf-8")
        for required in (
            "`baseline-capture:<change_id>`",
            "尚未存在 `Task N`",
            "只包含用户点名纳入基线的 diff",
            "不能授权后续实现 commit",
        ):
            self.assertIn(required, baseline)

    def test_candidate_movement_requires_a_new_selection(self):
        self.assertTrue(PLAN_BASELINE_SELECTION.is_file())
        baseline = PLAN_BASELINE_SELECTION.read_text(encoding="utf-8")
        for required in (
            "远程在等待选择期间移动",
            "重新执行选择门禁",
            "本地定位对象已经移动",
            "重新展示候选",
        ):
            self.assertIn(required, baseline)

    def test_every_new_plan_ref_reselects_a_baseline(self):
        baseline = PLAN_BASELINE_SELECTION.read_text(encoding="utf-8")
        for required in (
            "任何会产生新 `plan_ref` 的 Plan 修改",
            "内容不变但重新锚定到新的 Git SHA",
            "只有选中的候选",
        ):
            self.assertIn(required, baseline)

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
            "保持当前阶段并先执行材料变更评估",
        ):
            self.assertIn(required, self.text)

    def test_local_baseline_reuses_or_creates_only_an_exact_clean_worktree(self):
        for required in (
            "`base_source=local`",
            "不执行远程 fetch 或远程相等性比较",
            "`HEAD` 必须逐字等于 `base_sha`",
            "工作区必须干净",
            "创建新的隔离 worktree",
        ):
            self.assertIn(required, self.text)

    def test_status_and_stop_rules_branch_on_the_selected_baseline_source(self):
        for required in (
            "按 Plan 的 `base_source` 执行对应基线门禁",
            "仅当 `base_source=remote` 时",
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

    def test_sdd_authorization_is_specific_to_the_selected_baseline_source(self):
        for required in (
            "`base_source=remote`",
            "`base_source=local`",
            "不授权远程 fetch 或远程相等性比较",
            "精确显示的本地 `base_sha`",
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
            "材料变更评估",
            "任何材料、代码或阶段变化之前",
            "当前 `spec_ref` 与 `plan_ref`",
            "完整 Git SHA",
            "读取不可变内容",
            "`无需修改 / 局部修改 / 结构性修改`",
            "具体章节或 impact_id",
            "具体章节或 Task N",
        ):
            self.assertIn(required, self.material_change_assessment_text)

    def test_rework_routes_to_the_earliest_owning_stage(self):
        for required in (
            "Spec 与 Plan 均无需修改",
            "只有 Plan 需要变化",
            "Spec 需要变化",
            "只重新评估新 Spec 实际影响的 Plan 部分",
        ):
            self.assertIn(required, self.material_change_assessment_text)

    def test_rework_rejects_unscoped_document_rewrites(self):
        for required in (
            "以评估所用正式引用为基线检查 Git diff",
            "评估范围外的大段删除、整份替换、Task 全部重建或无理由重编号",
            "局部补丁不足",
            "等待用户明确确认",
            "已完成事件保持不可变",
        ):
            self.assertIn(required, self.material_change_assessment_text)

    def test_rework_material_changes_close_the_code_gate(self):
        for required in (
            "任一材料需要修改时，代码门保持关闭",
            "确认前不得修改生产代码或测试代码",
            "启动实现器",
            "创建代码 commit",
            "更新 `code_ref`",
        ):
            self.assertIn(required, self.material_change_assessment_text)

    def test_rework_reopens_code_gate_only_after_material_adoption(self):
        for required in (
            "先修改、确认并提交 Spec，更新 `spec_ref`",
            "重新独立 review 并调用 `adopt-plan`",
            "只有材料门重新打开后",
            "旧执行授权都不能恢复本次确认",
            "Spec 与 Plan 均无需修改",
        ):
            self.assertIn(required, self.material_change_assessment_text)

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
            self.assertIn(required, self.material_change_assessment_text)

    def test_impact_assessment_does_not_expand_test_drafts(self):
        self.assertIn("测试稿不因影响表自动扩展回归项", self.text)
        self.assertIn("不修改 `writing-test-drafts`", self.text)

    def test_material_change_assessment_is_required_before_material_or_stage_changes(self):
        self.assertIn(
            "[material-change-assessment.md](references/material-change-assessment.md)",
            self.text,
        )
        self.assertTrue(MATERIAL_CHANGE_ASSESSMENT.is_file())
        assessment = self.material_change_assessment_text
        for required in (
            "每次材料变更评估输出后都立即停止",
            "等待用户明确确认",
            "包括 Spec 与 Plan 均为 `无需修改`",
            "确认前不得修改、保存或提交 Spec/Plan",
            "确认前不得修改生产代码或测试代码",
            "确认前不得移动 `current_stage`",
        ):
            self.assertIn(required, assessment)

    def test_material_assessment_confirmation_is_explicit_and_version_specific(self):
        assessment = self.material_change_assessment_text
        for required in (
            "明确同意 Spec 与 Plan 两份结论",
            "只回复“继续”不构成确认",
            "正常的新事件登记不是材料变更",
            "第二轮仍输出 Spec 与 Plan 两份结论",
        ):
            self.assertIn(required, assessment)

    def test_material_change_assessment_supports_local_and_structural_scope(self):
        self.assertTrue(MATERIAL_CHANGE_ASSESSMENT.is_file())
        assessment = self.material_change_assessment_text
        for required in (
            "`无需修改 / 局部修改 / 结构性修改`",
            "修改规模只能由语义影响决定",
            "局部补丁为何不足",
            "明确保留",
            "允许合理的大幅修改",
        ):
            self.assertIn(required, assessment)

    def test_followup_changes_assess_related_immutable_materials_without_rewriting_them(self):
        self.assertTrue(MATERIAL_CHANGE_ASSESSMENT.is_file())
        assessment = self.material_change_assessment_text
        for required in (
            "后续追加内容",
            "已完成事件保持不可变",
            "只读取这些相关事件的正式引用",
            "新事件",
            "不得仅因为事件位于同一项目",
        ):
            self.assertIn(required, assessment)

    def test_parallel_bug_chats_share_one_frozen_git_baseline(self):
        self.assertIn("### 跨 Bug 并行与持续 MR 集线", self.text)
        section_start = self.text.index("### 跨 Bug 并行与持续 MR 集线")
        section_end = self.text.index("### 阶段与 Skill 对应", section_start)
        section = self.text[section_start:section_end]

        for required in (
            "不同的 Codex 顶层会话和不同的 Git Worktree",
            "自己的 `change_id`、`workflow_id`、Spec、Plan、分支和 `code_ref`",
            "同一轮所有 Bug 的 `base_sha` 必须逐字相同",
            "不得把另一个 Bug Worktree 的目录状态或可变 HEAD 作为基线",
            "MR 实际源分支头的 40 位完整 SHA",
            "本轮开始后冻结集线分支",
            "跨 Bug 并行不得由 `subagent-driven-development` 的 Subagent 代替",
            "SDD 授权只覆盖当前 Bug 的 Plan",
        ):
            self.assertIn(required, section)

    def test_one_hub_chat_updates_the_same_open_mr(self):
        self.assertIn("### 跨 Bug 并行与持续 MR 集线", self.text)
        section_start = self.text.index("### 跨 Bug 并行与持续 MR 集线")
        section_end = self.text.index("### 阶段与 Skill 对应", section_start)
        section = self.text[section_start:section_end]

        for required in (
            "一个开放 MR 只由一个长期集线会话独占其源分支和 Worktree",
            "工作流已经完成的 Bug 分支",
            "git merge --no-ff",
            "每个 Bug `code_ref` 的 commit 都是集线头的祖先",
            "组合验证",
            "push 同一源分支",
            "不得新建重复 MR",
            "MR 已合并或关闭",
            "不新增 SQLite 表、字段、阶段或正式材料引用",
            "Superpowers 原生 Skill 保持只读",
        ):
            self.assertIn(required, section)


if __name__ == "__main__":
    unittest.main()
