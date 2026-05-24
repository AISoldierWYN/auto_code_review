"""Top-level review report model — what gets serialized to review.json."""

from __future__ import annotations

from dataclasses import dataclass

from ai_code_review.models.finding import FilteredFinding, Finding


@dataclass(frozen=True)
class Author:
    name: str
    role: str | None = None
    initials: str | None = None


@dataclass(frozen=True)
class ReviewMeta:
    diff_path: str
    title: str
    branch: str | None
    target: str | None
    author: Author | None
    repo: str | None
    model: str
    scanned_seconds: float
    files_changed: int
    additions: int
    deletions: int
    summary: str
    rules_total: int
    rules_after_filter: int
    rules_dropped_by_l4: tuple[str, ...] = ()
    filtered_findings: tuple[FilteredFinding, ...] = ()
    review_language: str = "en"


@dataclass(frozen=True)
class FileSummary:
    """Per-file aggregate displayed in the UI file list.

    ``add``/``deletions`` use the UI's field names. ``diff_hunks`` is a flat
    list of dicts ready for direct JSON serialization (see ReportBuilder for
    the schema).
    """

    path: str
    lang: str | None
    add: int
    deletions: int
    severity_counts: dict[str, int]
    diff_hunks: tuple[dict, ...]


@dataclass(frozen=True)
class ReviewReport:
    schema_version: str
    review: ReviewMeta
    files: tuple[FileSummary, ...]
    findings: tuple[Finding, ...]
