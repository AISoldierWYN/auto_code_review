"""Stage 2 file-level review shard planning."""

from __future__ import annotations

from pathlib import Path

from ai_code_review.review.shards import (
    plan_file_review_shards,
    render_review_shard_plan_markdown,
    split_unified_diff_by_file,
)
from ai_code_review.rules.loader import load_rules

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CASES_ROOT = PROJECT_ROOT / "tests" / "cases"
RULES_ROOT = PROJECT_ROOT / "rules"


def _case_diff(name: str) -> str:
    return (CASES_ROOT / name / "change.diff").read_text(encoding="utf-8")


def test_split_unified_diff_by_file_keeps_each_git_section_parseable() -> None:
    diff_text = "\n".join(
        [
            _case_diff("case_android_app_main_thread_refresh_io"),
            _case_diff("case_android_app_zip_slip_theme_unpack"),
        ]
    )

    slices = split_unified_diff_by_file(diff_text)

    assert [slice_.paths for slice_ in slices] == [
        ("app/src/main/java/com/acme/news/FeedActivity.java",),
        ("app/src/main/java/com/acme/themes/ThemePackInstaller.java",),
    ]


def test_plan_file_review_shards_recalls_rules_per_file() -> None:
    rules = load_rules(RULES_ROOT)
    diff_text = "\n".join(
        [
            _case_diff("case_android_app_main_thread_refresh_io"),
            _case_diff("case_android_app_zip_slip_theme_unpack"),
        ]
    )

    plan = plan_file_review_shards(rules, diff_text)

    assert plan.total_files == 2
    assert plan.skipped_paths == ()
    assert [shard.paths for shard in plan.shards] == [
        ("app/src/main/java/com/acme/news/FeedActivity.java",),
        ("app/src/main/java/com/acme/themes/ThemePackInstaller.java",),
    ]
    assert [rule.rule_id for rule in plan.shards[0].rules] == ["RULE-ANDROID-APP-001"]
    assert [rule.rule_id for rule in plan.shards[1].rules] == ["RULE-ANDROID-APP-013"]


def test_plan_file_review_shards_skips_files_without_recalled_rules() -> None:
    rules = load_rules(RULES_ROOT)
    diff_text = _case_diff("case_android_app_zip_slip_safe_unpack")

    plan = plan_file_review_shards(rules, diff_text)

    assert plan.shards == ()
    assert plan.skipped_paths == (
        "app/src/main/java/com/acme/themes/SafeThemePackInstaller.java",
    )


def test_plan_file_review_shards_can_include_empty_files_for_diagnostics() -> None:
    rules = load_rules(RULES_ROOT)
    diff_text = _case_diff("case_android_app_zip_slip_safe_unpack")

    plan = plan_file_review_shards(rules, diff_text, include_empty=True)

    assert len(plan.shards) == 1
    assert plan.shards[0].rules == ()
    assert plan.skipped_paths == ()


def test_review_shard_markdown_lists_rules_and_skipped_files() -> None:
    rules = load_rules(RULES_ROOT)
    diff_text = "\n".join(
        [
            _case_diff("case_android_app_zip_slip_theme_unpack"),
            _case_diff("case_android_app_zip_slip_safe_unpack"),
        ]
    )

    plan = plan_file_review_shards(rules, diff_text)
    markdown = render_review_shard_plan_markdown(plan)

    assert "# Review Shard Plan" in markdown
    assert "RULE-ANDROID-APP-013" in markdown
    assert "SafeThemePackInstaller.java" in markdown
