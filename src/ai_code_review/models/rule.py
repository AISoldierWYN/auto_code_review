"""Rule models — typed view of a YAML rule file."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["critical", "warning", "suggestion"]
SourceType = Literal["bug_history", "typical_case", "review_history", "spec"]


@dataclass(frozen=True)
class Trigger:
    description: str
    signals: tuple[str, ...]


@dataclass(frozen=True)
class AppliesTo:
    languages: tuple[str, ...]
    paths: tuple[str, ...]
    exclude_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuleSource:
    type: SourceType
    refs: tuple[str, ...]


@dataclass(frozen=True)
class OriginalCase:
    bug_link: str | None = None
    minimal_repro: str | None = None
    fix_diff: str | None = None


@dataclass(frozen=True)
class RecallHints:
    """Cheap signals used by the rule recaller before prompt injection."""

    keywords: tuple[str, ...] = ()
    regexes: tuple[str, ...] = ()
    exclude_keywords: tuple[str, ...] = ()
    exclude_regexes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Rule:
    rule_id: str
    title: str
    category: str
    severity: Severity
    source: RuleSource
    applies_to: AppliesTo
    trigger: Trigger
    risk: str
    suggestion: str
    original_case: OriginalCase | None = None
    recall: RecallHints = field(default_factory=RecallHints)
