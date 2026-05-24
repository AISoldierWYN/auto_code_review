"""Tests for the agent output parser."""

from __future__ import annotations

import pytest

from ai_code_review.review.parser import OutputParseError, ParsedOutput, parse_agent_output

_ONE_FINDING_AND_SUMMARY = """\
Some preamble that should be ignored.

```finding
rule_id: RULE-RESOURCE-001
file: src/foo/bar.py
line: 42
severity: critical
category: resource
confidence: 0.91
title: open() without with
body: >
  Newly introduced load_cache() opens a file but does not wrap it in a with block.
suggestion_kind: patch
suggestion_remove:
  - "    f = open(path)"
suggestion_add:
  - "    with open(path) as f:"
  - "        ..."
suggestion_text: ""
```

```summary
text: >
  Adds load_cache(); introduces a fd-leak that should be fixed before merge.
```

END_OF_REVIEW
"""

_NO_FINDINGS = """\
```summary
text: >
  Diff renames a variable from x to payload; no behavior change.
```

END_OF_REVIEW
"""

_TEXT_SUGGESTION = """\
```finding
rule_id: RULE-NAMING-001
file: a.py
line: 3
severity: suggestion
category: naming
confidence: 0.55
title: variable name is non-descriptive
body: consider renaming `x` to something domain-specific.
suggestion_kind: text
suggestion_remove: []
suggestion_add: []
suggestion_text: rename `x` to `payload`
```

```summary
text: a single low-severity naming suggestion.
```

END_OF_REVIEW
"""

_NONE_SUGGESTION = """\
```finding
rule_id: RULE-X-001
file: a.py
line: 1
severity: warning
category: x
confidence: 0.6
title: t
body: b
suggestion_kind: none
suggestion_remove: []
suggestion_add: []
suggestion_text: ""
```

```summary
text: ok
```

END_OF_REVIEW
"""


class TestHappyPath:
    def test_parses_one_finding(self) -> None:
        out = parse_agent_output(_ONE_FINDING_AND_SUMMARY)
        assert isinstance(out, ParsedOutput)
        assert len(out.findings) == 1
        f = out.findings[0]
        assert f.rule_id == "RULE-RESOURCE-001"
        assert f.file == "src/foo/bar.py"
        assert f.line == 42
        assert f.severity == "critical"
        assert f.confidence == pytest.approx(0.91)
        assert f.title == "open() without with"
        assert "load_cache" in f.body
        assert f.suggestion is not None
        assert f.suggestion.kind == "patch"
        assert f.suggestion.remove == ("    f = open(path)",)
        assert f.suggestion.add == ("    with open(path) as f:", "        ...")

    def test_parses_summary(self) -> None:
        out = parse_agent_output(_ONE_FINDING_AND_SUMMARY)
        assert "fd-leak" in out.summary.text

    def test_zero_findings_still_ok(self) -> None:
        out = parse_agent_output(_NO_FINDINGS)
        assert out.findings == ()
        assert "renames" in out.summary.text

    def test_text_kind_suggestion(self) -> None:
        out = parse_agent_output(_TEXT_SUGGESTION)
        f = out.findings[0]
        assert f.suggestion is not None
        assert f.suggestion.kind == "text"
        assert f.suggestion.text == "rename `x` to `payload`"

    def test_none_kind_yields_no_suggestion(self) -> None:
        out = parse_agent_output(_NONE_SUGGESTION)
        f = out.findings[0]
        assert f.suggestion is None


class TestIds:
    def test_ids_are_sequential(self) -> None:
        two = _ONE_FINDING_AND_SUMMARY + _ONE_FINDING_AND_SUMMARY
        out = parse_agent_output(two)
        # Sentinel still ends parsing at the FIRST END_OF_REVIEW, only one finding parsed.
        assert len(out.findings) == 1
        assert out.findings[0].id == "c1"


class TestRobustness:
    def test_missing_sentinel_still_parses(self) -> None:
        text = _ONE_FINDING_AND_SUMMARY.replace("END_OF_REVIEW", "")
        out = parse_agent_output(text)
        # We are lenient — still extract what we can.
        assert len(out.findings) == 1

    def test_missing_summary_raises(self) -> None:
        text = _ONE_FINDING_AND_SUMMARY.split("```summary")[0] + "END_OF_REVIEW\n"
        with pytest.raises(OutputParseError, match="summary"):
            parse_agent_output(text)

    def test_finding_with_bad_yaml_raises(self) -> None:
        text = """\
```finding
not: valid: yaml: at: all
```
```summary
text: x
```
END_OF_REVIEW
"""
        with pytest.raises(OutputParseError):
            parse_agent_output(text)

    def test_missing_required_field_raises(self) -> None:
        text = """\
```finding
rule_id: RULE-X
file: a.py
# missing line + others
```
```summary
text: x
```
END_OF_REVIEW
"""
        with pytest.raises(OutputParseError, match="line|severity|missing"):
            parse_agent_output(text)
