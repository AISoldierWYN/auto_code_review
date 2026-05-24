"""End-to-end review pipeline — orchestrates Stage 1 modules.

```
diff_text + workspace + rules_dir + skill
        │
        ▼
  parse_unified_diff  ────►  list[FileChange]
  load_rules          ────►  list[Rule]
  filter_rules        ────►  list[Rule]  (recalled)
  build_prompts       ────►  Prompts
  AgentRunner.run     ────►  raw agent text
  parse_agent_output  ────►  ParsedOutput (findings, summary)
  build_report        ────►  ReviewReport
```
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from ai_code_review.diff.parser import parse_unified_diff
from ai_code_review.diff.sources import ChangeBundle
from ai_code_review.models.diff import FileChange
from ai_code_review.models.finding import Finding, Summary
from ai_code_review.models.review import Author, ReviewReport
from ai_code_review.models.rule import Rule
from ai_code_review.report.builder import ReportBuildInput, build_report
from ai_code_review.review.agent import AgentRunner
from ai_code_review.review.parser import parse_agent_output
from ai_code_review.review.prompt import build_prompts, normalize_review_language
from ai_code_review.rules.loader import load_rules
from ai_code_review.rules.recaller import recall_rules

_NO_RULES_SUMMARY = (
    "No applicable review rules matched this diff, so the rule-driven review "
    "did not run the agent."
)
_NO_RULES_SUMMARY_ZH = "没有匹配到适用于该 diff 的 review 规则，因此未运行规则驱动的 AI review。"


@dataclass(frozen=True)
class ReviewInput:
    """Inputs to one review run.

    ``diff_text`` is the actual unified-diff content (so the pipeline doesn't
    care whether it came from a file, GitHub, or a stream). ``diff_source_id``
    is what the UI displays — for a local file it's the path; for a GitHub
    PR it's the URL.
    """

    diff_text: str
    workspace: Path
    rules_dir: Path
    skill_path: Path
    model: str
    diff_source_id: str = ""
    title: str = ""
    author: Author | None = None
    branch: str | None = None
    target: str | None = None
    repo: str | None = None
    description: str | None = None
    review_language: str = "en"

    @classmethod
    def from_local_file(
        cls,
        diff_path: Path,
        workspace: Path,
        rules_dir: Path,
        skill_path: Path,
        model: str,
        review_language: str = "en",
        **kwargs: object,
    ) -> ReviewInput:
        """Convenience constructor — reads diff text from a local file."""
        return cls(
            diff_text=diff_path.read_text(encoding="utf-8"),
            workspace=workspace,
            rules_dir=rules_dir,
            skill_path=skill_path,
            model=model,
            review_language=normalize_review_language(review_language),
            diff_source_id=str(diff_path),
            title=kwargs.pop("title", "") or diff_path.stem,  # type: ignore[arg-type]
            **kwargs,  # type: ignore[arg-type]
        )

    @classmethod
    def from_bundle(
        cls,
        bundle: ChangeBundle,
        workspace: Path,
        rules_dir: Path,
        skill_path: Path,
        model: str,
        review_language: str = "en",
    ) -> ReviewInput:
        """Convenience constructor — accepts a fetched :class:`ChangeBundle`."""
        # The DiffSource Author and the model Author have the same shape; we
        # convert explicitly to avoid coupling models/ to diff/sources/.
        author = None
        if bundle.author is not None:
            author = Author(
                name=bundle.author.name,
                role=bundle.author.role,
                initials=bundle.author.initials,
            )
        return cls(
            diff_text=bundle.diff_text,
            workspace=workspace,
            rules_dir=rules_dir,
            skill_path=skill_path,
            model=model,
            review_language=normalize_review_language(review_language),
            diff_source_id=bundle.source_id,
            title=bundle.title,
            author=author,
            branch=bundle.branch,
            target=bundle.target,
            repo=bundle.repo,
            description=bundle.description,
        )


def _build_pipeline_report(
    inp: ReviewInput,
    diff: list[FileChange],
    findings: list[Finding],
    summary: Summary,
    rules_used: list[Rule],
    scanned_seconds: float,
    rules_total: int,
    rules_dropped_by_l4: tuple[str, ...] = (),
) -> ReviewReport:
    title = inp.title or "review"
    return build_report(
        ReportBuildInput(
            diff=diff,
            findings=findings,
            summary=summary,
            rules_used=rules_used,
            diff_path=inp.diff_source_id,
            title=title,
            model=inp.model,
            scanned_seconds=scanned_seconds,
            rules_total=rules_total,
            rules_after_filter=len(rules_used),
            rules_dropped_by_l4=rules_dropped_by_l4,
            review_language=inp.review_language,
            author=inp.author,
            branch=inp.branch,
            target=inp.target,
            repo=inp.repo,
        )
    )


async def run_review(inp: ReviewInput, runner: AgentRunner) -> ReviewReport:
    """Run the full Stage 1 pipeline and return a ReviewReport."""
    skill_text = inp.skill_path.read_text(encoding="utf-8")

    diff = parse_unified_diff(inp.diff_text)
    all_rules = load_rules(inp.rules_dir)
    recall = recall_rules(all_rules, diff, diff_text=inp.diff_text)
    recalled = list(recall.rules)

    if not recalled:
        no_rules_summary = (
            _NO_RULES_SUMMARY_ZH
            if normalize_review_language(inp.review_language) == "zh"
            else _NO_RULES_SUMMARY
        )
        return _build_pipeline_report(
            inp=inp,
            diff=diff,
            findings=[],
            summary=Summary(text=no_rules_summary),
            rules_used=[],
            scanned_seconds=0.0,
            rules_total=len(all_rules),
            rules_dropped_by_l4=recall.dropped_by_l4,
        )

    prompts = build_prompts(
        skill=skill_text,
        rules=recalled,
        diff_text=inp.diff_text,
        review_language=inp.review_language,
    )

    started = time.monotonic()
    agent_result = await runner.run(prompts, inp.workspace)
    elapsed = time.monotonic() - started

    parsed = parse_agent_output(agent_result.text)

    return _build_pipeline_report(
        inp=inp,
        diff=diff,
        findings=list(parsed.findings),
        summary=parsed.summary,
        rules_used=recalled,
        scanned_seconds=elapsed,
        rules_total=len(all_rules),
        rules_dropped_by_l4=recall.dropped_by_l4,
    )
