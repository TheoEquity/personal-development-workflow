from pathlib import Path
import unittest


TEXT = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")


class WritingSpecsContractTests(unittest.TestCase):
    def test_supports_light_and_full_profiles(self):
        self.assertIn("profile=light", TEXT)
        self.assertIn("profile=full", TEXT)
        self.assertIn("Direct 不调用", TEXT)

    def test_light_spec_is_small(self):
        for required in ("问题", "触发", "期望行为", "范围", "完成条件"):
            self.assertIn(required, TEXT)

    def test_full_spec_supports_system_development_without_forcing_test_draft(self):
        self.assertIn("从零开发完整系统", TEXT)
        self.assertIn("正式测试稿按风险决定", TEXT)
        self.assertNotIn("REQUIRED SUB-SKILL", TEXT)
        self.assertIn("不强制六列表格", TEXT)


if __name__ == "__main__":
    unittest.main()
