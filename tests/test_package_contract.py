from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "skills"

EXPECTED_SKILLS = {
    "using-personal-development-workflow",
    "managing-change-ledger",
    "exploring-and-grilling-requirements",
    "writing-specs",
    "writing-test-drafts",
    "writing-final-logic-drafts",
}

SUPERPOWERS_DEPENDENCIES = {
    "writing-plans",
    "using-git-worktrees",
    "subagent-driven-development",
    "executing-plans",
    "test-driven-development",
    "verification-before-completion",
    "finishing-a-development-branch",
}

REQUIRED_PATHS = {
    "README.md",
    "DEPENDENCIES.md",
    "examples/personal-development-workflow.json.example",
    "scripts/install.ps1",
    "scripts/test.ps1",
    ".github/workflows/tests.yml",
}


class PackageContractTests(unittest.TestCase):
    def test_package_contains_exactly_the_owned_skills(self):
        self.assertTrue(SKILLS_ROOT.is_dir(), SKILLS_ROOT)
        actual = {path.name for path in SKILLS_ROOT.iterdir() if path.is_dir()}
        self.assertEqual(actual, EXPECTED_SKILLS)
        for skill_name in EXPECTED_SKILLS:
            self.assertTrue((SKILLS_ROOT / skill_name / "SKILL.md").is_file())

    def test_required_distribution_files_exist(self):
        missing = [path for path in REQUIRED_PATHS if not (REPO_ROOT / path).is_file()]
        self.assertEqual(missing, [])

    @unittest.skipUnless(os.name == "nt", "PowerShell command shim is Windows-specific")
    def test_test_entry_point_enables_utf8_for_every_python_process(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            shim = Path(temp_dir) / "python.cmd"
            marker = Path(temp_dir) / "python-invocations.txt"
            shim.write_text(
                '@echo off\n'
                'echo invoked>>"%UTF8_PROBE_MARKER%"\n'
                'if "%PYTHONUTF8%"=="1" exit /b 0\n'
                'echo PYTHONUTF8=%PYTHONUTF8% 1>&2\n'
                'exit /b 97\n',
                encoding="ascii",
            )
            env = os.environ.copy()
            env.pop("PYTHONUTF8", None)
            env["UTF8_PROBE_MARKER"] = str(marker)
            env["PATH"] = f"{temp_dir}{os.pathsep}{env['PATH']}"
            result = subprocess.run(
                [
                    "pwsh",
                    "-NoProfile",
                    "-File",
                    str(REPO_ROOT / "scripts" / "test.ps1"),
                ],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertTrue(marker.is_file(), "test.ps1 did not invoke the Python probe")
            self.assertGreaterEqual(len(marker.read_text(encoding="ascii").splitlines()), 1)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_runtime_payload_excludes_local_state_and_caches(self):
        forbidden_names = {
            "__pycache__",
            ".local",
            "personal-workflow.sqlite3",
            "personal-development-workflow.json",
        }
        tracked = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        violations = []
        for relative in tracked:
            path = Path(relative)
            if (
                any(part in forbidden_names for part in path.parts)
                or path.suffix in {".pyc", ".sqlite", ".sqlite3"}
            ):
                violations.append(path.as_posix())
        self.assertEqual(violations, [])

    def test_text_payload_has_no_machine_paths_or_credentials(self):
        machine_path_pattern = re.compile(
            r"(?<![A-Za-z0-9])[A-Za-z]:\\[^\s'\"`<>]+"
        )
        credential_patterns = (
            re.compile(r"(?:gho|ghp|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{8,}"),
            re.compile(r"glpat-[A-Za-z0-9_-]{16,}"),
            re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
            re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
            re.compile(r"AKIA[0-9A-Z]{16}"),
            re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
            re.compile(r"https?://[^\s/:]+:[^\s/@]+@[^\s]+"),
        )
        violations = []
        for path in REPO_ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if machine_path_pattern.search(text):
                violations.append(f"machine-path:{path.relative_to(REPO_ROOT).as_posix()}")
            if any(pattern.search(text) for pattern in credential_patterns):
                violations.append(f"credential:{path.relative_to(REPO_ROOT).as_posix()}")
        self.assertEqual(violations, [])

    def test_reachable_git_history_has_no_sensitive_payloads(self):
        machine_path_pattern = re.compile(
            r"(?<![A-Za-z0-9])[A-Za-z]:\\[^\s'\"`<>]+"
        )
        credential_patterns = (
            re.compile(r"(?:gho|ghp|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{8,}"),
            re.compile(r"glpat-[A-Za-z0-9_-]{16,}"),
            re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
            re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
            re.compile(r"AKIA[0-9A-Z]{16}"),
            re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
            re.compile(r"https?://[^\s/:]+:[^\s/@]+@[^\s]+"),
        )
        forbidden_parts = {"__pycache__", ".local"}
        violations = []
        objects = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-list", "--objects", "--all"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        for entry in objects:
            object_id, separator, object_path = entry.partition(" ")
            if not separator:
                continue
            path = Path(object_path)
            if (
                any(part in forbidden_parts for part in path.parts)
                or path.name == "personal-development-workflow.json"
                or path.suffix in {".pyc", ".sqlite", ".sqlite3"}
            ):
                violations.append(f"forbidden-history-path:{object_path}")
                continue
            object_type = subprocess.run(
                ["git", "-C", str(REPO_ROOT), "cat-file", "-t", object_id],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            if object_type != "blob":
                continue
            blob = subprocess.run(
                ["git", "-C", str(REPO_ROOT), "cat-file", "blob", object_id],
                check=True,
                capture_output=True,
            ).stdout.decode("utf-8", errors="ignore")
            if machine_path_pattern.search(blob):
                violations.append(f"machine-path-history:{object_path}")
            if any(pattern.search(blob) for pattern in credential_patterns):
                violations.append(f"credential-history:{object_path}")
        self.assertEqual(violations, [])

    def test_superpowers_sources_are_dependencies_not_vendored_skills(self):
        self.assertTrue((REPO_ROOT / "DEPENDENCIES.md").is_file())
        text = (REPO_ROOT / "DEPENDENCIES.md").read_text(encoding="utf-8")
        for dependency in SUPERPOWERS_DEPENDENCIES:
            self.assertIn(f"`{dependency}`", text)
            self.assertFalse((SKILLS_ROOT / dependency).exists())
        self.assertIn("只读依赖", text)
        self.assertIn("不复制", text)
        self.assertIn("superpowers@openai-curated-remote", text)
        self.assertIn("frontmatter", text)

    def test_readme_documents_the_complete_workflow_contract(self):
        self.assertTrue((REPO_ROOT / "README.md").is_file())
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for required in (
            "需求讨论与确认",
            "change_id",
            "change.md",
            "只写两次",
            "一个 Plan",
            "多个 Task",
            "项目级 SQLite",
            "是否开启 Subagent-Driven Development 进行开发？",
            "统一材料变更评估",
            "等待用户确认",
            "局部修改",
            "结构性修改",
            "本地候选",
            "远程候选",
            "只回复“继续”",
            "base_source",
            "未提交修改不属于任何 SHA",
            "先改正式材料，再改代码",
            "最终逻辑稿",
            "logic/<change_id>.md",
        ):
            self.assertIn(required, text)

    def test_copied_workflow_integration_test_is_repository_relative(self):
        test_file = (
            SKILLS_ROOT
            / "using-personal-development-workflow"
            / "tests"
            / "test_workflow_integration_contract.py"
        )
        self.assertTrue(test_file.is_file(), test_file)
        text = test_file.read_text(encoding="utf-8")
        self.assertIn("PACKAGE_ROOT", text)
        self.assertIn('/ "skills"', text)
        self.assertIn('/ "managing-change-ledger"', text)
        self.assertIn('/ "scripts"', text)
        self.assertNotIn("Path.home()", text)
        self.assertNotIn("PROJECT_ROOT = Path(r\"", text)

    def test_example_configuration_is_sanitized(self):
        example = REPO_ROOT / "examples" / "personal-development-workflow.json.example"
        self.assertTrue(example.is_file(), example)
        text = example.read_text(encoding="utf-8")
        self.assertIn("<absolute-project-spec-vault-path>", text)
        self.assertIn("<absolute-code-repository-path>", text)
        self.assertNotRegex(text, r"[A-Za-z]:\\")

    def test_documentation_has_no_literal_windows_absolute_paths(self):
        for relative in ("README.md", "DEPENDENCIES.md"):
            text = (REPO_ROOT / relative).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"[A-Za-z]:\\", relative)


if __name__ == "__main__":
    unittest.main()
