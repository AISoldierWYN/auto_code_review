"""Diff sources — fetch a ChangeBundle from a local file or remote URL.

Stage 1 ships :class:`LocalDiffSource` (reads a ``.diff`` file from disk) and
:class:`GitHubDiffSource` (resolves a GitHub PR URL / shortcut into a diff
plus PR metadata). Gerrit is reserved as ``NotImplementedError`` until the
caller can run in a network that reaches a Gerrit host.

The :func:`select_source` helper dispatches on the identifier shape so the
calling code (HTTP server / CLI) does not need to know which concrete source
to use.
"""

from __future__ import annotations

from ai_code_review.diff.sources.base import (
    Author,
    ChangeBundle,
    DiffSource,
    DiffSourceError,
)
from ai_code_review.diff.sources.github import GitHubDiffSource
from ai_code_review.diff.sources.local import LocalDiffSource
from ai_code_review.diff.sources.registry import select_source

__all__ = [
    "Author",
    "ChangeBundle",
    "DiffSource",
    "DiffSourceError",
    "GitHubDiffSource",
    "LocalDiffSource",
    "select_source",
]
