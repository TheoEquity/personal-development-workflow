from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "SKILL.md"
REFERENCES = ROOT / "references"


def markdown_links(path: Path) -> list[Path]:
    text = path.read_text(encoding="utf-8")
    return [
        (path.parent / target).resolve()
        for target in re.findall(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]+)?\)", text)
        if "://" not in target
    ]


class ProgressiveRouterContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def route_row(self, stage: str) -> str:
        match = re.search(
            rf"^\|\s*`?{re.escape(stage)}`?\s*\|.*$",
            self.workflow,
            re.MULTILINE,
        )
        self.assertIsNotNone(match, f"missing route row for {stage}")
        return match.group(0)

    def test_entrypoint_is_a_thin_router(self):
        # Break caught: stage procedures are copied back into the always-loaded entrypoint.
        nonblank_lines = [line for line in self.workflow.splitlines() if line.strip()]
        self.assertLessEqual(len(nonblank_lines), 220)
        for moved_heading in (
            "**编写、评审并维护 Plan**",
            "#### 开发前远程基线门禁",
            "### 跨需求并行与持续 MR 集线",
        ):
            self.assertNotIn(moved_heading, self.workflow)

    def test_entrypoint_and_common_baseline_cover_all_change_events(self):
        # Break caught: the activation description or shared-baseline section
        # narrows the workflow to Bugs even though all requirements use the hub.
        frontmatter = self.workflow.split("---", 2)[1]
        baseline = (REFERENCES / "plan-baseline-selection.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("one or more requirements or change events", frontmatter)
        self.assertIn("shared delivery hub or MR", frontmatter)
        self.assertNotIn("Bug", frontmatter)
        for required in (
            "并发需求共同基线候选卡",
            "多个需求或变更事件并发开发",
            "本轮所有对应 Plan",
            "每个需求仍创建自己的隔离 worktree",
        ):
            self.assertIn(required, baseline)
        for legacy in ("跨 Bug", "多个 Bug", "Bug Plan", "每个 Bug"):
            self.assertNotIn(legacy, baseline)

    def test_requirement_discussion_route_has_no_future_stage_contracts(self):
        # Break caught: requirement discussion burns context on implementation/finishing rules.
        row = self.route_row("requirement_discussion")
        self.assertIn("exploring-and-grilling-requirements", row)
        self.assertIn("requirement-discussion.md", row)
        for forbidden in (
            "stage-worker-contract.md",
            "execution-contract.md",
            "plan-stage.md",
            "implementation-stage.md",
            "acceptance-stage.md",
            "integration-and-cleanup.md",
        ):
            self.assertNotIn(forbidden, row)

    def test_stage_specific_contracts_are_loaded_only_by_owning_routes(self):
        spec = self.route_row("writing_spec")
        plan = self.route_row("writing_plan")
        coding = self.route_row("tdd_coding")
        completed = self.route_row("completed")

        self.assertIn("stage-worker-contract.md", spec)
        self.assertNotIn("execution-contract.md", spec)
        self.assertIn("stage-worker-contract.md", plan)
        self.assertIn("plan-review-contract.md", plan)
        self.assertNotIn("execution-contract.md", plan)
        self.assertIn("stage-worker-contract.md", coding)
        self.assertIn("execution-contract.md", coding)
        self.assertIn("integration-and-cleanup.md", completed)

    def test_stage_transition_stops_before_loading_the_next_route(self):
        self.assertIn("阶段切换后立即停止", self.workflow)
        self.assertIn("下一轮才读取新 `current_stage` 对应行", self.workflow)
        self.assertIn("禁止提前读取其他阶段", self.workflow)

    def test_completed_request_can_restore_its_closed_cursor(self):
        # Break caught: a finished event has current_stage=completed but is absent
        # from the active-cursor query, making the completed route unreachable.
        self.assertIn("`workflow-list --state closed`", self.workflow)
        self.assertIn("明确要求已完成事件收尾", self.workflow)
        self.assertIn("唯一匹配的 closed 游标", self.workflow)

    def test_entrypoint_and_stage_reference_links_resolve(self):
        pending = [WORKFLOW]
        seen: set[Path] = set()
        while pending:
            source = pending.pop()
            if source in seen:
                continue
            seen.add(source)
            for target in markdown_links(source):
                self.assertTrue(target.is_file(), f"broken link: {source} -> {target}")
                if target.is_relative_to(ROOT) and target.suffix == ".md":
                    pending.append(target)

    def test_completed_route_owns_delivery_cleanup_safety(self):
        path = REFERENCES / "integration-and-cleanup.md"
        self.assertTrue(path.is_file(), path)
        text = path.read_text(encoding="utf-8")
        for required in (
            "清理候选卡",
            "Delivery",
            "integrated_commit",
            "git merge --no-ff",
            "是 Delivery HEAD 祖先",
            "Delivery 不动",
            "dirty/untracked",
            "不得 force",
            "不自动 Push",
            "source_ce",
            "用户对这张精确卡确认",
            "未集成 Worker 不清理",
        ):
            self.assertIn(required, text)

    def test_round_baseline_candidates_exclude_in_progress_branches(self):
        text = (REFERENCES / "plan-baseline-selection.md").read_text(encoding="utf-8")
        for required in (
            "本轮共同基线",
            "集线绿色 HEAD",
            "已完成事件 `code_ref`",
            "远端目标分支 HEAD",
            "禁止仍在开发中的需求分支",
            "进入新一轮",
        ):
            self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
