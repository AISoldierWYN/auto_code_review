"""Pipeline orchestration tests using a mock AgentRunner.

These tests assert the wiring: that ReviewInput → diff parsing → rule
filter → prompt building → agent call → output parsing → report builder
flows correctly. The agent's text is faked, so no API call is made.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

from ai_code_review.pipeline import ReviewInput, run_review
from ai_code_review.review.agent import AgentRunResult
from ai_code_review.review.prompt import Prompts

_FAKE_AGENT_OUTPUT = dedent(
    """\
    ```finding
    rule_id: RULE-RESOURCE-001
    file: examples/stage_1_demo/cache_loader.py
    line: 11
    severity: critical
    category: resource
    confidence: 0.91
    title: open() without with
    body: load_cache opens a file but does not wrap it in a with block.
    suggestion_kind: patch
    suggestion_remove:
      - "    f = open(path, \\"r\\", encoding=\\"utf-8\\")"
    suggestion_add:
      - "    with open(path, \\"r\\", encoding=\\"utf-8\\") as f:"
    suggestion_text: ""
    ```

    ```summary
    text: Adds load_cache(); introduces a fd-leak that should be fixed.
    ```

    END_OF_REVIEW
    """
)


@dataclass
class _FakeRunner:
    captured: list[Prompts]

    async def run(self, prompts: Prompts, workspace: Path) -> AgentRunResult:
        self.captured.append(prompts)
        return AgentRunResult(text=_FAKE_AGENT_OUTPUT, is_error=False, used_tools=("Read",))


class _FailingRunner:
    async def run(self, prompts: Prompts, workspace: Path) -> AgentRunResult:
        raise AssertionError("runner should not be called when no rules are recalled")


def test_pipeline_end_to_end_with_fake_runner(tmp_path: Path) -> None:
    # Use the bundled demo case as fixture.
    project_root = Path(__file__).resolve().parents[2]
    case_dir = project_root / "tests" / "cases" / "case_resource_leak"

    runner = _FakeRunner(captured=[])

    review_input = ReviewInput.from_local_file(
        diff_path=case_dir / "change.diff",
        workspace=case_dir / "workspace",
        rules_dir=case_dir / "rules",
        skill_path=project_root / "skills" / "code_review.md",
        model="glm-5",
        title="demo",
    )

    report = asyncio.run(run_review(review_input, runner))

    # Pipeline wired through: report is built.
    assert report.schema_version == "1.0"
    assert report.review.files_changed == 1
    assert report.review.additions == 11
    assert len(report.findings) == 1
    f = report.findings[0]
    assert f.rule_id == "RULE-RESOURCE-001"
    assert f.id == "c1"
    # Rationale was filled in by the report builder from the matched rule.
    assert f.rationale.rule_source_type == "typical_case"

    # Prompts received by the runner contain the recalled rule and the diff.
    assert len(runner.captured) == 1
    captured = runner.captured[0]
    assert "RULE-RESOURCE-001" in captured.user_prompt
    assert "+    f = open(" in captured.user_prompt
    assert "# SKILL" not in captured.user_prompt  # SKILL is in system_prompt only
    # SKILL frontmatter title -> system prompt
    assert "code_review" in captured.system_prompt or "Role" in captured.system_prompt


def test_pipeline_skips_agent_when_no_rules_recalled(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    case_dir = project_root / "tests" / "cases" / "case_resource_leak"

    review_input = ReviewInput.from_local_file(
        diff_path=case_dir / "change.diff",
        workspace=case_dir / "workspace",
        rules_dir=tmp_path / "empty_rules",
        skill_path=project_root / "skills" / "code_review.md",
        model="glm-5",
        title="demo",
    )

    report = asyncio.run(run_review(review_input, _FailingRunner()))

    assert report.findings == ()
    assert report.review.rules_total == 0
    assert report.review.rules_after_filter == 0
    assert "No applicable review rules" in report.review.summary
