"""Stage 2 rule inventory and health checks."""

from __future__ import annotations

from pathlib import Path

from ai_code_review.models.rule import (
    AppliesTo,
    OriginalCase,
    RecallHints,
    Rule,
    RuleSource,
    Trigger,
)
from ai_code_review.rules.audit import (
    build_rule_inventory,
    render_rule_inventory_markdown,
)
from ai_code_review.rules.loader import load_rules

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RULES_ROOT = PROJECT_ROOT / "rules"


def _rule(
    *,
    rule_id: str = "RULE-X-001",
    source_type: str = "typical_case",
    recall: RecallHints | None = None,
    original_case: OriginalCase | None = None,
    paths: tuple[str, ...] = ("src/**/*.java",),
) -> Rule:
    return Rule(
        rule_id=rule_id,
        title="example",
        category="resource",
        severity="critical",
        source=RuleSource(type=source_type, refs=("REF-1",)),  # type: ignore[arg-type]
        applies_to=AppliesTo(languages=("java",), paths=paths),
        trigger=Trigger(description="desc", signals=("signal",)),
        risk="risk",
        suggestion="fix",
        original_case=original_case,
        recall=recall or RecallHints(keywords=("signal",)),
    )


def test_current_rules_inventory_counts_seed_assets() -> None:
    inventory = build_rule_inventory(load_rules(RULES_ROOT))

    assert inventory.total >= 19
    assert inventory.by_source["typical_case"] >= 19
    assert inventory.by_language["java"] >= 1
    assert not [
        warning
        for warning in inventory.warnings
        if warning.code == "missing_recall_hints"
    ]


def test_warns_when_rule_has_no_recall_hints() -> None:
    inventory = build_rule_inventory([_rule(recall=RecallHints())])

    assert [warning.code for warning in inventory.warnings] == [
        "missing_recall_hints"
    ]


def test_warns_when_bug_history_rule_lacks_original_evidence() -> None:
    inventory = build_rule_inventory(
        [_rule(rule_id="RULE-BUG-001", source_type="bug_history")]
    )

    assert "missing_original_case" in {warning.code for warning in inventory.warnings}


def test_bug_history_rule_with_evidence_has_no_evidence_warning() -> None:
    inventory = build_rule_inventory(
        [
            _rule(
                rule_id="RULE-BUG-001",
                source_type="bug_history",
                original_case=OriginalCase(
                    bug_link="BUG-1",
                    minimal_repro="bad();",
                    fix_diff="+ good();",
                ),
            )
        ]
    )

    codes = {warning.code for warning in inventory.warnings}
    assert "missing_original_case" not in codes
    assert "missing_bug_link" not in codes
    assert "missing_fix_diff" not in codes


def test_warns_for_overly_broad_paths() -> None:
    inventory = build_rule_inventory([_rule(paths=("**/*",))])

    assert "broad_path_scope" in {warning.code for warning in inventory.warnings}


def test_markdown_report_includes_counts_and_warnings() -> None:
    inventory = build_rule_inventory([_rule(recall=RecallHints())])

    markdown = render_rule_inventory_markdown(inventory)

    assert "# Rule Inventory" in markdown
    assert "| typical_case | 1 |" in markdown
    assert "missing_recall_hints" in markdown
