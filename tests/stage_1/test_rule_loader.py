"""Tests for the YAML rule loader."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from ai_code_review.models.rule import OriginalCase, RecallHints, Rule
from ai_code_review.rules.loader import RuleLoadError, load_rules


def _write(p: Path, body: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(dedent(body), encoding="utf-8")


VALID_RULE = """\
rule_id: RULE-RESOURCE-001
title: open() without with
category: resource
severity: critical
source:
  type: typical_case
  refs: ["https://docs.python.org"]
applies_to:
  languages: [python]
  paths: ["**/*.py"]
  exclude_paths: ["tests/**"]
trigger:
  description: |
    open() returned value not wrapped in with.
  signals:
    - "open(...) assigned without with"
    - "no .close() or try/finally"
risk: |
  fd leak
suggestion: |
  use with statement
original_case:
  bug_link: null
  minimal_repro: |
    f = open("x")
  fix_diff: |
    -    f = open("x")
    +    with open("x") as f:
"""


class TestLoadRules:
    def test_loads_single_rule(self, tmp_path: Path) -> None:
        _write(tmp_path / "typical_case" / "RULE-RESOURCE-001.yaml", VALID_RULE)
        rules = load_rules(tmp_path)
        assert len(rules) == 1
        rule = rules[0]
        assert isinstance(rule, Rule)
        assert rule.rule_id == "RULE-RESOURCE-001"
        assert rule.severity == "critical"
        assert rule.applies_to.languages == ("python",)
        assert rule.applies_to.paths == ("**/*.py",)
        assert rule.applies_to.exclude_paths == ("tests/**",)
        assert rule.trigger.signals[0].startswith("open(...)")
        assert isinstance(rule.original_case, OriginalCase)

    def test_loads_rules_recursively_from_subdirs(self, tmp_path: Path) -> None:
        _write(tmp_path / "typical_case" / "a.yaml", VALID_RULE)
        _write(
            tmp_path / "bug_history" / "b.yaml",
            VALID_RULE.replace("RULE-RESOURCE-001", "RULE-RESOURCE-002").replace(
                "typical_case", "bug_history"
            ),
        )
        rules = load_rules(tmp_path)
        assert {r.rule_id for r in rules} == {"RULE-RESOURCE-001", "RULE-RESOURCE-002"}

    def test_skips_non_yaml_files(self, tmp_path: Path) -> None:
        _write(tmp_path / "typical_case" / "rule.yaml", VALID_RULE)
        _write(tmp_path / "typical_case" / "README.md", "# not a rule")
        rules = load_rules(tmp_path)
        assert len(rules) == 1

    def test_empty_dir_returns_empty(self, tmp_path: Path) -> None:
        assert load_rules(tmp_path) == []

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        bad = VALID_RULE.replace("severity: critical\n", "")
        _write(tmp_path / "bad.yaml", bad)
        with pytest.raises(RuleLoadError, match="severity"):
            load_rules(tmp_path)

    def test_duplicate_rule_id_raises(self, tmp_path: Path) -> None:
        _write(tmp_path / "a.yaml", VALID_RULE)
        _write(tmp_path / "b.yaml", VALID_RULE)  # same rule_id
        with pytest.raises(RuleLoadError, match="duplicate"):
            load_rules(tmp_path)

    def test_invalid_severity_raises(self, tmp_path: Path) -> None:
        bad = VALID_RULE.replace("severity: critical", "severity: blocker")
        _write(tmp_path / "bad.yaml", bad)
        with pytest.raises(RuleLoadError, match="severity"):
            load_rules(tmp_path)

    def test_yaml_syntax_error_includes_file_path(self, tmp_path: Path) -> None:
        _write(tmp_path / "broken.yaml", "::: not valid yaml :::")
        with pytest.raises(RuleLoadError, match="broken.yaml"):
            load_rules(tmp_path)

    def test_original_case_optional(self, tmp_path: Path) -> None:
        no_oc = VALID_RULE.split("original_case:")[0]
        _write(tmp_path / "min.yaml", no_oc)
        rule = load_rules(tmp_path)[0]
        assert rule.original_case is None

    def test_recall_hints_optional(self, tmp_path: Path) -> None:
        _write(tmp_path / "min.yaml", VALID_RULE)
        rule = load_rules(tmp_path)[0]
        assert rule.recall == RecallHints()

    def test_loads_recall_hints(self, tmp_path: Path) -> None:
        with_recall = VALID_RULE.replace(
            "trigger:\n",
            "recall:\n"
            "  keywords: [\"open(\", \"close()\"]\n"
            "  regexes: [\"open\\\\s*\\\\(\"]\n"
            "trigger:\n",
        )
        _write(tmp_path / "with_recall.yaml", with_recall)

        rule = load_rules(tmp_path)[0]

        assert rule.recall.keywords == ("open(", "close()")
        assert rule.recall.regexes == ("open\\s*\\(",)

    def test_recall_hints_must_be_lists(self, tmp_path: Path) -> None:
        bad = VALID_RULE.replace(
            "trigger:\n",
            "recall:\n"
            "  keywords: \"open(\"\n"
            "trigger:\n",
        )
        _write(tmp_path / "bad.yaml", bad)

        with pytest.raises(RuleLoadError, match="recall.keywords"):
            load_rules(tmp_path)
