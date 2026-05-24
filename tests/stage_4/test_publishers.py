"""Tests for GitHub and Gerrit review publishers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai_code_review.publish.gerrit import GerritPublisher, build_gerrit_review_payload
from ai_code_review.publish.github import GitHubPublisher


def _review(target: str = "https://github.com/acme/widgets/pull/7") -> dict:
    return {
        "review": {
            "title": "Demo",
            "repo": "acme/widgets",
            "diff_path": target,
            "summary": "One critical issue.",
            "metadata": {"filtered_findings": []},
        },
        "files": [],
        "findings": [
            {
                "id": "c1",
                "rule_id": "RULE-ANDROID-APP-001",
                "severity": "critical",
                "category": "performance",
                "file": "app/src/main/java/com/acme/Foo.java",
                "line": 42,
                "confidence": 0.95,
                "title": "Main-thread network request",
                "body": "Network I/O blocks the UI thread.",
            }
        ],
    }


@dataclass
class _FakeResponse:
    status: int
    body_json: Any = None

    async def json(self) -> Any:
        return self.body_json

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        pass


class _FakeSession:
    def __init__(self, comments: list[dict[str, Any]] | None = None) -> None:
        self.comments = comments or []
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append(("GET", url, kwargs))
        return _FakeResponse(status=200, body_json=self.comments)

    def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append(("POST", url, kwargs))
        return _FakeResponse(status=201, body_json={"id": 99})

    def patch(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append(("PATCH", url, kwargs))
        return _FakeResponse(status=200, body_json={"id": 55})

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        pass


async def test_github_dry_run_builds_idempotent_summary_payload() -> None:
    publisher = GitHubPublisher(target="https://github.com/acme/widgets/pull/7")

    result = await publisher.publish(_review(), mode="dry_run")

    assert result.platform == "github"
    assert result.action == "dry_run"
    assert not result.submitted
    assert result.payloads[0]["url"].endswith("/repos/acme/widgets/issues/7/comments")
    assert "<!-- ai-code-review:fingerprint=" in result.payloads[0]["json"]["body"]


async def test_github_submit_creates_comment_when_marker_is_absent() -> None:
    session = _FakeSession(comments=[])
    publisher = GitHubPublisher(
        target="https://github.com/acme/widgets/pull/7",
        session_factory=lambda: session,
    )

    result = await publisher.publish(_review(), mode="submit")

    assert result.action == "created"
    assert result.submitted
    assert [call[0] for call in session.calls] == ["GET", "POST"]


async def test_github_submit_updates_existing_ai_review_comment() -> None:
    session = _FakeSession(
        comments=[{"id": 55, "body": "<!-- ai-code-review:fingerprint=old -->"}]
    )
    publisher = GitHubPublisher(
        target="https://github.com/acme/widgets/pull/7",
        session_factory=lambda: session,
    )

    result = await publisher.publish(_review(), mode="submit")

    assert result.action == "updated"
    assert [call[0] for call in session.calls] == ["GET", "PATCH"]
    assert session.calls[-1][1].endswith("/repos/acme/widgets/issues/comments/55")


def test_gerrit_payload_groups_inline_comments_by_file() -> None:
    payload = build_gerrit_review_payload(_review(), fingerprint="abc")

    comments = payload["comments"]["app/src/main/java/com/acme/Foo.java"]
    assert payload["message"].startswith("<!-- ai-code-review:fingerprint=abc -->")
    assert comments[0]["line"] == 42
    assert comments[0]["unresolved"] is True
    assert "`RULE-ANDROID-APP-001`" in comments[0]["message"]


async def test_gerrit_dry_run_builds_review_endpoint() -> None:
    target = "https://gerrit.example.com/c/project/+/123/4"
    publisher = GerritPublisher(target=target)

    result = await publisher.publish(_review(target), mode="draft")

    assert result.platform == "gerrit"
    assert result.action == "draft_payload"
    assert result.payloads[0]["url"] == (
        "https://gerrit.example.com/changes/123/revisions/4/review"
    )
    assert "comments" in result.payloads[0]["json"]


async def test_gerrit_submit_posts_review_payload() -> None:
    session = _FakeSession()
    target = "https://gerrit.example.com/c/project/+/123"
    publisher = GerritPublisher(target=target, session_factory=lambda: session)

    result = await publisher.publish(_review(target), mode="submit")

    assert result.action == "submitted"
    assert result.submitted
    assert [call[0] for call in session.calls] == ["POST"]
    assert session.calls[0][1].endswith("/changes/123/revisions/current/review")
