from pathlib import Path
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "stage_worker_handoff.py"


def stage_inputs(stage, repository_path, workspace_path, vault_sha, repository_sha):
    common = {"repository_path": str(repository_path)}
    if stage == "writing_spec":
        return {
            "change_ref": f"changes/CE-0006/change.md@{vault_sha}",
            "related_formal_refs": "none",
            "acceptance_steps_ref": "none",
        }
    if stage == "writing_plan":
        return {
            **common,
            "change_ref": f"changes/CE-0006/change.md@{vault_sha}",
            "spec_ref": f"specs/CE-0006.md@{vault_sha}",
            "test_ref": f"tests/CE-0006.md@{vault_sha}",
            "base_source": "local",
            "base_locator": "selected local commit",
            "base_sha": repository_sha,
            "baseline_details": json.dumps(
                {
                    "base_worktree": str(repository_path),
                    "base_local_branch": "main",
                    "base_detached_sha": None,
                    "pushed_status": "unconfirmed",
                    "dirty_exclusions": "none",
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            "agents_inventory": "AGENTS.md@sha256:example",
            "workspace_differences": "none",
        }
    if stage == "implementation":
        plan_ref = f"plans/CE-0006.md@{vault_sha}"
        offer = {
            "repository": str(repository_path),
            "plan_ref": plan_ref,
            "plan_or_tasks": [plan_ref],
            "base_source": "local",
            "base_locator": {
                "kind": "local",
                "remote": None,
                "worktree": str(repository_path),
                "branch": "main",
                "detached_sha": None,
            },
            "base_sha": repository_sha,
            "remote_fetch_authorized": False,
            "worktree_creation_authorized": True,
            "tdd_required": True,
            "tdd_exemption_reason": None,
            "baseline_snapshot": None,
            "local_commit_authorized": True,
            "finish_after_execution": False,
        }
        contract = {
            "tdd_required": True,
            "tdd_exemption_reason": None,
            "baseline_snapshot": None,
            "local_commit_authorized": True,
            "local_commit_scope": {
                "repositories": [str(repository_path)],
                "workspace_or_branch": {
                    "workspace": str(workspace_path),
                    "branch": "impl",
                },
                "plan_or_tasks": [plan_ref],
            },
            "finish_after_execution": False,
        }
        return {
            **common,
            "change_ref": f"changes/CE-0006/change.md@{vault_sha}",
            "spec_ref": f"specs/CE-0006.md@{vault_sha}",
            "plan_ref": plan_ref,
            "test_ref": f"tests/CE-0006.md@{vault_sha}",
            "workspace_path": str(workspace_path),
            "authorization_offer": json.dumps(
                offer, sort_keys=True, separators=(",", ":")
            ),
            "execution_contract": json.dumps(
                contract, sort_keys=True, separators=(",", ":")
            ),
        }
    raise AssertionError(stage)


def load_module():
    spec = importlib.util.spec_from_file_location("stage_worker_handoff", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_git(root, *args):
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def write_implementation_report(path, artifact_ref, evidence):
    structured = {
        "artifact_ref": artifact_ref,
        "review_status": "Approved",
        "verification_evidence": evidence,
    }
    path.write_text(
        "# Implementation report\n\n"
        "## Structured Result\n\n"
        "```json\n"
        + json.dumps(structured, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n```\n",
        encoding="utf-8",
    )


class StageWorkerHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.vault = cls.root / "vault"
        cls.vault.mkdir()
        (cls.vault / ".local").mkdir()
        for relative in (
            "changes/CE-0006/change.md",
            "specs/CE-0006.md",
            "plans/CE-0006.md",
            "tests/CE-0006.md",
        ):
            path = cls.vault / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {relative}\n", encoding="utf-8")
        (cls.vault / ".gitignore").write_text(".local/\n", encoding="utf-8")
        run_git(cls.vault, "init", "-b", "main")
        run_git(cls.vault, "config", "user.email", "tests@example.invalid")
        run_git(cls.vault, "config", "user.name", "Stage Worker Tests")
        cls.database = cls.vault / ".local" / "workflow.sqlite3"
        cls.database.touch()
        cls.repository = cls.root / "repo"
        cls.repository.mkdir()
        (cls.repository / "source.txt").write_text("initial\n", encoding="utf-8")
        run_git(cls.repository, "init", "-b", "main")
        run_git(cls.repository, "config", "user.email", "tests@example.invalid")
        run_git(cls.repository, "config", "user.name", "Stage Worker Tests")

        cls.vault_shas = {}
        cls.repository_shas = {}
        for suffix in ("a", "b", "c", "d", "1", "2"):
            (cls.vault / "version.txt").write_text(suffix + "\n", encoding="utf-8")
            run_git(cls.vault, "add", ".gitignore", "changes", "specs", "plans", "tests", "version.txt")
            run_git(cls.vault, "commit", "-m", f"vault {suffix}")
            cls.vault_shas[suffix] = run_git(cls.vault, "rev-parse", "HEAD")

            (cls.repository / "source.txt").write_text(suffix + "\n", encoding="utf-8")
            run_git(cls.repository, "add", "source.txt")
            run_git(cls.repository, "commit", "-m", f"repo {suffix}")
            cls.repository_shas[suffix] = run_git(
                cls.repository, "rev-parse", "HEAD"
            )

        cls.worktree = cls.root / "repo-worktree"
        run_git(
            cls.repository,
            "worktree",
            "add",
            "-b",
            "impl",
            str(cls.worktree),
            cls.repository_shas["d"],
        )
        cls.config = cls.root / "workflow.json"
        cls.config.write_text(
            json.dumps(
                {
                    "spec_vault": str(cls.vault),
                    "database": str(cls.database),
                    "repositories": {"repo": str(cls.repository)},
                }
            ),
            encoding="utf-8",
        )

    def setUp(self):
        stage_workers = self.vault / ".local" / "stage-workers"
        if stage_workers.exists():
            shutil.rmtree(stage_workers)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def inputs(self, stage, suffix="a"):
        return stage_inputs(
            stage,
            self.repository,
            self.worktree,
            self.vault_shas[suffix],
            self.repository_shas[suffix],
        )

    def test_init_creates_durable_identity_bound_handoff(self):
        module = load_module()
        result = module.init_handoff(
            self.config,
            workflow_id="WF-001",
            change_id="CE-0006",
            stage="writing_spec",
            role="spec_worker",
            input_refs=self.inputs("writing_spec"),
        )

        handoff_path = Path(result["handoff_path"])
        self.assertTrue(handoff_path.is_file())
        self.assertEqual(
            handoff_path.parent.parent,
            self.vault
            / ".local"
            / "stage-workers"
            / "WF-001"
            / "CE-0006"
            / "writing_spec",
        )
        self.assertTrue(handoff_path.parent.name.startswith("run-"))
        payload = json.loads(handoff_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "initialized")
        self.assertEqual(payload["role"], "spec_worker")
        self.assertEqual(payload["candidate_path"], str(handoff_path.parent / "candidate.md"))

    def test_validate_rejects_another_event_stage_role_or_input_ref(self):
        module = load_module()
        result = module.init_handoff(
            self.config,
            workflow_id="WF-001",
            change_id="CE-0006",
            stage="writing_plan",
            role="plan_worker",
            input_refs=self.inputs("writing_plan", "b"),
        )
        handoff_path = Path(result["handoff_path"])

        module.validate_handoff(
            self.config,
            handoff_path,
            workflow_id="WF-001",
            change_id="CE-0006",
            stage="writing_plan",
            role="plan_worker",
            input_refs=self.inputs("writing_plan", "b"),
        )

        mismatches = (
            {"change_id": "CE-0007"},
            {"stage": "writing_spec"},
            {"role": "spec_worker"},
            {"input_refs": self.inputs("writing_plan", "c")},
        )
        for overrides in mismatches:
            kwargs = {
                "workflow_id": "WF-001",
                "change_id": "CE-0006",
                "stage": "writing_plan",
                "role": "plan_worker",
                "input_refs": self.inputs("writing_plan", "b"),
            }
            kwargs.update(overrides)
            with self.assertRaises(module.ContractError):
                module.validate_handoff(self.config, handoff_path, **kwargs)

    def test_write_updates_results_without_changing_identity_or_inputs(self):
        module = load_module()
        result = module.init_handoff(
            self.config,
            workflow_id="WF-001",
            change_id="CE-0006",
            stage="implementation",
            role="implementation_coordinator",
            input_refs=self.inputs("implementation", "d"),
        )
        handoff_path = Path(result["handoff_path"])
        report_path = Path(result["report_path"])
        head = run_git(self.worktree, "rev-parse", "HEAD")
        evidence = [
            {
                "code_sha": head,
                "command": "python -m unittest tests.test_feature",
                "environment_fingerprint": "python-3.13-windows",
                "input_fingerprint": "fixtures-v1-default-args",
                "scope": "Task 1 focused tests",
                "result": "passed",
                "produced_by": "task_implementer",
            }
        ]
        write_implementation_report(report_path, "repo@" + head, evidence)

        updated = module.write_handoff(
            self.config,
            handoff_path,
            expected_revision=0,
            status="complete",
            artifact_ref="repo@" + head,
            review_status="Approved",
            summary=["3 tasks complete", "all tests pass"],
            needs_user_decision=[],
            blockers=[],
            verification_evidence=evidence,
        )

        self.assertEqual(updated["workflow_id"], "WF-001")
        self.assertEqual(updated["change_id"], "CE-0006")
        self.assertEqual(
            updated["input_refs"]["plan_ref"],
            "plans/CE-0006.md@" + self.vault_shas["d"],
        )
        self.assertEqual(updated["status"], "complete")
        self.assertEqual(updated["review_status"], "Approved")
        self.assertRegex(updated["report_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(len(updated["verification_evidence"]), 1)

    def test_implementation_complete_requires_head_bound_unique_evidence_and_report(self):
        module = load_module()
        result = module.init_handoff(
            self.config,
            workflow_id="WF-001",
            change_id="CE-0006",
            stage="implementation",
            role="implementation_coordinator",
            input_refs=self.inputs("implementation", "d"),
        )
        handoff_path = Path(result["handoff_path"])
        head = run_git(self.worktree, "rev-parse", "HEAD")
        evidence = {
            "code_sha": head,
            "command": "python -m unittest tests.test_feature",
            "environment_fingerprint": "python-3.13-windows",
            "input_fingerprint": "fixtures-v1-default-args",
            "scope": "Task 1 focused tests",
            "result": "passed",
            "produced_by": "task_implementer",
        }

        with self.assertRaises(module.ContractError):
            module.write_handoff(
                self.config,
                handoff_path,
                expected_revision=0,
                status="complete",
                artifact_ref="repo@" + head,
                review_status="Approved",
                verification_evidence=[evidence],
            )

        Path(result["report_path"]).write_text("# Final report\n", encoding="utf-8")
        with self.assertRaises(module.ContractError):
            module.write_handoff(
                self.config,
                handoff_path,
                expected_revision=0,
                status="complete",
                artifact_ref="repo@" + head,
                review_status="Approved",
                verification_evidence=[evidence],
            )
        write_implementation_report(
            Path(result["report_path"]), "repo@" + head, [evidence]
        )
        report_path = Path(result["report_path"])
        report_path.write_text(
            report_path.read_text(encoding="utf-8").replace(
                '"review_status":"Approved"',
                '"review_status":"Approved","review_status":"Approved"',
                1,
            ),
            encoding="utf-8",
        )
        with self.assertRaises(module.ContractError):
            module.write_handoff(
                self.config,
                handoff_path,
                expected_revision=0,
                status="complete",
                artifact_ref="repo@" + head,
                review_status="Approved",
                verification_evidence=[evidence],
            )
        write_implementation_report(report_path, "repo@" + head, [evidence])
        with self.assertRaises(module.ContractError):
            module.write_handoff(
                self.config,
                handoff_path,
                expected_revision=0,
                status="complete",
                artifact_ref="repo@" + head,
                review_status="Approved",
                verification_evidence=[{**evidence, "code_sha": "e" * 40}],
            )
        with self.assertRaises(module.ContractError):
            module.write_handoff(
                self.config,
                handoff_path,
                expected_revision=0,
                status="complete",
                artifact_ref="repo@" + head,
                review_status="Approved",
                verification_evidence=[evidence, evidence],
            )

        write_implementation_report(
            Path(result["report_path"]), "repo@" + head, [evidence]
        )
        completed = module.write_handoff(
            self.config,
            handoff_path,
            expected_revision=0,
            status="complete",
            artifact_ref="repo@" + head,
            review_status="Approved",
            verification_evidence=[evidence],
        )
        Path(result["report_path"]).write_text("# Substituted report\n", encoding="utf-8")
        with self.assertRaises(module.ContractError):
            module.validate_handoff(
                self.config,
                handoff_path,
                workflow_id="WF-001",
                change_id="CE-0006",
                stage="implementation",
                role="implementation_coordinator",
                input_refs=self.inputs("implementation", "d"),
            )
        self.assertRegex(completed["report_sha256"], r"^[0-9a-f]{64}$")

    def test_legacy_optional_stage_inputs_can_resume_without_becoming_new_requirements(self):
        module = load_module()
        spec_inputs = self.inputs("writing_spec")
        spec_inputs["repository_path"] = str(self.repository)
        spec_inputs["code_sha"] = self.repository_shas["a"]
        spec_run = module.init_handoff(
            self.config,
            workflow_id="WF-001",
            change_id="CE-0006",
            stage="writing_spec",
            role="spec_worker",
            input_refs=spec_inputs,
        )
        module.validate_handoff(
            self.config,
            spec_run["handoff_path"],
            workflow_id="WF-001",
            change_id="CE-0006",
            stage="writing_spec",
            role="spec_worker",
            input_refs=spec_inputs,
        )

        plan_inputs = self.inputs("writing_plan")
        plan_inputs["plan_profile"] = "full"
        plan_run = module.init_handoff(
            self.config,
            workflow_id="WF-002",
            change_id="CE-0006",
            stage="writing_plan",
            role="plan_worker",
            input_refs=plan_inputs,
        )
        self.assertTrue(Path(plan_run["handoff_path"]).is_file())

    def test_changed_inputs_create_a_new_run_without_overwriting_the_old_handoff(self):
        module = load_module()
        first = module.init_handoff(
            self.config,
            workflow_id="WF-001",
            change_id="CE-0006",
            stage="writing_plan",
            role="plan_worker",
            input_refs=self.inputs("writing_plan", "1"),
        )
        second = module.init_handoff(
            self.config,
            workflow_id="WF-001",
            change_id="CE-0006",
            stage="writing_plan",
            role="plan_worker",
            input_refs=self.inputs("writing_plan", "2"),
        )

        self.assertNotEqual(first["workspace"], second["workspace"])
        self.assertTrue(Path(first["handoff_path"]).is_file())
        self.assertTrue(Path(second["handoff_path"]).is_file())
        self.assertEqual(
            json.loads(Path(first["handoff_path"]).read_text(encoding="utf-8"))[
                "input_refs"
            ]["spec_ref"],
            "specs/CE-0006.md@" + self.vault_shas["1"],
        )

    def test_invalid_identity_tokens_and_role_mapping_are_rejected(self):
        module = load_module()
        with self.assertRaises(module.ContractError):
            module.init_handoff(
                self.config,
                workflow_id="../WF-001",
                change_id="CE-0006",
                stage="writing_spec",
                role="spec_worker",
                input_refs=self.inputs("writing_spec"),
            )
        with self.assertRaises(module.ContractError):
            module.init_handoff(
                self.config,
                workflow_id="WF-001",
                change_id="CE-0006",
                stage="writing_spec",
                role="plan_worker",
                input_refs=self.inputs("writing_spec"),
            )

    def test_init_rejects_missing_or_invalid_stage_critical_inputs(self):
        module = load_module()
        plan_inputs = self.inputs("writing_plan")
        plan_inputs.pop("test_ref")
        with self.assertRaises(module.ContractError):
            module.init_handoff(
                self.config,
                workflow_id="WF-001",
                change_id="CE-0006",
                stage="writing_plan",
                role="plan_worker",
                input_refs=plan_inputs,
            )

        spec_inputs = self.inputs("writing_spec")
        spec_inputs.pop("related_formal_refs")
        with self.assertRaises(module.ContractError):
            module.init_handoff(
                self.config,
                workflow_id="WF-001",
                change_id="CE-0006",
                stage="writing_spec",
                role="spec_worker",
                input_refs=spec_inputs,
            )

        plan_inputs = self.inputs("writing_plan")
        plan_inputs["base_sha"] = "short"
        with self.assertRaises(module.ContractError):
            module.init_handoff(
                self.config,
                workflow_id="WF-001",
                change_id="CE-0006",
                stage="writing_plan",
                role="plan_worker",
                input_refs=plan_inputs,
            )

    def test_spec_handoff_does_not_require_a_code_repository_or_sha(self):
        module = load_module()
        inputs = self.inputs("writing_spec")

        result = module.init_handoff(
            self.config,
            workflow_id="WF-001",
            change_id="CE-0006",
            stage="writing_spec",
            role="spec_worker",
            input_refs=inputs,
        )

        self.assertTrue(Path(result["handoff_path"]).is_file())

    def test_plan_handoff_has_one_implicit_lean_profile(self):
        module = load_module()
        inputs = self.inputs("writing_plan")

        result = module.init_handoff(
            self.config,
            workflow_id="WF-001",
            change_id="CE-0006",
            stage="writing_plan",
            role="plan_worker",
            input_refs=inputs,
        )

        handoff = json.loads(Path(result["handoff_path"]).read_text(encoding="utf-8"))
        self.assertNotIn("plan_profile", handoff["input_refs"])

    def test_plan_approved_requires_exact_artifact_review_and_no_blockers(self):
        module = load_module()
        result = module.init_handoff(
            self.config,
            workflow_id="WF-001",
            change_id="CE-0006",
            stage="writing_plan",
            role="plan_worker",
            input_refs=self.inputs("writing_plan"),
        )
        handoff_path = Path(result["handoff_path"])

        with self.assertRaises(module.ContractError):
            module.write_handoff(
                self.config,
                handoff_path,
                expected_revision=0,
                status="approved",
            )
        with self.assertRaises(module.ContractError):
            module.write_handoff(
                self.config,
                handoff_path,
                expected_revision=0,
                status="approved",
                artifact_ref="plans/CE-0006.md@" + "f" * 40,
                review_status="Approved",
                blockers=["unresolved"],
            )

    def test_candidate_digest_and_fixed_paths_block_substitution(self):
        module = load_module()
        result = module.init_handoff(
            self.config,
            workflow_id="WF-001",
            change_id="CE-0006",
            stage="writing_spec",
            role="spec_worker",
            input_refs=self.inputs("writing_spec"),
        )
        handoff_path = Path(result["handoff_path"])
        candidate_path = Path(result["candidate_path"])
        candidate_path.write_text("# Candidate A\n", encoding="utf-8")
        updated = module.write_handoff(
            self.config,
            handoff_path,
            expected_revision=0,
            status="candidate_ready",
        )
        self.assertRegex(updated["candidate_sha256"], r"^[0-9a-f]{64}$")

        module.validate_handoff(
            self.config,
            handoff_path,
            workflow_id="WF-001",
            change_id="CE-0006",
            stage="writing_spec",
            role="spec_worker",
            input_refs=self.inputs("writing_spec"),
        )
        candidate_path.write_text("# Candidate B\n", encoding="utf-8")
        with self.assertRaises(module.ContractError):
            module.validate_handoff(
                self.config,
                handoff_path,
                workflow_id="WF-001",
                change_id="CE-0006",
                stage="writing_spec",
                role="spec_worker",
                input_refs=self.inputs("writing_spec"),
            )

        payload = json.loads(handoff_path.read_text(encoding="utf-8"))
        payload["candidate_path"] = str(self.root / "outside.md")
        handoff_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(module.ContractError):
            module.validate_handoff(
                self.config,
                handoff_path,
                workflow_id="WF-001",
                change_id="CE-0006",
                stage="writing_spec",
                role="spec_worker",
                input_refs=self.inputs("writing_spec"),
            )

    def test_spec_publish_requires_the_confirmed_candidate_digest(self):
        module = load_module()
        result = module.init_handoff(
            self.config,
            workflow_id="WF-001",
            change_id="CE-0006",
            stage="writing_spec",
            role="spec_worker",
            input_refs=self.inputs("writing_spec"),
        )
        handoff_path = Path(result["handoff_path"])
        Path(result["candidate_path"]).write_text("# Exact candidate\n", encoding="utf-8")
        ready = module.write_handoff(
            self.config,
            handoff_path,
            expected_revision=0,
            status="candidate_ready",
        )
        with self.assertRaises(module.ContractError):
            module.write_handoff(
                self.config,
                handoff_path,
                expected_revision=1,
                status="published",
                artifact_ref="specs/CE-0006.md@" + self.vault_shas["a"],
                confirmed_candidate_sha256="0" * 64,
            )
        published = module.write_handoff(
            self.config,
            handoff_path,
            expected_revision=1,
            status="published",
            artifact_ref="specs/CE-0006.md@" + self.vault_shas["a"],
            confirmed_candidate_sha256=ready["candidate_sha256"],
        )
        self.assertEqual(published["status"], "published")

    def test_stale_revision_and_authority_file_substitution_are_rejected(self):
        module = load_module()
        result = module.init_handoff(
            self.config,
            workflow_id="WF-001",
            change_id="CE-0006",
            stage="implementation",
            role="implementation_coordinator",
            input_refs=self.inputs("implementation"),
        )
        handoff_path = Path(result["handoff_path"])
        module.write_handoff(
            self.config,
            handoff_path,
            expected_revision=0,
            status="working",
        )
        with self.assertRaises(module.ContractError):
            module.write_handoff(
                self.config,
                handoff_path,
                expected_revision=0,
                status="complete",
            )

        offer_path = Path(result["authorization_offer_path"])
        offer_path.write_text("{}\n", encoding="utf-8")
        with self.assertRaises(module.ContractError):
            module.validate_handoff(
                self.config,
                handoff_path,
                workflow_id="WF-001",
                change_id="CE-0006",
                stage="implementation",
                role="implementation_coordinator",
                input_refs=self.inputs("implementation"),
            )


if __name__ == "__main__":
    unittest.main()
