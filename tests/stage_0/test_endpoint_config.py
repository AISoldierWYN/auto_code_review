"""Unit tests for EndpointConfig — Stage 0.

These tests pin down the contract of EndpointConfig BEFORE it exists,
following the TDD workflow from v1_plan.md §9.3.
"""

from __future__ import annotations

import pytest

from ai_code_review.config.endpoint import EndpointConfig


class TestFromMapping:
    """from_mapping(): parse env-like dict into EndpointConfig."""

    def test_parses_all_known_fields(self) -> None:
        mapping = {
            "ANTHROPIC_AUTH_TOKEN": "sk-test",
            "ANTHROPIC_BASE_URL": "https://example.com/v1",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "haiku-x",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "sonnet-x",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "opus-x",
            "API_TIMEOUT_MS": "3000000",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        }
        cfg = EndpointConfig.from_mapping(mapping)
        assert cfg.auth_token == "sk-test"
        assert cfg.base_url == "https://example.com/v1"
        assert cfg.default_haiku_model == "haiku-x"
        assert cfg.default_sonnet_model == "sonnet-x"
        assert cfg.default_opus_model == "opus-x"
        assert cfg.api_timeout_ms == 3_000_000
        assert cfg.disable_nonessential_traffic is True

    def test_missing_fields_become_none(self) -> None:
        cfg = EndpointConfig.from_mapping({})
        assert cfg.auth_token is None
        assert cfg.base_url is None
        assert cfg.default_haiku_model is None
        assert cfg.default_sonnet_model is None
        assert cfg.default_opus_model is None
        assert cfg.api_timeout_ms is None
        assert cfg.disable_nonessential_traffic is False

    def test_empty_string_treated_as_missing(self) -> None:
        # Common case from .env files with blank values.
        cfg = EndpointConfig.from_mapping(
            {"ANTHROPIC_AUTH_TOKEN": "", "ANTHROPIC_BASE_URL": ""}
        )
        assert cfg.auth_token is None
        assert cfg.base_url is None

    def test_disable_flag_truthy_values(self) -> None:
        for v in ("1", "true", "TRUE", "yes"):
            cfg = EndpointConfig.from_mapping({"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": v})
            assert cfg.disable_nonessential_traffic is True, f"failed for {v!r}"

    def test_disable_flag_falsy_values(self) -> None:
        for v in ("0", "false", "FALSE", "no", ""):
            cfg = EndpointConfig.from_mapping({"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": v})
            assert cfg.disable_nonessential_traffic is False, f"failed for {v!r}"

    def test_invalid_timeout_raises(self) -> None:
        with pytest.raises(ValueError, match="API_TIMEOUT_MS"):
            EndpointConfig.from_mapping({"API_TIMEOUT_MS": "not-a-number"})


class TestToEnvDict:
    """to_env_dict(): emit a dict suitable for ClaudeAgentOptions(env=...)."""

    def test_only_emits_non_none_fields(self) -> None:
        cfg = EndpointConfig(
            auth_token="sk-abc",
            base_url="https://x",
            default_haiku_model=None,
            default_sonnet_model=None,
            default_opus_model=None,
            api_timeout_ms=None,
            disable_nonessential_traffic=False,
        )
        env = cfg.to_env_dict()
        assert env == {
            "ANTHROPIC_AUTH_TOKEN": "sk-abc",
            "ANTHROPIC_BASE_URL": "https://x",
        }

    def test_disable_flag_emits_when_true(self) -> None:
        cfg = EndpointConfig(
            auth_token=None,
            base_url=None,
            default_haiku_model=None,
            default_sonnet_model=None,
            default_opus_model=None,
            api_timeout_ms=None,
            disable_nonessential_traffic=True,
        )
        env = cfg.to_env_dict()
        assert env == {"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}

    def test_disable_flag_omitted_when_false(self) -> None:
        cfg = EndpointConfig(
            auth_token=None,
            base_url=None,
            default_haiku_model=None,
            default_sonnet_model=None,
            default_opus_model=None,
            api_timeout_ms=None,
            disable_nonessential_traffic=False,
        )
        assert cfg.to_env_dict() == {}

    def test_timeout_serialized_as_string(self) -> None:
        cfg = EndpointConfig(
            auth_token=None,
            base_url=None,
            default_haiku_model=None,
            default_sonnet_model=None,
            default_opus_model=None,
            api_timeout_ms=3_000_000,
            disable_nonessential_traffic=False,
        )
        assert cfg.to_env_dict() == {"API_TIMEOUT_MS": "3000000"}

    def test_full_roundtrip(self) -> None:
        original = {
            "ANTHROPIC_AUTH_TOKEN": "tok",
            "ANTHROPIC_BASE_URL": "https://e",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "h",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "s",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "o",
            "API_TIMEOUT_MS": "1000",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        }
        cfg = EndpointConfig.from_mapping(original)
        assert cfg.to_env_dict() == original


class TestImmutability:
    def test_is_frozen(self) -> None:
        cfg = EndpointConfig.from_mapping({})
        with pytest.raises((AttributeError, Exception)):
            cfg.auth_token = "tampered"  # type: ignore[misc]


class TestHasOverrides:
    """has_overrides(): true if any env field is set — used to decide whether to inject."""

    def test_empty_config_has_no_overrides(self) -> None:
        cfg = EndpointConfig.from_mapping({})
        assert cfg.has_overrides() is False

    def test_only_disable_flag_is_an_override(self) -> None:
        cfg = EndpointConfig.from_mapping({"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
        assert cfg.has_overrides() is True

    def test_with_base_url_is_an_override(self) -> None:
        cfg = EndpointConfig.from_mapping({"ANTHROPIC_BASE_URL": "https://x"})
        assert cfg.has_overrides() is True
