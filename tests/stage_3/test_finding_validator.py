"""Stage 3 finding validation and noise filtering."""

from __future__ import annotations

from dataclasses import replace

from ai_code_review.diff.parser import parse_unified_diff
from ai_code_review.models.finding import Finding, Rationale
from ai_code_review.models.rule import AppliesTo, Rule, RuleSource, Trigger
from ai_code_review.review.validator import validate_and_filter_findings

_DIFF = """\
diff --git a/src/Foo.java b/src/Foo.java
--- a/src/Foo.java
+++ b/src/Foo.java
@@ -1,3 +1,5 @@
 class Foo {
+  void added() {}
   void existing() {}
+  void secondAdded() {}
 }
"""


def _rule(
    rule_id: str = "RULE-X-001",
    *,
    severity: str = "critical",
    category: str = "resource",
) -> Rule:
    return Rule(
        rule_id=rule_id,
        title="demo",
        category=category,
        severity=severity,  # type: ignore[arg-type]
        source=RuleSource(type="typical_case", refs=("ref",)),
        applies_to=AppliesTo(languages=("java",), paths=("**/*.java",)),
        trigger=Trigger(description="desc", signals=("signal",)),
        risk="risk",
        suggestion="fix",
    )


def _finding(
    rule_id: str = "RULE-X-001",
    *,
    severity: str = "critical",
    category: str = "resource",
    file: str = "src/Foo.java",
    line: int = 2,
    confidence: float = 0.9,
) -> Finding:
    return Finding(
        id="",
        rule_id=rule_id,
        severity=severity,  # type: ignore[arg-type]
        category=category,
        file=file,
        line=line,
        confidence=confidence,
        title="title",
        body="body",
        suggestion=None,
        rationale=Rationale(rule_source_type="typical_case", source_refs=()),
    )


def _diff():
    return parse_unified_diff(_DIFF)


def test_keeps_valid_finding_on_added_line() -> None:
    finding = _finding()

    result = validate_and_filter_findings((finding,), _diff(), [_rule()])

    assert result.findings == (finding,)
    assert result.filtered_findings == ()


def test_filters_unknown_rule() -> None:
    result = validate_and_filter_findings(
        (_finding(rule_id="RULE-UNKNOWN"),),
        _diff(),
        [_rule()],
    )

    assert result.findings == ()
    assert result.filtered_findings[0].reason == "unknown_rule"


def test_filters_model_severity_or_category_drift() -> None:
    severity_drift = _finding(severity="warning")
    category_drift = _finding(category="security")

    result = validate_and_filter_findings(
        (severity_drift, category_drift),
        _diff(),
        [_rule()],
    )

    assert result.findings == ()
    assert [item.reason for item in result.filtered_findings] == [
        "rule_metadata_mismatch",
        "rule_metadata_mismatch",
    ]


def test_filters_file_not_changed() -> None:
    result = validate_and_filter_findings(
        (_finding(file="src/Other.java"),),
        _diff(),
        [_rule()],
    )

    assert result.findings == ()
    assert result.filtered_findings[0].reason == "file_not_changed"


def test_filters_line_not_on_added_diff_line() -> None:
    result = validate_and_filter_findings(
        (_finding(line=3),),
        _diff(),
        [_rule()],
    )

    assert result.findings == ()
    assert result.filtered_findings[0].reason == "line_not_in_added_diff"


def test_filters_invalid_and_low_confidence() -> None:
    result = validate_and_filter_findings(
        (_finding(confidence=1.2), _finding(line=4, confidence=0.39)),
        _diff(),
        [_rule()],
    )

    assert result.findings == ()
    assert [item.reason for item in result.filtered_findings] == [
        "invalid_confidence",
        "low_confidence",
    ]


def test_filters_linter_noise_categories() -> None:
    finding = _finding(category="naming", line=2)

    result = validate_and_filter_findings(
        (finding,),
        _diff(),
        [_rule(category="naming")],
    )

    assert result.findings == ()
    assert result.filtered_findings[0].reason == "linter_noise"


def test_filters_duplicate_rule_file_line_after_first_kept() -> None:
    first = _finding()
    duplicate = replace(first, title="duplicate")

    result = validate_and_filter_findings((first, duplicate), _diff(), [_rule()])

    assert result.findings == (first,)
    assert result.filtered_findings[0].reason == "duplicate"
