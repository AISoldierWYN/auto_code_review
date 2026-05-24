# Stage 1 目标 — 跑通最小闭环

> 输入:diff + 规则库 + SKILL → 输出:UI 可消费的 `review.json`

## 一、对外契约

CLI:

```bash
review --diff <path-to-diff>      \
       --workspace <repo-root>    \
       --rules-dir rules/         \
       --skill skills/code_review.md \
       --out reviews/<run-id>/review.json
```

Python API:

```python
from ai_code_review.pipeline import run_review, ReviewInput

result: ReviewReport = run_review(ReviewInput(
    diff_path=Path("examples/stage_1_demo/change.diff"),
    workspace=Path("."),
    rules_dir=Path("rules"),
    skill_path=Path("skills/code_review.md"),
))
```

## 二、子模块拆分(每个独立可单测)

```
                ┌─────────────┐
diff_text  ───► │ DiffParser  │ ──► list[FileChange]
                └─────────────┘
                ┌─────────────┐
rules/*.yaml ─► │ RuleLoader  │ ──► list[Rule]
                └─────────────┘
                                    │
                                    ▼
                              ┌─────────────┐
                              │ RuleRecaller│ ──► list[Rule] (L1+L2 filtered)
                              └─────────────┘
                                    │
                                    ▼
                              ┌──────────────┐
SKILL.md ──────────────────►  │ PromptBuilder│ ──► (system_prompt, user_prompt)
                              └──────────────┘
                                    │
                                    ▼
                              ┌─────────────┐
                              │ AgentRunner │ ──► agent_output: str
                              └─────────────┘   (Claude Agent SDK, env from .env)
                                    │
                                    ▼
                              ┌──────────────┐
                              │ OutputParser │ ──► list[Finding], Summary
                              └──────────────┘
                                    │
                                    ▼
                              ┌──────────────┐
                              │ ReportBuilder│ ──► ReviewReport (= review.json)
                              └──────────────┘
```

每个箭头都是纯函数边界,可独立单测。

## 三、模块对外签名(初稿,实现时可微调)

```python
# diff/parser.py
def parse_unified_diff(text: str) -> list[FileChange]: ...

# rules/loader.py
def load_rules(root: Path) -> list[Rule]: ...

# rules/recaller.py
def filter_rules(rules: list[Rule], diff: list[FileChange]) -> list[Rule]:
    """L1 language filter + L2 path filter (Stage 2 加 L3/L4)"""

# review/prompt.py
def build_prompts(skill: str, rules: list[Rule], diff_text: str) -> Prompts: ...

# review/agent.py
class AgentRunner(Protocol):
    async def run(self, prompts: Prompts, workspace: Path) -> str: ...
# 实现: ClaudeSdkAgentRunner(env, model)

# review/parser.py
def parse_agent_output(text: str) -> ParsedOutput:
    """提取 ```finding 块、```summary 块、END_OF_REVIEW 哨兵"""

# report/builder.py
def build_report(
    diff: list[FileChange],
    findings: list[Finding],
    summary: str,
    meta: ReviewMeta,
) -> ReviewReport:
    """聚合 severity_counts + 解析 diff_hunks + 分配 finding.id"""
```

## 四、用户提供的测试用例 fixture(★ 本阶段重点)

预留目录 `tests/cases/`,用户可往里丢测试数据,**单测自动发现并 parametrize**。

### 4.1 目录布局

```
tests/cases/
├── README.md                              # 怎么加用例
├── case_resource_leak/                    # 一个用例
│   ├── case.yaml                          # 元数据 + 期望结果
│   ├── change.diff                        # unified diff
│   ├── workspace/                         # 工作区 after 状态(镜像仓库路径)
│   │   └── path/to/file.py
│   └── rules/                             # 本用例参与的规则
│       └── RULE-XXX-NNN.yaml
└── case_<name>/...
```

### 4.2 `case.yaml` schema

```yaml
name: case_resource_leak                   # [必填] 必须等于目录名
description: "open() without with — fd leak"
language_hint: python                      # 可选,加速 RuleRecaller
expected:
  findings:                                # [必填] 期望命中的 finding 列表
    - rule_id: RULE-RESOURCE-001
      file: examples/stage_1_demo/cache_loader.py
      line_range: [10, 12]                 # 命中点应落在此区间
  forbid_other_critical: true              # [可选] 不允许有此用例 expected 之外的 critical
  summary_substring: "open"                # [可选] summary 文本应包含
```

### 4.3 测试发现

```python
# tests/stage_1/test_end_to_end_cases.py
@pytest.mark.parametrize("case", discover_cases(), ids=lambda c: c.name)
@pytest.mark.integration                   # 端到端跑,慢,默认不跑
def test_pipeline_on_case(case: TestCase):
    report = run_review(case.to_review_input())
    assert_findings_match(report.findings, case.expected.findings)
```

用户后续丢一个新的 `case_xxx/` 进去,**不需要改任何测试代码**,
`pytest tests/stage_1/test_end_to_end_cases.py -m integration` 会自动跑上。

### 4.4 工作区状态来源

**Stage 1 只支持 `workspace/` 目录显式提供 after 状态**(就是把改完之后的完整文件
放进 workspace/,镜像仓库路径)。

**不支持** `before/` + 自动 apply。这是有意 YAGNI 的:
- 用户从历史 commit 提取用例时,`git checkout <fix-commit>` 后复制文件即可
- 加 apply 逻辑要引入 patch 库或 shell out 到 git,复杂度不值
- Stage 1.5 / Stage 2 再考虑

如果用户只提供了 `before/`,case loader 报清晰错误:
`"Stage 1 requires workspace/ (after state); before/ + diff apply is planned for Stage 1.5"`

## 五、非目标(本阶段不做)

- ❌ DiffSource 适配层(GitHub/Gerrit fetch) — Stage 4
- ❌ L3 关键词预筛 / L4 优先级裁剪 — Stage 2
- ❌ 大 diff 按文件 / hunk 分片 — Stage 2
- ❌ `report_finding` 工具强制结构化 — Stage 3
- ❌ 噪音过滤、findings 去重 — Stage 3
- ❌ 实际 UI 接入(只产 review.json) — Stage 5
- ❌ `before/` → `workspace/` 自动 apply — Stage 1.5 视需要

## 六、验收(Stage 1 结束条件)

- [ ] 所有子模块单测全绿,单元测试整体耗时 < 5s
- [ ] 端到端跑 `case_resource_leak`,产出的 `review.json`:
  - `findings[0].rule_id == "RULE-RESOURCE-001"`
  - `findings[0].file` 指向 demo 文件
  - `findings[0].line` 在 expected.findings[0].line_range 内
  - `review.summary` 非空
- [ ] AgentRunner **至少使用一次 `Read` 工具**(验证第三方端点 tool_use 可用 — Stage 0 留的红线)
- [ ] CLI `python scripts/review.py --diff ... --out ...` 跑通,产出可被 UI 消费的 JSON
- [ ] `docs/stages/stage_1_review.md` 按 §9.5 模板写完,含自审记录
- [ ] 用户后续往 `tests/cases/` 丢新用例,单测能自动发现并跑

## 七、风险与对策

| 风险 | 对策 |
|------|------|
| 第三方端点不支持 tool_use | Stage 0 红线;若不支持立刻报错并切回官方端点(env 切换) |
| agent 不按 SKILL 输出格式来 | OutputParser 做 lenient 解析 + 日志;Stage 3 加 L2 工具强制 |
| 端到端测试不稳定(模型非确定) | 测试只断言"命中正确的 rule_id + file + line 在区间内",不断言 message 文本 |
| 用户用例丢进来格式不对 | case.yaml schema 校验,错误信息明确指向哪一行 |
