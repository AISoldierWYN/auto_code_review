# Stage 2 — 规则资产与召回质量(开发说明)

## 1. 本阶段目标

Stage 2 的目标是把规则库从 demo 形态推进到可运营资产:

- 保留并扩展 `typical_case` 规则,用于冷启动和通用缺陷审查。
- 为 `bug_history` 规则建立入口,但真实规则数量不阻塞当前开发。
- 让规则库可以被审计:知道当前有多少规则、分布在哪些语言/严重级别/类别、哪些规则缺少召回线索或真实案例证据。
- 让 `tests/cases/` 成为规则召回回归集。

## 2. 最终对外契约

```python
from ai_code_review.rules.audit import (
    RuleInventory,
    RuleAuditWarning,
    build_rule_inventory,
    render_rule_inventory_markdown,
)

inventory = build_rule_inventory(load_rules(Path("rules")))
markdown = render_rule_inventory_markdown(inventory)
```

CLI:

```powershell
.\.venv\Scripts\python.exe scripts\rules_audit.py --rules-dir rules
.\.venv\Scripts\python.exe scripts\rules_audit.py --rules-dir rules --format json
```

## 3. 关键设计决策

### D1. `bug_history` 可以为空

真实 bug 需要用户从内部系统收集。Stage 2 先提供 `rules/bug_history/README.md`
和审计规则,保证后续素材一到就能按统一格式入库。

### D2. 审计 warning 不等于 loader error

`RuleLoader` 继续严格校验 schema,缺必填字段直接失败。`RuleAudit` 只报告非致命质量问题,
例如缺少 `recall` hint、bug_history 缺原始案例、路径范围太宽。这样不会影响当前 review
链路,但能持续提示规则资产质量。

### D3. 规则召回仍然不写硬匹配

Stage 2 已有 L1/L2/L3/L4:

- L1: language
- L2: path/exclude_path
- L3: `recall.keywords` / `recall.regexes`
- L4: source/severity/category 优先级裁剪

审计模块只衡量资产健康,不改变召回结果。

## 4. 测试覆盖

- `tests/stage_2/test_android_rules.py`:Android 规则加载与单规则召回。
- `tests/stage_2/test_android_case_fixtures.py`:Android case fixture 的 expected rule 必须被召回。
- `tests/stage_2/test_rule_audit.py`:规则资产统计、warning、Markdown 渲染。

当前验证:

```text
pytest tests/stage_2
39 passed
```

## 5. 自审记录

- 可读性:审计逻辑独立在 `rules/audit.py`,不掺入 loader/recaller。
- 可测性:构造内存 Rule 对象即可测试 warning,不需要临时 YAML。
- 耦合度:生产 review pipeline 不依赖 audit,后续可单独演进。
- 错误处理:loader 负责 hard fail,audit 只输出 warning。
- YAGNI:暂未做复杂评分体系,只做当前 Stage 2 需要的统计和 warning。

## 6. 已知限制 / 待办

- 还没有真实 `bug_history` 规则。
- 还没有负例 fixture,无法量化误召回。
- 还没有按文件切片的大 diff review。
- 还没有把 audit 结果接到 UI。

## 7. 回归用例链接

- `tests/cases/case_android_app_main_thread_refresh_io/`
- `tests/cases/case_android_app_cursor_leak_profile_lookup/`
- `tests/cases/case_android_app_pending_intent_mutability/`
- `tests/cases/case_android_app_webview_bridge_untrusted_url/`
- `tests/cases/case_android_app_sql_rawquery_injection/`
- `tests/cases/case_android_app_zip_slip_theme_unpack/`
- `tests/cases/case_android_fwk_binder_identity_restore/`

## 8. Case 覆盖报告

Stage 2 新增 case coverage 报告,用于回答两个问题:

1. 当前哪些规则已经有 `tests/cases/` 回归样例覆盖。
2. 每个 case 的 `expected.findings[].rule_id` 是否真的能通过 L1/L2/L3/L4 recall 进入 prompt。

Python API:

```python
from ai_code_review.testing.case_coverage import (
    build_case_coverage_report,
    render_case_coverage_markdown,
)

report = build_case_coverage_report(rules, cases)
markdown = render_case_coverage_markdown(report)
```

CLI:

```powershell
.\.venv\Scripts\python.exe scripts\case_coverage.py --rules-dir rules --cases-root tests\cases
.\.venv\Scripts\python.exe scripts\case_coverage.py --rules-dir rules --cases-root tests\cases --case-prefix case_android_
.\.venv\Scripts\python.exe scripts\case_coverage.py --fail-on-recall-misses
```

报告会输出:

- `covered_rule_ids`: 已有 expected case 的生产规则。
- `uncovered_rule_ids`: 暂时没有 case 覆盖的生产规则。
- `unknown_expected_rule_ids`: case 里声明了、但生产规则库没有的 rule id。
- `recall_misses`: case 期望命中的规则没有被召回,包括 `rule_not_loaded` 和 `not_recalled`。
