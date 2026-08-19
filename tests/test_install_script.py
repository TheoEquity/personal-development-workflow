from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install.ps1"
CUSTOM_SKILLS = {
    "using-personal-development-workflow",
    "managing-change-ledger",
    "exploring-and-grilling-requirements",
    "writing-specs",
    "writing-test-drafts",
    "writing-final-logic-drafts",
}
DEPENDENCIES = {
    "writing-plans",
    "using-git-worktrees",
    "subagent-driven-development",
    "executing-plans",
    "test-driven-development",
    "verification-before-completion",
    "finishing-a-development-branch",
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
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class InstallerTests(unittest.TestCase):
    def create_destination_with_dependencies(self, root):
        destination = root / "skills"
        destination.mkdir()
        for dependency in DEPENDENCIES:
            dependency_directory = destination / dependency
            dependency_directory.mkdir()
            (dependency_directory / "SKILL.md").write_text(
                f"---\nname: {dependency}\ndescription: test fixture\n---\n",
                encoding="utf-8",
            )
        return destination

    def test_installs_exactly_the_six_custom_skills(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = self.create_destination_with_dependencies(
                Path(temporary_directory)
            )

            result = run_installer(destination)

            self.assertEqual(
                result.returncode,
                0,
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            )
            for skill_name in CUSTOM_SKILLS:
                self.assertTrue((destination / skill_name / "SKILL.md").is_file())
            installed_custom = {
                path.name
                for path in destination.iterdir()
                if path.is_dir() and path.name in CUSTOM_SKILLS
            }
            self.assertEqual(installed_custom, CUSTOM_SKILLS)

    def test_refuses_to_overwrite_existing_custom_skills_without_force(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = self.create_destination_with_dependencies(
                Path(temporary_directory)
            )
            first = run_installer(destination)
            self.assertEqual(first.returncode, 0, first.stderr)

            second = run_installer(destination)

            self.assertNotEqual(second.returncode, 0)
            self.assertIn("already exists", second.stdout + second.stderr)

    def test_force_backs_up_existing_skills_before_replacement(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = self.create_destination_with_dependencies(
                Path(temporary_directory)
            )
            first = run_installer(destination)
            self.assertEqual(first.returncode, 0, first.stderr)
            marker = destination / "writing-specs" / "local-marker.txt"
            marker.write_text("preserve me", encoding="utf-8")

            forced = run_installer(destination, "-Force")

            self.assertEqual(
                forced.returncode,
                0,
                f"stdout:\n{forced.stdout}\nstderr:\n{forced.stderr}",
            )
            self.assertFalse(marker.exists())
            backup_root = destination / ".personal-development-workflow-backups"
            backups = [path for path in backup_root.iterdir() if path.is_dir()]
            self.assertEqual(len(backups), 1)
            self.assertTrue(
                (backups[0] / "writing-specs" / "local-marker.txt").is_file()
            )

    def test_missing_superpowers_dependencies_stop_without_installing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "skills"
            destination.mkdir()

            result = run_installer(destination)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Missing required Superpowers skills", result.stdout + result.stderr)
            for skill_name in CUSTOM_SKILLS:
                self.assertFalse((destination / skill_name).exists())

    def test_rejects_dependency_with_mismatched_frontmatter_name(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = self.create_destination_with_dependencies(
                Path(temporary_directory)
            )
            (destination / "writing-plans" / "SKILL.md").write_text(
                "---\nname: unrelated-skill\ndescription: forged dependency\n---\n",
                encoding="utf-8",
            )

            result = run_installer(destination)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Invalid Superpowers skill identity", result.stdout + result.stderr)
            for skill_name in CUSTOM_SKILLS:
                self.assertFalse((destination / skill_name).exists())


if __name__ == "__main__":
    unittest.main()
