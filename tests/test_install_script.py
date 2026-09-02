import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install.ps1"
TRIGGER_OVERRIDE_FILE = REPO_ROOT / "config" / "global-skill-trigger-overrides.json"
CUSTOM_SKILLS = {
    "using-personal-development-workflow",
    "managing-change-ledger",
    "exploring-and-grilling-requirements",
    "writing-specs",
    "writing-test-drafts",
}
EXPECTED_TRIGGER_OVERRIDES = {
    "test-driven-development": "Use when the user explicitly requests TDD or test-first development, or a high-risk change to pure logic, algorithms, or critical state transitions needs a failing regression test before implementation.",
    "systematic-debugging": "Use when a bug, test failure, or unexpected behavior has no clear cause after initial inspection, recurs after an attempted fix, or spans multiple components and needs evidence-driven root-cause analysis.",
    "writing-plans": "Use when the user explicitly asks for a detailed implementation plan, or a full or high-risk change has a confirmed spec and requires multi-stage coordination before coding.",
    "requesting-code-review": "Use when the user explicitly requests code review, or a large or high-risk change is ready for independent review before integration.",
    "dispatching-parallel-agents": "Use when the user requests parallel delegation, or a full-scope task has at least two independent workstreams that can be isolated, modified, and verified without shared state before serial integration.",
    "subagent-driven-development": "Use when the user explicitly chooses subagent-driven development, or an active full workflow has a reviewed implementation plan whose independent tasks are approved for delegated execution in the current session.",
    "executing-plans": "Use when the user explicitly asks to execute an existing written implementation plan in a separate session, or an active full workflow selects plan-driven execution with review checkpoints.",
}


def powershell_executable():
    executable = shutil.which("pwsh") or shutil.which("powershell")
    if executable is None:
        raise unittest.SkipTest("PowerShell is required for installer tests")
    return executable


def run_installer(destination_root, *arguments):
    return subprocess.run(
        [
            powershell_executable(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INSTALL_SCRIPT),
            "-DestinationRoot",
            str(destination_root),
            *arguments,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class InstallerTests(unittest.TestCase):
    def destination(self, directory):
        root = Path(directory) / "skills"
        root.mkdir()
        return root

    def seed_trigger_skills(self, destination):
        originals = {}
        for skill_name in EXPECTED_TRIGGER_OVERRIDES:
            skill_root = destination / skill_name
            skill_root.mkdir()
            text = (
                "---\n"
                f"name: {skill_name}\n"
                "description: Use when ordinary development work begins\n"
                "---\n\n"
                f"# {skill_name}\n\n"
                "body-marker\n"
            )
            (skill_root / "SKILL.md").write_text(text, encoding="utf-8")
            originals[skill_name] = text
        return originals

    def test_installs_five_self_contained_skills(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = self.destination(directory)
            result = run_installer(destination)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            installed = {
                path.name
                for path in destination.iterdir()
                if path.is_dir() and path.name in CUSTOM_SKILLS
            }
            self.assertEqual(installed, CUSTOM_SKILLS)

    def test_refuses_overwrite_without_force_and_force_creates_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = self.destination(directory)
            self.assertEqual(run_installer(destination).returncode, 0)
            marker = destination / "writing-specs" / "local-marker.txt"
            marker.write_text("preserve", encoding="utf-8")
            refused = run_installer(destination)
            self.assertNotEqual(refused.returncode, 0)
            forced = run_installer(destination, "-Force")
            self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)
            self.assertFalse(marker.exists())
            backups = destination / ".personal-development-workflow-backups"
            self.assertTrue(any(backups.iterdir()))

    def test_check_detects_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = self.destination(directory)
            self.assertEqual(run_installer(destination).returncode, 0)
            checked = run_installer(destination, "-Check")
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            (destination / "writing-specs" / "SKILL.md").write_text("drift\n", encoding="utf-8")
            drifted = run_installer(destination, "-Check")
            self.assertNotEqual(drifted.returncode, 0)
            self.assertIn("content differs", drifted.stdout + drifted.stderr)

    def test_applies_and_checks_seven_global_trigger_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = self.destination(directory)
            originals = self.seed_trigger_skills(destination)

            result = run_installer(destination)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            configured = json.loads(TRIGGER_OVERRIDE_FILE.read_text(encoding="utf-8"))
            self.assertEqual(configured, EXPECTED_TRIGGER_OVERRIDES)

            backups = destination / ".personal-development-workflow-backups"
            backup_root = next(backups.iterdir()) / "trigger-overrides"
            for skill_name, description in EXPECTED_TRIGGER_OVERRIDES.items():
                installed = (destination / skill_name / "SKILL.md").read_text(
                    encoding="utf-8"
                )
                self.assertIn(f"description: {description}\n", installed)
                self.assertIn("body-marker", installed)
                self.assertEqual(
                    (backup_root / skill_name / "SKILL.md").read_text(
                        encoding="utf-8"
                    ),
                    originals[skill_name],
                )

            checked = run_installer(destination, "-Check")
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

            drifted_skill = destination / "writing-plans" / "SKILL.md"
            drifted_skill.write_text(
                drifted_skill.read_text(encoding="utf-8").replace(
                    f"description: {EXPECTED_TRIGGER_OVERRIDES['writing-plans']}",
                    "description: Use when any task has multiple steps",
                ),
                encoding="utf-8",
            )
            drifted = run_installer(destination, "-Check")
            self.assertNotEqual(drifted.returncode, 0)
            self.assertIn(
                "trigger description differs: writing-plans",
                drifted.stdout + drifted.stderr,
            )


if __name__ == "__main__":
    unittest.main()
