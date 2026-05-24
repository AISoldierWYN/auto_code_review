# Stage 3 - Structured Output Validation And Filtering

## 1. Goal

Stage 3 makes parsed model output safe to render. The parser still extracts
fenced YAML, but the new validation layer decides which findings are allowed
into `review.json`.

## 2. Implemented Contract

`ai_code_review.review.validator.validate_and_filter_findings(...)` now enforces:

- `rule_id` must be in the recalled rule set.
- `severity` and `category` must match the rule definition.
- `file` must be present in the diff.
- `line` must point to an added `+` line in the diff.
- `confidence` must be in `[0, 1]` and at least `0.4`.
- Duplicate `(rule_id, file, line)` findings are dropped after the first.
- Pure linter categories (`style`, `format`, `formatting`, `lint`, `naming`) are dropped.

Dropped findings are not rendered, but they are kept for debugging as
`review.metadata.filtered_findings`.

## 3. Parse Repair

If the first agent response cannot be parsed, the pipeline sends one repair
prompt through the same runner:

```python
build_output_repair_prompts(skill, raw_output, parse_error, review_language)
```

The repair prompt asks the model to rewrite only the output format and not
invent new findings. If the repaired output still cannot be parsed, the parser
error is allowed to surface.

## 4. Report Metadata

Serialized report metadata now includes:

```json
{
  "metadata": {
    "rules_total": 20,
    "rules_after_filter": 3,
    "rules_dropped_by_l4": [],
    "filtered_findings": [
      {
        "reason": "unknown_rule",
        "rule_id": "RULE-X",
        "file": "app/src/main/java/Foo.java",
        "line": 42,
        "detail": "finding.rule_id was not present in the recalled rule set"
      }
    ]
  }
}
```

Known filter reasons:

- `unknown_rule`
- `rule_metadata_mismatch`
- `file_not_changed`
- `line_not_in_added_diff`
- `invalid_confidence`
- `low_confidence`
- `linter_noise`
- `duplicate`

## 5. Tests

Primary tests:

- `tests/stage_3/test_finding_validator.py`
- `tests/stage_1/test_pipeline.py`
- `tests/stage_1/test_report_builder.py`
- `tests/stage_1/test_prompt_builder.py`

The validator is unit-tested independently, and the pipeline test confirms
invalid model findings are filtered before report building.

## 6. Not In This Stage

- `report_finding` tool/hook enforcement is still deferred. The current short
  term path remains fenced YAML + repair + validator/filter.
- Summary text is not semantically rewritten when all findings are filtered.
- Cross-shard deduplication belongs with the future multi-agent shard execution
  path; Stage 2 only added the shard plan.
