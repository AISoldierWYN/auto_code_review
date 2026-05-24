"""Factory helpers for review publishers."""

from __future__ import annotations

from typing import Any

from ai_code_review.publish.base import ReviewPublisher, ReviewPublisherError
from ai_code_review.publish.github import GitHubPublisher
from ai_code_review.publish.gerrit import GerritPublisher


def create_publisher(
    platform: str,
    *,
    target: str | None = None,
    session_factory: Any | None = None,
) -> ReviewPublisher:
    """Create a publisher by platform name."""
    normalized = platform.strip().lower()
    if normalized == "github":
        return GitHubPublisher(target=target, session_factory=session_factory)
    if normalized == "gerrit":
        return GerritPublisher(target=target, session_factory=session_factory)
    raise ReviewPublisherError(f"unsupported publish platform: {platform!r}")
