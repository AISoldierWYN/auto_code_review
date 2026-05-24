"""CLI: run a Stage 1 review and write review.json.

Usage::

    python scripts/review.py \\
        --diff examples/stage_1_demo/change.diff \\
        --workspace . \\
        --rules-dir rules/ \\
        --skill skills/code_review.md \\
        --out reviews/demo/review.json

Endpoint config is loaded from ``.env`` in the project root (same as
``step0_endpoint_check.py``). The CLI fails fast if ``.env`` is missing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import dotenv_values

from ai_code_review.config.endpoint import EndpointConfig
from ai_code_review.pipeline import ReviewInput, run_review
from ai_code_review.report.builder import report_to_dict
from ai_code_review.review.agent import ClaudeSdkAgentRunner

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def _load_endpoint() -> EndpointConfig:
    if not ENV_FILE.exists():
        raise SystemExit(f"missing {ENV_FILE}; copy .env.example and fill in values")
    mapping = {k: v for k, v in dotenv_values(ENV_FILE).items() if v is not None}
    cfg = EndpointConfig.from_mapping(mapping)
    if cfg.base_url is None or cfg.auth_token is None:
        raise SystemExit("ANTHROPIC_BASE_URL and ANTHROPIC_AUTH_TOKEN are required in .env")
    return cfg


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run an AI code review on a diff.")
    p.add_argument("--diff", required=True, type=Path, help="Path to unified diff file")
    p.add_argument(
        "--workspace",
        required=True,
        type=Path,
        help="Path to repo working tree (after state)",
    )
    p.add_argument("--rules-dir", required=True, type=Path)
    p.add_argument("--skill", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument(
        "--model",
        default=None,
        help="Direct model id (e.g. glm-5). Defaults to .env's ANTHROPIC_DEFAULT_OPUS_MODEL.",
    )
    p.add_argument("--title", default="", help="Optional review title")
    return p.parse_args()


async def _amain() -> int:
    args = _parse_args()
    endpoint = _load_endpoint()

    model = args.model or endpoint.default_opus_model or endpoint.default_sonnet_model
    if model is None:
        raise SystemExit(
            "--model not provided and no ANTHROPIC_DEFAULT_*_MODEL set in .env"
        )

    runner = ClaudeSdkAgentRunner(endpoint=endpoint, model=model)

    review_input = ReviewInput.from_local_file(
        diff_path=args.diff,
        workspace=args.workspace,
        rules_dir=args.rules_dir,
        skill_path=args.skill,
        model=model,
        title=args.title,
    )

    print(f"[review] running on {args.diff} (model={model}) ...", file=sys.stderr)
    report = await run_review(review_input, runner)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report_to_dict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"[review] wrote {args.out} — {len(report.findings)} findings in "
        f"{report.review.scanned_seconds:.1f}s",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_amain()))
