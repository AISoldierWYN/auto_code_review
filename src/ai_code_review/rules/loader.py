"""Rule loader — reads ``rules/**/*.yaml`` files into :class:`Rule` objects.

Validation is intentionally strict: a malformed rule fails the whole load,
because shipping a broken rule into review silently is worse than crashing
the run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, get_args

import yaml

from ai_code_review.models.rule import (
    AppliesTo,
    OriginalCase,
    RecallHints,
    Rule,
    RuleSource,
    Severity,
    SourceType,
    Trigger,
)

_VALID_SEVERITIES = set(get_args(Severity))
_VALID_SOURCE_TYPES = set(get_args(SourceType))


class RuleLoadError(ValueError):
    """Raised when a rule file is malformed or violates the schema."""


def _require(d: dict, key: str, where: str) -> Any:
    if key not in d:
        raise RuleLoadError(f"{where}: missing required field {key!r}")
    return d[key]


def _as_tuple(value: Any, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise RuleLoadError(f"{where}: expected a list, got {type(value).__name__}")
    return tuple(str(x) for x in value)


def _parse_rule(data: dict, file: Path) -> Rule:
    where = f"{file.name}"

    rule_id = str(_require(data, "rule_id", where))
    title = str(_require(data, "title", where))
    category = str(_require(data, "category", where))

    severity = str(_require(data, "severity", where))
    if severity not in _VALID_SEVERITIES:
        raise RuleLoadError(
            f"{where}: severity {severity!r} must be one of {sorted(_VALID_SEVERITIES)}"
        )

    source_raw = _require(data, "source", where)
    if not isinstance(source_raw, dict):
        raise RuleLoadError(f"{where}: 'source' must be a mapping")
    source_type = str(_require(source_raw, "type", f"{where}.source"))
    if source_type not in _VALID_SOURCE_TYPES:
        raise RuleLoadError(
            f"{where}: source.type {source_type!r} must be one of "
            f"{sorted(_VALID_SOURCE_TYPES)}"
        )
    refs = _as_tuple(_require(source_raw, "refs", f"{where}.source"), f"{where}.source.refs")
    if not refs:
        raise RuleLoadError(f"{where}: source.refs must have at least one entry")
    source = RuleSource(type=source_type, refs=refs)  # type: ignore[arg-type]

    at_raw = _require(data, "applies_to", where)
    if not isinstance(at_raw, dict):
        raise RuleLoadError(f"{where}: 'applies_to' must be a mapping")
    applies_to = AppliesTo(
        languages=_as_tuple(
            _require(at_raw, "languages", f"{where}.applies_to"),
            f"{where}.applies_to.languages",
        ),
        paths=_as_tuple(
            _require(at_raw, "paths", f"{where}.applies_to"),
            f"{where}.applies_to.paths",
        ),
        exclude_paths=_as_tuple(
            at_raw.get("exclude_paths"), f"{where}.applies_to.exclude_paths"
        ),
    )

    trig_raw = _require(data, "trigger", where)
    if not isinstance(trig_raw, dict):
        raise RuleLoadError(f"{where}: 'trigger' must be a mapping")
    trigger = Trigger(
        description=str(_require(trig_raw, "description", f"{where}.trigger")),
        signals=_as_tuple(
            _require(trig_raw, "signals", f"{where}.trigger"),
            f"{where}.trigger.signals",
        ),
    )
    if not trigger.signals:
        raise RuleLoadError(f"{where}: trigger.signals must have at least one entry")

    risk = str(_require(data, "risk", where))
    suggestion = str(_require(data, "suggestion", where))

    original_case: OriginalCase | None = None
    oc_raw = data.get("original_case")
    if isinstance(oc_raw, dict):
        original_case = OriginalCase(
            bug_link=oc_raw.get("bug_link"),
            minimal_repro=oc_raw.get("minimal_repro"),
            fix_diff=oc_raw.get("fix_diff"),
        )

    recall = RecallHints()
    recall_raw = data.get("recall")
    if recall_raw is not None:
        if not isinstance(recall_raw, dict):
            raise RuleLoadError(f"{where}: 'recall' must be a mapping")
        recall = RecallHints(
            keywords=_as_tuple(recall_raw.get("keywords"), f"{where}.recall.keywords"),
            regexes=_as_tuple(recall_raw.get("regexes"), f"{where}.recall.regexes"),
        )

    return Rule(
        rule_id=rule_id,
        title=title,
        category=category,
        severity=severity,  # type: ignore[arg-type]
        source=source,
        applies_to=applies_to,
        trigger=trigger,
        risk=risk,
        suggestion=suggestion,
        original_case=original_case,
        recall=recall,
    )


def load_rules(root: Path) -> list[Rule]:
    """Load every ``*.yaml`` file under *root* recursively.

    Raises :class:`RuleLoadError` if any file is malformed or duplicate
    ``rule_id`` values are present.
    """
    if not root.exists():
        return []

    seen: dict[str, Path] = {}
    rules: list[Rule] = []
    for yaml_path in sorted(root.rglob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise RuleLoadError(f"{yaml_path}: invalid YAML: {exc}") from exc
        if not isinstance(data, dict):
            raise RuleLoadError(f"{yaml_path}: top-level value must be a mapping")

        rule = _parse_rule(data, yaml_path)
        if rule.rule_id in seen:
            raise RuleLoadError(
                f"duplicate rule_id {rule.rule_id!r}: "
                f"first seen in {seen[rule.rule_id]}, now in {yaml_path}"
            )
        seen[rule.rule_id] = yaml_path
        rules.append(rule)

    return rules
