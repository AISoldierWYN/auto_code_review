"""Tests for Gerrit URL parsing and mocked DiffSource fetch."""

from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass
from typing import Any

import pytest

from ai_code_review.diff.sources import GerritDiffSource, select_source
from ai_code_review.diff.sources.base import DiffSourceError
from ai_code_review.diff.sources.gerrit import (
    gerrit_rest_id,
    parse_gerrit_identifier,
    strip_gerrit_xssi,
)


@dataclass
class _FakeResponse:
    status: int
    body_text: str = ""

    async def text(self) -> str:
        return self.body_text

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        pass


class _FakeSession:
    def __init__(self, routes: dict[str, _FakeResponse]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, str]] = []

    def get(self, url: str, **_: Any) -> _FakeResponse:
        self.calls.append(("GET", url))
        return self.routes.get(url, _FakeResponse(status=404, body_text="not found"))

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        pass


_PATCH = "diff --git a/Foo.java b/Foo.java\n@@ -1 +1,2 @@\n class Foo {}\n"
_DETAIL = {
    "project": "platform/frameworks/base",
    "branch": "main",
    "subject": "Fix quota accounting",
    "owner": {"name": "Lin Wei"},
    "current_revision": "abc123",
    "revisions": {"abc123": {"commit": {"message": "Fix quota accounting\n\nBody"}}},
}


def _xssi_json(data: dict[str, Any]) -> str:
    return ")]}'\n" + json.dumps(data)


def _run_fetch(identifier: str, routes: dict[str, _FakeResponse]):
    source = GerritDiffSource(session_factory=lambda: _FakeSession(routes))
    return asyncio.run(source.afetch(identifier))


def test_parse_gerrit_change_url_with_project_and_revision() -> None:
    target = parse_gerrit_identifier(
        "https://gerrit.example.com/c/platform/frameworks/base/+/123/4"
    )

    assert target.base_url == "https://gerrit.example.com"
    assert target.project == "platform/frameworks/base"
    assert target.change == "123"
    assert target.revision == "4"


def test_parse_gerrit_rest_url_defaults_revision_to_current() -> None:
    target = parse_gerrit_identifier("https://gerrit.example.com/changes/123")

    assert target.change == "123"
    assert target.revision == "current"


def test_gerrit_rest_id_encodes_slashes_and_tildes() -> None:
    assert gerrit_rest_id("platform/base~main~Iabc") == "platform%2Fbase~main~Iabc"


def test_strip_xssi_prefix() -> None:
    assert strip_gerrit_xssi(")]}'\n{\"ok\": true}") == "{\"ok\": true}"


def test_select_source_picks_gerrit() -> None:
    source = select_source("https://gerrit.example.com/c/project/+/123")
    assert isinstance(source, GerritDiffSource)


def test_fetch_decodes_patch_and_populates_metadata() -> None:
    patch_body = base64.b64encode(_PATCH.encode("utf-8")).decode("ascii")
    routes = {
        "https://gerrit.example.com/changes/123/revisions/4/patch?download": (
            _FakeResponse(status=200, body_text=patch_body)
        ),
        "https://gerrit.example.com/changes/123/detail": _FakeResponse(
            status=200, body_text=_xssi_json(_DETAIL)
        ),
    }

    bundle = _run_fetch("https://gerrit.example.com/c/platform/frameworks/base/+/123/4", routes)

    assert bundle.diff_text == _PATCH
    assert bundle.title == "Fix quota accounting"
    assert bundle.description == "Fix quota accounting\n\nBody"
    assert bundle.author is not None
    assert bundle.author.name == "Lin Wei"
    assert bundle.repo == "platform/frameworks/base"
    assert bundle.source_kind == "gerrit"


def test_fetch_patch_failure_raises() -> None:
    routes = {
        "https://gerrit.example.com/changes/123/revisions/current/patch?download": (
            _FakeResponse(status=500, body_text="boom")
        )
    }

    with pytest.raises(DiffSourceError, match="500"):
        _run_fetch("https://gerrit.example.com/c/project/+/123", routes)
