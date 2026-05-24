"""GitHubDiffSource — fetch unified diff + PR metadata from github.com.

URL forms accepted:
  https://github.com/<owner>/<repo>/pull/<N>[/<anything>]
  http://...                                  (upgraded automatically)
  <owner>/<repo>#<N>                          (shorthand)

Implementation notes:
  * Diff is fetched from ``https://github.com/<owner>/<repo>/pull/<N>.diff``
    which 302-redirects to a raw file on patch-diff.githubusercontent.com.
  * Metadata is fetched from ``https://api.github.com/repos/<owner>/<repo>/pulls/<N>``
    which returns JSON. If the call fails (rate limit / private repo without
    token) we tolerate it: the diff is enough to run a review, metadata
    just makes the UI nicer.
  * Auth: optional ``GITHUB_TOKEN`` env var sent as ``Authorization: Bearer``.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Callable

from ai_code_review.diff.sources.base import (
    Author,
    ChangeBundle,
    DiffSourceError,
)

_GITHUB_URL_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)/pull/(?P<num>\d+)(?:/.*)?$"
)
_GITHUB_SHORTCUT_RE = re.compile(
    r"^(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)#(?P<num>\d+)$"
)


def parse_github_identifier(identifier: str) -> tuple[str, str, int]:
    """Parse a GitHub PR URL or shortcut into (owner, repo, pr_number).

    Raises :class:`DiffSourceError` for inputs we don't recognize.
    """
    for pattern in (_GITHUB_URL_RE, _GITHUB_SHORTCUT_RE):
        m = pattern.match(identifier)
        if m:
            return m["owner"], m["repo"], int(m["num"])
    raise DiffSourceError(f"not a GitHub PR identifier: {identifier!r}")


class GitHubDiffSource:
    """Resolves a GitHub PR identifier to a ChangeBundle.

    ``session_factory`` is injected so tests can substitute a fake
    aiohttp-like session without touching the network.
    """

    def __init__(
        self,
        token: str | None = None,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._token = token if token is not None else os.environ.get("GITHUB_TOKEN")
        self._session_factory = session_factory or self._default_session_factory

    @staticmethod
    def _default_session_factory() -> Any:
        import aiohttp

        return aiohttp.ClientSession()

    # ── Public API ────────────────────────────────────────────────────────

    def fetch(self, identifier: str) -> ChangeBundle:
        """Synchronous entry point — wraps :meth:`afetch` in ``asyncio.run``."""
        return asyncio.run(self.afetch(identifier))

    async def afetch(self, identifier: str) -> ChangeBundle:
        owner, repo, num = parse_github_identifier(identifier)
        diff_url = f"https://github.com/{owner}/{repo}/pull/{num}.diff"
        meta_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{num}"

        async with self._session_factory() as session:
            diff_text = await self._fetch_diff(session, diff_url)
            meta = await self._fetch_meta_or_none(session, meta_url)

        if meta is not None:
            title = str(meta.get("title") or f"{owner}/{repo}#{num}")
            description = meta.get("body")
            user = meta.get("user") or {}
            author_name = user.get("login")
            author = Author(name=str(author_name)) if author_name else None
            head = meta.get("head") or {}
            base = meta.get("base") or {}
            branch = head.get("ref")
            target = base.get("ref")
        else:
            title = f"{owner}/{repo}#{num}"
            description = None
            author = None
            branch = None
            target = None

        return ChangeBundle(
            diff_text=diff_text,
            title=title,
            description=description,
            author=author,
            branch=branch,
            target=target,
            repo=f"{owner}/{repo}",
            source_kind="github",
            source_id=identifier,
        )

    # ── HTTP helpers ──────────────────────────────────────────────────────

    def _headers(self, accept: str) -> dict[str, str]:
        h: dict[str, str] = {"Accept": accept, "User-Agent": "ai-code-review/0.1"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    async def _fetch_diff(self, session: Any, url: str) -> str:
        async with session.get(url, headers=self._headers("application/vnd.github.diff")) as resp:
            if resp.status != 200:
                raise DiffSourceError(
                    f"failed to fetch diff (HTTP {resp.status}) from {url}"
                )
            return await resp.text()

    async def _fetch_meta_or_none(
        self, session: Any, url: str
    ) -> dict | None:
        try:
            async with session.get(
                url, headers=self._headers("application/vnd.github+json")
            ) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
        except Exception:  # noqa: BLE001 — tolerate any network hiccup on metadata
            return None
