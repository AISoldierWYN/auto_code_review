"""Parse the agent's textual output into structured findings + summary.

The SKILL prompts the agent to emit ``finding`` and ``summary`` fenced YAML
blocks, terminated by an ``END_OF_REVIEW`` sentinel. This module extracts
those blocks, parses the YAML inside each, and validates required fields.

Lenient where it can be safely lenient (missing sentinel is a warning, not
an error). Strict where strictness protects downstream consumers (a finding
without a ``line`` or ``severity`` would render badly in the UI).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import yaml

from ai_code_review.models.finding import Finding, Rationale, Suggestion, Summary

_BLOCK_RE = re.compile(
    r"```(?P<kind>finding|summary)\s*\n(?P<body>.*?)\n```",
    re.DOTALL,
)
_SENTINEL = "END_OF_REVIEW"


class OutputParseError(ValueError):
    """Raised when the agent output cannot be parsed."""


@dataclass(frozen=True)
class ParsedOutput:
    findings: tuple[Finding, ...]
    summary: Summary


def _require(d: dict, key: str, where: str) -> Any:
    if key not in d:
        raise OutputParseError(f"{where}: missing required field {key!r}")
    return d[key]


def _as_str_tuple(value: Any) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, list):
        return tuple(str(x) for x in value)
    return (str(value),)


def _build_finding(data: dict, idx: int) -> Finding:
    where = f"finding #{idx}"
    try:
        rule_id = str(_require(data, "rule_id", where))
        file = str(_require(data, "file", where))
        line = int(_require(data, "line", where))
        severity = str(_require(data, "severity", where))
        category = str(_require(data, "category", where))
        confidence = float(_require(data, "confidence", where))
        title = str(_require(data, "title", where))
        body = str(_require(data, "body", where))
    except (TypeError, ValueError) as exc:
        raise OutputParseError(f"{where}: {exc}") from exc

    kind = data.get("suggestion_kind", "none")
    suggestion: Suggestion | None
    if kind == "patch":
        suggestion = Suggestion(
            kind="patch",
            remove=_as_str_tuple(data.get("suggestion_remove")),
            add=_as_str_tuple(data.get("suggestion_add")),
        )
    elif kind == "text":
        suggestion = Suggestion(
            kind="text",
            text=str(data.get("suggestion_text", "")),
        )
    else:
        suggestion = None

    # Rationale fields are filled by the pipeline (from the matched rule),
    # not by the agent. Use placeholders here; the pipeline overwrites them.
    rationale = Rationale(rule_source_type="typical_case", source_refs=())

    return Finding(
        id=f"c{idx}",
        rule_id=rule_id,
        severity=severity,  # type: ignore[arg-type]
        category=category,
        file=file,
        line=line,
        confidence=confidence,
        title=title.strip(),
        body=body.strip(),
        suggestion=suggestion,
        rationale=rationale,
    )


def _load_yaml(body: str, where: str) -> dict:
    try:
        data = yaml.safe_load(body)
    except yaml.YAMLError as exc:
        raise OutputParseError(f"{where}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise OutputParseError(f"{where}: expected a mapping, got {type(data).__name__}")
    return data


def parse_agent_output(text: str) -> ParsedOutput:
    """Parse the full agent output into ParsedOutput.

    Strategy:
      1. Truncate at the first ``END_OF_REVIEW`` sentinel if present.
      2. Iterate every fenced block in order; parse ``finding`` blocks as
         findings, ``summary`` block(s) — only the FIRST summary is kept.
      3. Validate that at least one summary was found.
    """
    if _SENTINEL in text:
        text = text.split(_SENTINEL, 1)[0]

    findings: list[Finding] = []
    summary_text: str | None = None

    for match in _BLOCK_RE.finditer(text):
        kind = match.group("kind")
        body = match.group("body")
        if kind == "finding":
            data = _load_yaml(body, f"finding #{len(findings) + 1}")
            findings.append(_build_finding(data, len(findings) + 1))
        elif kind == "summary":
            if summary_text is None:
                data = _load_yaml(body, "summary")
                summary_text = str(_require(data, "text", "summary")).strip()

    if summary_text is None:
        raise OutputParseError("no summary block found in agent output")

    return ParsedOutput(findings=tuple(findings), summary=Summary(text=summary_text))
