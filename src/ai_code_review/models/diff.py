"""Diff models — structured representation of a unified diff."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

HunkLineKind = Literal["context", "added", "removed"]


@dataclass(frozen=True)
class HunkLine:
    """One line inside a hunk.

    ``old_line`` is None for added lines; ``new_line`` is None for removed
    lines; both are set for context lines.
    """

    kind: HunkLineKind
    old_line: int | None
    new_line: int | None
    text: str


@dataclass(frozen=True)
class Hunk:
    header: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: tuple[HunkLine, ...]


@dataclass(frozen=True)
class FileChange:
    """One file's worth of changes inside a diff.

    Path is repo-root-relative POSIX form. ``language`` is derived from the
    extension at parse time, ``None`` if unknown.
    """

    path: str
    old_path: str | None
    is_new_file: bool
    is_deleted_file: bool
    language: str | None
    additions: int
    deletions: int
    hunks: tuple[Hunk, ...]
