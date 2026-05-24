"""Validate and filter parsed findings before report rendering."""

from __future__ import annotations

from dataclasses import dataclass

from ai_code_review.models.diff import FileChange
from ai_code_review.models.finding import FilteredFinding, Finding
from ai_code_review.models.rule import Rule

DEFAULT_MIN_CONFIDENCE = 0.4
_LINTER_NOISE_CATEGORIES = {"style", "format", "formatting", "lint", "naming"}


@dataclass(frozen=True)
class FindingValidationResult:
    findings: tuple[Finding, ...]
    filtered_findings: tuple[FilteredFinding, ...]


def _added_lines_by_file(diff: list[FileChange]) -> dict[str, set[int]]:
    out: dict[str, set[int]] = {}
    for file_change in diff:
        added_lines: set[int] = set()
        for hunk in file_change.hunks:
            for line in hunk.lines:
                if line.kind == "added" and line.new_line is not None:
                    added_lines.add(line.new_line)
        out[file_change.path] = added_lines
    return out


def _drop(finding: Finding, reason: str, detail: str) -> FilteredFinding:
    return FilteredFinding(
        reason=reason,
        rule_id=finding.rule_id,
        file=finding.file,
        line=finding.line,
        detail=detail,
    )


def validate_and_filter_findings(
    findings: tuple[Finding, ...],
    diff: list[FileChange],
    rules: list[Rule],
    *,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> FindingValidationResult:
    """Return only findings safe to render.

    Stage 3 enforces the contract that findings must be bound to recalled
    rules, anchored to added diff lines, non-duplicated, and above the minimum
    confidence threshold. It also prevents the model from changing a rule's
    category or severity.
    """
    rule_index = {rule.rule_id: rule for rule in rules}
    added_lines = _added_lines_by_file(diff)
    kept: list[Finding] = []
    filtered: list[FilteredFinding] = []
    seen: set[tuple[str, str, int]] = set()

    for finding in findings:
        rule = rule_index.get(finding.rule_id)
        if rule is None:
            filtered.append(
                _drop(
                    finding,
                    "unknown_rule",
                    "finding.rule_id was not present in the recalled rule set",
                )
            )
            continue

        if finding.severity != rule.severity:
            filtered.append(
                _drop(
                    finding,
                    "rule_metadata_mismatch",
                    f"severity {finding.severity!r} does not match rule severity {rule.severity!r}",
                )
            )
            continue

        if finding.category != rule.category:
            filtered.append(
                _drop(
                    finding,
                    "rule_metadata_mismatch",
                    f"category {finding.category!r} does not match rule category {rule.category!r}",
                )
            )
            continue

        if finding.file not in added_lines:
            filtered.append(
                _drop(
                    finding,
                    "file_not_changed",
                    "finding.file is not present in this diff",
                )
            )
            continue

        if finding.line not in added_lines[finding.file]:
            filtered.append(
                _drop(
                    finding,
                    "line_not_in_added_diff",
                    "finding.line is not an added '+' line in this diff",
                )
            )
            continue

        if not 0.0 <= finding.confidence <= 1.0:
            filtered.append(
                _drop(
                    finding,
                    "invalid_confidence",
                    "finding.confidence must be between 0 and 1",
                )
            )
            continue

        if finding.confidence < min_confidence:
            filtered.append(
                _drop(
                    finding,
                    "low_confidence",
                    f"finding.confidence {finding.confidence:.2f} is below {min_confidence:.2f}",
                )
            )
            continue

        if finding.category.lower() in _LINTER_NOISE_CATEGORIES:
            filtered.append(
                _drop(
                    finding,
                    "linter_noise",
                    "linter-style findings are outside this rule-driven reviewer",
                )
            )
            continue

        key = (finding.rule_id, finding.file, finding.line)
        if key in seen:
            filtered.append(
                _drop(
                    finding,
                    "duplicate",
                    "another finding already uses the same rule_id, file, and line",
                )
            )
            continue

        seen.add(key)
        kept.append(finding)

    return FindingValidationResult(
        findings=tuple(kept),
        filtered_findings=tuple(filtered),
    )
