"""Tests for the local HTTP publish endpoint handler."""

from __future__ import annotations

import json
from typing import Any

from scripts.serve import handle_publish


class _FakeRequest:
    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body

    async def json(self) -> dict[str, Any]:
        return self._body


def _review() -> dict[str, Any]:
    return {
        "review": {
            "title": "Demo",
            "diff_path": "https://gerrit.example.com/c/project/+/123",
            "summary": "No issues.",
        },
        "findings": [],
    }


async def test_publish_endpoint_dry_run_infers_gerrit_from_target() -> None:
    response = await handle_publish(_FakeRequest({"review": _review()}))  # type: ignore[arg-type]

    assert response.status == 200
    payload = json.loads(response.text)
    assert payload["platform"] == "gerrit"
    assert payload["submitted"] is False
    assert payload["payloads"][0]["url"].endswith("/changes/123/revisions/current/review")


async def test_publish_endpoint_rejects_missing_review() -> None:
    response = await handle_publish(_FakeRequest({}))  # type: ignore[arg-type]

    assert response.status == 400
    assert json.loads(response.text)["error"] == "review is required"
