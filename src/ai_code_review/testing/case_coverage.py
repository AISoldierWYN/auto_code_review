"""Case coverage reports for Stage 2 rule recall quality."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ai_code_review.diff.parser import parse_unified_diff
from ai_code_review.models.rule import Rule
from ai_code_review.rules.loader import load_rules
from ai_code_review.rules.recaller import DEFAULT_MAX_RULES, recall_rules
from ai_code_review.testing.cases import CaseFixture


@dataclass(frozen=True)
class CaseRecallMiss:
    """One expected rule that did not survive recall for a case."""

    case_name: str
    rule_id: str
    reason: str


@dataclass(frozen=True)
class CaseRecallSummary:
    """Per-case recall summary used by human reports and tests."""

    case_name: str
    expected_rule_ids: tuple[str, ...]
    recalled_rule_ids: tuple[str, ...]
    missed_rule_ids: tuple[str, ...]


@dataclass(frozen=True)
class CaseCoverageReport:
    """Rule-to-case coverage plus expected-rule recall misses."""

    total_rules: int
    total_cases: int
    cases_with_expected: int
    total_expected_findings: int
    covered_rule_ids: tuple[str, ...]
    uncovered_rule_ids: tuple[str, ...]
    unknown_expected_rule_ids: tuple[str, ...]
    cases_by_rule: dict[str, tuple[str, ...]]
    cases_without_expected: tuple[str, ...]
    recall_misses: tuple[CaseRecallMiss, ...]
    case_summaries: tuple[CaseRecallSummary, ...]


def _sorted_unique(values: list[str] | set[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def build_case_coverage_report(
    rules: list[Rule],
    cases: list[CaseFixture],
    *,
    max_rules: int | None = DEFAULT_MAX_RULES,
) -> CaseCoverageReport:
    """Build a case coverage report and verify expected rules are recalled.

    ``rules`` is the production rule inventory used for coverage accounting.
    Each case still loads its own ``case.rules_dir`` for recall validation, so
    case-local rule fixtures keep working.
    """
    production_rule_ids = {rule.rule_id for rule in rules}
    expected_rule_ids: set[str] = set()
    cases_by_rule: defaultdict[str, set[str]] = defaultdict(set)
    cases_without_expected: list[str] = []
    recall_misses: list[CaseRecallMiss] = []
    case_summaries: list[CaseRecallSummary] = []
    total_expected_findings = 0

    for case in cases:
        case_expected_ids = [finding.rule_id for finding in case.expected.findings]
        total_expected_findings += len(case_expected_ids)

        if not case_expected_ids:
            cases_without_expected.append(case.name)

        for rule_id in case_expected_ids:
            expected_rule_ids.add(rule_id)
            cases_by_rule[rule_id].add(case.name)

        diff_text = case.diff_path.read_text(encoding="utf-8")
        diff = parse_unified_diff(diff_text)
        case_rules = load_rules(case.rules_dir)
        case_rule_ids = {rule.rule_id for rule in case_rules}
        recalled_ids = {
            rule.rule_id
            for rule in recall_rules(
                case_rules,
                diff,
                diff_text=diff_text,
                max_rules=max_rules,
            ).rules
        }

        missed_ids: list[str] = []
        for rule_id in case_expected_ids:
            if rule_id not in case_rule_ids:
                recall_misses.append(
                    CaseRecallMiss(
                        case_name=case.name,
                        rule_id=rule_id,
                        reason="rule_not_loaded",
                    )
                )
                missed_ids.append(rule_id)
            elif rule_id not in recalled_ids:
                recall_misses.append(
                    CaseRecallMiss(
                        case_name=case.name,
                        rule_id=rule_id,
                        reason="not_recalled",
                    )
                )
                missed_ids.append(rule_id)

        case_summaries.append(
            CaseRecallSummary(
                case_name=case.name,
                expected_rule_ids=_sorted_unique(case_expected_ids),
                recalled_rule_ids=_sorted_unique(recalled_ids),
                missed_rule_ids=_sorted_unique(missed_ids),
            )
        )

    covered_rule_ids = production_rule_ids & expected_rule_ids
    unknown_expected_rule_ids = expected_rule_ids - production_rule_ids
    sorted_cases_by_rule = {
        rule_id: tuple(sorted(case_names))
        for rule_id, case_names in sorted(cases_by_rule.items())
    }

    return CaseCoverageReport(
        total_rules=len(production_rule_ids),
        total_cases=len(cases),
        cases_with_expected=len(cases) - len(cases_without_expected),
        total_expected_findings=total_expected_findings,
        covered_rule_ids=_sorted_unique(covered_rule_ids),
        uncovered_rule_ids=_sorted_unique(production_rule_ids - expected_rule_ids),
        unknown_expected_rule_ids=_sorted_unique(unknown_expected_rule_ids),
        cases_by_rule=sorted_cases_by_rule,
        cases_without_expected=tuple(sorted(cases_without_expected)),
        recall_misses=tuple(recall_misses),
        case_summaries=tuple(sorted(case_summaries, key=lambda summary: summary.case_name)),
    )


def _markdown_id_rows(ids: tuple[str, ...]) -> list[str]:
    if not ids:
        return ["| (none) |"]
    return [f"| {rule_id} |" for rule_id in ids]


def render_case_coverage_markdown(report: CaseCoverageReport) -> str:
    """Render a compact Markdown case coverage report."""
    lines = [
        "# Case Coverage",
        "",
        f"Total rules: **{report.total_rules}**",
        f"Total cases: **{report.total_cases}**",
        f"Cases with expected findings: **{report.cases_with_expected}**",
        f"Expected findings: **{report.total_expected_findings}**",
        f"Rules covered by cases: **{len(report.covered_rule_ids)}**",
        f"Expected recall misses: **{len(report.recall_misses)}**",
        "",
        "## Covered Rules",
        "",
        "| rule_id | cases |",
        "| --- | --- |",
    ]
    if report.covered_rule_ids:
        lines.extend(
            f"| {rule_id} | {', '.join(report.cases_by_rule.get(rule_id, ())) or '-'} |"
            for rule_id in report.covered_rule_ids
        )
    else:
        lines.append("| (none) | - |")
    lines.extend(
        [
            "",
            "## Rules Without Cases",
            "",
            "| rule_id |",
            "| --- |",
        ]
    )
    lines.extend(_markdown_id_rows(report.uncovered_rule_ids))
    lines.extend(
        [
            "",
            "## Unknown Expected Rules",
            "",
            "| rule_id |",
            "| --- |",
        ]
    )
    lines.extend(_markdown_id_rows(report.unknown_expected_rule_ids))
    lines.extend(["", "## Recall Misses", ""])
    if report.recall_misses:
        lines.append("| case | rule_id | reason |")
        lines.append("| --- | --- | --- |")
        for miss in report.recall_misses:
            lines.append(f"| {miss.case_name} | {miss.rule_id} | {miss.reason} |")
    else:
        lines.append("No recall misses.")
    lines.append("")
    return "\n".join(lines)
