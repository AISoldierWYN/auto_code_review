# Stage 1 — 跑通最小闭环(开发说明)

> 完成于 2026-05-20 · 模板:`v1_plan.md` §9.5

## 1. 本阶段目标(摘自 `stage_1_goal.md`)

输入 diff + 规则库 + SKILL → 输出 UI 可消费的 `review.json`。8 个子模块拆出、
独立单测,串成 pipeline,端到端跑通 demo case。

## 2. 最终对外契约

### 2.1 CLI

```
python scripts/review.py \
  --diff tests/cases/case_resource_leak/change.diff \
  --workspace tests/cases/case_resource_leak/workspace \
  --rules-dir tests/cases/case_resource_leak/rules \
  --skill skills/code_review.md \
  --out reviews/demo/review.json
```

`.env` 提供端点凭证;`--model` 缺省时从 `ANTHROPIC_DEFAULT_OPUS_MODEL` 取。

### 2.2 Python API

```python
from ai_code_review.pipeline import run_review, ReviewInput
from ai_code_review.review.agent import ClaudeSdkAgentRunner

runner = ClaudeSdkAgentRunner(endpoint=cfg, model="glm-5")
report = await run_review(ReviewInput(
    diff_path=..., workspace=..., rules_dir=..., skill_path=..., model="glm-5",
), runner)
```

### 2.3 8 个子模块的公有签名

```python
parse_unified_diff(text: str) -> list[FileChange]
load_rules(root: Path) -> list[Rule]                    # 严格,malformed 直接抛
filter_rules(rules, diff) -> list[Rule]                 # L1+L2
build_prompts(skill, rules, diff_text) -> Prompts
class AgentRunner(Protocol):                            # 接口
    async def run(self, prompts, workspace) -> AgentRunResult
parse_agent_output(text) -> ParsedOutput
build_report(ReportBuildInput) -> ReviewReport
report_to_dict(ReviewReport) -> dict                    # UI 字段名 (add/del/sev)
```

### 2.4 用户提供测试用例的契约

`tests/cases/case_<name>/` 目录,含 `case.yaml` + `change.diff` + `workspace/` +
(可选) `rules/`。`discover_cases()` 自动发现。详见 `tests/cases/README.md`。

## 3. 关键设计决策

### D1. 选 `unidiff` 库而不是自写 parser

理由:unified diff 格式细节多(renames、no-newline-at-eof、binary、CRLF、
encoding 边缘 case),自写易出错。`unidiff` 已经稳定多年。本项目薄薄一层
适配,加 language 检测和路径归一化,~100 行。

代价:多一个依赖。可接受。

### D2. `AgentRunner` 抽象成 Protocol,SDK 实现是其中一个

```python
class AgentRunner(Protocol):
    async def run(self, prompts: Prompts, workspace: Path) -> AgentRunResult: ...
```

pipeline 依赖 Protocol,SDK 调用具体到 `ClaudeSdkAgentRunner`。测试里能用 `_FakeRunner`
替换,完全脱离 SDK 跑 pipeline 单测——这是 §9.4"依赖倒置"条的直接应用。
也为 Stage 4 接 GitHub Action 时换 runner 留路。

### D3. SKILL 进 system_prompt,规则 + diff 进 user_prompt

理由:SKILL 是稳定的"角色"指令,适合系统提示;规则和 diff 是"本次任务"输入。
分开放有助于模型理解什么是不变的、什么是这次特有的。也有利于 Stage 3 加 prompt
caching 时区分 cache 边界。

### D4. 规则注入时做字段瘦身

注入到 prompt 的规则**省略** `applies_to`(已被 recaller 消化)、`source.refs`
(给 UI rationale 用)、`original_case`(默认不进 prompt,见 v1_plan §三.2.3)。

实现在 `_serialize_rule()`。测试用 `test_original_case_is_excluded_from_prompt`
等 4 个 case 锁死这个不变量。

### D5. OutputParser **lenient 解析 + 强校验关键字段**

`END_OF_REVIEW` 哨兵缺失只警告(模型常忘);但 `line` / `severity` 等字段缺失直接抛。
理由:轻微违规可恢复,关键字段缺失会导致 UI 渲染异常,值得 fail-fast。

### D6. ReportBuilder 在 diff_hunks 里**注入 comment 锚点**

UI 的 `data.js` 期望 diff_hunks 数组里有 `{type:"comment", anchorNew, id}` 项。
ReportBuilder 在 build 阶段把每条 finding 转成 comment marker 追加到对应文件的
hunks 列表。这样 UI 不需要自己关联 finding 和 diff 行。

### D7. 单测 fixture 加载器 **拒绝 `before/`**

`workspace/` (after state) 才是 Stage 1 的唯一支持形态;`before/` + 自动 apply 是
Stage 1.5 工作。如果用户错放 `before/`,loader 抛清晰的引导性错误信息。

### D8. 故意没做的事(YAGNI)

- 没有自定义工具(`report_finding`)—— Stage 3
- 没有 prompt cache —— Stage 3 / 调优阶段
- 没有重试 / 超时控制 —— Stage 4 真上线时加
- 没有去重 / 合并 finding —— Stage 3
- 没有按文件 / hunk 分片 —— Stage 2
- 没有 L3 / L4 规则过滤 —— Stage 2

## 4. 测试覆盖

```
tests/
├── stage_0/test_endpoint_config.py     15 passed
├── stage_1/
│   ├── test_diff_parser.py             22 passed
│   ├── test_rule_loader.py              9 passed
│   ├── test_rule_recaller.py           12 passed
│   ├── test_prompt_builder.py           8 passed
│   ├── test_output_parser.py           10 passed
│   ├── test_report_builder.py          14 passed
│   ├── test_case_loader.py             15 passed
│   └── test_pipeline.py                 1 passed (mock runner)
└── cases/case_resource_leak/                       ← 用户 fixture 入口
```

**总计**:106 passed in 0.44s(全部单元,无慢测)。

**端到端实跑**(`scripts/review.py`,调真实 SDK + 第三方端点):

```
[review] wrote reviews/demo/review.json — 1 findings in 28.5s
```

输出 JSON:
- `schema_version: 1.0` ✓
- `findings[0].rule_id = RULE-RESOURCE-001` ✓
- `findings[0].file = examples/stage_1_demo/cache_loader.py` ✓
- `findings[0].line = 12` (在 case.yaml 期望区间 [9, 12]) ✓
- `findings[0].severity = critical`,`confidence = 0.95` ✓
- `findings[0].rationale.source_refs` 从规则透传 ✓
- `review.summary` 包含 "load_cache" ✓
- `files[0].diff_hunks` 含 add/ctx/hunk/comment 四种 type ✓

## 5. 自审记录(§9.4 清单逐项)

| 项 | 结果 | 说明 |
|----|------|------|
| 可读性 | ✅ | 模块短(50–200 行),命名表意;关键决策有注释解释 why |
| 可测性 | ✅ | 每个模块独立 testable;`AgentRunner` 是 Protocol,pipeline 测试用 fake |
| 耦合度 | ✅ | 数据模型零依赖;parsers/builders 互不依赖;只在 pipeline.py 装配 |
| 错误处理 | ✅ | 边界(YAML 解析、agent 输出格式、用户用例格式)都有显式异常;内部不防御 |
| 资源管理 | ✅ | `async for` 完整 drain query 流;`pathlib` 读写无句柄泄漏 |
| 性能 | ✅ | 单测 0.44s;实跑 28.5s(主要在模型推理,可接受) |
| 类型注解 | ✅ | 所有公有 API 有类型注解;`from __future__ import annotations` 启用 PEP 604 |
| 命名一致 | ✅ | `parse_*` / `load_*` / `filter_*` / `build_*` 动宾对称 |
| YAGNI | ✅ | 见 D8;两处 fake runner 的"drain async generator"重复故意保留,Stage 2 再抽 |
| 依赖倒置 | ✅ | `AgentRunner` Protocol;pipeline 不直接依赖 SDK |

### 实际踩过的坑(必须记)

1. **`unidiff` 不处理 CRLF**——首次单测就跪。修:在 parser 入口手动 `replace("\r\n", "\n")`。已用单测 `test_crlf_endings_normalized` 锁死。

2. **pytest 把 `TestCase` 类名当成 test class 收集**——产生 `PytestCollectionWarning`。修:dataclass 改名 `CaseFixture`。

3. **`findings or [_finding()]` 陷阱**——`[]` 被当成 falsy,触发默认实参,跑不出"空 findings"的分支。修:改为 `findings if findings is not None else [...]`。这是 §9.4"可测性"里的隐藏 bug,测试本身写错才发现。

4. **agent 偶发输出格式偏离**——第一次 CLI 跑时 parser 报 "no summary block";第二次跑相同输入就 OK。模型非确定性。当前对策:OutputParser 已经 lenient(`END_OF_REVIEW` 哨兵缺失不 fail);summary 缺失仍 fail,因为 UI 必须有 summary。**Stage 3 加 L2 工具强制后这个问题消失**。

5. **`used_tools` 在本次实跑为空**——demo case 体量小,agent 一次就推完了,没主动 Read 工作区。**这意味着 Stage 0 review 留的红线"agent 至少用一次 Read 工具"在 Stage 1 没被自然验证**。下面 §6 单独立项。

6. **Windows 控制台显示 Unicode `��`**——只是 stdout 用 gbk 编码显示 em-dash 时挂了;JSON 文件本身存的是正确 UTF-8。无需修。

## 6. 已知限制 / 待办

- ⚠️ **Stage 0 红线未自然验证**:第三方端点的 `tool_use` 在 Stage 1 实跑中没被触发(prompt 够小,agent 没拉 Read)。**待办**:Stage 2 第一个动作前,加一个专门的 smoke——让 agent 必须 Read 工作区某个文件才能完成任务,验证 `tool_use` 在 lkeap 端点上确实可用。如果不可用,Stage 2 的"按需上下文"假设崩盘。
- ⚠️ **未做 prompt cache**:当前每次跑都把 SKILL 重发,~3k tokens 重复消耗。Stage 3 接 prompt cache。
- ⚠️ **未做 retry / 超时**:agent 偶发失败直接 raise。Stage 4 真上线前补。
- ⚠️ **`scripts/review.py` 无 mock 模式**:debug 不方便。Stage 2 之前可考虑加 `--mock-output` 接受预录文本。
- ⚠️ **OutputParser 对模型偏格式行为不够宽容**:`title:` / `body:` 字段如果模型用 string 而非 `> block scalar` 写,YAML 解析可能行为不同。当前 case 没踩坑,后续大规模跑后再视情况加防御。
- ⚠️ **`pyproject.toml` 还没装 pre-commit / ruff / mypy 钩子**——§9.6 列了但 Stage 0 没补;Stage 2 开工前补。

## 7. 回归用例

- 单元测试 106 个,提交即跑:`pytest tests/ -m "not integration"` < 1s
- 端到端 case 在 `tests/cases/case_resource_leak/` — 当前手动跑 `scripts/review.py` 验证;**待办**:Stage 2 加 `@pytest.mark.integration` 的自动化 case 测试
- 用户后续提交新用例的方式:看 `tests/cases/README.md`

## 8. 下一步交接给 Stage 2

护城河阶段。重点是规则积累——用 `docs/templates/rule_extraction_prompt.md` 喂团队:

1. 收 30–50 条 bug_history 规则(分散到各模块负责人)
2. 加 10–20 条 typical_case 规则(语言通用陷阱)
3. RuleRecaller 实现 L3(关键词预筛) + L4(优先级裁剪) + 元数据回填
4. 大 diff 分片策略(按文件,Stage 2 默认)
5. 把 Stage 1 留的 Stage 0 红线先验证掉(强制 Read 的 smoke)
