"""Tests for the rule recaller (L1 language + L2 path filtering)."""

from __future__ import annotations

from ai_code_review.models.diff import FileChange
from ai_code_review.models.rule import AppliesTo, RecallHints, Rule, RuleSource, Trigger
from ai_code_review.rules.recaller import filter_rules, recall_rules


def _rule(
    rule_id: str = "RULE-X-001",
    languages: tuple[str, ...] = ("python",),
    paths: tuple[str, ...] = ("**/*.py",),
    exclude_paths: tuple[str, ...] = (),
    severity: str = "critical",
    source_type: str = "typical_case",
    recall: RecallHints | None = None,
) -> Rule:
    return Rule(
        rule_id=rule_id,
        title="t",
        category="resource",
        severity=severity,  # type: ignore[arg-type]
        source=RuleSource(type=source_type, refs=("x",)),  # type: ignore[arg-type]
        applies_to=AppliesTo(
            languages=languages, paths=paths, exclude_paths=exclude_paths
        ),
        trigger=Trigger(description="d", signals=("s",)),
        risk="r",
        suggestion="sg",
        recall=recall or RecallHints(),
    )


def _filechange(path: str, language: str | None = None) -> FileChange:
    return FileChange(
        path=path,
        old_path=None,
        is_new_file=False,
        is_deleted_file=False,
        language=language,
        additions=1,
        deletions=0,
        hunks=(),
    )


class TestL1LanguageFilter:
    def test_language_match_keeps_rule(self) -> None:
        rules = [_rule(languages=("python",))]
        diff = [_filechange("a.py", language="python")]
        assert filter_rules(rules, diff) == rules

    def test_language_mismatch_drops_rule(self) -> None:
        rules = [_rule(languages=("go",))]
        diff = [_filechange("a.py", language="python")]
        assert filter_rules(rules, diff) == []

    def test_unknown_language_in_diff_drops_lang_specific_rule(self) -> None:
        rules = [_rule(languages=("python",))]
        diff = [_filechange("Makefile", language=None)]
        assert filter_rules(rules, diff) == []

    def test_rule_with_multiple_languages(self) -> None:
        rules = [_rule(languages=("python", "go"), paths=("**/*.py", "**/*.go"))]
        diff = [_filechange("a.go", language="go")]
        assert filter_rules(rules, diff) == rules


class TestL2PathFilter:
    def test_path_match_keeps_rule(self) -> None:
        rules = [_rule(paths=("src/**/*.py",))]
        diff = [_filechange("src/foo/bar.py", language="python")]
        assert filter_rules(rules, diff) == rules

    def test_path_no_match_drops_rule(self) -> None:
        rules = [_rule(paths=("src/api/**",))]
        diff = [_filechange("tests/foo.py", language="python")]
        assert filter_rules(rules, diff) == []

    def test_exclude_path_drops_otherwise_matching_rule(self) -> None:
        rules = [_rule(paths=("**/*.py",), exclude_paths=("tests/**",))]
        diff = [_filechange("tests/foo.py", language="python")]
        assert filter_rules(rules, diff) == []

    def test_one_file_matches_is_enough(self) -> None:
        rules = [_rule(paths=("src/**/*.py",))]
        diff = [
            _filechange("tests/foo.py", language="python"),
            _filechange("src/main.py", language="python"),
        ]
        # As long as ONE diff file matches src/**/*.py the rule is recalled.
        assert filter_rules(rules, diff) == rules


class TestCombined:
    def test_lang_and_path_both_must_pass(self) -> None:
        # rule requires python AND src/** path
        rules = [_rule(languages=("python",), paths=("src/**",))]
        diff = [_filechange("src/foo.go", language="go")]  # path ok, lang fail
        assert filter_rules(rules, diff) == []

    def test_empty_diff_returns_empty(self) -> None:
        rules = [_rule()]
        assert filter_rules(rules, []) == []

    def test_empty_rules_returns_empty(self) -> None:
        diff = [_filechange("a.py", language="python")]
        assert filter_rules([], diff) == []


class TestMultiRule:
    def test_keeps_only_passing_rules(self) -> None:
        rules = [
            _rule(rule_id="A", languages=("python",)),
            _rule(rule_id="B", languages=("go",)),
        ]
        diff = [_filechange("x.py", language="python")]
        kept = filter_rules(rules, diff)
        assert [r.rule_id for r in kept] == ["A"]


class TestL3SignalFilter:
    def test_rule_without_recall_hints_keeps_stage_1_behavior(self) -> None:
        rules = [_rule()]
        diff = [_filechange("x.py", language="python")]

        result = recall_rules(rules, diff, diff_text="+print('hello')")

        assert result.rules == tuple(rules)
        assert result.dropped_by_l4 == ()

    def test_keyword_hint_keeps_matching_rule(self) -> None:
        rules = [_rule(recall=RecallHints(keywords=("open(",)))]
        diff = [_filechange("x.py", language="python")]

        result = recall_rules(rules, diff, diff_text="+    f = open(path)")

        assert result.rules == tuple(rules)

    def test_keyword_hint_drops_rule_when_signal_absent(self) -> None:
        rules = [_rule(recall=RecallHints(keywords=("open(",)))]
        diff = [_filechange("x.py", language="python")]

        result = recall_rules(rules, diff, diff_text="+    return path")

        assert result.rules == ()

    def test_regex_hint_keeps_matching_rule(self) -> None:
        rules = [_rule(recall=RecallHints(regexes=(r"open\s*\(",)))]
        diff = [_filechange("x.py", language="python")]

        result = recall_rules(rules, diff, diff_text="+    f = open (path)")

        assert result.rules == tuple(rules)

    def test_invalid_regex_hint_is_treated_as_non_match(self) -> None:
        rules = [_rule(recall=RecallHints(regexes=("[",)))]
        diff = [_filechange("x.py", language="python")]

        result = recall_rules(rules, diff, diff_text="+    f = open(path)")

        assert result.rules == ()

    def test_legacy_filter_rules_skips_l3_for_backward_compatibility(self) -> None:
        rules = [_rule(recall=RecallHints(keywords=("open(",)))]
        diff = [_filechange("x.py", language="python")]

        assert filter_rules(rules, diff) == rules


class TestL4PriorityPruning:
    def test_prunes_to_max_rules_and_reports_dropped_ids(self) -> None:
        rules = [
            _rule(rule_id="suggestion-spec", severity="suggestion", source_type="spec"),
            _rule(rule_id="critical-typical", severity="critical", source_type="typical_case"),
            _rule(rule_id="warning-bug", severity="warning", source_type="bug_history"),
        ]
        diff = [_filechange("x.py", language="python")]

        result = recall_rules(rules, diff, diff_text="+print('x')", max_rules=2)

        assert [r.rule_id for r in result.rules] == ["critical-typical", "warning-bug"]
        assert result.dropped_by_l4 == ("suggestion-spec",)

    def test_bug_history_wins_tie_within_same_severity(self) -> None:
        rules = [
            _rule(rule_id="critical-spec", severity="critical", source_type="spec"),
            _rule(rule_id="critical-bug", severity="critical", source_type="bug_history"),
        ]
        diff = [_filechange("x.py", language="python")]

        result = recall_rules(rules, diff, diff_text="+print('x')", max_rules=1)

        assert [r.rule_id for r in result.rules] == ["critical-bug"]
        assert result.dropped_by_l4 == ("critical-spec",)

    def test_no_max_keeps_all_l3_matches(self) -> None:
        rules = [
            _rule(rule_id="A", severity="suggestion"),
            _rule(rule_id="B", severity="suggestion"),
        ]
        diff = [_filechange("x.py", language="python")]

        result = recall_rules(rules, diff, diff_text="+print('x')", max_rules=None)

        assert [r.rule_id for r in result.rules] == ["A", "B"]
        assert result.dropped_by_l4 == ()
