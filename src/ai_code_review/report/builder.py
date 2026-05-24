"""Build the final ReviewReport (and its JSON form) from parsed agent output.

Responsibilities:
  * Assign sequential ids (c1, c2, ...) to findings
  * Fill in each finding's rationale from the matching rule's source
  * Aggregate per-file severity_counts
  * Convert structured Hunks into the flat list[dict] the UI expects
  * Inject ``comment`` markers at finding anchor lines into diff_hunks
  * Serialize to a JSON-compatible dict using the UI's field names
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ai_code_review.models.diff import FileChange, Hunk
from ai_code_review.models.finding import FilteredFinding, Finding, Rationale, Summary
from ai_code_review.models.review import (
    Author,
    FileSummary,
    ReviewMeta,
    ReviewReport,
)
from ai_code_review.models.rule import Rule

SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class ReportBuildInput:
    diff: list[FileChange]
    findings: list[Finding]
    summary: Summary
    rules_used: list[Rule]
    diff_path: str
    title: str
    model: str
    scanned_seconds: float
    rules_total: int
    rules_after_filter: int
    rules_dropped_by_l4: tuple[str, ...] = ()
    filtered_findings: tuple[FilteredFinding, ...] = ()
    review_language: str = "en"
    author: Author | None = None
    branch: str | None = None
    target: str | None = None
    repo: str | None = None


def _serialize_hunk(hunk: Hunk) -> list[dict]:
    out: list[dict] = [{"type": "hunk", "text": hunk.header or f"@@ -{hunk.old_start},{hunk.old_count} +{hunk.new_start},{hunk.new_count} @@"}]
    for line in hunk.lines:
        if line.kind == "context":
            out.append(
                {"type": "ctx", "old": line.old_line, "new": line.new_line, "text": line.text}
            )
        elif line.kind == "added":
            out.append(
                {"type": "add", "old": None, "new": line.new_line, "text": line.text}
            )
        elif line.kind == "removed":
            out.append(
                {"type": "del", "old": line.old_line, "new": None, "text": line.text}
            )
    return out


def _assign_id_and_rationale(
    f: Finding, idx: int, rule_index: dict[str, Rule]
) -> Finding:
    rule = rule_index.get(f.rule_id)
    if rule is None:
        rationale = Rationale(rule_source_type="typical_case", source_refs=())
    else:
        rationale = Rationale(
            rule_source_type=rule.source.type,
            source_refs=rule.source.refs,
        )
    return replace(f, id=f"c{idx}", rationale=rationale)


def _count_severities(findings: list[Finding]) -> dict[str, int]:
    counts = {"critical": 0, "warning": 0, "suggestion": 0}
    for f in findings:
        if f.severity in counts:
            counts[f.severity] += 1
    return counts


def _build_file_summary(
    fc: FileChange, findings_for_file: list[Finding]
) -> FileSummary:
    hunks_flat: list[dict] = []
    for h in fc.hunks:
        hunks_flat.extend(_serialize_hunk(h))

    # Inject comment markers at finding anchor lines, in order of appearance.
    for f in findings_for_file:
        hunks_flat.append({"type": "comment", "anchorNew": f.line, "id": f.id})

    return FileSummary(
        path=fc.path,
        lang=fc.language,
        add=fc.additions,
        deletions=fc.deletions,
        severity_counts=_count_severities(findings_for_file),
        diff_hunks=tuple(hunks_flat),
    )


def build_report(inp: ReportBuildInput) -> ReviewReport:
    """Assemble a ReviewReport from the pipeline's outputs."""
    rule_index = {r.rule_id: r for r in inp.rules_used}

    findings = tuple(
        _assign_id_and_rationale(f, idx, rule_index)
        for idx, f in enumerate(inp.findings, start=1)
    )

    files = tuple(
        _build_file_summary(fc, [f for f in findings if f.file == fc.path])
        for fc in inp.diff
    )

    meta = ReviewMeta(
        diff_path=inp.diff_path,
        title=inp.title,
        branch=inp.branch,
        target=inp.target,
        author=inp.author,
        repo=inp.repo,
        model=inp.model,
        scanned_seconds=inp.scanned_seconds,
        files_changed=len(inp.diff),
        additions=sum(fc.additions for fc in inp.diff),
        deletions=sum(fc.deletions for fc in inp.diff),
        summary=inp.summary.text,
        rules_total=inp.rules_total,
        rules_after_filter=inp.rules_after_filter,
        rules_dropped_by_l4=inp.rules_dropped_by_l4,
        filtered_findings=inp.filtered_findings,
        review_language=inp.review_language,
    )

    return ReviewReport(
        schema_version=SCHEMA_VERSION,
        review=meta,
        files=files,
        findings=findings,
    )


# ── Serialization ───────────────────────────────────────────────────────────


def _author_to_dict(a: Author | None) -> dict | None:
    if a is None:
        return None
    return {"name": a.name, "role": a.role, "initials": a.initials}


def _meta_to_dict(m: ReviewMeta) -> dict:
    return {
        "diff_path": m.diff_path,
        "title": m.title,
        "branch": m.branch,
        "target": m.target,
        "author": _author_to_dict(m.author),
        "repo": m.repo,
        "model": m.model,
        "scanned_seconds": m.scanned_seconds,
        "files_changed": m.files_changed,
        "additions": m.additions,
        "deletions": m.deletions,
        "summary": m.summary,
        "language": m.review_language,
        "metadata": {
            "rules_total": m.rules_total,
            "rules_after_filter": m.rules_after_filter,
            "rules_dropped_by_l4": list(m.rules_dropped_by_l4),
            "filtered_findings": [
                {
                    "reason": filtered.reason,
                    "rule_id": filtered.rule_id,
                    "file": filtered.file,
                    "line": filtered.line,
                    "detail": filtered.detail,
                }
                for filtered in m.filtered_findings
            ],
        },
    }


def _file_to_dict(fs: FileSummary) -> dict:
    return {
        "path": fs.path,
        "lang": fs.lang,
        "add": fs.add,
        "del": fs.deletions,
        "sev": fs.severity_counts,
        "diff_hunks": list(fs.diff_hunks),
    }


def _finding_to_dict(f: Finding) -> dict:
    suggestion: dict | None
    if f.suggestion is None:
        suggestion = None
    elif f.suggestion.kind == "patch":
        suggestion = {
            "kind": "patch",
            "remove": list(f.suggestion.remove),
            "add": list(f.suggestion.add),
        }
    else:
        suggestion = {"kind": "text", "text": f.suggestion.text}
    return {
        "id": f.id,
        "rule_id": f.rule_id,
        "severity": f.severity,
        "category": f.category,
        "file": f.file,
        "line": f.line,
        "confidence": f.confidence,
        "title": f.title,
        "body": f.body,
        "suggestion": suggestion,
        "rationale": {
            "rule_source_type": f.rationale.rule_source_type,
            "source_refs": list(f.rationale.source_refs),
        },
    }


def report_to_dict(report: ReviewReport) -> dict:
    """JSON-serializable dict matching the UI's expected schema."""
    return {
        "schema_version": report.schema_version,
        "review": _meta_to_dict(report.review),
        "files": [_file_to_dict(f) for f in report.files],
        "findings": [_finding_to_dict(f) for f in report.findings],
    }
