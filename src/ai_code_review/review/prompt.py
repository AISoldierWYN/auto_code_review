"""Prompt assembly — combine SKILL, applicable rules, and diff into prompts.

The pattern: the SKILL goes into the **system prompt** so it's stable across
all reviews. The rules + diff go into the **user prompt** so they're treated
as the current task's inputs. This keeps the agent's persona/output-format
instructions separate from per-run data.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai_code_review.models.rule import Rule


@dataclass(frozen=True)
class Prompts:
    system_prompt: str
    user_prompt: str


def normalize_review_language(review_language: str | None) -> str:
    """Return the supported language code used for human-facing review text."""
    raw = (review_language or "en").strip().lower().replace("_", "-")
    if raw in {"zh", "zh-cn", "cn", "chinese", "simplified-chinese"}:
        return "zh"
    if raw in {"en", "en-us", "english"}:
        return "en"
    return "en"


def _language_instruction(review_language: str | None) -> str:
    language = normalize_review_language(review_language)
    if language == "zh":
        return (
            "Write every human-facing review field in Simplified Chinese: "
            "finding.title, finding.body, suggestion.text when present, and "
            "summary.text. Keep schema keys, rule ids, file paths, code, symbols, "
            "and fenced YAML structure unchanged."
        )
    return (
        "Write every human-facing review field in English: finding.title, "
        "finding.body, suggestion.text when present, and summary.text. Keep "
        "schema keys, rule ids, file paths, code, symbols, and fenced YAML "
        "structure unchanged."
    )


def _serialize_rule(rule: Rule) -> str:
    """Emit a lean YAML-like form for one rule (no original_case, no source.refs)."""
    signals = "\n".join(f"    - {s}" for s in rule.trigger.signals)
    lines = [
        f"- rule_id: {rule.rule_id}",
        f"  title: {rule.title}",
        f"  category: {rule.category}",
        f"  severity: {rule.severity}",
        f"  source_type: {rule.source.type}",
        "  trigger:",
        "    description: |",
        *(f"      {line}" for line in rule.trigger.description.splitlines() or [""]),
        "    signals:",
        signals,
        "  risk: |",
        *(f"    {line}" for line in rule.risk.splitlines() or [""]),
        "  suggestion: |",
        *(f"    {line}" for line in rule.suggestion.splitlines() or [""]),
    ]
    return "\n".join(lines)


def build_prompts(
    skill: str,
    rules: list[Rule],
    diff_text: str,
    review_language: str | None = "en",
) -> Prompts:
    """Build the system + user prompts for a single review run.

    The system prompt carries the SKILL verbatim. The user prompt has two
    labeled sections — ``RULES:`` and ``DIFF:`` — that match what SKILL
    documents the agent will receive.
    """
    if rules:
        rules_block = "\n".join(_serialize_rule(r) for r in rules)
    else:
        rules_block = "(no applicable rules — emit zero finding blocks and a brief summary)"

    user_prompt = (
        "# OUTPUT_LANGUAGE\n"
        f"{_language_instruction(review_language)}\n"
        "\n"
        "# RULES\n"
        f"{rules_block}\n"
        "\n"
        "# DIFF\n"
        f"{diff_text}\n"
    )
    return Prompts(system_prompt=skill, user_prompt=user_prompt)
