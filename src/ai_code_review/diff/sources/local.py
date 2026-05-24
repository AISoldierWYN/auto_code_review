"""LocalDiffSource — read a unified diff from a local file path."""

from __future__ import annotations

from pathlib import Path

from ai_code_review.diff.sources.base import ChangeBundle, DiffSourceError


class LocalDiffSource:
    """Resolves a filesystem path to a ChangeBundle."""

    def fetch(self, identifier: str) -> ChangeBundle:
        path = Path(identifier)
        if not path.exists():
            raise DiffSourceError(f"diff file not found: {path}")
        if not path.is_file():
            raise DiffSourceError(f"diff path is not a file: {path}")
        try:
            diff_text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise DiffSourceError(f"cannot read {path}: {exc}") from exc

        return ChangeBundle(
            diff_text=diff_text,
            title=path.stem,
            source_kind="local",
            source_id=str(path),
        )

    async def afetch(self, identifier: str) -> ChangeBundle:
        """Async variant — local I/O is fast so this just delegates."""
        return self.fetch(identifier)
