"""CLI: publish or dry-run a generated review report.

Examples:

    python scripts/publish_review.py --review reviews/demo/review.json \\
        --platform gerrit --target https://gerrit.example.com/c/project/+/123

    python scripts/publish_review.py --review reviews/demo/review.json \\
        --platform github --target https://github.com/owner/repo/pull/123 \\
        --mode submit
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from ai_code_review.publish import PublishMode, ReviewPublisherError, create_publisher


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish an AI code review report to GitHub or Gerrit."
    )
    parser.add_argument("--review", required=True, type=Path, help="Path to review.json")
    parser.add_argument("--platform", required=True, choices=("github", "gerrit"))
    parser.add_argument(
        "--target",
        default=None,
        help="PR/CL URL. Defaults to review.review.diff_path when available.",
    )
    parser.add_argument(
        "--mode",
        default="dry_run",
        choices=("dry_run", "draft", "submit"),
        help="dry_run prints payloads; submit performs platform write-back.",
    )
    parser.add_argument("--out", type=Path, default=None, help="Optional result JSON path")
    return parser.parse_args()


def _load_review(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ReviewPublisherError(f"cannot read review file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ReviewPublisherError(f"invalid review JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ReviewPublisherError("review JSON root must be an object")
    return data


async def _amain() -> int:
    args = _parse_args()
    review = _load_review(args.review)
    publisher = create_publisher(args.platform, target=args.target)
    result = await publisher.publish(review, mode=cast(PublishMode, args.mode))
    output = json.dumps(asdict(result), ensure_ascii=False, indent=2)

    if args.out is None:
        print(output)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")
        print(f"[publish] wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(_amain()))
    except ReviewPublisherError as exc:
        print(f"[publish] {exc}", file=sys.stderr)
        sys.exit(2)
