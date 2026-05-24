"""Endpoint configuration for Claude Agent SDK.

This module owns the mapping between environment-variable-style strings
(as produced by ``.env`` files or shell exports) and the typed
:class:`EndpointConfig` used internally.

Design notes
------------
* ``frozen=True``: configs are pass-by-value and safe to share across threads.
* ``to_env_dict()`` only emits keys whose values are set, so the dict
  passed to :class:`claude_agent_sdk.ClaudeAgentOptions` never overrides
  inherited environment variables with empty strings.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields

_TRUTHY = frozenset({"1", "true", "yes", "y", "on"})


def _read(mapping: Mapping[str, str], key: str) -> str | None:
    value = mapping.get(key)
    if value is None or value == "":
        return None
    return value


@dataclass(frozen=True)
class EndpointConfig:
    """Typed view of the Anthropic-compatible endpoint environment.

    All fields are optional. A field that is ``None`` means "do not
    override the inherited environment for this variable".
    """

    auth_token: str | None
    base_url: str | None
    default_haiku_model: str | None
    default_sonnet_model: str | None
    default_opus_model: str | None
    api_timeout_ms: int | None
    disable_nonessential_traffic: bool = False

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str]) -> EndpointConfig:
        """Build a config from an env-style mapping.

        Empty strings are treated as missing — a common pattern in
        ``.env`` files where a key is declared but intentionally blank.
        """
        timeout_raw = _read(mapping, "API_TIMEOUT_MS")
        if timeout_raw is None:
            timeout_ms: int | None = None
        else:
            try:
                timeout_ms = int(timeout_raw)
            except ValueError as exc:
                raise ValueError(
                    f"API_TIMEOUT_MS must be an integer, got {timeout_raw!r}"
                ) from exc

        disable_raw = _read(mapping, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC")
        disable = disable_raw is not None and disable_raw.lower() in _TRUTHY

        return cls(
            auth_token=_read(mapping, "ANTHROPIC_AUTH_TOKEN"),
            base_url=_read(mapping, "ANTHROPIC_BASE_URL"),
            default_haiku_model=_read(mapping, "ANTHROPIC_DEFAULT_HAIKU_MODEL"),
            default_sonnet_model=_read(mapping, "ANTHROPIC_DEFAULT_SONNET_MODEL"),
            default_opus_model=_read(mapping, "ANTHROPIC_DEFAULT_OPUS_MODEL"),
            api_timeout_ms=timeout_ms,
            disable_nonessential_traffic=disable,
        )

    def to_env_dict(self) -> dict[str, str]:
        """Render to a ``dict[str, str]`` suitable for ``ClaudeAgentOptions.env``.

        Only set fields are emitted, so this dict can be passed without
        clobbering inherited variables that we intentionally did not override.
        """
        out: dict[str, str] = {}
        if self.auth_token is not None:
            out["ANTHROPIC_AUTH_TOKEN"] = self.auth_token
        if self.base_url is not None:
            out["ANTHROPIC_BASE_URL"] = self.base_url
        if self.default_haiku_model is not None:
            out["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = self.default_haiku_model
        if self.default_sonnet_model is not None:
            out["ANTHROPIC_DEFAULT_SONNET_MODEL"] = self.default_sonnet_model
        if self.default_opus_model is not None:
            out["ANTHROPIC_DEFAULT_OPUS_MODEL"] = self.default_opus_model
        if self.api_timeout_ms is not None:
            out["API_TIMEOUT_MS"] = str(self.api_timeout_ms)
        if self.disable_nonessential_traffic:
            out["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
        return out

    def has_overrides(self) -> bool:
        """Return True if any field would be emitted by :meth:`to_env_dict`."""
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name == "disable_nonessential_traffic":
                if value:
                    return True
            elif value is not None:
                return True
        return False
