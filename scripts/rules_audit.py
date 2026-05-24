"""CLI: print a Stage 2 rule inventory and health report."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from ai_code_review.rules.audit import (
    build_rule_inventory,
    render_rule_inventory_markdown,
)
from ai_code_review.rules.loader import load_rules


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules-dir", type=Path, default=Path("rules"))
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="exit with status 2 when non-fatal audit warnings are present",
    )
    args = parser.parse_args()

    rules = load_rules(args.rules_dir)
    inventory = build_rule_inventory(rules)

    if args.format == "json":
        print(json.dumps(asdict(inventory), indent=2, ensure_ascii=False))
    else:
        print(render_rule_inventory_markdown(inventory))

    if args.fail_on_warnings and inventory.warnings:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
