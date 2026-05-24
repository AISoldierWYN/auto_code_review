"""Test-case fixture loader.

Users drop directories under ``tests/cases/case_<name>/`` and the framework
discovers them. Each case bundles:

* ``case.yaml``      — metadata + expected outcomes
* ``change.diff``    — the unified diff under review
* ``workspace/``     — after-state files (mirror the repo's layout)
* ``rules/``         — (optional) the rules to use for this case

Stage 1 deliberately rejects ``before/`` — only ``workspace/`` (after state)
is supported. See docs/stages/stage_1_goal.md §4.4.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class CaseLoadError(ValueError):
    """Raised when a test-case directory is malformed."""


@dataclass(frozen=True)
class ExpectedFinding:
    rule_id: str
    file: str
    line_range: tuple[int, int]

    def matches(self, *, rule_id: str, file: str, line: int) -> bool:
        if rule_id != self.rule_id:
            return False
        if file != self.file:
            return False
        return self.line_range[0] <= line <= self.line_range[1]


@dataclass(frozen=True)
class ExpectedOutcome:
    findings: tuple[ExpectedFinding, ...]
    forbidden_rule_ids: tuple[str, ...] = ()
    forbid_other_critical: bool = False
    summary_substring: str | None = None


@dataclass(frozen=True)
class CaseFixture:
    name: str
    description: str
    diff_path: Path
    workspace_dir: Path
    rules_dir: Path
    expected: ExpectedOutcome
    language_hint: str | None = None


def _require(d: dict, key: str, where: str) -> Any:
    if key not in d:
        raise CaseLoadError(f"{where}: missing required field {key!r}")
    return d[key]


def _parse_line_range(value: Any, where: str) -> tuple[int, int]:
    if isinstance(value, int):
        return (value, value)
    if isinstance(value, list) and len(value) == 2 and all(isinstance(x, int) for x in value):
        return (value[0], value[1])
    raise CaseLoadError(
        f"{where}: line_range must be an int or a [start, end] pair, got {value!r}"
    )


def _parse_expected(data: dict, where: str) -> ExpectedOutcome:
    findings_raw = data.get("findings", []) or []
    findings: list[ExpectedFinding] = []
    for idx, ef_raw in enumerate(findings_raw):
        sub = f"{where}.findings[{idx}]"
        findings.append(
            ExpectedFinding(
                rule_id=str(_require(ef_raw, "rule_id", sub)),
                file=str(_require(ef_raw, "file", sub)),
                line_range=_parse_line_range(
                    _require(ef_raw, "line_range", sub), f"{sub}.line_range"
                ),
            )
        )
    return ExpectedOutcome(
        findings=tuple(findings),
        forbidden_rule_ids=_as_str_tuple(
            data.get("forbidden_rules"), f"{where}.forbidden_rules"
        ),
        forbid_other_critical=bool(data.get("forbid_other_critical", False)),
        summary_substring=data.get("summary_substring"),
    )


def _as_str_tuple(value: Any, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise CaseLoadError(f"{where}: expected a list, got {type(value).__name__}")
    return tuple(str(item) for item in value)


def load_case(
    case_dir: Path, fallback_rules_dir: Path | None = None
) -> CaseFixture:
    """Load one test case from a directory; raise CaseLoadError if malformed.

    ``fallback_rules_dir``: used when the case has no ``rules/`` subdir.
    Pass the project-level ``rules/`` here so most cases run against the full
    production rule library. Set to None for legacy behaviour (use case-local
    path even if absent).
    """
    if not case_dir.is_dir():
        raise CaseLoadError(f"{case_dir} is not a directory")

    case_yaml = case_dir / "case.yaml"
    if not case_yaml.exists():
        raise CaseLoadError(f"{case_dir}: missing case.yaml")

    try:
        data = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CaseLoadError(f"{case_yaml}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise CaseLoadError(f"{case_yaml}: top-level must be a mapping")

    name = str(_require(data, "name", str(case_yaml)))
    if name != case_dir.name:
        raise CaseLoadError(
            f"{case_yaml}: name {name!r} must match directory name {case_dir.name!r}"
        )

    diff_path = case_dir / "change.diff"
    if not diff_path.exists():
        raise CaseLoadError(f"{case_dir}: missing change.diff")

    workspace_dir = case_dir / "workspace"
    if not workspace_dir.is_dir():
        if (case_dir / "before").is_dir():
            raise CaseLoadError(
                f"{case_dir}: found before/ but Stage 1 requires workspace/ "
                f"(after state). Automatic before/ -> workspace/ apply is "
                f"planned for Stage 1.5."
            )
        raise CaseLoadError(f"{case_dir}: missing workspace/ directory")

    case_local_rules = case_dir / "rules"
    if case_local_rules.is_dir():
        rules_dir = case_local_rules
    elif fallback_rules_dir is not None:
        rules_dir = fallback_rules_dir
    else:
        rules_dir = case_local_rules  # caller (load_rules) returns [] if absent

    expected = _parse_expected(
        data.get("expected", {}) or {}, where=f"{case_yaml}.expected"
    )

    return CaseFixture(
        name=name,
        description=str(data.get("description", "")),
        diff_path=diff_path,
        workspace_dir=workspace_dir,
        rules_dir=rules_dir,
        expected=expected,
        language_hint=data.get("language_hint"),
    )


def discover_cases(
    root: Path, fallback_rules_dir: Path | None = None
) -> list[CaseFixture]:
    """Discover all valid test cases under *root*.

    A directory is considered a case if it starts with ``case_`` and contains
    a ``case.yaml`` file. Other directories are silently skipped.

    ``fallback_rules_dir`` propagates to every loaded case (see :func:`load_case`).
    """
    if not root.is_dir():
        return []
    cases: list[CaseFixture] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or not entry.name.startswith("case_"):
            continue
        if not (entry / "case.yaml").exists():
            continue
        cases.append(load_case(entry, fallback_rules_dir=fallback_rules_dir))
    return cases
