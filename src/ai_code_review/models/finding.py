"""Finding models — agent output after parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ai_code_review.models.rule import Severity, SourceType


@dataclass(frozen=True)
class Suggestion:
    """Optional code change suggestion attached to a finding.

    ``kind="patch"`` means use ``remove``/``add``; ``kind="text"`` means use
    ``text``. A finding without a suggestion uses ``None``, not a special kind.
    """

    kind: Literal["patch", "text"]
    remove: tuple[str, ...] = ()
    add: tuple[str, ...] = ()
    text: str = ""


@dataclass(frozen=True)
class Rationale:
    rule_source_type: SourceType
    source_refs: tuple[str, ...]


@dataclass(frozen=True)
class Finding:
    id: str
    rule_id: str
    severity: Severity
    category: str
    file: str
    line: int
    confidence: float
    title: str
    body: str
    suggestion: Suggestion | None
    rationale: Rationale


@dataclass(frozen=True)
class Summary:
    text: str
