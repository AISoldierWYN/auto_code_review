"""Tiny aiohttp server — wires the UI to the Stage 1 pipeline.

Endpoints:
  GET  /                 → redirect to /ui/index.html
  GET  /ui/*             → static files from ui/
  POST /api/review       → body {identifier, workspace?, rules_dir?, skill_path?}
                            returns the review.json shape

The ``identifier`` may be:
  * a local diff file path (e.g. ``tests/cases/case_resource_leak/change.diff``)
  * a GitHub PR URL (``https://github.com/owner/repo/pull/123``)
  * the shorthand form ``owner/repo#123``

For back-compat, the body key ``diff_path`` is also accepted.

Endpoint credentials are loaded from ``.env`` (same as ``scripts/review.py``).
"""

from __future__ import annotations

import argparse
import json
import logging
import traceback
from pathlib import Path

from aiohttp import web
from dotenv import dotenv_values

from ai_code_review.config.endpoint import EndpointConfig
from ai_code_review.diff.sources import (
    DiffSourceError,
    LocalDiffSource,
    select_source,
)
from ai_code_review.pipeline import ReviewInput, run_review
from ai_code_review.report.builder import report_to_dict
from ai_code_review.review.agent import ClaudeSdkAgentRunner
from ai_code_review.review.prompt import Prompts, normalize_review_language
from ai_code_review.workspace import detect_workspace

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
UI_DIR = PROJECT_ROOT / "ui"
NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

log = logging.getLogger("serve")


def _compact_review_context(review: dict) -> dict:
    meta = review.get("review") if isinstance(review.get("review"), dict) else {}
    files_raw = review.get("files") if isinstance(review.get("files"), list) else []
    findings_raw = review.get("findings") if isinstance(review.get("findings"), list) else []

    files: list[dict] = []
    for f in files_raw[:20]:
        if not isinstance(f, dict):
            continue
        changed_lines = []
        for row in f.get("diff_hunks", [])[:140]:
            if not isinstance(row, dict):
                continue
            if row.get("type") in {"add", "del", "comment"}:
                changed_lines.append(
                    {
                        "type": row.get("type"),
                        "line": row.get("new") or row.get("old") or row.get("anchorNew"),
                        "text": row.get("text", ""),
                        "comment_id": row.get("id"),
                    }
                )
        files.append(
            {
                "path": f.get("path"),
                "lang": f.get("lang"),
                "add": f.get("add"),
                "del": f.get("del"),
                "severity": f.get("sev"),
                "changed_lines": changed_lines,
            }
        )

    findings: list[dict] = []
    for item in findings_raw[:40]:
        if not isinstance(item, dict):
            continue
        findings.append(
            {
                "id": item.get("id"),
                "rule_id": item.get("rule_id"),
                "severity": item.get("severity"),
                "category": item.get("category"),
                "file": item.get("file"),
                "line": item.get("line"),
                "title": item.get("title"),
                "body": item.get("body"),
                "suggestion": item.get("suggestion"),
            }
        )

    return {
        "review": {
            "title": meta.get("title"),
            "diff_path": meta.get("diff_path"),
            "repo": meta.get("repo"),
            "branch": meta.get("branch"),
            "target": meta.get("target"),
            "summary": meta.get("summary"),
            "language": meta.get("language"),
        },
        "files": files,
        "findings": findings,
    }


def _chat_system_prompt(review_language: str) -> str:
    if normalize_review_language(review_language) == "zh":
        lang = "Use Simplified Chinese for the answer."
    else:
        lang = "Use English for the answer."
    return (
        "You are the follow-up assistant for one code review. Answer the "
        "reviewer's question using only the provided review context and local "
        "workspace files when available. Do not invent files, services, or call "
        "sites that are not present in the context or workspace. If there is not "
        "enough evidence, say what is missing. Keep the answer concise and "
        "actionable. Return plain text, not YAML. "
        + lang
    )


def _chat_user_prompt(question: str, review: dict) -> str:
    context = json.dumps(
        _compact_review_context(review), ensure_ascii=False, indent=2
    )
    return (
        "# REVIEW_CONTEXT\n"
        f"{context}\n\n"
        "# QUESTION\n"
        f"{question}\n"
    )


def _load_endpoint() -> EndpointConfig:
    if not ENV_FILE.exists():
        raise SystemExit(f"missing {ENV_FILE}; copy .env.example and fill in values")
    mapping = {k: v for k, v in dotenv_values(ENV_FILE).items() if v is not None}
    cfg = EndpointConfig.from_mapping(mapping)
    if cfg.base_url is None or cfg.auth_token is None:
        raise SystemExit("ANTHROPIC_BASE_URL and ANTHROPIC_AUTH_TOKEN required in .env")
    return cfg


def _resolve(path_str: str, default: Path | None = None) -> Path:
    if not path_str:
        if default is None:
            raise ValueError("path is empty and no default provided")
        return default
    p = Path(path_str)
    if not p.is_absolute():
        p = (PROJECT_ROOT / p).resolve()
    return p


async def handle_review(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001
        return web.json_response({"error": f"invalid JSON body: {exc}"}, status=400)

    identifier = body.get("identifier") or body.get("diff_path")
    if not identifier:
        return web.json_response(
            {"error": "identifier (or diff_path) is required"}, status=400
        )

    # 1) Pick the right source.
    try:
        source = select_source(identifier)
    except DiffSourceError as exc:
        return web.json_response({"error": str(exc)}, status=400)

    # 2) Fetch the diff (and metadata if available).
    try:
        bundle = await source.afetch(identifier)
    except DiffSourceError as exc:
        status = 404 if "not found" in str(exc).lower() else 400
        return web.json_response({"error": str(exc)}, status=status)
    except Exception as exc:  # noqa: BLE001
        log.exception("source fetch failed")
        return web.json_response(
            {"error": f"source fetch failed: {exc}"}, status=502
        )

    # 3) Resolve workspace + rules + skill.
    try:
        if body.get("workspace"):
            workspace = _resolve(body["workspace"])
        elif isinstance(source, LocalDiffSource):
            workspace = detect_workspace(Path(identifier), fallback=PROJECT_ROOT)
        else:
            # Remote source: no local workspace context (degraded mode).
            # The agent reviews from diff text alone; Read/Grep on
            # PROJECT_ROOT won't yield useful context for the PR's repo.
            workspace = PROJECT_ROOT

        rules_dir = _resolve(
            body.get("rules_dir") or "rules", default=PROJECT_ROOT / "rules"
        )
        skill_path = _resolve(
            body.get("skill_path") or "skills/code_review.md",
            default=PROJECT_ROOT / "skills" / "code_review.md",
        )
    except Exception as exc:  # noqa: BLE001
        return web.json_response({"error": str(exc)}, status=400)

    review_language = normalize_review_language(
        body.get("review_language") or body.get("language")
    )

    endpoint: EndpointConfig = request.app["endpoint"]
    model = endpoint.default_opus_model or endpoint.default_sonnet_model
    if model is None:
        return web.json_response(
            {"error": "no model in .env (set ANTHROPIC_DEFAULT_OPUS_MODEL)"},
            status=500,
        )

    log.info(
        "review start: source=%s id=%s workspace=%s model=%s",
        bundle.source_kind, identifier, workspace, model,
    )
    runner = ClaudeSdkAgentRunner(endpoint=endpoint, model=model)
    try:
        report = await run_review(
            ReviewInput.from_bundle(
                bundle=bundle,
                workspace=workspace,
                rules_dir=rules_dir,
                skill_path=skill_path,
                model=model,
                review_language=review_language,
            ),
            runner,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("pipeline failed")
        return web.json_response(
            {"error": str(exc), "trace": traceback.format_exc()},
            status=500,
        )

    log.info(
        "review done: %d findings in %.1fs",
        len(report.findings),
        report.review.scanned_seconds,
    )
    return web.json_response(report_to_dict(report))


async def handle_chat(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001
        return web.json_response({"error": f"invalid JSON body: {exc}"}, status=400)

    question = str(body.get("question") or "").strip()
    if not question:
        return web.json_response({"error": "question is required"}, status=400)

    review = body.get("review")
    if not isinstance(review, dict):
        return web.json_response({"error": "review context is required"}, status=400)

    review_meta = review.get("review") if isinstance(review.get("review"), dict) else {}
    review_language = normalize_review_language(
        body.get("review_language")
        or body.get("language")
        or review_meta.get("language")
    )

    endpoint: EndpointConfig = request.app["endpoint"]
    model = endpoint.default_opus_model or endpoint.default_sonnet_model
    if model is None:
        return web.json_response(
            {"error": "no model in .env (set ANTHROPIC_DEFAULT_OPUS_MODEL)"},
            status=500,
        )

    workspace = PROJECT_ROOT
    diff_path = review_meta.get("diff_path")
    if isinstance(diff_path, str) and diff_path.strip():
        try:
            workspace = detect_workspace(Path(diff_path), fallback=PROJECT_ROOT)
        except Exception:  # noqa: BLE001
            workspace = PROJECT_ROOT

    runner = ClaudeSdkAgentRunner(
        endpoint=endpoint,
        model=model,
        allowed_tools=("Read", "Glob", "Grep"),
        max_turns=8,
    )
    prompts = Prompts(
        system_prompt=_chat_system_prompt(review_language),
        user_prompt=_chat_user_prompt(question, review),
    )
    try:
        result = await runner.run(prompts, workspace)
    except Exception as exc:  # noqa: BLE001
        log.exception("chat failed")
        return web.json_response(
            {"error": f"chat failed: {exc}", "trace": traceback.format_exc()},
            status=502,
        )

    answer = result.text.strip()
    if not answer:
        answer = (
            "没有拿到可用回答。"
            if review_language == "zh"
            else "I did not get a usable answer."
        )
    return web.json_response({"answer": answer})


async def handle_root(_: web.Request) -> web.Response:
    raise web.HTTPFound("/ui/index.html")


async def handle_ui_asset(request: web.Request) -> web.StreamResponse:
    tail = request.match_info.get("tail", "")
    if not tail:
        tail = "index.html"

    ui_root = UI_DIR.resolve()
    asset_path = (UI_DIR / tail).resolve()
    try:
        asset_path.relative_to(ui_root)
    except ValueError:
        raise web.HTTPNotFound() from None

    if not asset_path.is_file():
        raise web.HTTPNotFound()

    response = web.FileResponse(asset_path)
    response.headers.update(NO_CACHE_HEADERS)
    return response


def build_app() -> web.Application:
    app = web.Application()
    app["endpoint"] = _load_endpoint()
    app.router.add_post("/api/review", handle_review)
    app.router.add_post("/api/chat", handle_chat)
    app.router.add_get("/", handle_root)
    app.router.add_get("/ui/{tail:.*}", handle_ui_asset)
    return app


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    web.run_app(build_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
