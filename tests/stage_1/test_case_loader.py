"""Tests for the user-provided test-case fixture loader.

The user drops a directory under ``tests/cases/case_<name>/`` and the loader
discovers it automatically. Each case bundles a diff, an after-state
workspace, applicable rules, and expected outcomes.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from ai_code_review.testing.cases import (
    CaseLoadError,
    ExpectedFinding,
    CaseFixture,
    discover_cases,
    load_case,
)


def _make_case(root: Path, name: str = "case_demo", **overrides: str) -> Path:
    case_dir = root / name
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "change.diff").write_text(
        overrides.get(
            "diff",
            "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1,2 @@\n a\n+b\n",
        ),
        encoding="utf-8",
    )
    workspace = case_dir / "workspace"
    workspace.mkdir(exist_ok=True)
    (workspace / "x.py").write_text("a\nb\n", encoding="utf-8")
    rules = case_dir / "rules"
    rules.mkdir(exist_ok=True)
    (case_dir / "case.yaml").write_text(
        overrides.get(
            "case_yaml",
            dedent(
                f"""\
                name: {name}
                description: a demo case
                expected:
                  findings:
                    - rule_id: RULE-X-001
                      file: x.py
                      line_range: [1, 5]
                  forbid_other_critical: false
                """
            ),
        ),
        encoding="utf-8",
    )
    return case_dir


class TestLoadCase:
    def test_loads_metadata(self, tmp_path: Path) -> None:
        case_dir = _make_case(tmp_path)
        case = load_case(case_dir)
        assert isinstance(case, CaseFixture)
        assert case.name == "case_demo"
        assert case.description == "a demo case"
        assert case.diff_path == case_dir / "change.diff"
        assert case.workspace_dir == case_dir / "workspace"
        assert case.rules_dir == case_dir / "rules"

    def test_parses_expected_findings(self, tmp_path: Path) -> None:
        case_dir = _make_case(tmp_path)
        case = load_case(case_dir)
        assert len(case.expected.findings) == 1
        ef = case.expected.findings[0]
        assert isinstance(ef, ExpectedFinding)
        assert ef.rule_id == "RULE-X-001"
        assert ef.file == "x.py"
        assert ef.line_range == (1, 5)

    def test_name_must_match_directory(self, tmp_path: Path) -> None:
        case_dir = _make_case(
            tmp_path,
            name="case_demo",
            case_yaml=dedent(
                """\
                name: mismatched_name
                description: x
                expected:
                  findings: []
                """
            ),
        )
        with pytest.raises(CaseLoadError, match="name"):
            load_case(case_dir)

    def test_missing_change_diff_raises(self, tmp_path: Path) -> None:
        case_dir = _make_case(tmp_path)
        (case_dir / "change.diff").unlink()
        with pytest.raises(CaseLoadError, match="change.diff"):
            load_case(case_dir)

    def test_missing_workspace_raises(self, tmp_path: Path) -> None:
        case_dir = _make_case(tmp_path)
        # Replace workspace with before/ to trigger the helpful error message.
        (case_dir / "workspace" / "x.py").unlink()
        (case_dir / "workspace").rmdir()
        (case_dir / "before").mkdir()
        with pytest.raises(CaseLoadError, match="workspace.*Stage 1.5"):
            load_case(case_dir)

    def test_line_range_single_int_is_accepted(self, tmp_path: Path) -> None:
        case_dir = _make_case(
            tmp_path,
            case_yaml=dedent(
                """\
                name: case_demo
                description: x
                expected:
                  findings:
                    - rule_id: RULE-X-001
                      file: x.py
                      line_range: 3
                """
            ),
        )
        case = load_case(case_dir)
        assert case.expected.findings[0].line_range == (3, 3)

    def test_parses_forbidden_rules_for_negative_cases(self, tmp_path: Path) -> None:
        case_dir = _make_case(
            tmp_path,
            case_yaml=dedent(
                """\
                name: case_demo
                description: x
                expected:
                  findings: []
                  forbidden_rules:
                    - RULE-X-002
                    - RULE-X-003
                """
            ),
        )

        case = load_case(case_dir)

        assert case.expected.forbidden_rule_ids == ("RULE-X-002", "RULE-X-003")


class TestRulesFallback:
    def test_case_local_rules_take_precedence(self, tmp_path: Path) -> None:
        case_dir = _make_case(tmp_path)  # creates case_dir / "rules/"
        fallback = tmp_path / "fallback_rules"
        fallback.mkdir()
        case = load_case(case_dir, fallback_rules_dir=fallback)
        assert case.rules_dir == case_dir / "rules"

    def test_falls_back_when_case_has_no_rules_dir(self, tmp_path: Path) -> None:
        case_dir = _make_case(tmp_path)
        # Remove the auto-created case-local rules dir.
        (case_dir / "rules").rmdir()
        fallback = tmp_path / "fallback_rules"
        fallback.mkdir()
        case = load_case(case_dir, fallback_rules_dir=fallback)
        assert case.rules_dir == fallback

    def test_without_fallback_returns_case_local_path_even_if_missing(
        self, tmp_path: Path
    ) -> None:
        case_dir = _make_case(tmp_path)
        (case_dir / "rules").rmdir()
        case = load_case(case_dir, fallback_rules_dir=None)
        # Path returned for caller to handle (load_rules will return [] for missing).
        assert case.rules_dir == case_dir / "rules"


class TestDiscoverCases:
    def test_discovers_multiple(self, tmp_path: Path) -> None:
        _make_case(tmp_path, name="case_one")
        _make_case(tmp_path, name="case_two")
        cases = discover_cases(tmp_path)
        names = sorted(c.name for c in cases)
        assert names == ["case_one", "case_two"]

    def test_discover_passes_fallback_to_each_case(self, tmp_path: Path) -> None:
        case_dir = _make_case(tmp_path, name="case_one")
        (case_dir / "rules").rmdir()
        fallback = tmp_path / "fallback"
        fallback.mkdir()
        cases = discover_cases(tmp_path, fallback_rules_dir=fallback)
        assert cases[0].rules_dir == fallback

    def test_ignores_non_case_dirs(self, tmp_path: Path) -> None:
        _make_case(tmp_path, name="case_real")
        (tmp_path / "README.md").write_text("not a case", encoding="utf-8")
        (tmp_path / "not_a_case").mkdir()
        cases = discover_cases(tmp_path)
        assert [c.name for c in cases] == ["case_real"]

    def test_empty_root_returns_empty(self, tmp_path: Path) -> None:
        assert discover_cases(tmp_path) == []

    def test_missing_root_returns_empty(self, tmp_path: Path) -> None:
        assert discover_cases(tmp_path / "does_not_exist") == []


class TestExpectedFindingMatcher:
    def test_line_in_range_matches(self) -> None:
        ef = ExpectedFinding(rule_id="R", file="x.py", line_range=(5, 10))
        assert ef.matches(rule_id="R", file="x.py", line=7) is True

    def test_line_at_boundary_matches(self) -> None:
        ef = ExpectedFinding(rule_id="R", file="x.py", line_range=(5, 10))
        assert ef.matches(rule_id="R", file="x.py", line=5) is True
        assert ef.matches(rule_id="R", file="x.py", line=10) is True

    def test_line_outside_range_no_match(self) -> None:
        ef = ExpectedFinding(rule_id="R", file="x.py", line_range=(5, 10))
        assert ef.matches(rule_id="R", file="x.py", line=4) is False
        assert ef.matches(rule_id="R", file="x.py", line=11) is False

    def test_wrong_rule_no_match(self) -> None:
        ef = ExpectedFinding(rule_id="R", file="x.py", line_range=(1, 5))
        assert ef.matches(rule_id="OTHER", file="x.py", line=3) is False

    def test_wrong_file_no_match(self) -> None:
        ef = ExpectedFinding(rule_id="R", file="x.py", line_range=(1, 5))
        assert ef.matches(rule_id="R", file="y.py", line=3) is False
