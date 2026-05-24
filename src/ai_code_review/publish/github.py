"""GitHub PR summary comment publisher."""

from __future__ import annotations

import os
from typing import Any

from ai_code_review.diff.sources.base import DiffSourceError
from ai_code_review.diff.sources.github import parse_github_identifier
from ai_code_review.publish.base import (
    PublishMode,
    PublishResult,
    ReviewPayload,
    ReviewPublisherError,
)
from ai_code_review.publish.format import (
    build_summary_comment,
    contains_ai_review_marker,
    review_fingerprint,
)


class GitHubPublisher:
    """Publishes the review as one idempotent PR conversation comment."""

    def __init__(
        self,
        *,
        target: str | None = None,
        token: str | None = None,
        session_factory: Any | None = None,
    ) -> None:
        self._target = target
        self._token = token if token is not None else os.environ.get("GITHUB_TOKEN")
        self._session_factory = session_factory or self._default_session_factory

    @staticmethod
    def _default_session_factory() -> Any:
        import aiohttp

        return aiohttp.ClientSession()

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ai-code-review/0.1",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _target_from_review(self, review: ReviewPayload) -> tuple[str, str, int, str]:
        target = self._target
        meta = review.get("review")
        if target is None and isinstance(meta, dict):
            raw = meta.get("diff_path")
            if raw:
                target = str(raw)
        if target is None:
            raise ReviewPublisherError("GitHub target is required")
        try:
            owner, repo, pr_number = parse_github_identifier(target)
        except DiffSourceError as exc:
            raise ReviewPublisherError(str(exc)) from exc
        return owner, repo, pr_number, target

    async def publish(
        self,
        review: ReviewPayload,
        *,
        mode: PublishMode = "dry_run",
    ) -> PublishResult:
        owner, repo, pr_number, target = self._target_from_review(review)
        fingerprint = review_fingerprint(review)
        body = build_summary_comment(review, fingerprint=fingerprint)
        payload = {
            "method": "POST",
            "url": f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments",
            "json": {"body": body},
        }

        if mode in {"dry_run", "draft"}:
            action = "dry_run" if mode == "dry_run" else "draft_unsupported_dry_run"
            return PublishResult(
                platform="github",
                mode=mode,
                fingerprint=fingerprint,
                target=target,
                action=action,
                submitted=False,
                payloads=(payload,),
            )

        async with self._session_factory() as session:
            existing = await self._find_existing_comment(session, owner, repo, pr_number)
            if existing is None:
                await self._create_comment(session, owner, repo, pr_number, body)
                action = "created"
                payloads = (payload,)
            else:
                comment_id = int(existing["id"])
                update_payload = {
                    "method": "PATCH",
                    "url": (
                        f"https://api.github.com/repos/{owner}/{repo}/issues/"
                        f"comments/{comment_id}"
                    ),
                    "json": {"body": body},
                }
                await self._update_comment(session, owner, repo, comment_id, body)
                action = "updated"
                payloads = (update_payload,)

        return PublishResult(
            platform="github",
            mode=mode,
            fingerprint=fingerprint,
            target=target,
            action=action,
            submitted=True,
            payloads=payloads,
        )

    async def _find_existing_comment(
        self,
        session: Any,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> dict[str, Any] | None:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
        async with session.get(
            url,
            headers=self._headers(),
            params={"per_page": 100},
        ) as resp:
            if resp.status != 200:
                raise ReviewPublisherError(
                    f"failed to list GitHub comments (HTTP {resp.status})"
                )
            data = await resp.json()
        if not isinstance(data, list):
            return None
        for item in data:
            body = str(item.get("body", "")) if isinstance(item, dict) else ""
            if isinstance(item, dict) and contains_ai_review_marker(body):
                return item
        return None

    async def _create_comment(
        self,
        session: Any,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
    ) -> None:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
        async with session.post(url, headers=self._headers(), json={"body": body}) as resp:
            if resp.status not in {200, 201}:
                raise ReviewPublisherError(
                    f"failed to create GitHub comment (HTTP {resp.status})"
                )

    async def _update_comment(
        self,
        session: Any,
        owner: str,
        repo: str,
        comment_id: int,
        body: str,
    ) -> None:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/comments/{comment_id}"
        async with session.patch(url, headers=self._headers(), json={"body": body}) as resp:
            if resp.status not in {200, 201}:
                raise ReviewPublisherError(
                    f"failed to update GitHub comment (HTTP {resp.status})"
                )
