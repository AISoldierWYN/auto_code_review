"""CLI: print Stage 2 case coverage and expected-rule recall quality."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from ai_code_review.rules.loader import load_rules
from ai_code_review.testing.case_coverage import (
    build_case_coverage_report,
    render_case_coverage_markdown,
)
from ai_code_review.testing.cases import discover_cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules-dir", type=Path, default=Path("rules"))
    parser.add_argument("--cases-root", type=Path, default=Path("tests/cases"))
    parser.add_argument("--case-prefix", default=None)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--max-rules", type=int, default=50)
    parser.add_argument(
        "--no-max-rules",
        action="store_true",
        help="disable L4 pruning while checking expected-rule recall",
    )
    parser.add_argument(
        "--fail-on-recall-misses",
        action="store_true",
        help="exit with status 2 when any expected rule is not recalled",
    )
    parser.add_argument(
        "--fail-on-forbidden-recalls",
        action="store_true",
        help="exit with status 4 when any forbidden rule is recalled",
    )
    parser.add_argument(
        "--fail-on-uncovered",
        action="store_true",
        help="exit with status 3 when production rules have no expected case",
    )
    args = parser.parse_args()

    rules = load_rules(args.rules_dir)
    cases = discover_cases(args.cases_root, fallback_rules_dir=args.rules_dir)
    if args.case_prefix:
        cases = [case for case in cases if case.name.startswith(args.case_prefix)]

    max_rules = None if args.no_max_rules else args.max_rules
    report = build_case_coverage_report(rules, cases, max_rules=max_rules)

    if args.format == "json":
        print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
    else:
        print(render_case_coverage_markdown(report))

    if args.fail_on_recall_misses and report.recall_misses:
        raise SystemExit(2)
    if args.fail_on_uncovered and report.uncovered_rule_ids:
        raise SystemExit(3)
    if args.fail_on_forbidden_recalls and report.forbidden_recall_hits:
        raise SystemExit(4)


if __name__ == "__main__":
    main()
