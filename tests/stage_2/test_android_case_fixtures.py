"""Checks for Android end-to-end case fixtures under tests/cases."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_code_review.diff.parser import parse_unified_diff
from ai_code_review.rules.loader import load_rules
from ai_code_review.rules.recaller import recall_rules
from ai_code_review.testing.cases import CaseFixture, discover_cases

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CASES_ROOT = PROJECT_ROOT / "tests" / "cases"
RULES_ROOT = PROJECT_ROOT / "rules"


def _android_cases() -> list[CaseFixture]:
    return [
        case
        for case in discover_cases(CASES_ROOT, fallback_rules_dir=RULES_ROOT)
        if case.name.startswith("case_android_")
    ]


def test_android_cases_are_discoverable() -> None:
    cases = _android_cases()

    assert len(cases) >= 6
    assert {case.name for case in cases} >= {
        "case_android_app_main_thread_refresh_io",
        "case_android_app_cursor_leak_profile_lookup",
        "case_android_app_pending_intent_mutability",
        "case_android_app_webview_bridge_untrusted_url",
        "case_android_app_sql_rawquery_injection",
        "case_android_fwk_binder_identity_restore",
    }


@pytest.mark.parametrize("case", _android_cases(), ids=lambda c: c.name)
def test_android_case_expected_rules_are_recalled(case: CaseFixture) -> None:
    diff_text = case.diff_path.read_text(encoding="utf-8")
    diff = parse_unified_diff(diff_text)
    rules = load_rules(case.rules_dir)

    result = recall_rules(rules, diff, diff_text=diff_text)
    recalled_ids = {rule.rule_id for rule in result.rules}

    assert diff, f"{case.name} should contain a parseable diff"
    for expected in case.expected.findings:
        assert expected.rule_id in recalled_ids
