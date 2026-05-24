"""Data models shared across pipeline stages.

All types are frozen dataclasses with full type hints. They contain no
business logic — pure data containers — so they can be passed across
module boundaries without coupling.
"""

from ai_code_review.models.diff import FileChange, Hunk, HunkLine
from ai_code_review.models.finding import (
    FilteredFinding,
    Finding,
    Rationale,
    Suggestion,
    Summary,
)
from ai_code_review.models.review import (
    Author,
    FileSummary,
    ReviewMeta,
    ReviewReport,
)
from ai_code_review.models.rule import AppliesTo, OriginalCase, Rule, RuleSource, Trigger

__all__ = [
    "AppliesTo",
    "Author",
    "FileChange",
    "FileSummary",
    "FilteredFinding",
    "Finding",
    "Hunk",
    "HunkLine",
    "OriginalCase",
    "Rationale",
    "ReviewMeta",
    "ReviewReport",
    "Rule",
    "RuleSource",
    "Suggestion",
    "Summary",
    "Trigger",
]
