from pathlib import Path
import re
import subprocess
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "skills"

EXPECTED_SKILLS = {
    "using-personal-development-workflow",
    "managing-change-ledger",
    "exploring-and-grilling-requirements",
    "writing-specs",
    "writing-test-drafts",
}


class PackageContractTests(unittest.TestCase):
    def test_package_contains_only_runtime_skills(self):
        actual = {
            path.name
            for path in SKILLS_ROOT.iterdir()
            if path.is_dir() and (path / "SKILL.md").is_file()
        }
        self.assertEqual(actual, EXPECTED_SKILLS)
        for skill_name in EXPECTED_SKILLS:
            self.assertTrue((SKILLS_ROOT / skill_name / "SKILL.md").is_file())

    def test_readme_describes_the_thin_workflow(self):
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for required in (
            "direct / light / full",
            "单 Worktree 串行",
            "多 Worktree 并行",
            "一个 Worktree 同时只有一个写入者",
            "define → implement → verify → done",
            "从零开发完整系统",
            "正式验收按需启用",
        ):
            self.assertIn(required, text)
        for removed in (
            "最终逻辑稿",
            "Implementation Coordinator",
            "authorization_offer",
            "auto_stop_points",
        ):
            self.assertNotIn(removed, text)

    def test_distribution_files_exist(self):
        for relative in (
            "README.md",
            "DEPENDENCIES.md",
            "examples/personal-development-workflow.json.example",
            "config/global-skill-trigger-overrides.json",
            "scripts/install.ps1",
            "scripts/test.ps1",
        ):
            self.assertTrue((REPO_ROOT / relative).is_file(), relative)

    def test_runtime_payload_excludes_local_state(self):
        tracked = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        violations = [
            path
            for path in tracked
            if any(part in {"__pycache__", ".local"} for part in Path(path).parts)
            or Path(path).suffix in {".pyc", ".sqlite", ".sqlite3"}
        ]
        self.assertEqual(violations, [])

    def test_docs_do_not_hardcode_windows_paths(self):
        pattern = re.compile(r"[A-Za-z]:\\")
        for relative in ("README.md", "DEPENDENCIES.md"):
            self.assertNotRegex(
                (REPO_ROOT / relative).read_text(encoding="utf-8"),
                pattern,
                relative,
            )


if __name__ == "__main__":
    unittest.main()
