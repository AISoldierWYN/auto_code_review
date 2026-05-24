"""Rule recaller — filters loaded rules down to those that apply to a diff.

Stage 1 implements:
  L1: language filter — drop rules whose languages don't include any
      diff file's language.
  L2: path filter — drop rules whose paths/exclude_paths globs don't
      match any diff file.

Stages 2+ will add L3 (keyword pre-filter) and L4 (priority pruning).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatch

from ai_code_review.models.diff import FileChange
from ai_code_review.models.rule import Rule

DEFAULT_MAX_RULES = 50

_SEVERITY_RANK = {"critical": 0, "warning": 1, "suggestion": 2}
_SOURCE_RANK = {
    "bug_history": 0,
    "typical_case": 1,
    "review_history": 2,
    "spec": 3,
}


@dataclass(frozen=True)
class RuleRecallResult:
    """Rules selected for prompt injection plus audit metadata."""

    rules: tuple[Rule, ...]
    dropped_by_l4: tuple[str, ...] = ()


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch(path, p) or _glob_double_star(path, p) for p in patterns)


def _glob_double_star(path: str, pattern: str) -> bool:
    """Support ``**`` wildcards (fnmatch alone does not).

    Approach: convert ``**`` to a regex-like behavior by greedy fnmatch.
    Specifically ``a/**/b.py`` should match ``a/b.py``, ``a/x/b.py``,
    ``a/x/y/b.py``. We test by progressively splitting the pattern.
    """
    if "**" not in pattern:
        return False
    # Replace **/ with empty so a/**/b matches a/b.
    # And keep the standard version too.
    candidates = {
        pattern.replace("**/", ""),
        pattern.replace("/**", ""),
        pattern.replace("**", "*"),
    }
    return any(fnmatch(path, c) for c in candidates)


def _path_matches(path: str, rule: Rule) -> bool:
    if rule.applies_to.exclude_paths and _matches_any(
        path, rule.applies_to.exclude_paths
    ):
        return False
    return _matches_any(path, rule.applies_to.paths)


def _rule_applies(rule: Rule, diff: list[FileChange]) -> bool:
    rule_langs = set(rule.applies_to.languages)
    for fc in diff:
        if fc.language is None or fc.language not in rule_langs:
            continue
        if _path_matches(fc.path, rule):
            return True
    return False


def _rule_has_signal(rule: Rule, diff_text: str | None) -> bool:
    """Return whether *diff_text* contains any optional L3 recall signal.

    Rules without recall hints keep Stage 1 behavior and pass through. Passing
    ``diff_text=None`` disables L3 entirely for backward-compatible callers.
    """
    if diff_text is None:
        return True
    if not rule.recall.keywords and not rule.recall.regexes:
        return True

    lowered = diff_text.lower()
    if any(keyword.lower() in lowered for keyword in rule.recall.keywords):
        return True

    for pattern in rule.recall.regexes:
        try:
            if re.search(pattern, diff_text, flags=re.IGNORECASE | re.MULTILINE):
                return True
        except re.error:
            continue
    return False


def _priority_key(indexed_rule: tuple[int, Rule]) -> tuple[int, int, int]:
    idx, rule = indexed_rule
    return (
        _SEVERITY_RANK.get(rule.severity, 99),
        _SOURCE_RANK.get(rule.source.type, 99),
        idx,
    )


def _prune_rules(rules: list[Rule], max_rules: int | None) -> RuleRecallResult:
    if max_rules is None or len(rules) <= max_rules:
        return RuleRecallResult(rules=tuple(rules))
    if max_rules < 0:
        raise ValueError("max_rules must be >= 0 or None")

    ranked = sorted(enumerate(rules), key=_priority_key)
    kept_indexed = ranked[:max_rules]
    dropped_indexed = ranked[max_rules:]
    return RuleRecallResult(
        rules=tuple(rule for _, rule in kept_indexed),
        dropped_by_l4=tuple(rule.rule_id for _, rule in dropped_indexed),
    )


def recall_rules(
    rules: list[Rule],
    diff: list[FileChange],
    *,
    diff_text: str | None = None,
    max_rules: int | None = DEFAULT_MAX_RULES,
) -> RuleRecallResult:
    """Recall applicable rules using Stage 2's L1-L4 pipeline.

    L1/L2 are language/path filters. L3 is an optional rough signal filter
    driven by ``rule.recall`` keyword/regex hints. L4 caps the final rules by
    priority so prompt size stays bounded and records dropped ids for audit.
    """
    if not rules or not diff:
        return RuleRecallResult(rules=())

    after_l2 = [r for r in rules if _rule_applies(r, diff)]
    after_l3 = [r for r in after_l2 if _rule_has_signal(r, diff_text)]
    return _prune_rules(after_l3, max_rules)


def filter_rules(rules: list[Rule], diff: list[FileChange]) -> list[Rule]:
    """Return the subset of *rules* that apply to at least one file in *diff*.

    A rule applies when there exists a file in the diff such that:
      * the file's detected ``language`` is in ``rule.applies_to.languages``
      * the file's ``path`` matches one of ``rule.applies_to.paths`` and
        none of ``rule.applies_to.exclude_paths``.
    """
    return list(recall_rules(rules, diff, diff_text=None, max_rules=None).rules)
