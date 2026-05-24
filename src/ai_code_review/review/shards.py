"""File-level review shard planning for larger diffs."""

from __future__ import annotations

from dataclasses import dataclass

from ai_code_review.diff.parser import parse_unified_diff
from ai_code_review.models.diff import FileChange
from ai_code_review.models.rule import Rule
from ai_code_review.rules.recaller import DEFAULT_MAX_RULES, recall_rules


@dataclass(frozen=True)
class DiffFileSlice:
    """One raw unified-diff section, normally representing one file."""

    index: int
    diff_text: str
    files: tuple[FileChange, ...]

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(file.path for file in self.files)


@dataclass(frozen=True)
class ReviewShard:
    """One planned review batch: a file slice plus the rules recalled for it."""

    index: int
    diff_text: str
    files: tuple[FileChange, ...]
    rules: tuple[Rule, ...]
    dropped_by_l4: tuple[str, ...] = ()

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(file.path for file in self.files)


@dataclass(frozen=True)
class ReviewShardPlan:
    """A deterministic plan for running review in file-level batches."""

    total_files: int
    total_rules: int
    shards: tuple[ReviewShard, ...]
    skipped_paths: tuple[str, ...]


def split_unified_diff_by_file(diff_text: str) -> tuple[DiffFileSlice, ...]:
    """Split a unified diff into parseable file-level sections.

    Git-style diffs are delimited by ``diff --git`` headers. If the input is a
    minimal single-file patch without those headers, the whole diff is returned
    as one slice.
    """
    normalized = diff_text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        return ()

    sections: list[str] = []
    current: list[str] = []
    for line in normalized.splitlines(keepends=True):
        if line.startswith("diff --git "):
            if current:
                sections.append("".join(current))
            current = [line]
        elif current:
            current.append(line)

    if current:
        sections.append("".join(current))
    if not sections:
        sections = [normalized]

    slices: list[DiffFileSlice] = []
    for idx, section in enumerate(sections, start=1):
        files = tuple(parse_unified_diff(section))
        if files:
            slices.append(DiffFileSlice(index=idx, diff_text=section, files=files))
    return tuple(slices)


def plan_file_review_shards(
    rules: list[Rule],
    diff_text: str,
    *,
    max_rules: int | None = DEFAULT_MAX_RULES,
    include_empty: bool = False,
) -> ReviewShardPlan:
    """Plan file-level review batches and recall rules per batch.

    ``include_empty=False`` means files with no recalled rules are skipped, which
    keeps downstream agent calls focused. Use ``include_empty=True`` for
    diagnostics and UI previews.
    """
    slices = split_unified_diff_by_file(diff_text)
    shards: list[ReviewShard] = []
    skipped_paths: list[str] = []

    for file_slice in slices:
        recall = recall_rules(
            rules,
            list(file_slice.files),
            diff_text=file_slice.diff_text,
            max_rules=max_rules,
        )
        if recall.rules or include_empty:
            shards.append(
                ReviewShard(
                    index=file_slice.index,
                    diff_text=file_slice.diff_text,
                    files=file_slice.files,
                    rules=recall.rules,
                    dropped_by_l4=recall.dropped_by_l4,
                )
            )
        else:
            skipped_paths.extend(file_slice.paths)

    return ReviewShardPlan(
        total_files=sum(len(file_slice.files) for file_slice in slices),
        total_rules=len(rules),
        shards=tuple(shards),
        skipped_paths=tuple(sorted(skipped_paths)),
    )


def render_review_shard_plan_markdown(plan: ReviewShardPlan) -> str:
    """Render a compact Markdown review-shard plan."""
    lines = [
        "# Review Shard Plan",
        "",
        f"Total files: **{plan.total_files}**",
        f"Total rules: **{plan.total_rules}**",
        f"Planned shards: **{len(plan.shards)}**",
        f"Skipped files: **{len(plan.skipped_paths)}**",
        "",
        "## Shards",
        "",
        "| # | files | rules | dropped_by_l4 |",
        "| ---: | --- | --- | --- |",
    ]
    if plan.shards:
        for shard in plan.shards:
            lines.append(
                "| "
                f"{shard.index} | "
                f"{', '.join(shard.paths) or '-'} | "
                f"{', '.join(rule.rule_id for rule in shard.rules) or '-'} | "
                f"{', '.join(shard.dropped_by_l4) or '-'} |"
            )
    else:
        lines.append("| 0 | (none) | - | - |")

    lines.extend(["", "## Skipped Files", "", "| file |", "| --- |"])
    if plan.skipped_paths:
        lines.extend(f"| {path} |" for path in plan.skipped_paths)
    else:
        lines.append("| (none) |")
    lines.append("")
    return "\n".join(lines)
