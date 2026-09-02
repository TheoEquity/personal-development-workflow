import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "change_ledger.py"


class LedgerTests(unittest.TestCase):
    def run_cli(self, db: Path, *args: str, check: bool = True):
        environment = os.environ.copy()
        environment["PYTHONUTF8"] = "1"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--db", str(db), *args],
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=environment,
        )
        if check and result.returncode != 0:
            self.fail(result.stdout + result.stderr)
        return result

    def payload(self, result):
        return json.loads(result.stdout)

    def make_worktree(self, directory: str):
        source = Path(directory) / "source"
        worktree = Path(directory) / "worktree"
        source.mkdir()
        subprocess.run(["git", "init", "-b", "main", str(source)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(source), "config", "user.email", "tests@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(source), "config", "user.name", "Tests"], check=True)
        (source / "README.md").write_text("baseline\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(source), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(source), "commit", "-m", "baseline"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(source), "worktree", "add", "-b", "work", str(worktree)], check=True, capture_output=True)
        head = subprocess.run(["git", "-C", str(worktree), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
        return worktree, head

    def test_direct_change_moves_through_four_stages(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "ledger.sqlite3"
            worktree, head = self.make_worktree(directory)
            self.run_cli(db, "init")
            workflow = self.payload(self.run_cli(db, "workflow-create", "--flow", "direct"))
            self.assertEqual(workflow["current_stage"], "define")
            change = self.payload(
                self.run_cli(db, "create", "--flow", "direct", "--summary", "修复保存失败")
            )
            self.run_cli(
                db,
                "workflow-bind-change",
                workflow["workflow_id"],
                change["change_id"],
            )
            self.run_cli(db, "workflow-bind-worktree", workflow["workflow_id"], "--worktree", str(worktree))
            self.run_cli(db, "workflow-set-stage", workflow["workflow_id"], "implement")
            self.run_cli(db, "set-ref", change["change_id"], "--field", "code_ref", "--value", f"source@{head}")
            self.run_cli(db, "workflow-set-stage", workflow["workflow_id"], "verify")
            completed = self.payload(
                self.run_cli(db, "complete", change["change_id"], "--summary", "保存路径已修复并通过测试")
            )
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(completed["current_stage"], "done")

    def test_light_and_full_require_spec_before_implementation(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "ledger.sqlite3"
            self.run_cli(db, "init")
            for flow in ("light", "full"):
                flow_directory = Path(directory) / flow
                flow_directory.mkdir()
                worktree, _ = self.make_worktree(str(flow_directory))
                workflow = self.payload(self.run_cli(db, "workflow-create", "--flow", flow))
                change = self.payload(self.run_cli(db, "create", "--flow", flow, "--summary", flow))
                self.run_cli(db, "workflow-bind-change", workflow["workflow_id"], change["change_id"])
                self.run_cli(db, "workflow-bind-worktree", workflow["workflow_id"], "--worktree", str(worktree))
                rejected = self.run_cli(
                    db,
                    "workflow-set-stage",
                    workflow["workflow_id"],
                    "implement",
                    check=False,
                )
                self.assertNotEqual(rejected.returncode, 0)
                self.run_cli(db, "set-ref", change["change_id"], "--field", "spec_ref", "--value", f"specs/{change['change_id']}.md@" + "b" * 40)
                accepted = self.payload(self.run_cli(db, "workflow-set-stage", workflow["workflow_id"], "implement"))
                self.assertEqual(accepted["current_stage"], "implement")

    def test_completed_change_is_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "ledger.sqlite3"
            worktree, head = self.make_worktree(directory)
            self.run_cli(db, "init")
            workflow = self.payload(self.run_cli(db, "workflow-create", "--flow", "direct"))
            change = self.payload(self.run_cli(db, "create", "--flow", "direct", "--summary", "x"))
            self.run_cli(db, "workflow-bind-change", workflow["workflow_id"], change["change_id"])
            self.run_cli(db, "workflow-bind-worktree", workflow["workflow_id"], "--worktree", str(worktree))
            self.run_cli(db, "workflow-set-stage", workflow["workflow_id"], "implement")
            self.run_cli(db, "set-ref", change["change_id"], "--field", "code_ref", "--value", f"source@{head}")
            self.run_cli(db, "workflow-set-stage", workflow["workflow_id"], "verify")
            self.run_cli(db, "complete", change["change_id"], "--summary", "done")
            rejected = self.run_cli(
                db,
                "set-ref",
                change["change_id"],
                "--field",
                "evidence_ref",
                "--value",
                "evidence.md@" + "d" * 40,
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)

    def test_init_migrates_legacy_rows_and_stages(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "ledger.sqlite3"
            connection = sqlite3.connect(db)
            connection.executescript(
                """
                CREATE TABLE change_ledger (
                    change_id TEXT PRIMARY KEY,
                    spec_ref TEXT,
                    change_ref TEXT NOT NULL,
                    plan_ref TEXT,
                    test_ref TEXT,
                    code_ref TEXT,
                    evidence_ref TEXT,
                    status TEXT NOT NULL
                );
                CREATE TABLE workflow_state (
                    workflow_id TEXT PRIMARY KEY,
                    change_id TEXT,
                    current_stage TEXT NOT NULL,
                    flow TEXT NOT NULL,
                    review_mode TEXT NOT NULL,
                    state TEXT NOT NULL
                );
                INSERT INTO change_ledger VALUES (
                    'CE-0007', 'specs/CE-0007.md@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                    'changes/CE-0007/change.md@bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
                    'plans/CE-0007.md@cccccccccccccccccccccccccccccccccccccccc',
                    'tests/CE-0007.md@dddddddddddddddddddddddddddddddddddddddd',
                    NULL, NULL, 'in_progress'
                );
                INSERT INTO workflow_state VALUES (
                    'WF-0004', 'CE-0007', 'acceptance', 'full', 'manual', 'active'
                );
                """
            )
            connection.commit()
            connection.close()

            self.run_cli(db, "init")
            change = self.payload(self.run_cli(db, "show", "CE-0007"))
            workflow = self.payload(self.run_cli(db, "workflow-show", "WF-0004"))
            self.assertEqual(change["plan_ref"], "plans/CE-0007.md@" + "c" * 40)
            self.assertEqual(change["test_ref"], "tests/CE-0007.md@" + "d" * 40)
            self.assertEqual(workflow["current_stage"], "verify")
            self.assertNotIn("review_mode", workflow)


if __name__ == "__main__":
    unittest.main()
