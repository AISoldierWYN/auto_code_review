"""Stage 0 smoke test A — reuse the local Claude CLI credentials.

Run: ``python scripts/step0_local_cli.py``

Pass condition: a non-empty text response from the model and exit code 0.

We do NOT inject any env vars, so the spawned ``claude`` subprocess
inherits the current shell environment and uses whatever credentials
the user has already configured via ``claude login``.
"""

from __future__ import annotations

import asyncio
import sys

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)


async def run_smoke_test() -> int:
    options = ClaudeAgentOptions(
        # No env override — let the subprocess inherit local creds.
        # No tools needed — pure text round-trip.
        allowed_tools=[],
        max_turns=1,
        permission_mode="bypassPermissions",
    )

    prompt = "Reply with exactly the single word: PONG"
    saw_text = False
    final_result: ResultMessage | None = None

    print("[smoke A] sending prompt to local-CLI-backed agent ...", flush=True)
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    text = block.text.strip()
                    if text:
                        saw_text = True
                        print(f"[smoke A] assistant: {text}", flush=True)
        elif isinstance(msg, ResultMessage):
            final_result = msg

    if not saw_text:
        print("[smoke A] FAIL — no assistant text received", file=sys.stderr)
        return 2
    if final_result is None:
        print("[smoke A] FAIL — no ResultMessage received", file=sys.stderr)
        return 3
    if final_result.is_error:
        print(f"[smoke A] FAIL — result error: {final_result}", file=sys.stderr)
        return 4

    print("[smoke A] PASS", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run_smoke_test()))
