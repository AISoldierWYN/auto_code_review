"""Tests for DiffSource adapters."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_code_review.diff.sources import (
    ChangeBundle,
    DiffSourceError,
    LocalDiffSource,
    select_source,
)


class TestLocalDiffSource:
    def test_fetch_returns_bundle_with_diff_text(self, tmp_path: Path) -> None:
        diff_file = tmp_path / "x.diff"
        diff_file.write_text("diff --git a/x b/x\n", encoding="utf-8")

        bundle = LocalDiffSource().fetch(str(diff_file))
        assert isinstance(bundle, ChangeBundle)
        assert bundle.diff_text == "diff --git a/x b/x\n"
        assert bundle.source_kind == "local"
        assert bundle.source_id == str(diff_file)

    def test_metadata_fields_default_to_none(self, tmp_path: Path) -> None:
        diff_file = tmp_path / "x.diff"
        diff_file.write_text("", encoding="utf-8")
        b = LocalDiffSource().fetch(str(diff_file))
        assert b.author is None
        assert b.branch is None
        assert b.target is None
        assert b.repo is None
        assert b.description is None
        assert b.related_links == ()

    def test_title_derived_from_filename(self, tmp_path: Path) -> None:
        diff_file = tmp_path / "my-change.diff"
        diff_file.write_text("", encoding="utf-8")
        assert LocalDiffSource().fetch(str(diff_file)).title == "my-change"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(DiffSourceError, match="not found"):
            LocalDiffSource().fetch(str(tmp_path / "missing.diff"))


class TestSelectSource:
    def test_existing_path_picks_local(self, tmp_path: Path) -> None:
        diff_file = tmp_path / "x.diff"
        diff_file.write_text("", encoding="utf-8")
        src = select_source(str(diff_file))
        assert isinstance(src, LocalDiffSource)

    def test_github_url_picks_github(self) -> None:
        # GitHubDiffSource is imported lazily; we just check the source class name
        # to avoid pulling network deps into this test.
        src = select_source("https://github.com/python/cpython/pull/1000")
        assert type(src).__name__ == "GitHubDiffSource"

    def test_github_shortcut_form(self) -> None:
        src = select_source("python/cpython#1000")
        assert type(src).__name__ == "GitHubDiffSource"

    def test_unknown_input_raises(self) -> None:
        with pytest.raises(DiffSourceError, match="cannot identify"):
            select_source("this is gibberish")
