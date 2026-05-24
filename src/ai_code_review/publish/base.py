"""Publisher protocol and shared result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Protocol

ReviewPayload = Mapping[str, Any]
PublishMode = Literal["dry_run", "draft", "submit"]


class ReviewPublisherError(RuntimeError):
    """Raised when a publisher cannot build or submit a review payload."""


@dataclass(frozen=True)
class PublishResult:
    platform: str
    mode: PublishMode
    fingerprint: str
    target: str
    action: str
    submitted: bool
    payloads: tuple[dict[str, Any], ...]


class ReviewPublisher(Protocol):
    async def publish(
        self,
        review: ReviewPayload,
        *,
        mode: PublishMode = "dry_run",
    ) -> PublishResult:
        """Publish or dry-run a review payload."""
