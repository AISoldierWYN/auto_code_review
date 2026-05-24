"""Smoke tests for the Stage 4 publish CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_publish_review_cli_dry_run_outputs_payload(tmp_path: Path) -> None:
    review = {
        "review": {
            "title": "Demo",
            "diff_path": "https://gerrit.example.com/c/project/+/123",
            "summary": "No issues.",
        },
        "findings": [],
    }
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/publish_review.py",
            "--review",
            str(review_path),
            "--platform",
            "gerrit",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["platform"] == "gerrit"
    assert payload["action"] == "dry_run"
    assert payload["payloads"][0]["url"].endswith("/changes/123/revisions/current/review")
