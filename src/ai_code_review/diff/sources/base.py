"""DiffSource Protocol + ChangeBundle data class."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol


class DiffSourceError(ValueError):
    """Raised when a DiffSource cannot fetch the requested change."""


@dataclass(frozen=True)
class Author:
    name: str
    role: str | None = None
    initials: str | None = None


@dataclass(frozen=True)
class ChangeBundle:
    """The output of any DiffSource — a normalized view of one change.

    All metadata fields are optional; only ``diff_text`` is guaranteed.
    Downstream stages use whichever metadata is present.
    """

    diff_text: str
    title: str
    description: str | None = None
    author: Author | None = None
    branch: str | None = None
    target: str | None = None
    repo: str | None = None
    related_links: tuple[str, ...] = field(default_factory=tuple)
    source_kind: Literal["github", "gerrit", "local"] = "local"
    source_id: str = ""


class DiffSource(Protocol):
    """Protocol for any source that can resolve an identifier to a ChangeBundle.

    Implementations provide both a sync ``fetch`` and an async ``afetch``.
    Local sources can delegate one to the other; remote sources implement
    the async path natively to play nicely with web servers.
    """

    def fetch(self, identifier: str) -> ChangeBundle:  # pragma: no cover - protocol
        ...

    async def afetch(self, identifier: str) -> ChangeBundle:  # pragma: no cover
        ...
