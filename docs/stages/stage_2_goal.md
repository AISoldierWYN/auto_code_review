# Stage 2 目标 — 规则召回与规模化输入

## 1. 本阶段目标

Stage 1 已经跑通 `diff + rules + skill -> review.json` 的最小闭环。Stage 2 的目标是让这条链路可以承载更大的规则库和更大的 diff，而不是把所有候选规则都塞进 prompt。

本阶段优先交付三件事：

1. 规则召回 L3 粗信号过滤：规则可以声明可选 `recall.keywords` / `recall.regexes`，只有 diff 文本命中任一信号时才注入 prompt。
2. 规则召回 L4 优先级裁剪：候选规则超过上限时，按 `severity` 与 `source.type` 排序裁剪，并在报告 metadata 中记录被裁掉的 `rule_id`。
3. 大 diff 分片设计：默认按文件分片，超大文件后续再按 hunk 分片。

## 2. 对外契约

规则 YAML 新增可选字段：

```yaml
recall:
  keywords:
    - "open("
  regexes:
    - "\\bopen\\s*\\("
```

没有 `recall` 字段的规则保持 Stage 1 行为，只经过语言和路径过滤。

Python API：

```python
from ai_code_review.rules.recaller import recall_rules

result = recall_rules(rules, diff, diff_text=raw_diff, max_rules=50)
result.rules          # 注入 prompt 的规则
result.dropped_by_l4  # 因 L4 裁剪丢弃的 rule_id
```

旧 API `filter_rules(rules, diff)` 保留，用于 Stage 1 兼容，只执行 L1/L2。

## 3. 优先级规则

L4 裁剪顺序：

1. `severity`: `critical` > `warning` > `suggestion`
2. `source.type`: `bug_history` > `typical_case` > `review_history` > `spec`
3. 同级保持规则加载顺序

默认上限为 50 条。被裁掉的规则进入 `review.metadata.rules_dropped_by_l4`，用于后续审计和调参。

## 4. 非目标

- 不在本阶段实现 `report_finding` 工具强制结构化输出。
- 不在本阶段自动从历史 bug 批量生成规则。
- 不在本阶段实现 hunk 级分片和 token 预算器。
- 不在本阶段改造 UI 展示规则召回细节，只保证 JSON metadata 可消费。
## Completion Note

Stage 2 implementation now includes:

- `recall.exclude_keywords` / `recall.exclude_regexes`
- negative case checks through `expected.forbidden_rules`
- `scripts/case_coverage.py`
- file-level shard planning through `ai_code_review.review.shards`
- `scripts/review_shards.py`

