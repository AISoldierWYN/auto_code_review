"""Tests for the report builder — produces the UI-consumed review.json."""

from __future__ import annotations

import json

from ai_code_review.diff.parser import parse_unified_diff
from ai_code_review.models.finding import Finding, Rationale, Suggestion, Summary
from ai_code_review.models.review import Author
from ai_code_review.models.rule import AppliesTo, Rule, RuleSource, Trigger
from ai_code_review.report.builder import ReportBuildInput, build_report, report_to_dict

_DIFF = """\
diff --git a/foo/bar.py b/foo/bar.py
--- a/foo/bar.py
+++ b/foo/bar.py
@@ -1,3 +1,5 @@
 line one
+inserted A
+inserted B
 line two
 line three
"""


def _finding(rule_id: str = "RULE-X-001", severity: str = "critical", line: int = 2) -> Finding:
    return Finding(
        id="",  # builder reassigns
        rule_id=rule_id,
        severity=severity,  # type: ignore[arg-type]
        category="resource",
        file="foo/bar.py",
        line=line,
        confidence=0.9,
        title="t",
        body="b",
        suggestion=Suggestion(kind="patch", remove=("x",), add=("y",)),
        rationale=Rationale(rule_source_type="typical_case", source_refs=()),
    )


def _rule() -> Rule:
    return Rule(
        rule_id="RULE-X-001",
        title="t",
        category="resource",
        severity="critical",
        source=RuleSource(type="bug_history", refs=("BUG-1", "https://x")),
        applies_to=AppliesTo(languages=("python",), paths=("**/*.py",)),
        trigger=Trigger(description="d", signals=("s",)),
        risk="r",
        suggestion="sg",
    )


def _input(
    findings: list[Finding] | None = None, rules: list[Rule] | None = None
) -> ReportBuildInput:
    return ReportBuildInput(
        diff=parse_unified_diff(_DIFF),
        findings=findings if findings is not None else [_finding()],
        summary=Summary(text="A short summary."),
        rules_used=rules if rules is not None else [_rule()],
        diff_path="examples/demo/change.diff",
        title="demo",
        model="glm-5",
        scanned_seconds=1.5,
        rules_total=10,
        rules_after_filter=1,
        rules_dropped_by_l4=(),
        author=Author(name="LW", role="L4"),
        branch="feature/x",
        target="main",
        repo="acme/svc",
    )


class TestTopLevel:
    def test_schema_version_set(self) -> None:
        report = build_report(_input())
        assert report.schema_version == "1.0"

    def test_review_metadata(self) -> None:
        report = build_report(_input())
        m = report.review
        assert m.diff_path == "examples/demo/change.diff"
        assert m.title == "demo"
        assert m.model == "glm-5"
        assert m.scanned_seconds == 1.5
        assert m.files_changed == 1
        assert m.additions == 2
        assert m.deletions == 0
        assert m.summary == "A short summary."
        assert m.rules_total == 10
        assert m.rules_after_filter == 1


class TestFilesAggregation:
    def test_one_filesummary_per_file(self) -> None:
        report = build_report(_input())
        assert len(report.files) == 1
        f = report.files[0]
        assert f.path == "foo/bar.py"
        assert f.lang == "python"
        assert f.add == 2
        assert f.deletions == 0

    def test_severity_counts_per_file(self) -> None:
        findings = [
            _finding(severity="critical"),
            _finding(severity="warning"),
            _finding(severity="warning"),
            _finding(severity="suggestion"),
        ]
        report = build_report(_input(findings=findings))
        assert report.files[0].severity_counts == {
            "critical": 1,
            "warning": 2,
            "suggestion": 1,
        }

    def test_zero_counts_when_no_findings(self) -> None:
        report = build_report(_input(findings=[]))
        # Zero counts still present so UI can render the badges.
        assert report.files[0].severity_counts == {
            "critical": 0,
            "warning": 0,
            "suggestion": 0,
        }

    def test_diff_hunks_structured(self) -> None:
        report = build_report(_input())
        hunks = report.files[0].diff_hunks
        assert len(hunks) > 0
        kinds = {h["type"] for h in hunks}
        assert "hunk" in kinds
        assert "add" in kinds
        assert "ctx" in kinds


class TestFindings:
    def test_ids_reassigned_sequentially(self) -> None:
        findings = [_finding(), _finding(), _finding()]
        report = build_report(_input(findings=findings))
        assert [f.id for f in report.findings] == ["c1", "c2", "c3"]

    def test_rationale_filled_from_matching_rule(self) -> None:
        # Builder should overwrite the parser's placeholder rationale using
        # the actual rule's source_type + refs.
        report = build_report(_input())
        f = report.findings[0]
        assert f.rationale.rule_source_type == "bug_history"
        assert f.rationale.source_refs == ("BUG-1", "https://x")

    def test_finding_referencing_unknown_rule_keeps_empty_rationale(self) -> None:
        unknown = _finding(rule_id="RULE-DOES-NOT-EXIST")
        report = build_report(_input(findings=[unknown]))
        f = report.findings[0]
        # Empty refs but the finding is not dropped here (Stage 3 will filter).
        assert f.rationale.source_refs == ()


class TestCommentAnchorsInHunks:
    def test_comment_marker_inserted_at_finding_line(self) -> None:
        report = build_report(_input(findings=[_finding(line=2)]))
        hunks = report.files[0].diff_hunks
        comments = [h for h in hunks if h.get("type") == "comment"]
        assert len(comments) == 1
        assert comments[0]["anchorNew"] == 2
        assert comments[0]["id"] == "c1"


class TestSerialization:
    def test_to_dict_roundtrips_through_json(self) -> None:
        report = build_report(_input())
        d = report_to_dict(report)
        # Must be json-serializable
        text = json.dumps(d)
        assert "schema_version" in text
        round_tripped = json.loads(text)
        assert round_tripped["review"]["files_changed"] == 1

    def test_file_uses_ui_field_names(self) -> None:
        report = build_report(_input())
        d = report_to_dict(report)
        f = d["files"][0]
        # UI's data.js: {path, lang, add, del, sev: {critical, warning, suggestion}, diff_hunks}
        assert "add" in f
        assert "del" in f
        assert "sev" in f
        assert "critical" in f["sev"]

    def test_finding_suggestion_patch_shape(self) -> None:
        report = build_report(_input())
        d = report_to_dict(report)
        sug = d["findings"][0]["suggestion"]
        assert sug["kind"] == "patch"
        assert sug["remove"] == ["x"]
        assert sug["add"] == ["y"]

    def test_finding_no_suggestion_serialized_as_null(self) -> None:
        f = _finding()
        f_no_sug = Finding(
            id=f.id, rule_id=f.rule_id, severity=f.severity, category=f.category,
            file=f.file, line=f.line, confidence=f.confidence, title=f.title,
            body=f.body, suggestion=None, rationale=f.rationale,
        )
        report = build_report(_input(findings=[f_no_sug]))
        d = report_to_dict(report)
        assert d["findings"][0]["suggestion"] is None
