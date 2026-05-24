"""Dispatch an identifier to the right DiffSource implementation."""

from __future__ import annotations

import re
from pathlib import Path

from ai_code_review.diff.sources.base import DiffSource, DiffSourceError
from ai_code_review.diff.sources.gerrit import GerritDiffSource, parse_gerrit_identifier
from ai_code_review.diff.sources.github import GitHubDiffSource
from ai_code_review.diff.sources.local import LocalDiffSource

_GITHUB_URL_RE = re.compile(r"^https?://github\.com/[^/]+/[^/]+/pull/\d+/?")
_GITHUB_SHORTCUT_RE = re.compile(r"^[\w.-]+/[\w.-]+#\d+$")


def _looks_like_github(identifier: str) -> bool:
    return bool(_GITHUB_URL_RE.match(identifier) or _GITHUB_SHORTCUT_RE.match(identifier))


def _looks_like_gerrit(identifier: str) -> bool:
    try:
        parse_gerrit_identifier(identifier)
    except DiffSourceError:
        return False
    return True


def select_source(identifier: str) -> DiffSource:
    """Pick the right DiffSource based on the shape of *identifier*.

    Order:
      1. Local file that exists → :class:`LocalDiffSource`
      2. Looks like a GitHub PR URL or ``owner/repo#NN`` → :class:`GitHubDiffSource`
      3. Looks like a Gerrit change URL → :class:`GerritDiffSource`
      4. Otherwise raise :class:`DiffSourceError`.
    """
    candidate = Path(identifier)
    if candidate.exists() and candidate.is_file():
        return LocalDiffSource()
    if _looks_like_github(identifier):
        return GitHubDiffSource()
    if _looks_like_gerrit(identifier):
        return GerritDiffSource()
    raise DiffSourceError(
        f"cannot identify diff source for {identifier!r}: "
        f"not a local file and not a recognized URL"
    )
