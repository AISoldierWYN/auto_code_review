"""Unified-diff parser — turns ``git diff`` text into structured FileChanges.

Built on top of the ``unidiff`` library; this module adds language detection
and the project's flat data model on top.
"""

from __future__ import annotations

from unidiff import PatchSet  # type: ignore[import-untyped]

from ai_code_review.models.diff import FileChange, Hunk, HunkLine

_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".rb": "ruby",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".sh": "shell",
    ".bash": "shell",
}


def _detect_language(path: str) -> str | None:
    lower = path.lower()
    for ext, lang in _EXT_TO_LANG.items():
        if lower.endswith(ext):
            return lang
    return None


def _strip_ab_prefix(p: str) -> str:
    if p.startswith(("a/", "b/")):
        return p[2:]
    return p


def _real_path(pf, fallback: str) -> str:
    """Return the path of the file ignoring /dev/null markers."""
    target = pf.target_file if pf.target_file != "/dev/null" else pf.source_file
    if target == "/dev/null":
        return fallback
    return _strip_ab_prefix(target)


def parse_unified_diff(text: str) -> list[FileChange]:
    """Parse a unified diff string into a list of FileChange objects.

    Returns an empty list for empty input. CRLF line endings are normalized
    by the underlying ``unidiff`` library, so callers do not need to.
    """
    if not text.strip():
        return []

    # unidiff does not normalize CRLF; without this, paths and line text
    # would carry trailing \r characters and break downstream matching.
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    patch_set = PatchSet(normalized)
    changes: list[FileChange] = []
    for pf in patch_set:
        # When source is /dev/null it's a new file; when target is /dev/null it's a delete.
        is_new = pf.is_added_file
        is_deleted = pf.is_removed_file

        # path: prefer the surviving side
        if is_deleted:
            raw_path = pf.source_file
        else:
            raw_path = pf.target_file
        path = _strip_ab_prefix(raw_path) if raw_path != "/dev/null" else "<unknown>"

        old_path: str | None = None
        if pf.source_file != pf.target_file and not is_new and not is_deleted:
            old_path = _strip_ab_prefix(pf.source_file)

        hunks: list[Hunk] = []
        additions = 0
        deletions = 0
        for h in pf:
            lines: list[HunkLine] = []
            for line in h:
                if line.is_added:
                    kind = "added"
                    additions += 1
                elif line.is_removed:
                    kind = "removed"
                    deletions += 1
                else:
                    kind = "context"
                lines.append(
                    HunkLine(
                        kind=kind,  # type: ignore[arg-type]
                        old_line=line.source_line_no,
                        new_line=line.target_line_no,
                        text=line.value.rstrip("\n"),
                    )
                )
            hunks.append(
                Hunk(
                    header=h.section_header or "",
                    old_start=h.source_start,
                    old_count=h.source_length,
                    new_start=h.target_start,
                    new_count=h.target_length,
                    lines=tuple(lines),
                )
            )

        changes.append(
            FileChange(
                path=path,
                old_path=old_path,
                is_new_file=is_new,
                is_deleted_file=is_deleted,
                language=_detect_language(path),
                additions=additions,
                deletions=deletions,
                hunks=tuple(hunks),
            )
        )
    return changes
