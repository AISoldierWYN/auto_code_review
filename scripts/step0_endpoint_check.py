"""Stage 0 smoke test B — inject a third-party Anthropic-compatible endpoint.

Run: ``python scripts/step0_endpoint_check.py``

Pass conditions:
  1. The agent returns non-empty assistant text via the third-party endpoint.
  2. The local ``~/.claude/`` user-config files (``.credentials.json``,
     ``settings.json``, ``settings.claude.json``) are NOT modified by this run.

The third-party env (``ANTHROPIC_BASE_URL``, ``ANTHROPIC_AUTH_TOKEN``, model
aliases) is injected via ``ClaudeAgentOptions(env=...)`` so only the SDK's
child process sees it. The local CLI config is intentionally untouched.
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

from ai_code_review.config.endpoint import EndpointConfig
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

WATCHED_LOCAL_FILES = (
    ".credentials.json",
    "settings.json",
    "settings.claude.json",
)


@dataclass(frozen=True)
class FileSnapshot:
    path: Path
    mtime_ns: int
    size: int

    @classmethod
    def of(cls, path: Path) -> FileSnapshot | None:
        if not path.exists():
            return None
        st = path.stat()
        return cls(path=path, mtime_ns=st.st_mtime_ns, size=st.st_size)


def snapshot_local_config() -> dict[str, FileSnapshot | None]:
    base = Path.home() / ".claude"
    return {name: FileSnapshot.of(base / name) for name in WATCHED_LOCAL_FILES}


def diff_snapshots(
    before: dict[str, FileSnapshot | None],
    after: dict[str, FileSnapshot | None],
) -> list[str]:
    changes: list[str] = []
    for name in before:
        b, a = before[name], after[name]
        if b is None and a is None:
            continue
        if b is None or a is None:
            changes.append(f"{name}: existence changed ({b} -> {a})")
            continue
        if b.mtime_ns != a.mtime_ns or b.size != a.size:
            changes.append(
                f"{name}: modified "
                f"(mtime {b.mtime_ns}->{a.mtime_ns}, size {b.size}->{a.size})"
            )
    return changes


def load_endpoint_config() -> EndpointConfig:
    if not ENV_FILE.exists():
        raise SystemExit(
            f"Missing {ENV_FILE}. Copy .env.example to .env and fill in values."
        )
    mapping = {k: v for k, v in dotenv_values(ENV_FILE).items() if v is not None}
    cfg = EndpointConfig.from_mapping(mapping)
    if not cfg.has_overrides():
        raise SystemExit(".env produced an empty EndpointConfig — nothing to inject.")
    if cfg.base_url is None or cfg.auth_token is None:
        raise SystemExit(
            "ANTHROPIC_BASE_URL and ANTHROPIC_AUTH_TOKEN are both required for smoke B."
        )
    return cfg


async def run_smoke_test() -> int:
    cfg = load_endpoint_config()
    env_overrides = cfg.to_env_dict()
    redacted_url = cfg.base_url
    print(f"[smoke B] injecting env -> {sorted(env_overrides)} (base_url={redacted_url})")

    before = snapshot_local_config()

    # Pick the model alias the endpoint maps to its opus default.
    # The third-party config uses ANTHROPIC_DEFAULT_OPUS_MODEL to remap.
    # IMPORTANT: On Claude CLI 2.1.143 the ANTHROPIC_DEFAULT_*_MODEL env vars
    # do NOT remap the "opus"/"sonnet" aliases — the CLI sends the official
    # Anthropic model id and a third-party endpoint will reject it as 400.
    # We must pass the third-party's real model id directly. Prefer the
    # ANTHROPIC_DEFAULT_OPUS_MODEL value from .env so endpoint and model
    # stay in lockstep.
    model_for_endpoint = cfg.default_opus_model or cfg.default_sonnet_model
    if model_for_endpoint is None:
        raise SystemExit(
            "No ANTHROPIC_DEFAULT_OPUS_MODEL or ANTHROPIC_DEFAULT_SONNET_MODEL "
            "in .env — third-party endpoints reject Anthropic-native model ids."
        )

    options = ClaudeAgentOptions(
        env=env_overrides,
        model=model_for_endpoint,
        allowed_tools=[],
        max_turns=1,
        permission_mode="bypassPermissions",
    )
    print(f"[smoke B] model={model_for_endpoint}")

    prompt = "Reply with exactly the single word: PONG"
    saw_text = False
    final_result: ResultMessage | None = None

    print("[smoke B] sending prompt via third-party endpoint ...", flush=True)
    try:
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        text = block.text.strip()
                        if text:
                            saw_text = True
                            print(f"[smoke B] assistant: {text}", flush=True)
            elif isinstance(msg, ResultMessage):
                final_result = msg
    except Exception as exc:  # noqa: BLE001
        print(f"[smoke B] FAIL — exception during query: {exc!r}", file=sys.stderr)
        return 5

    after = snapshot_local_config()
    changes = diff_snapshots(before, after)
    if changes:
        print("[smoke B] FAIL — local CLI config was modified:", file=sys.stderr)
        for c in changes:
            print(f"  - {c}", file=sys.stderr)
        return 10

    if not saw_text:
        print("[smoke B] FAIL — no assistant text received", file=sys.stderr)
        return 2
    if final_result is None:
        print("[smoke B] FAIL — no ResultMessage received", file=sys.stderr)
        return 3
    if final_result.is_error:
        print(f"[smoke B] FAIL — result error: {final_result}", file=sys.stderr)
        return 4

    # Confirm env override didn't leak into the parent process.
    leaked = [k for k in env_overrides if os.environ.get(k) == env_overrides[k]]
    if leaked:
        print(
            f"[smoke B] WARN — env leaked into parent process: {leaked}",
            file=sys.stderr,
        )

    print("[smoke B] PASS — third-party endpoint works, local config untouched")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run_smoke_test()))
