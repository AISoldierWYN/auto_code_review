"""Tests for GitHubDiffSource — URL parsing + (mocked) HTTP fetch."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from ai_code_review.diff.sources.base import DiffSourceError
from ai_code_review.diff.sources.github import (
    GitHubDiffSource,
    parse_github_identifier,
)


class TestParseGithubIdentifier:
    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("https://github.com/python/cpython/pull/1000", ("python", "cpython", 1000)),
            ("http://github.com/python/cpython/pull/1000", ("python", "cpython", 1000)),
            ("https://github.com/python/cpython/pull/1000/", ("python", "cpython", 1000)),
            ("https://github.com/python/cpython/pull/1000/files", ("python", "cpython", 1000)),
            ("python/cpython#1000", ("python", "cpython", 1000)),
            ("acme-corp/payments_svc#42", ("acme-corp", "payments_svc", 42)),
        ],
    )
    def test_parses_valid(self, input_str: str, expected: tuple) -> None:
        assert parse_github_identifier(input_str) == expected

    @pytest.mark.parametrize(
        "input_str",
        [
            "",
            "not a url",
            "https://gitlab.com/python/cpython/pull/1000",
            "python/cpython/1000",
            "https://github.com/python/cpython/issues/1000",
        ],
    )
    def test_rejects_invalid(self, input_str: str) -> None:
        with pytest.raises(DiffSourceError):
            parse_github_identifier(input_str)


# ── Fetch tests with a fake HTTP client ───────────────────────────────────


@dataclass
class _FakeResponse:
    status: int
    body_text: str = ""
    body_json: Any = None
    headers: dict[str, str] = None  # type: ignore[assignment]

    async def text(self) -> str:
        return self.body_text

    async def json(self) -> Any:
        return self.body_json

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        pass


class _FakeSession:
    """Minimal stand-in for aiohttp.ClientSession used in fetch tests."""

    def __init__(self, routes: dict[str, _FakeResponse]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, str]] = []  # (method, url)

    def get(self, url: str, **_: Any) -> _FakeResponse:
        self.calls.append(("GET", url))
        if url not in self.routes:
            return _FakeResponse(status=404, body_text="not found")
        return self.routes[url]

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        pass


_SAMPLE_DIFF = "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1,2 @@\n a\n+b\n"
_SAMPLE_META = {
    "title": "Add b to x",
    "body": "Closes #42",
    "user": {"login": "octocat"},
    "head": {"ref": "feature/add-b"},
    "base": {"ref": "main"},
    "html_url": "https://github.com/python/cpython/pull/1000",
}


def _fake_routes() -> dict[str, _FakeResponse]:
    return {
        "https://github.com/python/cpython/pull/1000.diff": _FakeResponse(
            status=200, body_text=_SAMPLE_DIFF
        ),
        "https://api.github.com/repos/python/cpython/pulls/1000": _FakeResponse(
            status=200, body_json=_SAMPLE_META
        ),
    }


def _run_fetch(identifier: str, routes: dict | None = None):
    src = GitHubDiffSource(session_factory=lambda: _FakeSession(routes or _fake_routes()))
    return asyncio.run(src.afetch(identifier))


class TestFetch:
    def test_returns_diff_text(self) -> None:
        bundle = _run_fetch("https://github.com/python/cpython/pull/1000")
        assert bundle.diff_text == _SAMPLE_DIFF

    def test_metadata_populated_from_api(self) -> None:
        bundle = _run_fetch("python/cpython#1000")
        assert bundle.title == "Add b to x"
        assert bundle.description == "Closes #42"
        assert bundle.author is not None
        assert bundle.author.name == "octocat"
        assert bundle.branch == "feature/add-b"
        assert bundle.target == "main"
        assert bundle.repo == "python/cpython"

    def test_source_kind_is_github(self) -> None:
        bundle = _run_fetch("python/cpython#1000")
        assert bundle.source_kind == "github"

    def test_diff_fetch_failure_raises(self) -> None:
        broken = {
            "https://github.com/python/cpython/pull/1000.diff": _FakeResponse(
                status=500, body_text="boom"
            ),
            "https://api.github.com/repos/python/cpython/pulls/1000": _FakeResponse(
                status=200, body_json=_SAMPLE_META
            ),
        }
        with pytest.raises(DiffSourceError, match="500"):
            _run_fetch("python/cpython#1000", routes=broken)

    def test_meta_fetch_failure_is_tolerated(self) -> None:
        # If the metadata endpoint is rate-limited we still want the diff.
        partial = {
            "https://github.com/python/cpython/pull/1000.diff": _FakeResponse(
                status=200, body_text=_SAMPLE_DIFF
            ),
            "https://api.github.com/repos/python/cpython/pulls/1000": _FakeResponse(
                status=403, body_text="rate limited"
            ),
        }
        bundle = _run_fetch("python/cpython#1000", routes=partial)
        assert bundle.diff_text == _SAMPLE_DIFF
        assert bundle.title == "python/cpython#1000"  # falls back to identifier
        assert bundle.author is None
