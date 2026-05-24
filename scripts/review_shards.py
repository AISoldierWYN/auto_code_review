"""CLI: print the Stage 2 file-level review shard plan for a diff."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from ai_code_review.review.shards import (
    plan_file_review_shards,
    render_review_shard_plan_markdown,
)
from ai_code_review.rules.loader import load_rules


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diff", type=Path, required=True)
    parser.add_argument("--rules-dir", type=Path, default=Path("rules"))
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--max-rules", type=int, default=50)
    parser.add_argument("--no-max-rules", action="store_true")
    parser.add_argument(
        "--include-empty",
        action="store_true",
        help="include files that have no recalled rules",
    )
    args = parser.parse_args()

    rules = load_rules(args.rules_dir)
    diff_text = args.diff.read_text(encoding="utf-8")
    max_rules = None if args.no_max_rules else args.max_rules
    plan = plan_file_review_shards(
        rules,
        diff_text,
        max_rules=max_rules,
        include_empty=args.include_empty,
    )

    if args.format == "json":
        print(json.dumps(asdict(plan), indent=2, ensure_ascii=False))
    else:
        print(render_review_shard_plan_markdown(plan))


if __name__ == "__main__":
    main()
