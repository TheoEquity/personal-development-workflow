import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "change_ledger.py"


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.repo = self.root / "code-repo"
        self.vault.mkdir()
        self.repo.mkdir()
        (self.root / "AGENTS.md").write_text("workspace rules\n", encoding="utf-8")
        (self.repo / "tests").mkdir()
        (self.repo / "AGENTS.md").write_text("repository rules\n", encoding="utf-8")
        (self.repo / "tests/AGENTS.md").write_text("test rules\n", encoding="utf-8")
        (self.vault / ".local").mkdir()
        (self.vault / ".gitignore").write_text("/.local\n", encoding="utf-8")
        self._init_git(self.vault)
        self._init_git(self.repo)
        for directory in ("changes", "specs", "plans", "tests", "acceptance"):
            (self.vault / directory).mkdir()
        (self.vault / "acceptance/CE-0001").mkdir()
        (self.repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        self.code_sha = self._commit(self.repo, "code")
        self.agent_paths = (
            self.root / "AGENTS.md",
            self.repo / "AGENTS.md",
            self.repo / "tests/AGENTS.md",
        )
        self.agents_inventory = ";".join(
            f"{path}@{hashlib.sha256(path.read_bytes()).hexdigest()}"
            for path in self.agent_paths
        )
        (self.vault / "changes/CE-0001").mkdir()
        (self.vault / "changes/CE-0002").mkdir()
        (self.vault / "changes/CE-0001/change.md").write_text(
            "---\nchange_id: CE-0001\nstatus: in_progress\n---\n# CE-0001 变更事件\n",
            encoding="utf-8",
        )
        (self.vault / "changes/CE-0002/change.md").write_text(
            "---\nchange_id: CE-0002\nstatus: in_progress\n---\n# CE-0002 变更事件\n",
            encoding="utf-8",
        )
        (self.vault / "specs/CE-0001.md").write_text(
            "# Spec：批注同步\n\n"
            "## 功能目标\n\n- 保持批注同步。\n\n"
            "## 输入与触发条件\n\n- 用户创建批注。\n\n"
            "## 行为规则\n\n"
            "### 规则：唯一同步\n\n"
            "当：\n\n- 用户创建批注。\n\n"
            "系统必须：\n\n- 创建唯一映射。\n\n"
            "结果：\n\n- 只存在一个映射。\n\n"
            "## 输出与状态变化\n\n- 批注进入已同步状态。\n\n"
            "## 边界\n\n- 重试不得创建重复项。\n\n"
            "## 既有功能与流程影响\n\n"
            "| impact_id | 既有功能或流程 | 当前行为 | 与新需求的交点 | 影响结论 | Spec 处理 |\n"
            "|---|---|---|---|---|---|\n"
            "| I-001 | 批注唯一同步 | 同一批注只创建一个映射 | 新策略复用映射入口 | 保持不变 | 无需修改 |\n\n"
            "## 可能的影响范围（非行为契约）\n\n"
            f"- 代码基线：`code-repo@{self.code_sha}`\n\n"
            "| 可能影响对象 | 当前路径 | 可能的影响类型 | 判断依据 |\n"
            "|---|---|---|---|\n"
            "| 同步入口 | `app.py` | 需要核对 | 与唯一同步规则相关 |\n",
            encoding="utf-8",
        )
        (self.vault / "plans/CE-0001.md").write_text(
            "# Annotation Sync Implementation Plan\n\n"
            "> **For agentic workers:** Use the required execution skill.\n\n"
            "**Goal:** Implement unique annotation synchronization.\n\n"
            "**Architecture:** Keep identity validation at the synchronization boundary. "
            "Reuse the existing persistence seam.\n\n"
            "**Tech Stack:** Python, unittest\n\n"
            "## Global Constraints\n\n- Preserve stable annotation identity.\n\n"
            "## 实现兼容性分析\n\n"
            "| 来源影响项 | 现有代码或方法 | 新方案交点 | 技术影响 | 处理方式 | 对应任务 |\n"
            "|---|---|---|---|---|---|\n"
            "| I-001 | `app.py` synchronization boundary | New strategy shares the existing identity guard | 无影响 | Existing stable annotation ID remains the isolation key | 无需任务 |\n\n"
            "---\n\n"
            "### Task 1: Synchronization guard\n\n"
            "**Files:**\n- Modify: `app.py`\n- Test: `tests/test_app.py`\n\n"
            "**Interfaces:**\n- Consumes: annotation ID\n- Produces: unique mapping\n\n"
            "- [ ] **Step 1: Write the failing test**\n\n"
            "Run the focused unit test and confirm the duplicate mapping assertion fails.\n",
            encoding="utf-8",
        )
        (self.vault / "tests/CE-0001.md").write_text(
            "# 测试稿：同步\n\n"
            "## 测试流程\n\n"
            "### T-001 创建批注\n\n"
            "test_id: T-001\n\n"
            "操作：\n\n1. 创建批注。\n\n"
            "预期结果：\n\n- 批注已创建。\n\n"
            "### T-002 检查同步\n\n"
            "test_id: T-002\n\n"
            "操作：\n\n1. 检查同步。\n\n"
            "预期结果：\n\n- 同步完成且没有重复项。\n",
            encoding="utf-8",
        )
        self.vault_sha = self._commit(self.vault, "materials")
        self.test_ref = f"tests/CE-0001.md@{self.vault_sha}"
        self.db = self.vault / ".local" / "ledger.sqlite3"
        self.config = self.root / "config.json"
        self._write_config()
        self.cli("init")

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _init_git(path):
        subprocess.run(["git", "init", "-q", str(path)], check=True)
        subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True)

    @staticmethod
    def _commit(path, message):
        subprocess.run(["git", "-C", str(path), "add", "."], check=True)
        subprocess.run(["git", "-C", str(path), "commit", "-qm", message], check=True)
        return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()

    def _write_config(self, **overrides):
        payload = {
            "spec_vault": str(self.vault),
            "database": str(self.db),
            "repositories": {"code-repo": str(self.repo)},
        }
        payload.update(overrides)
        self.config.write_text(json.dumps(payload), encoding="utf-8")

    def cli(self, *args, code=0, config=None):
        command = [sys.executable, str(SCRIPT), "--config", str(config or self.config), *args]
        result = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(code, result.returncode, result.stderr)
        return result

    def test_runtime_commands_require_explicit_project_config(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "list"],
            text=True,
            capture_output=True,
        )

        self.assertEqual(2, result.returncode, result.stderr)
        self.assertIn("--config is required", result.stderr)

    def db_cli(self, db, *args, code=0):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--db", str(db), *args],
            text=True,
            capture_output=True,
        )
        self.assertEqual(code, result.returncode, result.stderr)
        return result

    def create_change(self, change_id="CE-0001"):
        self.cli(
            "create",
            "--change-id",
            change_id,
            "--change-ref",
            f"changes/{change_id}/change.md@{self.vault_sha}",
        )

    def set_code_ref(self, change_id="CE-0001", worktree=None):
        return self.cli(
            "set-code-ref",
            change_id,
            "--worktree",
            str(worktree or self.repo),
        )

    def _prepare_atomic_adoption(
        self,
        *,
        plan_ref=None,
        spec_ref=None,
    ):
        self.create_change()
        refs = {
            "spec_ref": spec_ref or f"specs/CE-0001.md@{self.vault_sha}",
            "plan_ref": plan_ref or f"plans/CE-0001.md@{self.vault_sha}",
            "test_ref": self.test_ref,
        }
        for field in ("spec_ref", "test_ref"):
            self.cli(
                "set-ref",
                "CE-0001",
                "--field",
                field,
                "--value",
                refs[field],
            )
        self.cli("workflow-create", "--change-id", "CE-0001", "--stage", "writing_spec")
        self.cli("workflow-set-stage", "WF-0001", "--stage", "writing_plan")
        registration_ref = json.loads(self.cli("show", "CE-0001").stdout)[
            "change_ref"
        ]
        return refs, registration_ref

    def _adopt_plan(self, plan_ref, _registration_ref=None, *, code=0):
        return self.cli(
            "adopt-plan",
            "CE-0001",
            "--workflow-id",
            "WF-0001",
            "--plan-ref",
            plan_ref,
            code=code,
        )

    def _commit_material(self, relative_path, text, message):
        (self.vault / relative_path).write_text(text, encoding="utf-8")
        status = subprocess.check_output(
            ["git", "-C", str(self.vault), "status", "--porcelain"],
            text=True,
        )
        sha = (
            self._commit(self.vault, message)
            if status.strip()
            else subprocess.check_output(
                ["git", "-C", str(self.vault), "rev-parse", "HEAD"],
                text=True,
            ).strip()
        )
        return f"{relative_path}@{sha}"

    def _enter_writing_plan_with_spec(self, spec_text, *, code=0):
        spec_ref = self._commit_material(
            "specs/CE-0001.md",
            spec_text,
            "spec impact contract variant",
        )
        self.create_change()
        self.cli("set-ref", "CE-0001", "--field", "spec_ref", "--value", spec_ref)
        self.cli("set-ref", "CE-0001", "--field", "test_ref", "--value", self.test_ref)
        self.cli("workflow-create", "--change-id", "CE-0001", "--stage", "writing_spec")
        return self.cli(
            "workflow-set-stage",
            "WF-0001",
            "--stage",
            "writing_plan",
            code=code,
        )

    def _adopt_plan_variant(self, plan_text, *, code=0, spec_ref=None):
        plan_ref = self._commit_material(
            "plans/CE-0001.md",
            plan_text,
            "plan compatibility contract variant",
        )
        refs, adoption_ref = self._prepare_atomic_adoption(
            plan_ref=plan_ref,
            spec_ref=spec_ref,
        )
        before_row = json.loads(self.cli("show", "CE-0001").stdout)
        before_workflow = json.loads(self.cli("workflow-show", "WF-0001").stdout)
        result = self._adopt_plan(plan_ref, adoption_ref, code=code)
        return result, before_row, before_workflow, refs

    def test_writing_plan_rejects_spec_without_existing_flow_impact_contract(self):
        spec = (self.vault / "specs/CE-0001.md").read_text(encoding="utf-8")
        start = spec.index("## 既有功能与流程影响")
        end = spec.index("## 可能的影响范围（非行为契约）")

        result = self._enter_writing_plan_with_spec(spec[:start] + spec[end:], code=2)

        self.assertIn("既有功能与流程影响", result.stderr)
        self.assertEqual(
            "writing_spec",
            json.loads(self.cli("workflow-show", "WF-0001").stdout)["current_stage"],
        )

    def test_writing_plan_accepts_canonical_no_existing_flow_impact_conclusion(self):
        spec = (self.vault / "specs/CE-0001.md").read_text(encoding="utf-8")
        start = spec.index("## 既有功能与流程影响")
        end = spec.index("## 可能的影响范围（非行为契约）")
        no_impact = (
            "## 既有功能与流程影响\n\n"
            "- 结论：未发现与本需求直接关联的既有功能或流程。\n\n"
        )

        self._enter_writing_plan_with_spec(spec[:start] + no_impact + spec[end:])

        self.assertEqual(
            "writing_plan",
            json.loads(self.cli("workflow-show", "WF-0001").stdout)["current_stage"],
        )

    def test_writing_plan_rejects_no_impact_conclusion_combined_with_table(self):
        spec = (self.vault / "specs/CE-0001.md").read_text(encoding="utf-8")
        spec = spec.replace(
            "\n## 可能的影响范围",
            "\n- 结论：未发现与本需求直接关联的既有功能或流程。\n\n"
            "## 可能的影响范围",
        )

        result = self._enter_writing_plan_with_spec(spec, code=2)

        self.assertIn("cannot combine", result.stderr)

    def test_writing_plan_rejects_misordered_existing_flow_impact_section(self):
        spec = (self.vault / "specs/CE-0001.md").read_text(encoding="utf-8")
        start = spec.index("## 既有功能与流程影响")
        end = spec.index("## 可能的影响范围（非行为契约）")
        impact_block = spec[start:end]
        spec = spec[:start] + spec[end:] + "\n" + impact_block

        result = self._enter_writing_plan_with_spec(spec, code=2)

        self.assertIn("canonical order", result.stderr)

    def test_spec_impact_section_cannot_mask_an_empty_boundary(self):
        spec = (self.vault / "specs/CE-0001.md").read_text(encoding="utf-8")
        spec = spec.replace(
            "## 边界\n\n- 重试不得创建重复项。\n\n",
            "## 边界\n\n",
        )

        result = self._enter_writing_plan_with_spec(spec, code=2)

        self.assertIn("spec ##", result.stderr)

    def test_writing_plan_rejects_invalid_spec_impact_ids_and_semantics(self):
        scenarios = (
            (
                "invalid-id",
                lambda text: text.replace("| I-001 |", "| impact-1 |"),
                "impact_id",
            ),
            (
                "duplicate-id",
                lambda text: text.replace(
                    "\n## 可能的影响范围",
                    "\n| I-001 | 批注重试 | 重试复用原映射 | 新策略改变重试入口 | 兼容扩展 | 已写入规则或边界 |\n\n## 可能的影响范围",
                ),
                "duplicate",
            ),
            (
                "unknown-conclusion",
                lambda text: text.replace(
                    "| 保持不变 | 无需修改 |", "| 待确认 | 无需修改 |"
                ),
                "invalid",
            ),
            (
                "unrecorded-change",
                lambda text: text.replace(
                    "| 保持不变 | 无需修改 |", "| 明确改变 | 无需修改 |"
                ),
                "must be",
            ),
        )
        for index, (label, transform, expected) in enumerate(scenarios):
            with self.subTest(label=label):
                if index:
                    self.tearDown()
                    self.setUp()
                base = (self.vault / "specs/CE-0001.md").read_text(encoding="utf-8")
                spec = transform(base)
                result = self._enter_writing_plan_with_spec(spec, code=2)
                self.assertIn(expected, result.stderr)

    def test_adopt_plan_rejects_missing_compatibility_analysis_atomically(self):
        plan = (self.vault / "plans/CE-0001.md").read_text(encoding="utf-8")
        start = plan.index("## 实现兼容性分析")
        end = plan.index("\n---\n", start) + 1

        _, before_row, before_workflow, _ = self._adopt_plan_variant(
            plan[:start] + plan[end:],
            code=2,
        )

        self.assertEqual(before_row, json.loads(self.cli("show", "CE-0001").stdout))
        self.assertEqual(
            before_workflow,
            json.loads(self.cli("workflow-show", "WF-0001").stdout),
        )

    def test_adopt_plan_rejects_compatibility_analysis_after_tasks(self):
        plan = (self.vault / "plans/CE-0001.md").read_text(encoding="utf-8")
        start = plan.index("## 实现兼容性分析")
        end = plan.index("\n---\n", start) + 1
        compatibility_block = plan[start:end]
        plan = plan[:start] + plan[end:] + "\n" + compatibility_block

        result, _, _, _ = self._adopt_plan_variant(plan, code=2)

        self.assertIn("must precede plan tasks", result.stderr)

    def test_compatibility_analysis_cannot_mask_empty_global_constraints(self):
        plan = (self.vault / "plans/CE-0001.md").read_text(encoding="utf-8")
        plan = plan.replace(
            "## Global Constraints\n\n- Preserve stable annotation identity.\n\n",
            "## Global Constraints\n\n",
        )

        result, _, _, _ = self._adopt_plan_variant(plan, code=2)

        self.assertIn("Global Constraints", result.stderr)

    def test_adopt_plan_rejects_missing_or_unknown_spec_impact_mapping(self):
        base = (self.vault / "plans/CE-0001.md").read_text(encoding="utf-8")
        scenarios = (
            (
                "missing",
                base.replace("| I-001 |", "| implementation-only |"),
                "I-001",
            ),
            (
                "unknown",
                base.replace(
                    "\n---\n\n### Task 1",
                    "\n| I-999 | `other.py` | Shares a global queue | 无影响 | Separate identity key proves isolation | 无需任务 |\n\n---\n\n### Task 1",
                ),
                "I-999",
            ),
        )
        for index, (label, plan, expected) in enumerate(scenarios):
            with self.subTest(label=label):
                if index:
                    self.tearDown()
                    self.setUp()
                result, before_row, before_workflow, _ = self._adopt_plan_variant(
                    plan,
                    code=2,
                )
                self.assertIn(expected, result.stderr)
                self.assertEqual(before_row, json.loads(self.cli("show", "CE-0001").stdout))
                self.assertEqual(
                    before_workflow,
                    json.loads(self.cli("workflow-show", "WF-0001").stdout),
                )

    def test_adopt_plan_rejects_blocked_or_unmapped_technical_work(self):
        base = (self.vault / "plans/CE-0001.md").read_text(encoding="utf-8")
        scenarios = (
            (
                "blocked",
                base.replace("| 无影响 |", "| 阻塞 |"),
                "阻塞",
            ),
            (
                "unknown-status",
                base.replace("| 无影响 |", "| 待确认 |"),
                "技术影响",
            ),
            (
                "adapt-no-task",
                base.replace("| 无影响 |", "| 需要适配 |").replace(
                    "| 无需任务 |", "| 无需任务 |"
                ),
                "Task N",
            ),
            (
                "migration-missing-task",
                base.replace("| 无影响 |", "| 需要迁移 |").replace(
                    "| 无需任务 |", "| Task 2 |"
                ),
                "Task 2",
            ),
            (
                "no-impact-has-task",
                base.replace("| 无需任务 |", "| Task 1 |"),
                "无需任务",
            ),
            (
                "empty-handling",
                base.replace(
                    "| Existing stable annotation ID remains the isolation key |",
                    "|  |",
                ),
                "concrete values",
            ),
        )
        for index, (label, plan, expected) in enumerate(scenarios):
            with self.subTest(label=label):
                if index:
                    self.tearDown()
                    self.setUp()
                result, _, _, _ = self._adopt_plan_variant(plan, code=2)
                self.assertIn(expected, result.stderr)

    def test_adopt_plan_rejects_explicit_behavior_change_without_technical_task(self):
        spec = (self.vault / "specs/CE-0001.md").read_text(encoding="utf-8")
        spec = spec.replace(
            "| 保持不变 | 无需修改 |",
            "| 明确改变 | 已写入规则或边界 |",
        )
        spec_ref = self._commit_material(
            "specs/CE-0001.md",
            spec,
            "explicit behavior change",
        )
        plan = (self.vault / "plans/CE-0001.md").read_text(encoding="utf-8")

        result, before_row, before_workflow, _ = self._adopt_plan_variant(
            plan,
            code=2,
            spec_ref=spec_ref,
        )

        self.assertIn("explicit behavior change", result.stderr)
        self.assertEqual(before_row, json.loads(self.cli("show", "CE-0001").stdout))
        self.assertEqual(
            before_workflow,
            json.loads(self.cli("workflow-show", "WF-0001").stdout),
        )

    def test_adopt_plan_accepts_explicit_behavior_change_with_adaptation_task(self):
        spec = (self.vault / "specs/CE-0001.md").read_text(encoding="utf-8")
        spec = spec.replace(
            "| 保持不变 | 无需修改 |",
            "| 明确改变 | 已写入规则或边界 |",
        )
        spec_ref = self._commit_material(
            "specs/CE-0001.md",
            spec,
            "explicit behavior change with task",
        )
        plan = (self.vault / "plans/CE-0001.md").read_text(encoding="utf-8")
        plan = plan.replace("| 无影响 |", "| 需要适配 |").replace(
            "| 无需任务 |", "| Task 1 |"
        )

        result, _, _, _ = self._adopt_plan_variant(plan, spec_ref=spec_ref)

        self.assertEqual("adopted", json.loads(result.stdout)["status"])

    def test_adopt_plan_rejects_duplicate_task_numbers_as_ambiguous_mapping(self):
        plan = (self.vault / "plans/CE-0001.md").read_text(encoding="utf-8")
        duplicate = (
            "\n### Task 1: Duplicate synchronization task\n\n"
            "**Files:**\n- Modify: `app.py`\n- Test: `tests/test_app.py`\n\n"
            "**Interfaces:**\n- Consumes: annotation ID\n- Produces: duplicate task output\n\n"
            "- [ ] **Step 1: Write another failing test**\n\n"
            "Run the focused unit test and confirm failure.\n"
        )

        result, _, _, _ = self._adopt_plan_variant(plan + duplicate, code=2)

        self.assertIn("duplicate Task", result.stderr)

    def test_adopt_plan_rejects_leading_zero_task_number(self):
        plan = (self.vault / "plans/CE-0001.md").read_text(encoding="utf-8")
        plan = plan.replace("### Task 1:", "### Task 01:").replace(
            "| 无需任务 |", "| Task 01 |"
        ).replace("| 无影响 |", "| 需要适配 |")

        result, _, _, _ = self._adopt_plan_variant(plan, code=2)

        self.assertIn("canonical decimal", result.stderr)

    def test_adopt_plan_accepts_complete_mapping_and_implementation_only_rows(self):
        plan = (self.vault / "plans/CE-0001.md").read_text(encoding="utf-8")
        plan = plan.replace(
            "\n---\n\n### Task 1",
            "\n"
            "| I-001 | `app.py` retry path | Retry enters the same guard | 需要适配 | Route retries through the stable identity guard | Task 1 |\n"
            "| implementation-only | `cache.py` | Cache is private to the new strategy | 无影响 | Repository inspection shows no shared key or call path | 无需任务 |\n\n"
            "---\n\n### Task 1",
        )

        result, _, _, refs = self._adopt_plan_variant(plan)

        self.assertEqual("adopted", json.loads(result.stdout)["status"])
        self.assertEqual(
            refs["plan_ref"],
            json.loads(self.cli("show", "CE-0001").stdout)["plan_ref"],
        )

    def test_adopt_plan_accepts_no_impact_spec_with_code_evidence(self):
        spec = (self.vault / "specs/CE-0001.md").read_text(encoding="utf-8")
        spec_start = spec.index("## 既有功能与流程影响")
        spec_end = spec.index("## 可能的影响范围（非行为契约）")
        spec = (
            spec[:spec_start]
            + "## 既有功能与流程影响\n\n"
            + "- 结论：未发现与本需求直接关联的既有功能或流程。\n\n"
            + spec[spec_end:]
        )
        spec_ref = self._commit_material(
            "specs/CE-0001.md",
            spec,
            "no existing flow impact",
        )
        plan = (self.vault / "plans/CE-0001.md").read_text(encoding="utf-8")
        plan_start = plan.index("## 实现兼容性分析")
        plan_end = plan.index("\n---\n", plan_start) + 1
        plan = (
            plan[:plan_start]
            + "## 实现兼容性分析\n\n"
            + f"- 无交点代码证据：code-repo@{self.code_sha} | `app.py` | "
            + "Read-only call-graph inspection found no shared method, state, or dependency.\n\n"
            + plan[plan_end:]
        )

        result, _, _, _ = self._adopt_plan_variant(plan, spec_ref=spec_ref)

        self.assertEqual("adopted", json.loads(result.stdout)["status"])

    def test_adopt_plan_rejects_vague_no_intersection_evidence(self):
        spec = (self.vault / "specs/CE-0001.md").read_text(encoding="utf-8")
        spec_start = spec.index("## 既有功能与流程影响")
        spec_end = spec.index("## 可能的影响范围（非行为契约）")
        spec = (
            spec[:spec_start]
            + "## 既有功能与流程影响\n\n"
            + "- 结论：未发现与本需求直接关联的既有功能或流程。\n\n"
            + spec[spec_end:]
        )
        spec_ref = self._commit_material(
            "specs/CE-0001.md",
            spec,
            "no impact with vague evidence",
        )
        plan = (self.vault / "plans/CE-0001.md").read_text(encoding="utf-8")
        plan_start = plan.index("## 实现兼容性分析")
        plan_end = plan.index("\n---\n", plan_start) + 1
        plan = (
            plan[:plan_start]
            + "## 实现兼容性分析\n\n"
            + "- 无交点代码证据：banana\n\n"
            + plan[plan_end:]
        )

        result, _, _, _ = self._adopt_plan_variant(
            plan,
            code=2,
            spec_ref=spec_ref,
        )

        self.assertIn("baseline | `path-or-symbol` | reason", result.stderr)

    def test_legacy_adopted_plan_can_continue_without_retroactive_impact_contract(self):
        spec = (self.vault / "specs/CE-0001.md").read_text(encoding="utf-8")
        spec_start = spec.index("## 既有功能与流程影响")
        spec_end = spec.index("## 可能的影响范围（非行为契约）")
        legacy_spec_ref = self._commit_material(
            "specs/CE-0001.md",
            spec[:spec_start] + spec[spec_end:],
            "legacy spec",
        )
        plan = (self.vault / "plans/CE-0001.md").read_text(encoding="utf-8")
        plan_start = plan.index("## 实现兼容性分析")
        plan_end = plan.index("\n---\n", plan_start) + 1
        legacy_plan_ref = self._commit_material(
            "plans/CE-0001.md",
            plan[:plan_start] + plan[plan_end:],
            "legacy plan",
        )
        self.create_change()
        self.cli(
            "set-ref",
            "CE-0001",
            "--field",
            "spec_ref",
            "--value",
            legacy_spec_ref,
        )
        self.cli("set-ref", "CE-0001", "--field", "test_ref", "--value", self.test_ref)
        self.cli("workflow-create", "--change-id", "CE-0001", "--stage", "writing_spec")
        refs = {
            "spec_ref": legacy_spec_ref,
            "plan_ref": legacy_plan_ref,
            "test_ref": self.test_ref,
        }
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute(
                "UPDATE change_ledger SET plan_ref=? WHERE change_id='CE-0001'",
                (legacy_plan_ref,),
            )
            connection.execute(
                "UPDATE workflow_state SET current_stage='tdd_coding' WHERE workflow_id='WF-0001'"
            )
            connection.commit()

        repeated = self._adopt_plan(legacy_plan_ref)
        self.assertEqual("adopted", json.loads(repeated.stdout)["status"])
        self.set_code_ref()
        self.cli("workflow-set-stage", "WF-0001", "--stage", "writing_test")
        self.cli("workflow-set-stage", "WF-0001", "--stage", "acceptance")
        evidence_ref, _ = self.report_ref()
        self.cli(
            "set-ref",
            "CE-0001",
            "--field",
            "evidence_ref",
            "--value",
            evidence_ref,
        )
        refs.update(
            {
                "code_ref": f"code-repo@{self.code_sha}",
                "evidence_ref": evidence_ref,
            }
        )
        final_ref = self._write_final_change(refs)

        self.assertEqual(
            "completed",
            json.loads(
                self.cli(
                    "complete",
                    "CE-0001",
                    "--change-ref",
                    final_ref,
                ).stdout
            )["status"],
        )

    def test_adopt_plan_requires_test_ref_even_for_legacy_writing_plan_state(self):
        self.create_change()
        refs = {
            "spec_ref": f"specs/CE-0001.md@{self.vault_sha}",
            "plan_ref": f"plans/CE-0001.md@{self.vault_sha}",
            "test_ref": self.test_ref,
        }
        self.cli(
            "set-ref",
            "CE-0001",
            "--field",
            "spec_ref",
            "--value",
            refs["spec_ref"],
        )
        self.cli("workflow-create", "--change-id", "CE-0001", "--stage", "writing_spec")
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute(
                "UPDATE workflow_state SET current_stage='writing_plan' WHERE workflow_id='WF-0001'"
            )
            connection.commit()
        result = self._adopt_plan(refs["plan_ref"], code=2)

        self.assertIn("test_ref", result.stderr)

    def _write_final_change(self, refs):
        final_change = (
            "---\n"
            "change_id: CE-0001\n"
            "status: completed\n"
            f"spec_ref: {refs['spec_ref']}\n"
            f"plan_ref: {refs['plan_ref']}\n"
            f"test_ref: {refs['test_ref']}\n"
            f"code_ref: {refs['code_ref']}\n"
            f"evidence_ref: {refs['evidence_ref']}\n"
            "---\n"
            "# CE-0001 变更事件\n\n"
            "## 最终结论\n\n- 已按最终材料完成。\n"
        )
        (self.vault / "changes/CE-0001/change.md").write_text(final_change, encoding="utf-8")
        final_sha = self._commit(self.vault, "final-change")
        return f"changes/CE-0001/change.md@{final_sha}"

    def report_ref(
        self,
        overall="passed",
        code_ref=None,
        statuses=("passed", "passed"),
        *,
        change_id="CE-0001",
        test_ref=None,
        complete_items=True,
        fenced=False,
        include_failure_handoff=True,
    ):
        code_ref = code_ref or f"code-repo@{self.code_sha}"
        test_ref = test_ref or self.test_ref
        human_overall = {
            "passed": "通过",
            "failed": "失败",
            "incomplete": "未完成",
        }.get(overall, "失败")
        lines = [
            "---",
            f"change_id: {change_id}",
            f"test_ref: {test_ref}",
            f"code_ref: {code_ref}",
            f"overall_status: {overall}",
            "---",
            "# 验收报告：同步",
            "",
            "## 测试项结果",
            "",
            f"- 总体结果：{human_overall}",
        ]
        if fenced:
            lines.append("```")
        for index, status in enumerate(statuses, 1):
            title = "创建批注" if index == 1 else "检查同步"
            lines += [f"### T-{index:03d} {title}", "", f"test_id: T-{index:03d}", f"status: {status}"]
            if complete_items:
                expected = "批注已创建。" if index == 1 else "同步完成且没有重复项。"
                lines += [
                    "",
                    "预期结果：",
                    "",
                    f"- {expected}",
                    "",
                    "实际结果：",
                    "",
                    f"- 已观察到：{expected}",
                    "",
                    "证据：",
                    "",
                    f"- 2026-08-17T12:00:0{index}Z | command | test-{index}",
                ]
        if fenced:
            lines.append("```")
        if overall == "failed" and include_failure_handoff and complete_items:
            lines += [
                "",
                "## 失败回传",
                "",
                "| test_id | 失败测试项 | 预期结果 | 实际结果 | 错误摘要 | 证据与日志 |",
                "|---|---|---|---|---|---|",
            ]
            for index, status in enumerate(statuses, 1):
                if status != "failed":
                    continue
                title = "创建批注" if index == 1 else "检查同步"
                expected = "批注已创建。" if index == 1 else "同步完成且没有重复项。"
                actual = f"已观察到：{expected}"
                evidence = f"2026-08-17T12:00:0{index}Z | command | test-{index}"
                cells = (
                    f"T-{index:03d}",
                    title,
                    expected,
                    actual,
                    "观察结果不符合验收目标",
                    evidence,
                )
                escaped = tuple(cell.replace("|", r"\|") for cell in cells)
                lines.append(
                    "| " + " | ".join(escaped) + " |"
                )
        (self.vault / "acceptance/CE-0001/report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        sha = self._commit(self.vault, f"report-{overall}-{'-'.join(statuses)}")
        return f"acceptance/CE-0001/report.md@{sha}", sha

    def set_completion_refs(
        self,
        evidence_ref=None,
        material_sha=None,
        *,
        spec_ref=None,
        plan_ref=None,
    ):
        if evidence_ref is None:
            evidence_ref, material_sha = self.report_ref()
        material_sha = material_sha or evidence_ref.rsplit("@", 1)[1]
        refs = {
            "spec_ref": spec_ref or f"specs/CE-0001.md@{self.vault_sha}",
            "plan_ref": plan_ref or f"plans/CE-0001.md@{self.vault_sha}",
            "test_ref": self.test_ref,
            "code_ref": f"code-repo@{self.code_sha}",
            "evidence_ref": evidence_ref,
        }
        for field in ("spec_ref", "plan_ref", "test_ref"):
            value = refs[field]
            self.cli("set-ref", "CE-0001", "--field", field, "--value", value)
        self.set_code_ref()
        self.cli(
            "set-ref",
            "CE-0001",
            "--field",
            "evidence_ref",
            "--value",
            refs["evidence_ref"],
        )
        refs["change_ref"] = self._write_final_change(refs)
        return refs

    def set_evidence_prerequisites(self):
        self.cli(
            "set-ref", "CE-0001", "--field", "test_ref", "--value", self.test_ref
        )
        self.set_code_ref()

    def set_completion_refs_with_workflow(self):
        self.create_change()
        refs = {
            "spec_ref": f"specs/CE-0001.md@{self.vault_sha}",
            "plan_ref": f"plans/CE-0001.md@{self.vault_sha}",
            "test_ref": self.test_ref,
            "code_ref": f"code-repo@{self.code_sha}",
        }
        self.cli(
            "set-ref", "CE-0001", "--field", "spec_ref", "--value", refs["spec_ref"]
        )
        self.cli(
            "set-ref", "CE-0001", "--field", "test_ref", "--value", refs["test_ref"]
        )
        self.cli("workflow-create", "--change-id", "CE-0001", "--stage", "writing_spec")
        self.cli("workflow-set-stage", "WF-0001", "--stage", "writing_plan")
        self._adopt_plan(refs["plan_ref"])
        self.set_code_ref()
        self.cli("workflow-set-stage", "WF-0001", "--stage", "acceptance")
        evidence_ref, _ = self.report_ref()
        refs["evidence_ref"] = evidence_ref
        self.cli(
            "set-ref", "CE-0001", "--field", "evidence_ref", "--value", evidence_ref
        )
        refs["change_ref"] = self._write_final_change(refs)
        return refs

    def test_complete_accepts_real_reproducible_refs(self):
        self.create_change()
        refs = self.set_completion_refs()
        self.assertEqual(
            "completed",
            json.loads(
                self.cli(
                    "complete", "CE-0001", "--change-ref", refs["change_ref"]
                ).stdout
            )["status"],
        )
        self.assertEqual("completed", json.loads(self.cli("complete", "CE-0001").stdout)["status"])

    def test_complete_requires_bound_active_workflow_to_be_at_acceptance(self):
        refs = self.set_completion_refs_with_workflow()
        self.cli("workflow-set-stage", "WF-0001", "--stage", "writing_spec")
        self.cli(
            "complete", "CE-0001", "--change-ref", refs["change_ref"], code=2
        )
        self.assertEqual("in_progress", json.loads(self.cli("show", "CE-0001").stdout)["status"])

    def test_complete_allows_bound_active_workflow_at_acceptance(self):
        refs = self.set_completion_refs_with_workflow()
        self.cli("complete", "CE-0001", "--change-ref", refs["change_ref"])
        self.cli("workflow-close", "WF-0001")
        state = json.loads(self.cli("workflow-show", "WF-0001").stdout)
        self.assertEqual(("completed", "closed"), (state["current_stage"], state["state"]))

    def test_complete_rejects_semantic_shell_spec(self):
        (self.vault / "specs/CE-0001.md").write_text("# Spec：空壳\n", encoding="utf-8")
        shell_sha = self._commit(self.vault, "shell-spec")
        self.create_change()
        refs = self.set_completion_refs(spec_ref=f"specs/CE-0001.md@{shell_sha}")
        self.cli("complete", "CE-0001", "--change-ref", refs["change_ref"], code=2)

    def test_complete_rejects_semantic_shell_plan(self):
        (self.vault / "plans/CE-0001.md").write_text(
            "# Empty Implementation Plan\n", encoding="utf-8"
        )
        shell_sha = self._commit(self.vault, "shell-plan")
        self.create_change()
        refs = self.set_completion_refs(plan_ref=f"plans/CE-0001.md@{shell_sha}")
        self.cli("complete", "CE-0001", "--change-ref", refs["change_ref"], code=2)

    def test_complete_rejects_plan_that_bypasses_spec_compatibility_contract(self):
        plan = (self.vault / "plans/CE-0001.md").read_text(encoding="utf-8")
        start = plan.index("## 实现兼容性分析")
        end = plan.index("\n---\n", start) + 1
        (self.vault / "plans/CE-0001.md").write_text(
            plan[:start] + plan[end:],
            encoding="utf-8",
        )
        bypass_sha = self._commit(self.vault, "plan without compatibility contract")
        self.create_change()
        refs = self.set_completion_refs(
            plan_ref=f"plans/CE-0001.md@{bypass_sha}"
        )

        result = self.cli(
            "complete",
            "CE-0001",
            "--change-ref",
            refs["change_ref"],
            code=2,
        )

        self.assertIn("实现兼容性分析", result.stderr)

    def test_complete_rejects_plan_file_path_escape(self):
        plan = (self.vault / "plans/CE-0001.md").read_text(encoding="utf-8")
        (self.vault / "plans/CE-0001.md").write_text(
            plan.replace("- Modify: `app.py`", "- Modify: `../escape.py`"),
            encoding="utf-8",
        )
        escape_sha = self._commit(self.vault, "escaping-plan")
        self.create_change()
        refs = self.set_completion_refs(plan_ref=f"plans/CE-0001.md@{escape_sha}")
        self.cli("complete", "CE-0001", "--change-ref", refs["change_ref"], code=2)

    def test_complete_does_not_require_an_intermediate_adoption_change_commit(self):
        self.create_change()
        refs = self.set_completion_refs()
        self.cli("complete", "CE-0001", "--change-ref", refs["change_ref"])

    def test_complete_rechecks_injected_fake_shas_and_stays_open(self):
        self.create_change()
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute(
                "UPDATE change_ledger SET change_ref=?,spec_ref=?,plan_ref=?,test_ref=?,code_ref=?,evidence_ref=? WHERE change_id='CE-0001'",
                ("changes/CE-0001.md@abcdef0", "specs/CE-0001.md@abcdef1", "plans/CE-0001.md@abcdef2", "tests/CE-0001.md@abcdef3", "code-repo@abcdef4", "acceptance/CE-0001/report.md@abcdef5"),
            )
            connection.commit()
        self.cli(
            "complete",
            "CE-0001",
            "--change-ref",
            f"changes/CE-0001/change.md@{self.vault_sha}",
            code=2,
        )
        self.assertEqual("in_progress", json.loads(self.cli("show", "CE-0001").stdout)["status"])

    def test_vault_commit_without_path_is_rejected(self):
        self.create_change()
        self.cli("set-ref", "CE-0001", "--field", "spec_ref", "--value", f"specs/missing.md@{self.vault_sha}", code=2)

    def test_abbreviated_commit_sha_is_rejected_even_when_git_resolves_it(self):
        self.create_change()
        self.cli(
            "set-ref",
            "CE-0001",
            "--field",
            "spec_ref",
            "--value",
            f"specs/CE-0001.md@{self.vault_sha[:7]}",
            code=2,
        )

    def test_vault_reference_role_is_validated_by_field(self):
        self.create_change()
        self.cli(
            "set-ref",
            "CE-0001",
            "--field",
            "spec_ref",
            "--value",
            f"plans/CE-0001.md@{self.vault_sha}",
            code=2,
        )

    def test_failed_evidence_is_rejected(self):
        self.create_change()
        ref, sha = self.report_ref(overall="failed", statuses=("failed", "passed"))
        refs = self.set_completion_refs(ref, sha)
        self.cli("complete", "CE-0001", "--change-ref", refs["change_ref"], code=2)

    def test_not_executed_evidence_is_rejected(self):
        self.create_change()
        ref, sha = self.report_ref(
            overall="incomplete", statuses=("passed", "not_executed")
        )
        refs = self.set_completion_refs(ref, sha)
        self.cli("complete", "CE-0001", "--change-ref", refs["change_ref"], code=2)

    def test_evidence_code_ref_must_match_exactly(self):
        self.create_change()
        ref, _ = self.report_ref(code_ref="code-repo@abcdef1")
        self.set_evidence_prerequisites()
        self.cli("set-ref", "CE-0001", "--field", "evidence_ref", "--value", ref, code=2)

    def test_evidence_requires_at_least_one_test_result(self):
        self.create_change()
        ref, _ = self.report_ref(statuses=())
        self.set_evidence_prerequisites()
        self.cli("set-ref", "CE-0001", "--field", "evidence_ref", "--value", ref, code=2)

    def test_evidence_frontmatter_must_bind_change_and_exact_test_ref(self):
        self.create_change()
        other_test_ref = f"tests/CE-0001.md@{self.vault_sha[:7]}"
        ref, _ = self.report_ref(test_ref=other_test_ref)
        self.set_evidence_prerequisites()
        self.cli("set-ref", "CE-0001", "--field", "evidence_ref", "--value", ref, code=2)

    def test_empty_shell_evidence_is_rejected(self):
        self.create_change()
        ref, _ = self.report_ref(complete_items=False)
        self.set_evidence_prerequisites()
        self.cli("set-ref", "CE-0001", "--field", "evidence_ref", "--value", ref, code=2)

    def test_noncanonical_status_and_test_id_are_rejected(self):
        self.create_change()
        ref, _ = self.report_ref(statuses=("通过", "passed"))
        self.set_evidence_prerequisites()
        self.cli("set-ref", "CE-0001", "--field", "evidence_ref", "--value", ref, code=2)

        (self.vault / "tests/CE-0001.md").write_text(
            "### T1 非规范编号\n\ntest_id: T1\n\n预期结果：\n\n- 有结果。\n",
            encoding="utf-8",
        )
        bad_test_sha = self._commit(self.vault, "noncanonical-test-id")
        self.create_change("CE-0002")
        self.cli(
            "set-ref",
            "CE-0002",
            "--field",
            "test_ref",
            "--value",
            f"tests/CE-0001.md@{bad_test_sha}",
            code=2,
        )

    def test_code_fence_fields_do_not_count_as_report_items(self):
        self.create_change()
        ref, sha = self.report_ref(fenced=True)
        refs = {
            "test_ref": self.test_ref,
            "code_ref": f"code-repo@{self.code_sha}",
        }
        self.cli(
            "set-ref", "CE-0001", "--field", "test_ref", "--value", refs["test_ref"]
        )
        self.set_code_ref()
        self.cli("set-ref", "CE-0001", "--field", "evidence_ref", "--value", ref, code=2)

    def test_set_ref_evidence_uses_single_validator_and_returns_normalized_result(self):
        self.create_change()
        self.cli(
            "set-ref", "CE-0001", "--field", "test_ref", "--value", self.test_ref
        )
        self.set_code_ref()

        failed_ref, _ = self.report_ref(
            overall="failed", statuses=("failed", "passed")
        )
        payload = json.loads(
            self.cli(
                "set-ref",
                "CE-0001",
                "--field",
                "evidence_ref",
                "--value",
                failed_ref,
            ).stdout
        )
        self.assertEqual("failed", payload["report_validation"]["overall_status"])
        self.assertTrue(payload["report_validation"]["failure_handoff_valid"])
        self.assertEqual(["T-001"], payload["report_validation"]["failed_test_ids"])

        incomplete_ref, _ = self.report_ref(
            overall="incomplete", statuses=("passed", "not_executed")
        )
        payload = json.loads(
            self.cli(
                "set-ref",
                "CE-0001",
                "--field",
                "evidence_ref",
                "--value",
                incomplete_ref,
            ).stdout
        )
        self.assertEqual("incomplete", payload["report_validation"]["overall_status"])
        self.assertEqual(["T-002"], payload["report_validation"]["not_executed_ids"])

    def test_set_ref_evidence_rejects_stale_or_invalid_report_before_write(self):
        self.create_change()
        self.cli(
            "set-ref", "CE-0001", "--field", "test_ref", "--value", self.test_ref
        )
        self.set_code_ref()

        stale_ref, _ = self.report_ref(test_ref=f"tests/CE-0001.md@{'a' * 40}")
        self.cli(
            "set-ref", "CE-0001", "--field", "evidence_ref", "--value", stale_ref, code=2
        )
        self.assertIsNone(json.loads(self.cli("show", "CE-0001").stdout)["evidence_ref"])

        invalid_ref, _ = self.report_ref(
            overall="failed",
            statuses=("failed", "passed"),
            include_failure_handoff=False,
        )
        self.cli(
            "set-ref", "CE-0001", "--field", "evidence_ref", "--value", invalid_ref, code=2
        )
        self.assertIsNone(json.loads(self.cli("show", "CE-0001").stdout)["evidence_ref"])

    def test_final_change_document_must_match_ledger(self):
        self.create_change()
        ref, sha = self.report_ref()
        self.set_completion_refs(ref, sha)
        final_path = self.vault / "changes/CE-0001/change.md"
        final_path.write_text(final_path.read_text(encoding="utf-8").replace("status: completed", "status: in_progress"), encoding="utf-8")
        bad_sha = self._commit(self.vault, "wrong-final-status")
        self.cli(
            "complete",
            "CE-0001",
            "--change-ref",
            f"changes/CE-0001/change.md@{bad_sha}",
            code=2,
        )

    def test_stage_binding_invariants_and_atomic_bind(self):
        self.cli("workflow-create")
        self.cli("workflow-set-stage", "WF-0001", "--stage", "tdd_coding", code=2)
        self.create_change()
        self.cli("workflow-bind-change", "WF-0001", "CE-0001")
        state = json.loads(self.cli("workflow-show", "WF-0001").stdout)
        self.assertEqual(("CE-0001", "writing_spec"), (state["change_id"], state["current_stage"]))
        self.cli("workflow-set-stage", "WF-0001", "--stage", "requirement_discussion", code=2)

    def test_forward_workflow_stages_require_target_materials_but_rollback_does_not(self):
        self.create_change()
        self.cli("workflow-create", "--change-id", "CE-0001", "--stage", "writing_spec")
        self.cli("workflow-set-stage", "WF-0001", "--stage", "writing_plan", code=2)
        self.cli("set-ref", "CE-0001", "--field", "spec_ref", "--value", f"specs/CE-0001.md@{self.vault_sha}")
        self.cli("workflow-set-stage", "WF-0001", "--stage", "writing_plan", code=2)
        self.cli("set-ref", "CE-0001", "--field", "test_ref", "--value", self.test_ref)
        self.cli("workflow-set-stage", "WF-0001", "--stage", "writing_plan")
        self.cli("workflow-set-stage", "WF-0001", "--stage", "acceptance", code=2)
        self.cli("workflow-set-stage", "WF-0001", "--stage", "writing_spec")

    def test_entering_tdd_coding_requires_atomic_plan_adoption(self):
        self.create_change()
        self.cli("set-ref", "CE-0001", "--field", "spec_ref", "--value", f"specs/CE-0001.md@{self.vault_sha}")
        self.cli("set-ref", "CE-0001", "--field", "plan_ref", "--value", f"plans/CE-0001.md@{self.vault_sha}")
        self.cli("set-ref", "CE-0001", "--field", "test_ref", "--value", self.test_ref)
        self.cli("workflow-create", "--change-id", "CE-0001", "--stage", "writing_spec")
        self.cli("workflow-set-stage", "WF-0001", "--stage", "writing_plan")
        self.cli("workflow-set-stage", "WF-0001", "--stage", "tdd_coding", code=2)

    def test_workflow_set_stage_cannot_replace_atomic_adopt_plan(self):
        self.create_change()
        refs = {
            "spec_ref": f"specs/CE-0001.md@{self.vault_sha}",
            "plan_ref": f"plans/CE-0001.md@{self.vault_sha}",
            "test_ref": self.test_ref,
        }
        for field, value in refs.items():
            self.cli("set-ref", "CE-0001", "--field", field, "--value", value)
        self.cli("workflow-create", "--change-id", "CE-0001", "--stage", "writing_spec")
        self.cli("workflow-set-stage", "WF-0001", "--stage", "writing_plan")
        self.cli("workflow-set-stage", "WF-0001", "--stage", "tdd_coding", code=2)
        self.assertEqual(
            "writing_plan",
            json.loads(self.cli("workflow-show", "WF-0001").stdout)["current_stage"],
        )

    def test_workflow_cannot_skip_over_atomic_plan_adoption(self):
        self.create_change()
        refs = {
            "spec_ref": f"specs/CE-0001.md@{self.vault_sha}",
            "plan_ref": f"plans/CE-0001.md@{self.vault_sha}",
            "test_ref": self.test_ref,
        }
        for field, value in refs.items():
            self.cli("set-ref", "CE-0001", "--field", field, "--value", value)
        self.set_code_ref()
        self.cli("workflow-create", "--change-id", "CE-0001", "--stage", "writing_spec")
        self.cli("workflow-set-stage", "WF-0001", "--stage", "writing_plan")
        for stage in ("writing_test", "acceptance"):
            with self.subTest(stage=stage):
                self.cli("workflow-set-stage", "WF-0001", "--stage", stage, code=2)
                self.assertEqual(
                    "writing_plan",
                    json.loads(self.cli("workflow-show", "WF-0001").stdout)["current_stage"],
                )

    def test_bound_workflow_create_starts_at_writing_spec_only(self):
        self.create_change()
        refs = {
            "spec_ref": f"specs/CE-0001.md@{self.vault_sha}",
            "plan_ref": f"plans/CE-0001.md@{self.vault_sha}",
            "test_ref": self.test_ref,
        }
        for field, value in refs.items():
            self.cli("set-ref", "CE-0001", "--field", field, "--value", value)
        self.cli("workflow-create", "--change-id", "CE-0001", "--stage", "tdd_coding", code=2)

    def test_plan_adoption_contract_is_machine_readable_without_runtime_config(self):
        missing_config = self.root / "does-not-exist.json"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--config",
                str(missing_config),
                "plan-adoption-contract",
            ],
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        contract = json.loads(result.stdout)
        self.assertEqual((3, "adopt-plan"), (contract["contract_version"], contract["command"]))
        self.assertNotIn("proof", contract)
        self.assertNotIn("adoption_change_ref", contract["arguments"])
        self.assertEqual(
            ["change_ledger.plan_ref", "workflow_state.current_stage"],
            contract["atomic_writes"],
        )
        self.assertIn(
            "spec_ref contains a valid existing-flow impact contract",
            contract["preconditions"],
        )
        self.assertIn(
            "candidate plan covers all Spec impact_id values with no blocking rows",
            contract["preconditions"],
        )
        self.assertIn(
            "explicit Spec behavior changes map to adaptation or migration tasks",
            contract["preconditions"],
        )

    def test_adopt_plan_atomically_persists_refs_and_enters_tdd(self):
        refs, registration_ref = self._prepare_atomic_adoption()
        payload = json.loads(self._adopt_plan(refs["plan_ref"]).stdout)
        self.assertEqual("adopted", payload["status"])
        row = json.loads(self.cli("show", "CE-0001").stdout)
        workflow = json.loads(self.cli("workflow-show", "WF-0001").stdout)
        self.assertEqual((refs["plan_ref"], registration_ref), (row["plan_ref"], row["change_ref"]))
        self.assertEqual("tdd_coding", workflow["current_stage"])

    def test_active_writing_plan_rejects_split_plan_and_change_ref_writes(self):
        refs, registration_ref = self._prepare_atomic_adoption()
        before = json.loads(self.cli("show", "CE-0001").stdout)
        self.cli(
            "set-ref",
            "CE-0001",
            "--field",
            "plan_ref",
            "--value",
            refs["plan_ref"],
            code=2,
        )
        self.cli(
            "set-ref",
            "CE-0001",
            "--field",
            "change_ref",
            "--value",
            registration_ref,
            code=2,
        )
        self.assertEqual(before, json.loads(self.cli("show", "CE-0001").stdout))
        self._adopt_plan(refs["plan_ref"])

    def test_adopted_plan_cannot_be_replaced_by_direct_set_ref_even_after_rollback(self):
        refs, adoption_ref = self._prepare_atomic_adoption()
        self._adopt_plan(refs["plan_ref"], adoption_ref)
        plan = (self.vault / "plans/CE-0001.md").read_text(encoding="utf-8")
        (self.vault / "plans/CE-0001.md").write_text(
            plan.replace("Implement unique annotation synchronization.", "Implement revised synchronization."),
            encoding="utf-8",
        )
        plan_b_sha = self._commit(self.vault, "plan-b")
        plan_b_ref = f"plans/CE-0001.md@{plan_b_sha}"
        self.cli("set-ref", "CE-0001", "--field", "plan_ref", "--value", plan_b_ref, code=2)
        self.assertEqual(refs["plan_ref"], json.loads(self.cli("show", "CE-0001").stdout)["plan_ref"])
        self.cli("workflow-set-stage", "WF-0001", "--stage", "writing_plan")
        self.cli("set-ref", "CE-0001", "--field", "plan_ref", "--value", plan_b_ref, code=2)
        self.assertEqual(
            refs["plan_ref"],
            json.loads(self.cli("show", "CE-0001").stdout)["plan_ref"],
        )

    def test_adopted_spec_cannot_be_replaced_by_direct_set_ref_until_writing_spec(self):
        refs, adoption_ref = self._prepare_atomic_adoption()
        self._adopt_plan(refs["plan_ref"], adoption_ref)
        spec = (self.vault / "specs/CE-0001.md").read_text(encoding="utf-8")
        (self.vault / "specs/CE-0001.md").write_text(
            spec.replace("保持批注同步。", "保持批注双向同步。"),
            encoding="utf-8",
        )
        spec_b_sha = self._commit(self.vault, "spec-b")
        spec_b_ref = f"specs/CE-0001.md@{spec_b_sha}"
        self.cli("set-ref", "CE-0001", "--field", "spec_ref", "--value", spec_b_ref, code=2)
        self.assertEqual(refs["spec_ref"], json.loads(self.cli("show", "CE-0001").stdout)["spec_ref"])
        self.cli("workflow-set-stage", "WF-0001", "--stage", "writing_spec")
        self.cli("set-ref", "CE-0001", "--field", "spec_ref", "--value", spec_b_ref)

    def test_duplicate_concurrent_adopt_plan_calls_are_idempotent(self):
        refs, adoption_ref = self._prepare_atomic_adoption()
        command = [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(self.config),
            "adopt-plan",
            "CE-0001",
            "--workflow-id",
            "WF-0001",
            "--plan-ref",
            refs["plan_ref"],
        ]
        processes = [
            subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for _ in range(2)
        ]
        results = [process.communicate() + (process.returncode,) for process in processes]
        self.assertEqual([0, 0], sorted(result[2] for result in results), results)
        self.assertEqual("tdd_coding", json.loads(self.cli("workflow-show", "WF-0001").stdout)["current_stage"])

    def test_two_concurrent_binds_cannot_rebind(self):
        self.cli("workflow-create")
        self.create_change("CE-0001")
        self.create_change("CE-0002")
        base = [sys.executable, str(SCRIPT), "--config", str(self.config), "workflow-bind-change", "WF-0001"]
        processes = [subprocess.Popen([*base, cid], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for cid in ("CE-0001", "CE-0002")]
        results = [process.communicate() + (process.returncode,) for process in processes]
        self.assertEqual([0, 2], sorted(result[2] for result in results))
        self.assertIn(json.loads(self.cli("workflow-show", "WF-0001").stdout)["change_id"], ("CE-0001", "CE-0002"))

    def test_set_ref_and_complete_race_cannot_modify_completed_row(self):
        self.create_change()
        refs = self.set_completion_refs()
        base = [sys.executable, str(SCRIPT), "--config", str(self.config)]
        commands = [[*base, "complete", "CE-0001", "--change-ref", refs["change_ref"]], [*base, "set-ref", "CE-0001", "--field", "spec_ref", "--value", f"specs/CE-0001.md@{self.vault_sha}"]]
        processes = [subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for command in commands]
        results = [process.communicate() + (process.returncode,) for process in processes]
        self.assertIn(0, [result[2] for result in results])
        self.assertEqual("completed", json.loads(self.cli("show", "CE-0001").stdout)["status"])
        self.cli("set-ref", "CE-0001", "--field", "spec_ref", "--value", f"specs/CE-0001.md@{self.vault_sha}", code=2)

    def test_set_stage_and_close_race_leaves_closed_completed(self):
        refs = self.set_completion_refs_with_workflow()
        self.cli("complete", "CE-0001", "--change-ref", refs["change_ref"])
        base = [sys.executable, str(SCRIPT), "--config", str(self.config)]
        commands = [[*base, "workflow-close", "WF-0001"], [*base, "workflow-set-stage", "WF-0001", "--stage", "writing_spec"]]
        processes = [subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for command in commands]
        for process in processes:
            process.communicate()
        state = json.loads(self.cli("workflow-show", "WF-0001").stdout)
        self.assertEqual(("completed", "closed"), (state["current_stage"], state["state"]))

    def test_config_requires_spec_vault(self):
        bad = self.root / "missing-vault.json"
        bad.write_text(json.dumps({"database": str(self.db)}), encoding="utf-8")
        self.cli("init", config=bad, code=2)

    def test_database_must_be_inside_vault_local(self):
        bad = self.root / "outside.json"
        bad.write_text(json.dumps({"spec_vault": str(self.vault), "database": str(self.root / "outside.sqlite")}), encoding="utf-8")
        self.cli("init", config=bad, code=2)

    def test_init_rejects_unignored_local(self):
        (self.vault / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
        self.cli("init", code=2)

    def test_config_rejects_placeholder_and_tracked_local(self):
        placeholder = self.root / "placeholder.json"
        placeholder.write_text(json.dumps({"spec_vault": "<spec-vault>", "database": str(self.db)}), encoding="utf-8")
        self.cli("init", config=placeholder, code=2)
        tracked = self.vault / ".local/tracked.txt"
        tracked.write_text("must not be tracked", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.vault), "add", "-f", ".local/tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(self.vault), "commit", "-qm", "track-local"], check=True)
        self.cli("init", code=2)

    def test_db_override_must_be_absolute(self):
        self.db_cli(Path("relative.sqlite"), "init", code=2)

    def test_read_missing_database_does_not_create_it(self):
        missing = self.root / "missing.sqlite"
        self.db_cli(missing, "list", code=2)
        self.assertFalse(missing.exists())

    def _legacy_db(self, *, both_refs=False, plan="P", implementation="P", stage="writing_implementation", change_id="CE-0001"):
        path = self.root / f"legacy-{len(list(self.root.glob('legacy-*.sqlite')))}.sqlite"
        connection = sqlite3.connect(path)
        plan_column = ", plan_ref TEXT" if both_refs else ""
        connection.execute(f"CREATE TABLE change_ledger(change_id TEXT PRIMARY KEY,spec_ref TEXT,change_ref TEXT NOT NULL{plan_column},implementation_ref TEXT,test_ref TEXT,code_ref TEXT,evidence_ref TEXT,status TEXT NOT NULL)")
        columns = "change_id,spec_ref,change_ref," + ("plan_ref," if both_refs else "") + "implementation_ref,test_ref,code_ref,evidence_ref,status"
        values = [change_id, None, "changes/x.md@abcdef1"] + ([plan] if both_refs else []) + [implementation, None, None, None, "in_progress"]
        connection.execute(f"INSERT INTO change_ledger({columns}) VALUES ({','.join('?' for _ in values)})", values)
        connection.execute("CREATE TABLE workflow_state(workflow_id TEXT PRIMARY KEY,change_id TEXT,current_stage TEXT NOT NULL,state TEXT NOT NULL)")
        connection.execute("INSERT INTO workflow_state VALUES('WF-0001',?,?, 'active')", (change_id, stage))
        connection.commit()
        connection.close()
        return path

    def test_migration_conflicting_plan_refs_rolls_back(self):
        legacy = self._legacy_db(both_refs=True, plan="A", implementation="B")
        self.db_cli(legacy, "init", code=2)
        with closing(sqlite3.connect(legacy)) as connection:
            self.assertEqual(("A", "B"), connection.execute("SELECT plan_ref,implementation_ref FROM change_ledger").fetchone())

    def test_migration_same_or_single_plan_ref_is_lossless(self):
        for both, plan, implementation in ((False, "P", "P"), (True, "P", "P"), (True, "P", None), (True, None, "P")):
            with self.subTest(both=both, plan=plan, implementation=implementation):
                legacy = self._legacy_db(both_refs=both, plan=plan, implementation=implementation)
                self.db_cli(legacy, "init")
                with closing(sqlite3.connect(legacy)) as connection:
                    self.assertEqual("P", connection.execute("SELECT plan_ref FROM change_ledger").fetchone()[0])
                    self.assertNotIn("implementation_ref", [row[1] for row in connection.execute("PRAGMA table_info(change_ledger)")])

    def test_migration_rebuilds_canonical_checks_and_foreign_key(self):
        legacy = self._legacy_db()
        self.db_cli(legacy, "init")
        with closing(sqlite3.connect(legacy)) as connection:
            ledger_sql = connection.execute("SELECT sql FROM sqlite_master WHERE name='change_ledger'").fetchone()[0]
            workflow_sql = connection.execute("SELECT sql FROM sqlite_master WHERE name='workflow_state'").fetchone()[0]
            self.assertIn("CHECK", ledger_sql.upper())
            self.assertIn("CHECK", workflow_sql.upper())
            self.assertTrue(list(connection.execute("PRAGMA foreign_key_list(workflow_state)")))
            self.assertEqual("writing_plan", connection.execute("SELECT current_stage FROM workflow_state").fetchone()[0])

    def test_migration_rejects_unknown_stage_or_orphan_or_duplicate_active(self):
        unknown = self._legacy_db(stage="mystery")
        self.assertIn("unknown stage", self.db_cli(unknown, "init", code=2).stderr.lower())
        orphan = self._legacy_db(change_id="CE-9999")
        with closing(sqlite3.connect(orphan)) as connection:
            connection.execute("UPDATE workflow_state SET change_id='CE-missing'")
            connection.commit()
        self.assertIn("orphan", self.db_cli(orphan, "init", code=2).stderr.lower())
        duplicate = self._legacy_db()
        with closing(sqlite3.connect(duplicate)) as connection:
            connection.execute("INSERT INTO workflow_state VALUES('WF-0002','CE-0001','writing_plan','active')")
            connection.commit()
        self.assertIn("duplicate active", self.db_cli(duplicate, "init", code=2).stderr.lower())

    def test_migration_rejects_completed_rows_with_missing_references(self):
        legacy = self._legacy_db()
        with closing(sqlite3.connect(legacy)) as connection:
            connection.execute("UPDATE change_ledger SET status='completed'")
            connection.execute("UPDATE workflow_state SET current_stage='completed',state='closed'")
            connection.commit()
        self.db_cli(legacy, "init", code=2)

    def test_migration_rejects_workflow_and_change_terminal_state_mismatch(self):
        active_completed = self._legacy_db()
        with closing(sqlite3.connect(active_completed)) as connection:
            connection.execute(
                "UPDATE change_ledger SET spec_ref='spec',implementation_ref='plan',"
                "test_ref='test',code_ref='code',evidence_ref='evidence',status='completed'"
            )
            connection.commit()
        self.assertIn("active workflow", self.db_cli(active_completed, "init", code=2).stderr.lower())

        closed_active = self._legacy_db()
        with closing(sqlite3.connect(closed_active)) as connection:
            connection.execute("UPDATE workflow_state SET current_stage='completed',state='closed'")
            connection.commit()
        self.assertIn("closed workflow", self.db_cli(closed_active, "init", code=2).stderr.lower())

    def test_spec_ref_path_must_use_change_id(self):
        self.create_change()
        result = self.cli(
            "set-ref",
            "CE-0001",
            "--field",
            "spec_ref",
            "--value",
            f"specs/spec.md@{self.vault_sha}",
            code=2,
        )
        self.assertIn("specs/<change_id>.md", result.stderr)

    def test_plan_ref_path_must_use_change_id(self):
        self.create_change()
        result = self.cli(
            "set-ref",
            "CE-0001",
            "--field",
            "plan_ref",
            "--value",
            f"plans/plan.md@{self.vault_sha}",
            code=2,
        )
        self.assertIn("plans/<change_id>.md", result.stderr)

    def test_test_ref_path_must_use_change_id(self):
        self.create_change()
        result = self.cli(
            "set-ref",
            "CE-0001",
            "--field",
            "test_ref",
            "--value",
            f"tests/test.md@{self.vault_sha}",
            code=2,
        )
        self.assertIn("tests/<change_id>.md", result.stderr)

    def test_evidence_ref_path_must_live_under_change_id(self):
        self.create_change()
        result = self.cli(
            "set-ref",
            "CE-0001",
            "--field",
            "evidence_ref",
            "--value",
            f"acceptance/report.md@{self.vault_sha}",
            code=2,
        )
        self.assertIn("acceptance/<change_id>/", result.stderr)

    def test_resolve_code_ref_from_linked_worktree(self):
        worktree = self.root / "linked-worktree"
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repo),
                "worktree",
                "add",
                "--detach",
                str(worktree),
                self.code_sha,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(
            self.cli("resolve-code-ref", "--worktree", str(worktree)).stdout
        )
        self.assertEqual("code-repo", payload["repository"])
        self.assertEqual(self.code_sha, payload["commit_sha"])
        self.assertEqual(f"code-repo@{self.code_sha}", payload["code_ref"])
        self.assertEqual(str(worktree.resolve()), payload["worktree"])
        self.assertTrue(payload["detached"])

    def test_resolve_code_ref_requires_worktree_root(self):
        result = self.cli(
            "resolve-code-ref",
            "--worktree",
            str((self.repo / "tests").resolve()),
            code=2,
        )
        self.assertIn("Git worktree root", result.stderr)

    def test_resolve_code_ref_rejects_unconfigured_repository(self):
        other = self.root / "other-repo"
        other.mkdir()
        self._init_git(other)
        (other / "file.txt").write_text("other\n", encoding="utf-8")
        self._commit(other, "other")
        result = self.cli(
            "resolve-code-ref",
            "--worktree",
            str(other),
            code=2,
        )
        self.assertIn("does not match a configured repository", result.stderr)

    def test_resolve_code_ref_rejects_duplicate_repository_mapping(self):
        duplicate_config = self.root / "duplicate-config.json"
        duplicate_config.write_text(
            json.dumps(
                {
                    "spec_vault": str(self.vault),
                    "database": str(self.db),
                    "repositories": {
                        "code-repo": str(self.repo),
                        "same-repo": str(self.repo),
                    },
                }
            ),
            encoding="utf-8",
        )
        result = self.cli(
            "resolve-code-ref",
            "--worktree",
            str(self.repo),
            config=duplicate_config,
            code=2,
        )
        self.assertIn("multiple configured repositories", result.stderr)

    def test_set_ref_code_ref_requires_atomic_worktree_command(self):
        self.create_change()
        result = self.cli(
            "set-ref",
            "CE-0001",
            "--field",
            "code_ref",
            "--value",
            f"code-repo@{self.code_sha}",
            code=2,
        )
        self.assertIn("set-code-ref", result.stderr)
        self.assertIsNone(json.loads(self.cli("show", "CE-0001").stdout)["code_ref"])

    def test_set_code_ref_atomically_derives_current_worktree_head(self):
        self.create_change()
        payload = json.loads(
            self.cli(
                "set-code-ref",
                "CE-0001",
                "--worktree",
                str(self.repo),
            ).stdout
        )
        self.assertEqual(f"code-repo@{self.code_sha}", payload["code_ref"])
        self.assertEqual(
            f"code-repo@{self.code_sha}",
            json.loads(self.cli("show", "CE-0001").stdout)["code_ref"],
        )

    def test_set_code_ref_requires_tdd_stage_for_active_workflow(self):
        self.create_change()
        self.cli("workflow-create", "--change-id", "CE-0001", "--stage", "writing_spec")
        result = self.cli(
            "set-code-ref",
            "CE-0001",
            "--worktree",
            str(self.repo),
            code=2,
        )
        self.assertIn("tdd_coding", result.stderr)
        self.assertIsNone(json.loads(self.cli("show", "CE-0001").stdout)["code_ref"])

    def test_repository_mapping_name_must_be_a_stable_identifier(self):
        bad_config = self.root / "absolute-name-config.json"
        bad_config.write_text(
            json.dumps(
                {
                    "spec_vault": str(self.vault),
                    "database": str(self.db),
                    "repositories": {str(self.repo): str(self.repo)},
                }
            ),
            encoding="utf-8",
        )
        result = self.cli(
            "resolve-code-ref",
            "--worktree",
            str(self.repo),
            config=bad_config,
            code=2,
        )
        self.assertIn("stable identifiers", result.stderr)

    def test_absolute_repository_locator_is_not_a_formal_code_identity(self):
        self.create_change()
        result = self.cli(
            "set-ref",
            "CE-0001",
            "--field",
            "code_ref",
            "--value",
            f"{self.repo}@{self.code_sha}",
            code=2,
        )
        self.assertIn("set-code-ref", result.stderr)

    def test_writing_plan_requires_initial_test_ref(self):
        self.create_change()
        self.cli(
            "set-ref",
            "CE-0001",
            "--field",
            "spec_ref",
            "--value",
            f"specs/CE-0001.md@{self.vault_sha}",
        )
        self.cli("workflow-create", "--change-id", "CE-0001", "--stage", "writing_spec")
        result = self.cli(
            "workflow-set-stage",
            "WF-0001",
            "--stage",
            "writing_plan",
            code=2,
        )
        self.assertIn("test_ref", result.stderr)

    def test_set_ref_cannot_replace_registration_change_ref(self):
        self.create_change()
        original = json.loads(self.cli("show", "CE-0001").stdout)["change_ref"]

        result = self.cli(
            "set-ref",
            "CE-0001",
            "--field",
            "change_ref",
            "--value",
            original,
            code=2,
        )

        self.assertIn("registration and completion", result.stderr)
        self.assertEqual(
            original,
            json.loads(self.cli("show", "CE-0001").stdout)["change_ref"],
        )

    def test_adopt_plan_keeps_registration_change_ref_and_reports_agents(self):
        self.create_change()
        registration_ref = json.loads(self.cli("show", "CE-0001").stdout)[
            "change_ref"
        ]
        spec_ref = f"specs/CE-0001.md@{self.vault_sha}"
        plan_ref = f"plans/CE-0001.md@{self.vault_sha}"
        self.cli("set-ref", "CE-0001", "--field", "spec_ref", "--value", spec_ref)
        self.cli("set-ref", "CE-0001", "--field", "test_ref", "--value", self.test_ref)
        self.cli("workflow-create", "--change-id", "CE-0001", "--stage", "writing_spec")
        self.cli("workflow-set-stage", "WF-0001", "--stage", "writing_plan")

        result = self.cli(
            "adopt-plan",
            "CE-0001",
            "--workflow-id",
            "WF-0001",
            "--plan-ref",
            plan_ref,
        )
        payload = json.loads(result.stdout)

        self.assertEqual(registration_ref, payload["change"]["change_ref"])
        self.assertEqual("tdd_coding", payload["workflow"]["current_stage"])
        self.assertEqual(
            set(self.agents_inventory.split(";")),
            set(payload["agents"]),
        )

    def test_plan_adoption_contract_has_no_intermediate_change_document(self):
        payload = json.loads(self.cli("plan-adoption-contract").stdout)

        self.assertNotIn("adoption_change_ref", payload["arguments"])
        self.assertNotIn("proof", payload)
        self.assertEqual(
            ["change_ledger.plan_ref", "workflow_state.current_stage"],
            payload["atomic_writes"],
        )

    def test_complete_requires_final_change_ref_for_in_progress_event(self):
        self.create_change()

        result = self.cli("complete", "CE-0001", code=2)

        self.assertIn("final --change-ref", result.stderr)

    def test_complete_atomically_installs_final_change_ref(self):
        self.create_change()
        evidence_ref, _ = self.report_ref()
        refs = {
            "spec_ref": f"specs/CE-0001.md@{self.vault_sha}",
            "plan_ref": f"plans/CE-0001.md@{self.vault_sha}",
            "test_ref": self.test_ref,
            "code_ref": f"code-repo@{self.code_sha}",
            "evidence_ref": evidence_ref,
        }
        for field in ("spec_ref", "plan_ref", "test_ref"):
            self.cli("set-ref", "CE-0001", "--field", field, "--value", refs[field])
        self.set_code_ref()
        self.cli(
            "set-ref",
            "CE-0001",
            "--field",
            "evidence_ref",
            "--value",
            evidence_ref,
        )
        final_text = (
            "---\n"
            "change_id: CE-0001\n"
            "status: completed\n"
            f"spec_ref: {refs['spec_ref']}\n"
            f"plan_ref: {refs['plan_ref']}\n"
            f"test_ref: {refs['test_ref']}\n"
            f"code_ref: {refs['code_ref']}\n"
            f"evidence_ref: {refs['evidence_ref']}\n"
            "---\n"
            "# CE-0001 变更事件\n"
        )
        (self.vault / "changes/CE-0001/change.md").write_text(
            final_text,
            encoding="utf-8",
        )
        final_sha = self._commit(self.vault, "final change")
        final_ref = f"changes/CE-0001/change.md@{final_sha}"

        payload = json.loads(
            self.cli(
                "complete",
                "CE-0001",
                "--change-ref",
                final_ref,
            ).stdout
        )

        self.assertEqual("completed", payload["status"])
        self.assertEqual(final_ref, payload["change_ref"])
        self.assertEqual(final_ref, json.loads(self.cli("show", "CE-0001").stdout)["change_ref"])
        self.assertEqual("completed", json.loads(self.cli("complete", "CE-0001").stdout)["status"])
        self.assertEqual(
            "completed",
            json.loads(
                self.cli(
                    "complete",
                    "CE-0001",
                    "--change-ref",
                    final_ref,
                ).stdout
            )["status"],
        )
        mismatch = self.cli(
            "complete",
            "CE-0001",
            "--change-ref",
            f"changes/CE-0001/change.md@{'f' * 40}",
            code=2,
        )
        self.assertIn("does not match", mismatch.stderr)


if __name__ == "__main__":
    unittest.main()
