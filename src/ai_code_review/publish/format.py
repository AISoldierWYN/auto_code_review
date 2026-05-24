"""Shared formatting for platform review comments."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, cast

from ai_code_review.publish.base import ReviewPayload

COMMENT_MARKER_PREFIX = "ai-code-review"


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return cast(Mapping[str, Any], value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _mapping_items(items: list[Any]) -> list[Mapping[str, Any]]:
    return [
        cast(Mapping[str, Any], item)
        for item in items
        if isinstance(item, Mapping)
    ]


def review_fingerprint(review: ReviewPayload) -> str:
    """Return a stable fingerprint for idempotent platform comments."""
    meta = _as_mapping(review.get("review"))
    findings = _as_list(review.get("findings"))
    normalized_findings = []
    for item in findings:
        if not isinstance(item, Mapping):
            continue
        normalized_findings.append(
            {
                "rule_id": item.get("rule_id"),
                "severity": item.get("severity"),
                "file": item.get("file"),
                "line": item.get("line"),
            }
        )
    seed = {
        "diff_path": meta.get("diff_path"),
        "repo": meta.get("repo"),
        "title": meta.get("title"),
        "findings": sorted(
            normalized_findings,
            key=lambda item: (
                str(item.get("rule_id")),
                str(item.get("file")),
                str(item.get("line")),
            ),
        ),
    }
    raw = json.dumps(seed, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def comment_marker(fingerprint: str) -> str:
    return f"<!-- {COMMENT_MARKER_PREFIX}:fingerprint={fingerprint} -->"


def contains_ai_review_marker(body: str) -> bool:
    return f"<!-- {COMMENT_MARKER_PREFIX}:" in body


def _severity_counts(findings: list[Mapping[str, Any]]) -> dict[str, int]:
    counts = {"critical": 0, "warning": 0, "suggestion": 0}
    for finding in findings:
        severity = str(finding.get("severity") or "")
        if severity in counts:
            counts[severity] += 1
    return counts


def _finding_line(finding: Mapping[str, Any]) -> str:
    severity = finding.get("severity") or "unknown"
    rule_id = finding.get("rule_id") or "unknown-rule"
    file = finding.get("file") or "unknown-file"
    line = finding.get("line") or "?"
    title = finding.get("title") or "(untitled)"
    confidence = finding.get("confidence")
    confidence_text = ""
    if isinstance(confidence, (int, float)):
        confidence_text = f" confidence={confidence:.2f}"
    return f"- **{severity}** `{rule_id}` `{file}:{line}`{confidence_text}: {title}"


def build_summary_comment(review: ReviewPayload, *, fingerprint: str | None = None) -> str:
    """Build a compact, idempotent top-level review comment."""
    fingerprint = fingerprint or review_fingerprint(review)
    meta = _as_mapping(review.get("review"))
    findings = _mapping_items(_as_list(review.get("findings")))
    counts = _severity_counts(findings)
    summary = str(meta.get("summary") or "AI code review completed.")

    lines = [
        comment_marker(fingerprint),
        "### AI Code Review",
        "",
        summary,
        "",
        (
            f"Findings: **{len(findings)}** "
            f"(critical {counts['critical']}, warning {counts['warning']}, "
            f"suggestion {counts['suggestion']})"
        ),
    ]
    filtered = _as_mapping(meta.get("metadata"))
    filtered_findings = filtered.get("filtered_findings")
    if isinstance(filtered_findings, list) and filtered_findings:
        lines.append(f"Filtered model findings: **{len(filtered_findings)}**")

    if findings:
        lines.extend(["", "#### Findings"])
        lines.extend(_finding_line(finding) for finding in findings[:20])
        if len(findings) > 20:
            lines.append(f"- ... and {len(findings) - 20} more")
    else:
        lines.extend(["", "No rule-backed findings passed validation."])

    return "\n".join(lines)


def build_inline_comment_text(finding: Mapping[str, Any]) -> str:
    """Build one per-line platform comment from a finding."""
    rule_id = finding.get("rule_id") or "unknown-rule"
    severity = finding.get("severity") or "unknown"
    title = finding.get("title") or "(untitled)"
    body = finding.get("body") or ""
    return f"**{severity}** `{rule_id}`: {title}\n\n{body}".strip()
