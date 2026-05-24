"""Tests for the prompt builder."""

from __future__ import annotations

from pathlib import Path

from ai_code_review.models.rule import AppliesTo, OriginalCase, Rule, RuleSource, Trigger
from ai_code_review.review.prompt import (
    Prompts,
    build_prompts,
    normalize_review_language,
)

_SKILL = "# SKILL CONTENT\nYou are a reviewer."

_RULE = Rule(
    rule_id="RULE-RESOURCE-001",
    title="open() without with",
    category="resource",
    severity="critical",
    source=RuleSource(type="typical_case", refs=("PEP-343",)),
    applies_to=AppliesTo(languages=("python",), paths=("**/*.py",)),
    trigger=Trigger(
        description="open() returned value not wrapped in with.",
        signals=("signal-1", "signal-2"),
    ),
    risk="fd leak",
    suggestion="use with",
    original_case=OriginalCase(bug_link="X", minimal_repro="m", fix_diff="f"),
)

_DIFF = "diff --git a/x.py b/x.py\n@@ -1 +1,2 @@\n a\n+b\n"


class TestBuildPrompts:
    def test_returns_prompts_dataclass(self) -> None:
        p = build_prompts(skill=_SKILL, rules=[_RULE], diff_text=_DIFF)
        assert isinstance(p, Prompts)

    def test_skill_goes_into_system_prompt(self) -> None:
        p = build_prompts(skill=_SKILL, rules=[_RULE], diff_text=_DIFF)
        assert "# SKILL CONTENT" in p.system_prompt

    def test_diff_goes_into_user_prompt(self) -> None:
        p = build_prompts(skill=_SKILL, rules=[_RULE], diff_text=_DIFF)
        assert _DIFF in p.user_prompt

    def test_review_language_instruction_goes_into_user_prompt(self) -> None:
        p = build_prompts(
            skill=_SKILL,
            rules=[_RULE],
            diff_text=_DIFF,
            review_language="zh",
        )
        assert "# OUTPUT_LANGUAGE" in p.user_prompt
        assert "Simplified Chinese" in p.user_prompt
        assert "finding.title" in p.user_prompt

    def test_rules_appear_in_user_prompt(self) -> None:
        p = build_prompts(skill=_SKILL, rules=[_RULE], diff_text=_DIFF)
        assert "RULE-RESOURCE-001" in p.user_prompt
        assert "signal-1" in p.user_prompt
        assert "signal-2" in p.user_prompt

    def test_original_case_is_excluded_from_prompt(self) -> None:
        # Per v1_plan §3.D.2: original_case is NOT injected by default.
        p = build_prompts(skill=_SKILL, rules=[_RULE], diff_text=_DIFF)
        assert "minimal_repro" not in p.user_prompt
        assert "fix_diff" not in p.user_prompt
        # The body content itself should be absent
        assert "m" not in p.user_prompt.split("RULE-RESOURCE-001")[1].split("\n# DIFF")[0] \
               or "m" in _RULE.suggestion  # tolerate substring overlap

    def test_source_refs_are_excluded_from_prompt(self) -> None:
        # source_type is included; source.refs are not — they go to the UI rationale instead.
        p = build_prompts(skill=_SKILL, rules=[_RULE], diff_text=_DIFF)
        assert "PEP-343" not in p.user_prompt

    def test_applies_to_excluded_from_prompt(self) -> None:
        # applies_to has already been consumed by the recaller; don't waste tokens.
        p = build_prompts(skill=_SKILL, rules=[_RULE], diff_text=_DIFF)
        assert "applies_to" not in p.user_prompt.lower()


class TestNoRulesCase:
    def test_no_rules_still_returns_prompts(self) -> None:
        p = build_prompts(skill=_SKILL, rules=[], diff_text=_DIFF)
        assert "# SKILL CONTENT" in p.system_prompt
        # Indicate to agent there are no rules — this prevents hallucinated findings.
        assert "no applicable rules" in p.user_prompt.lower() or "rules: []" in p.user_prompt.lower()


class TestNormalizeReviewLanguage:
    def test_accepts_chinese_aliases(self) -> None:
        assert normalize_review_language("zh-CN") == "zh"
        assert normalize_review_language("chinese") == "zh"

    def test_unknown_defaults_to_english(self) -> None:
        assert normalize_review_language("fr") == "en"


class TestBundledSkill:
    def test_uses_single_review_sentinel(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        skill = (project_root / "skills" / "code_review.md").read_text(encoding="utf-8")

        assert "END_OF_REVIEW" in skill
        assert "END_OF_FINDINGS" not in skill
        assert "emit ONLY the single line `NO_FINDINGS`" not in skill
