"""Workspace auto-detection — find the repo root containing a diff file."""

from __future__ import annotations

from pathlib import Path


def detect_workspace(diff_path: Path, fallback: Path | None = None) -> Path:
    """Find the workspace directory that contains *diff_path*.

    If ``diff_path`` is one of the bundled/user test-case fixtures and has a
    sibling ``workspace/`` directory, returns that after-state workspace.
    Otherwise walks up from ``diff_path.parent`` looking for a ``.git`` entry
    (which may be a directory in a normal clone or a file in a ``git worktree``).
    Returns the first ancestor that has one.

    If no ``.git`` is found:
      * returns *fallback* if provided
      * otherwise returns ``diff_path.parent``
    """
    start = diff_path.parent.resolve()
    fixture_workspace = start / "workspace"
    if fixture_workspace.is_dir():
        return fixture_workspace

    current = start
    while True:
        if (current / ".git").exists():
            return current
        if current.parent == current:
            break
        current = current.parent

    return fallback if fallback is not None else start
