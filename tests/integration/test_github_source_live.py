"""Live network integration test for GitHubDiffSource.

Hits github.com / api.github.com. Excluded from the default ``pytest`` run;
opt in with ``pytest -m integration``.
"""

from __future__ import annotations

import pytest

from ai_code_review.diff.sources.github import GitHubDiffSource


@pytest.mark.integration
def test_fetches_small_public_pr_diff() -> None:
    """python/cpython#1000 is a small (329-line) public PR — stable target."""
    src = GitHubDiffSource()
    bundle = src.fetch("https://github.com/python/cpython/pull/1000")
    assert bundle.source_kind == "github"
    assert bundle.repo == "python/cpython"
    # Diff content sanity checks — don't over-pin specifics that GitHub may reflow.
    assert bundle.diff_text.startswith("diff --git ")
    assert len(bundle.diff_text.splitlines()) > 50
    # Metadata: title is usually present (PR has a title)
    assert bundle.title  # non-empty
