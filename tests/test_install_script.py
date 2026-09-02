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


if __name__ == "__main__":
    unittest.main()
