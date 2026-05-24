"""Stage 2 case coverage and expected-rule recall quality."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from ai_code_review.rules.loader import load_rules
from ai_code_review.testing.case_coverage import (
    build_case_coverage_report,
    render_case_coverage_markdown,
)
from ai_code_review.testing.cases import discover_cases

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CASES_ROOT = PROJECT_ROOT / "tests" / "cases"
RULES_ROOT = PROJECT_ROOT / "rules"


def test_current_cases_cover_seed_rules_and_recall_expected_rules() -> None:
    rules = load_rules(RULES_ROOT)
    cases = discover_cases(CASES_ROOT, fallback_rules_dir=RULES_ROOT)

    report = build_case_coverage_report(rules, cases)

    assert report.total_cases >= 7
    assert report.total_rules >= 19
    assert report.total_expected_findings >= 7
    assert "RULE-ANDROID-APP-001" in report.covered_rule_ids
    assert report.cases_by_rule["RULE-ANDROID-APP-001"] == (
        "case_android_app_main_thread_refresh_io",
    )
    assert "RULE-ANDROID-APP-003" in report.uncovered_rule_ids
    assert report.unknown_expected_rule_ids == ()
    assert report.recall_misses == ()


def test_case_coverage_can_be_limited_to_android_cases() -> None:
    rules = load_rules(RULES_ROOT)
    cases = [
        case
        for case in discover_cases(CASES_ROOT, fallback_rules_dir=RULES_ROOT)
        if case.name.startswith("case_android_")
    ]

    report = build_case_coverage_report(rules, cases)

    assert report.total_cases >= 6
    assert "RULE-RESOURCE-001" in report.uncovered_rule_ids
    assert "RULE-ANDROID-FWK-001" in report.covered_rule_ids
    assert report.recall_misses == ()


def test_case_coverage_reports_recall_miss_when_signal_does_not_match(
    tmp_path: Path,
) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "RULE-X-001.yaml").write_text(
        dedent(
            """\
            rule_id: RULE-X-001
            title: demo
            category: resource
            severity: critical
            source:
              type: typical_case
              refs: [demo]
            applies_to:
              languages: [java]
              paths: ["src/**/*.java"]
            trigger:
              description: demo
              signals: [needle]
            risk: risk
            suggestion: fix
            recall:
              keywords: [needle]
            """
        ),
        encoding="utf-8",
    )

    case_dir = tmp_path / "case_demo"
    workspace = case_dir / "workspace" / "src"
    workspace.mkdir(parents=True)
    (workspace / "Demo.java").write_text("class Demo { }\n", encoding="utf-8")
    (case_dir / "change.diff").write_text(
        dedent(
            """\
            diff --git a/src/Demo.java b/src/Demo.java
            --- a/src/Demo.java
            +++ b/src/Demo.java
            @@ -1,2 +1,3 @@
             class Demo {
            +  void changed() {}
             }
            """
        ),
        encoding="utf-8",
    )
    (case_dir / "case.yaml").write_text(
        dedent(
            """\
            name: case_demo
            description: expected rule is not recalled because L3 misses
            expected:
              findings:
                - rule_id: RULE-X-001
                  file: src/Demo.java
                  line_range: 2
            """
        ),
        encoding="utf-8",
    )

    rules = load_rules(rules_dir)
    cases = discover_cases(tmp_path, fallback_rules_dir=rules_dir)
    report = build_case_coverage_report(rules, cases)

    assert [(miss.case_name, miss.rule_id, miss.reason) for miss in report.recall_misses] == [
        ("case_demo", "RULE-X-001", "not_recalled")
    ]
    assert report.case_summaries[0].missed_rule_ids == ("RULE-X-001",)


def test_case_coverage_reports_unknown_expected_rule(tmp_path: Path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    case_dir = tmp_path / "case_demo"
    (case_dir / "workspace").mkdir(parents=True)
    (case_dir / "workspace" / "x.py").write_text("print('x')\n", encoding="utf-8")
    (case_dir / "change.diff").write_text(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-print('a')\n+print('x')\n",
        encoding="utf-8",
    )
    (case_dir / "case.yaml").write_text(
        dedent(
            """\
            name: case_demo
            description: unknown rule
            expected:
              findings:
                - rule_id: RULE-MISSING-001
                  file: x.py
                  line_range: 1
            """
        ),
        encoding="utf-8",
    )

    report = build_case_coverage_report(
        load_rules(rules_dir),
        discover_cases(tmp_path, fallback_rules_dir=rules_dir),
    )

    assert report.unknown_expected_rule_ids == ("RULE-MISSING-001",)
    assert [(miss.rule_id, miss.reason) for miss in report.recall_misses] == [
        ("RULE-MISSING-001", "rule_not_loaded")
    ]


def test_case_coverage_markdown_includes_misses_and_uncovered_rules() -> None:
    rules = load_rules(RULES_ROOT)
    cases = discover_cases(CASES_ROOT, fallback_rules_dir=RULES_ROOT)
    report = build_case_coverage_report(rules, cases)

    markdown = render_case_coverage_markdown(report)

    assert "# Case Coverage" in markdown
    assert "RULE-ANDROID-APP-001" in markdown
    assert "RULE-ANDROID-APP-003" in markdown
    assert "No recall misses." in markdown
