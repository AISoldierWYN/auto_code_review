"""Agent runner — call Claude Agent SDK with prompts and collect output.

The runner is split into:
  * :class:`AgentRunner` Protocol — what the pipeline depends on (pure
    interface, easy to mock in tests)
  * :class:`ClaudeSdkAgentRunner` — concrete implementation backed by
    ``claude-agent-sdk``

The protocol takes a ``Prompts`` object and a workspace directory; returns
the raw agent text output. Parsing happens elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from ai_code_review.config.endpoint import EndpointConfig
from ai_code_review.review.prompt import Prompts


@dataclass(frozen=True)
class AgentRunResult:
    text: str
    is_error: bool
    used_tools: tuple[str, ...]


class AgentRunner(Protocol):
    async def run(self, prompts: Prompts, workspace: Path) -> AgentRunResult: ...


@dataclass(frozen=True)
class ClaudeSdkAgentRunner:
    """Concrete runner backed by ``claude-agent-sdk``.

    ``endpoint`` controls env injection (third-party vs. local CLI creds).
    ``model`` is the direct model name to use (must be the endpoint's real
    model id — see Stage 0 review on why aliases don't work).
    """

    endpoint: EndpointConfig
    model: str
    allowed_tools: tuple[str, ...] = ("Read", "Glob", "Grep")
    max_turns: int = 20

    async def run(self, prompts: Prompts, workspace: Path) -> AgentRunResult:
        options = ClaudeAgentOptions(
            env=self.endpoint.to_env_dict(),
            model=self.model,
            system_prompt=prompts.system_prompt,
            allowed_tools=list(self.allowed_tools),
            max_turns=self.max_turns,
            permission_mode="bypassPermissions",
            cwd=str(workspace.resolve()),
        )

        chunks: list[str] = []
        used_tools: set[str] = set()
        is_error = False

        async for msg in query(prompt=prompts.user_prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        chunks.append(block.text)
                    else:
                        # Tool-use blocks expose a ``name`` attribute on the SDK
                        # side; tolerate absence for forward compatibility.
                        name = getattr(block, "name", None)
                        if name:
                            used_tools.add(str(name))
            elif isinstance(msg, ResultMessage):
                is_error = bool(msg.is_error)

        return AgentRunResult(
            text="".join(chunks),
            is_error=is_error,
            used_tools=tuple(sorted(used_tools)),
        )
