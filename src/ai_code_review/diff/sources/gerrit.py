"""GerritDiffSource — fetch unified patches and CL metadata from Gerrit.

The implementation is intentionally small but real: it understands common
Gerrit change URLs, fetches the base64-encoded patch via REST, and tolerates
metadata failures so review can still run from the diff alone.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import quote

from ai_code_review.diff.sources.base import Author, ChangeBundle, DiffSourceError

_GERRIT_CHANGE_URL_RE = re.compile(
    r"^(?P<base>https?://[^/#?]+)(?:/#)?/c/(?P<project>.+?)/\+/"
    r"(?P<change>[^/?#]+)(?:/(?P<revision>[^/?#]+))?(?:[/?#].*)?$"
)
_GERRIT_CHANGE_API_RE = re.compile(
    r"^(?P<base>https?://[^/#?]+)/changes/(?P<change>[^/?#]+)"
    r"(?:/revisions/(?P<revision>[^/?#]+))?(?:[/?#].*)?$"
)
_GERRIT_XSSI_PREFIX = ")]}'"


@dataclass(frozen=True)
class GerritTarget:
    base_url: str
    change: str
    revision: str = "current"
    project: str | None = None


def parse_gerrit_identifier(identifier: str) -> GerritTarget:
    """Parse common Gerrit change URLs into a REST target."""
    for pattern in (_GERRIT_CHANGE_URL_RE, _GERRIT_CHANGE_API_RE):
        match = pattern.match(identifier)
        if match:
            return GerritTarget(
                base_url=match.group("base").rstrip("/"),
                change=match.group("change"),
                revision=match.group("revision") or "current",
                project=match.groupdict().get("project"),
            )
    raise DiffSourceError(f"not a Gerrit change identifier: {identifier!r}")


def gerrit_rest_id(value: str) -> str:
    """Encode a Gerrit change/revision id for REST paths."""
    return quote(value, safe="")


def strip_gerrit_xssi(text: str) -> str:
    """Remove Gerrit's JSON XSSI prefix when present."""
    if text.startswith(_GERRIT_XSSI_PREFIX):
        _, _, rest = text.partition("\n")
        return rest
    return text


class GerritDiffSource:
    """Resolves a Gerrit CL URL to a normalized ChangeBundle."""

    def __init__(
        self,
        auth_token: str | None = None,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._auth_token = (
            auth_token if auth_token is not None else os.environ.get("GERRIT_AUTH_TOKEN")
        )
        self._session_factory = session_factory or self._default_session_factory

    @staticmethod
    def _default_session_factory() -> Any:
        import aiohttp

        return aiohttp.ClientSession()

    def fetch(self, identifier: str) -> ChangeBundle:
        return asyncio.run(self.afetch(identifier))

    async def afetch(self, identifier: str) -> ChangeBundle:
        target = parse_gerrit_identifier(identifier)
        async with self._session_factory() as session:
            diff_text = await self._fetch_patch(session, target)
            meta = await self._fetch_detail_or_none(session, target)
        return _bundle_from_gerrit(target, identifier, diff_text, meta)

    def _headers(self, accept: str) -> dict[str, str]:
        headers = {"Accept": accept, "User-Agent": "ai-code-review/0.1"}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        return headers

    async def _fetch_patch(self, session: Any, target: GerritTarget) -> str:
        change_id = gerrit_rest_id(target.change)
        revision_id = gerrit_rest_id(target.revision)
        url = (
            f"{target.base_url}/changes/{change_id}/revisions/{revision_id}"
            "/patch?download"
        )
        async with session.get(url, headers=self._headers("text/plain")) as resp:
            if resp.status != 200:
                raise DiffSourceError(
                    f"failed to fetch Gerrit patch (HTTP {resp.status}) from {url}"
                )
            encoded_patch = await resp.text()
        return _decode_gerrit_patch(encoded_patch)

    async def _fetch_detail_or_none(
        self, session: Any, target: GerritTarget
    ) -> dict[str, Any] | None:
        change_id = gerrit_rest_id(target.change)
        url = f"{target.base_url}/changes/{change_id}/detail"
        try:
            async with session.get(
                url, headers=self._headers("application/json")
            ) as resp:
                if resp.status != 200:
                    return None
                text = await resp.text()
        except Exception:  # noqa: BLE001 - metadata is optional
            return None

        try:
            decoded = json.loads(strip_gerrit_xssi(text))
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None


def _decode_gerrit_patch(encoded_patch: str) -> str:
    raw = "".join(strip_gerrit_xssi(encoded_patch).split())
    try:
        return base64.b64decode(raw.encode("ascii")).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise DiffSourceError("failed to decode Gerrit patch response") from exc


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bundle_from_gerrit(
    target: GerritTarget,
    identifier: str,
    diff_text: str,
    meta: Mapping[str, Any] | None,
) -> ChangeBundle:
    meta = meta or {}
    owner = _as_mapping(meta.get("owner"))
    owner_name = owner.get("name") or owner.get("username") or owner.get("email")
    author = Author(name=str(owner_name)) if owner_name else None

    project = str(meta.get("project") or target.project or "") or None
    title = str(meta.get("subject") or f"Gerrit change {target.change}")
    description = _commit_message(meta)

    return ChangeBundle(
        diff_text=diff_text,
        title=title,
        description=description,
        author=author,
        branch=str(meta.get("branch")) if meta.get("branch") else None,
        target=str(meta.get("branch")) if meta.get("branch") else None,
        repo=project,
        source_kind="gerrit",
        source_id=identifier,
    )


def _commit_message(meta: Mapping[str, Any]) -> str | None:
    revisions = _as_mapping(meta.get("revisions"))
    current_revision = meta.get("current_revision")
    revision_meta = _as_mapping(revisions.get(current_revision)) if current_revision else {}
    commit = _as_mapping(revision_meta.get("commit"))
    message = commit.get("message")
    return str(message) if message else None
