"""Tests for the workspace auto-detection helper."""

from __future__ import annotations

from pathlib import Path

from ai_code_review.workspace import detect_workspace


class TestDetectWorkspace:
    def test_returns_dir_with_dotgit_when_diff_is_inside_repo(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "myrepo"
        (repo / ".git").mkdir(parents=True)
        (repo / "subdir").mkdir()
        diff = repo / "subdir" / "change.diff"
        diff.write_text("", encoding="utf-8")
        assert detect_workspace(diff) == repo

    def test_walks_up_multiple_levels(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        deep = repo / "a" / "b" / "c"
        deep.mkdir(parents=True)
        diff = deep / "x.diff"
        diff.write_text("", encoding="utf-8")
        assert detect_workspace(diff) == repo

    def test_falls_back_to_diff_parent_when_no_dotgit(self, tmp_path: Path) -> None:
        diff = tmp_path / "loose" / "x.diff"
        diff.parent.mkdir()
        diff.write_text("", encoding="utf-8")
        assert detect_workspace(diff) == diff.parent

    def test_explicit_fallback_override(self, tmp_path: Path) -> None:
        diff = tmp_path / "loose" / "x.diff"
        diff.parent.mkdir()
        diff.write_text("", encoding="utf-8")
        fallback = tmp_path / "elsewhere"
        fallback.mkdir()
        assert detect_workspace(diff, fallback=fallback) == fallback

    def test_dotgit_can_be_a_file_too(self, tmp_path: Path) -> None:
        # `git worktree` creates .git as a FILE, not a dir. Detection should still work.
        repo = tmp_path / "wt"
        repo.mkdir()
        (repo / ".git").write_text("gitdir: ../main/.git/worktrees/wt", encoding="utf-8")
        diff = repo / "x.diff"
        diff.write_text("", encoding="utf-8")
        assert detect_workspace(diff) == repo

    def test_case_fixture_workspace_takes_precedence(self, tmp_path: Path) -> None:
        case_dir = tmp_path / "case_android_demo"
        workspace = case_dir / "workspace"
        workspace.mkdir(parents=True)
        diff = case_dir / "change.diff"
        diff.write_text("", encoding="utf-8")

        assert detect_workspace(diff) == workspace
