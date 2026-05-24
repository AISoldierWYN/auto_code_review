"""Rule inventory and health checks for Stage 2 rule assets."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from ai_code_review.models.rule import Rule


@dataclass(frozen=True)
class RuleAuditWarning:
    """Non-fatal rule quality issue surfaced by the Stage 2 audit."""

    rule_id: str
    code: str
    message: str


@dataclass(frozen=True)
class RuleInventory:
    total: int
    by_source: dict[str, int]
    by_category: dict[str, int]
    by_severity: dict[str, int]
    by_language: dict[str, int]
    warnings: tuple[RuleAuditWarning, ...]


def _sorted_counter(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _warnings_for_rule(rule: Rule) -> list[RuleAuditWarning]:
    warnings: list[RuleAuditWarning] = []

    if not rule.recall.keywords and not rule.recall.regexes:
        warnings.append(
            RuleAuditWarning(
                rule_id=rule.rule_id,
                code="missing_recall_hints",
                message="rule has no recall.keywords or recall.regexes, so L3 cannot narrow it",
            )
        )

    if rule.source.type == "bug_history":
        if rule.original_case is None:
            warnings.append(
                RuleAuditWarning(
                    rule_id=rule.rule_id,
                    code="missing_original_case",
                    message="bug_history rule should keep original_case evidence",
                )
            )
        else:
            if not rule.original_case.bug_link:
                warnings.append(
                    RuleAuditWarning(
                        rule_id=rule.rule_id,
                        code="missing_bug_link",
                        message="bug_history original_case should include bug_link",
                    )
                )
            if not rule.original_case.fix_diff:
                warnings.append(
                    RuleAuditWarning(
                        rule_id=rule.rule_id,
                        code="missing_fix_diff",
                        message="bug_history original_case should include the key fix_diff",
                    )
                )

    if any(path in {"*", "**", "**/*"} for path in rule.applies_to.paths):
        warnings.append(
            RuleAuditWarning(
                rule_id=rule.rule_id,
                code="broad_path_scope",
                message="rule applies_to.paths is very broad; consider narrowing to reduce noise",
            )
        )

    return warnings


def build_rule_inventory(rules: Iterable[Rule]) -> RuleInventory:
    """Return counts and non-fatal quality warnings for a rule collection."""
    rules_list = list(rules)
    source_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    severity_counter: Counter[str] = Counter()
    language_counter: Counter[str] = Counter()
    warnings: list[RuleAuditWarning] = []

    for rule in rules_list:
        source_counter[rule.source.type] += 1
        category_counter[rule.category] += 1
        severity_counter[rule.severity] += 1
        for language in rule.applies_to.languages:
            language_counter[language] += 1
        warnings.extend(_warnings_for_rule(rule))

    return RuleInventory(
        total=len(rules_list),
        by_source=_sorted_counter(source_counter),
        by_category=_sorted_counter(category_counter),
        by_severity=_sorted_counter(severity_counter),
        by_language=_sorted_counter(language_counter),
        warnings=tuple(warnings),
    )


def _markdown_table(title: str, rows: dict[str, int]) -> list[str]:
    out = [f"## {title}", "", "| key | count |", "| --- | ---: |"]
    if rows:
        out.extend(f"| {key} | {count} |" for key, count in rows.items())
    else:
        out.append("| (none) | 0 |")
    return out


def render_rule_inventory_markdown(inventory: RuleInventory) -> str:
    """Render a compact Markdown health report for humans."""
    lines = [
        "# Rule Inventory",
        "",
        f"Total rules: **{inventory.total}**",
        "",
    ]
    lines.extend(_markdown_table("By Source", inventory.by_source))
    lines.append("")
    lines.extend(_markdown_table("By Category", inventory.by_category))
    lines.append("")
    lines.extend(_markdown_table("By Severity", inventory.by_severity))
    lines.append("")
    lines.extend(_markdown_table("By Language", inventory.by_language))
    lines.append("")
    lines.append("## Warnings")
    lines.append("")
    if inventory.warnings:
        lines.append("| rule_id | code | message |")
        lines.append("| --- | --- | --- |")
        for warning in inventory.warnings:
            lines.append(
                f"| {warning.rule_id} | {warning.code} | {warning.message} |"
            )
    else:
        lines.append("No warnings.")
    lines.append("")
    return "\n".join(lines)
