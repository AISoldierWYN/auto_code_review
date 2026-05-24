"""Tests for platform-neutral review comment formatting."""

from __future__ import annotations

from ai_code_review.publish.format import (
    build_inline_comment_text,
    build_summary_comment,
    comment_marker,
    contains_ai_review_marker,
    review_fingerprint,
)


def _review() -> dict:
    return {
        "review": {
            "title": "Demo",
            "repo": "acme/widgets",
            "diff_path": "https://github.com/acme/widgets/pull/7",
            "summary": "One risky change needs attention.",
            "metadata": {"filtered_findings": [{"reason": "duplicate"}]},
        },
        "findings": [
            {
                "rule_id": "RULE-ANDROID-APP-001",
                "severity": "critical",
                "category": "performance",
                "file": "app/src/main/java/com/acme/Foo.java",
                "line": 42,
                "confidence": 0.91,
                "title": "Main-thread network request",
                "body": "Network I/O blocks the UI thread.",
            },
            {
                "rule_id": "RULE-ANDROID-APP-002",
                "severity": "warning",
                "category": "security",
                "file": "app/src/main/java/com/acme/Bar.java",
                "line": 9,
                "title": "Unsafe bridge",
                "body": "Bridge is exposed before origin checks.",
            },
        ],
    }


def test_fingerprint_is_stable_for_same_findings_in_different_order() -> None:
    review = _review()
    reordered = _review()
    reordered["findings"] = list(reversed(reordered["findings"]))

    assert review_fingerprint(review) == review_fingerprint(reordered)


def test_summary_comment_contains_marker_counts_and_filtered_count() -> None:
    review = _review()
    fingerprint = review_fingerprint(review)

    body = build_summary_comment(review, fingerprint=fingerprint)

    assert comment_marker(fingerprint) in body
    assert contains_ai_review_marker(body)
    assert "Findings: **2** (critical 1, warning 1, suggestion 0)" in body
    assert "Filtered model findings: **1**" in body
    assert "`RULE-ANDROID-APP-001`" in body
    assert "confidence=0.91" in body


def test_inline_comment_text_is_compact_and_rule_backed() -> None:
    finding = _review()["findings"][0]

    body = build_inline_comment_text(finding)

    assert body.startswith("**critical** `RULE-ANDROID-APP-001`")
    assert "Network I/O blocks the UI thread." in body
