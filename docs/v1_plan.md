# AI Code Review v1 规划

## 一、定位

> 工具 = Agent SDK（引擎，不自造） + 业务上下文层（护城河） + 工程化外壳

不重复造代码理解能力——Claude Agent SDK 已经把 agent loop、文件读取、命令执行、子代理、hooks、skills、permissions 这一整套做完了。把精力全部压在三件 SDK 给不了的事情上：

1. **业务上下文的获取与组装**：规范 + 历史踩坑 + 按需检索
2. **信噪比控制**：过滤掉通用 linter 就能发现的低价值建议
3. **工作流嵌入**：把结果以 MR 评论形式落地

如果做不出第 1 件，工具就是个套壳；如果做不到第 2 件，工具会被 reviewer 拉黑；第 3 件决定能不能进生产。

---

## 二、输入 / 输出契约

### 输入

- **必须是 diff / MR**，不是整文件。整文件会把 token、信噪比、模型注意力一起拖垮。
- 附带元数据：
  - 作者（用于个性化提示语气，可选）
  - 目标分支（决定使用的规则集）
  - 关联的 issue / 需求 ID（让 agent 能拉到业务背景）
  - 改动涉及的模块路径（决定挂载哪些 skill / 召回哪些规则）

### 输出

结构化的审查意见列表，每条形如：

```jsonc
{
  "id": "c1",                                    // 与 diff_hunks 里的 comment 锚点对应
  "rule_id": "RULE-CONCUR-007",
  "severity": "critical | warning | suggestion", // 与前端 UI 词表对齐
  "category": "concurrency | resource | compatibility | naming | business | ...",
  "file": "src/foo/bar.go",
  "line": 142,
  "confidence": 0.92,                            // agent 自评 0..1
  "title": "短标题(≤80字)",
  "body": "1-3 句解释,允许内嵌 <code>identifier</code>",
  "suggestion": {                                // 可为 null
    "kind": "patch",                             // "patch" | "text" | null
    "remove": ["..."],                           // patch 时必填
    "add":    ["..."]
  },
  "rationale": {
    "rule_source_type": "bug_history",           // 规则可信度档位
    "source_refs": ["BUG-2024-1183", "docs/standards/concurrency.md#section-3"]
  }
}
```

`rationale` 是这个工具区别于通用 linter 的关键——每条意见必须能溯源到具体规则或历史 bug。无依据的"模型直觉"意见在过滤层会被丢掉。

完整 schema(含 review 元数据 / files[] / diff_hunks)见 `docs/stages/stage_1_spec.md §4`。

---

## 三、核心依赖与获取方式

### 1. 代码规范知识

- **来源**：内部已有的编码规范文档 + lint 配置
- **获取方式**：
  - 文档→ skill 文件，按主题分类（命名 / 并发 / 资源管理 / 兼容性 / 错误处理 / 日志 等）
  - lint 规则直接复用现成配置，不要让模型重新发明
- **预期工作量**：1–2 天能整出第一版骨架

### 2. 业务约束 / 历史踩坑知识（最有价值，重点投入）

来源分必选 / 可选两档，v1 先打通必选项：

#### a. 历史 bug 库（金矿，**必选**）

- 从缺陷管理系统导出"根因 + 修复 commit"对
- **每个根因抽象成一条审查规则**，按下方"规则模板"写
- 工具:把 `docs/templates/rule_extraction_prompt.md` 整块拷给团队 QA / 开发负责人,
  配合一段素材丢进任意 AI 助手,就能产出规范 YAML(详见该模板)
- v1 目标：30–50 条高频 / 高严重度规则。做完这步就和通用 CI 拉开差距。

#### b. 典型案例库（**必选**，跨模块通用）

- 与 a 的区别：a 是本厂本模块的具体 bug；b 是跨模块、跨项目都成立的通用陷阱（例：并发 map 写入崩溃、defer 在循环里资源泄漏、SQL 拼接注入、time.After 在循环里内存泄漏等）
- 来源：业界公开的踩坑案例、语言官方 anti-pattern、内部跨团队总结
- v1 目标：10–20 条，覆盖语言级和框架级的高频通用陷阱
- 模板与 a 共用，只是 `source.type` 标为 `typical_case`

#### c. 历史 code review 意见（可选）

- 从 MR 系统导出人工 review comment，聚类后高频项→规则
- 作为 a 的补充

#### d. 架构 / 设计文档（可选）

- 模块责任、接口约定、跨服务契约
- **这部分适合 RAG 检索库**——因为是自然语言文档，不是代码
- ⚠️ **不要对代码做 RAG**。代码的 RAG 召回效果远不如让 agent 用 grep / Read 按需检索。

---

#### 规则模板（统一格式，YAML）

你提的 "出现 X 模式时提示 Y 风险，可能复现 BUG-xxxx" 是对的方向，但作为一行字太薄落不了地。结构化成这样：

```yaml
rule_id: RULE-CONCUR-007                  # 规则唯一 ID
title: 共享 map 在多 goroutine 下未加锁写入
category: concurrency                     # 与 finding.category 对齐
severity: critical                        # critical | warning | suggestion (与 UI 词表对齐)
source:
  type: bug_history                       # bug_history | typical_case | review_history | spec
  refs:
    - BUG-2024-1183                       # 历史 bug 单号
    - https://internal.wiki/...           # 或链接
applies_to:
  languages: [go]
  paths: ["**/*.go"]                      # glob 限定召回范围,避免噪音
  exclude_paths: ["**/*_test.go"]

trigger:
  description: |
    多个 goroutine 直接对未加锁的 plain map 做 m[k]=v 写入,
    或一个 goroutine 写、另一个读且未加锁。
  signals:                                # 给 agent 的检索线索,自然语言,不强求正则
    - "结构体字段是 map 类型,且被多个方法在 goroutine 中访问"
    - "go func(...) { ... m[..] = ... }"
    - "sync.Mutex / sync.RWMutex / sync.Map 缺席"

risk: |
  Go runtime 检测到并发 map 写入会直接 fatal error,
  整个进程 crash,无法 recover。
suggestion: |
  - 改用 sync.Map(读多写少场景)
  - 或加 sync.RWMutex 包裹访问

original_case:                            # 可选,但建议保留(必选项 a/b 都尽量带上)
  bug_link: https://...
  minimal_repro: |                        # 从原 bug 抽出来的最小可复现片段
    type Cache struct { data map[string]int }
    func (c *Cache) Set(k string, v int) { c.data[k] = v }   // 未加锁
  fix_diff: |                             # 修复 commit 的关键 diff
    + mu sync.RWMutex
    + c.mu.Lock(); defer c.mu.Unlock()
```

**字段必填性**：

| 字段 | 必填 | 说明 |
|------|------|------|
| `rule_id` / `title` / `category` / `severity` | ✅ | 输出 finding 时溯源需要 |
| `source.type` / `source.refs` | ✅ | 没有 source 的规则就是模型直觉,直接拒收 |
| `applies_to` | ✅ | 不限定范围会被无关 diff 召回,炸信噪比 |
| `trigger.description` + `trigger.signals` | ✅ | 没 signals,agent 没法在 diff 里识别 |
| `risk` / `suggestion` | ✅ | suggestion 是给 reviewer 的可操作输出 |
| `original_case` | 可选 | 见下条 |

**原始案例要不要留？**——**留，但分场景用**：

- 规则文件里保留 `original_case`（最小复现 + 修复 diff）。这是规则的"证据",出了 false-positive 能回溯。
- **默认不进 prompt**，避免 token 浪费和信噪比下降。
- 仅在两种情况下注入：
  1. agent 召回了这条规则,但模型对当前 diff 是否真的命中**没把握**（可以用 hook 检测 confidence 信号）
  2. 用户在审查报告里点"为什么这条规则触发"时,展开看原始案例
- 完整原始 bug 报告（堆栈、上下文、讨论）**不要进规则文件**，只在 `source.refs` 里留链接,需要时让人去原系统看。

**召回逻辑（v1 简版）**：

1. diff 路径 vs `applies_to.paths` / `exclude_paths` 过滤
2. 语言匹配
3. 把命中的规则塞进 agent prompt 的 "applicable rules" 段
4. 由 agent 用 `signals` 描述去 diff 里实际判定是否命中——**不在 pipeline 里写硬规则匹配**，让模型来判（这是用模型而不是用 grep 的根本原因）

### 3. 代码上下文获取能力

- 不用造。Agent SDK 自带 Read / Glob / Bash(grep) 等工具
- 让 agent 自己按需拉取被改函数的调用方、依赖、相关实现
- 这就是"动态按需上下文"，而不是预先把一堆代码塞进 prompt

### 4. Diff 来源适配层（DiffSource）

不同代码评审平台(GitHub / GitLab / Gerrit / 本地)给 diff 的 URL 格式、
认证方式、元信息字段都不同。统一抽象成 Protocol:

```python
class DiffSource(Protocol):
    def fetch(self, identifier: str) -> ChangeBundle: ...

@dataclass(frozen=True)
class ChangeBundle:
    diff_text: str                          # unified diff
    title: str                              # PR/CL 标题
    description: str | None                 # PR body / 提交说明 body
    author: Author | None                   # 作者信息
    branch: str | None
    target: str | None
    repo: str | None
    related_links: list[str]                # issue URLs from PR body / Gerrit topic
    source_kind: Literal["github", "gerrit", "local"]
    source_id: str                          # 原始 identifier,UI 用于回链
```

实现优先级(对应 Stage 1 → Stage 4):

| 实现 | identifier 形态 | 何时做 | 备注 |
|------|----------------|--------|------|
| `LocalDiffSource` | 本地 `.diff` 文件路径 | **Stage 1** | meta 字段全空,够跑 demo |
| `GitHubDiffSource` | `https://github.com/<owner>/<repo>/pull/<N>` | **Stage 4** | 用 `pull/<N>.diff` + `api.github.com/repos/.../pulls/<N>`;PAT 可选(私库需要);本机已实测 github.com 可达 |
| `GerritDiffSource` | Gerrit URL | **Stage 4** | 已实现 URL 识别、REST patch 拉取、XSSI/base64 decode 与 metadata 降级;真实内网认证需在可达环境继续验 |

### 5. 模型与认证

- 语言：**Python**（用 `claude-agent-sdk` 官方 Python 包）
- 默认模型：**Opus 4.7**（ID: `claude-opus-4-7`）
- ⚠️ 不要写死旧模型 ID，老一代 ID 已退役
- 视成本决定子任务能否降级到 Sonnet 4.6（`claude-sonnet-4-6`）

#### 认证与 base_url 切换（重要：要和本地 Claude CLI 配置隔离）

`claude-agent-sdk` (Python) 底层是子进程拉起 `claude` CLI。要让审查工具走第三方 Anthropic 兼容端点、又不动本地 CLI 配置，**通过 `ClaudeAgentOptions.env` 把环境变量注入到子进程**：

```python
from claude_agent_sdk import ClaudeAgentOptions, query

options = ClaudeAgentOptions(
    env={
        "ANTHROPIC_BASE_URL": "https://your-third-party-endpoint/v1",
        "ANTHROPIC_API_KEY":  "sk-xxx",      # 第三方端点签发的 key
        # 注意:这里只影响 SDK 拉起的子进程,
        # 本地 ~/.claude 里的用户 CLI 配置完全不动
    },
    model="claude-opus-4-7",
)
```

要在第 0 步实测验证的事情（任何一项失败,就要回到官方端点或换接入方式）：

1. 设置 `ANTHROPIC_BASE_URL` 后,SDK 是否真的发请求到该端点（抓包 / 看端点日志）
2. 第三方端点是否支持 Agent SDK 用到的 streaming / tool_use / system prompt 等能力
3. 本地原有的 `claude` CLI 用户配置（OAuth / 默认 key）是否被影响——预期：**完全不影响**,因为 env 注入只作用于 SDK 拉起的子进程
4. 同进程内能否多次切换端点（例如 review 走第三方,subagent 走官方）

---

## 四、流程设计

整个审查是一次 agent 任务，分 6 个环节：

### 1) 预处理

- 解析 diff，识别改动的文件、函数、模块
- 准备 agent 工作目录
- 通过 `settingSources` 加载对应模块的 skill
- 准备好元数据上下文（issue 描述、目标分支规则集）

### 2) 上下文组装（工具的技术核心）

**不要一股脑塞代码**。分三路：

| 路径 | 做法 |
|------|------|
| 规范 skill | 根据改动模块挂载对应的 skill 文件 |
| 历史规则 | 从规则库召回与本次 diff 模式匹配的规则（按改动文件路径 / 调用 API / 语法模式过滤） |
| 代码上下文 | **让 agent 自己用 grep / Read 工具按需检索**——调用方、依赖实现、相关测试 |

这层做得好不好，直接决定模型能不能给出有依据的意见。

### 3) 审查执行

- 跑 Agent SDK 的 agent loop
- 带着「规范 + 业务规则 + 按需代码上下文」做分析
- 复杂模块可以拆 subagent（例如一个专门看并发、一个看资源泄漏）

### 4) 结构化输出与分级

强制结构化（两种手段任选其一或组合）：

- **自定义工具**：定义一个 `report_finding` 工具，模型必须通过它输出每条意见——schema 强制带 severity / rule_id / file:line
- **PostToolUse hook**：在输出落地前做 schema 校验，不合规的拒掉重写

分级标准（v1 简单版，与前端 UI 词表对齐）：

- `critical`：违反硬规则（资源未释放、并发写、SQL 注入这类）→ 必须修
- `warning`：违反风格 / 设计建议 → 作者自行权衡
- `suggestion`：细节优化 / 可选改进 → 默认折叠展示

### 5) 信噪比过滤（工具的生死线）

丢掉两类意见：

- **通用 linter 能发现的**（拼写、未使用变量、格式）——别和 lint 工具抢饭碗
- **无依据的模型直觉**（rationale 里 rule_id 和 related_bugs 都为空的）

留下来的必须是"靠业务上下文才能发现"的意见。

宁可少给意见，不要给噪音。一个被打回去 3 次的工具，第 4 次就没人用了。

### 6) 输出

- 结构化报告
- 以 MR / PR 评论形式回写，按文件分组、按行号定位
- critical 级意见可上升为 review check 的 fail 状态（可选，v1 先不接 gating）

---

## 五、实施顺序

| 阶段 | 目标 | 当前状态 | 剩余交付物 |
|------|------|----------|------------|
| **第 0 步** | SDK 可用性 + 端点切换验证 | 已有 `.env.example`、EndpointConfig、两个 smoke 脚本 | 补强制 `Read/Grep` tool_use smoke；接 pre-commit/CI |
| **第 1 步** | 跑通最小闭环 | 已完成 diff → rules → prompt → agent → parser → review.json；本地 diff/GitHub PR source 可用 | `before/` + diff 自动生成 `workspace/` 可后置 |
| **第 2 步** | 规则资产 + 召回质量 | 已完成:20 条 `typical_case` 规则、Android case fixtures、L1/L2/L3/L4 召回、规则审计、case 覆盖、negative case、按文件分片 plan | 持续运营:bug_history 真实素材、更多 case、UI 展示 |
| **第 3 步** | 结构化输出 + 分级 + 噪音过滤 | 已完成:fenced YAML parser、parse repair、validator/filter、filtered metadata、去重与置信度阈值 | 中期增强:`report_finding` 工具或 hook |
| **第 4 步** | 嵌入 MR 流程 | 已完成:GitHub/Gerrit DiffSource、ReviewPublisher 抽象、GitHub summary 回写、Gerrit review payload、CLI/HTTP dry-run、fingerprint 幂等 | 生产化增强:真实平台 live auth 验证、webhook、GitLab、GitHub inline comment、可选 gating |
| **第 5 步** | UI 接入与 reviewer 工作台 | 已有 aiohttp server、`/api/review`、`/api/chat`、本地/GitHub 输入、Markdown chat | 去 mock 化、真实 History/Stats、copy/post 操作、配置持久化、运行记录 |

### Stage 2 详细计划:规则资产与召回质量

Stage 2 不阻塞在 `bug_history` 素材上。真实 bug 由团队同步收集；工程侧先把入口、校验、审计和回归体系搭好。

1. **规则资产分层**
   - `rules/typical_case/`: 通用陷阱。当前 Android APP/FWK 规则属于这一层,可继续扩展。
   - `rules/bug_history/`: 真实项目 bug/事故/线上问题抽象规则。当前先建目录、README、模板与审计规则,允许为空。
   - `rules/review_history/` 与 `rules/spec/`: 保留入口,不作为 v1 阻塞项。
2. **规则质量门禁**
   - 所有规则必须有 `source.refs`、`applies_to`、`trigger.signals`、`risk`、`suggestion`。
   - Stage 2 新增 `RuleInventory`/audit 能力,输出按 `source.type`、category、severity、language 的统计。
   - 对缺少 `recall.keywords/regexes` 的规则给 warning;对缺必填字段保持 loader hard fail。
3. **召回质量**
   - 保持 L1 语言、L2 路径、L3 recall hint、L4 priority cap。
   - 已新增 `recall.exclude_keywords/exclude_regexes`,用于压制已知安全写法的误召回。
   - 已新增 case-level 覆盖统计:每个 `tests/cases/*/case.yaml` 的 `expected.findings[].rule_id` 必须能被召回。
   - 已新增"负例 case":`expected.forbidden_rules` 不允许被召回,用来压误报。
4. **测试用例资产**
   - 每条高价值 Android 规则至少 1 个复杂 diff fixture。
   - fixture 继续使用 `change.diff` + `workspace/` after-state。
   - bug_history 规则到位后,每条 bug_history 至少 1 个历史回归 case。
5. **大 diff 策略**
   - Stage 2 已实现按文件切片的 review shard plan。
   - 每批只注入该文件相关规则,最后合并 findings 并去重。
   - 默认仍保留小 diff 单次 review 路径,避免过早复杂化。

Stage 2 完成标准:

- `scripts/rules_audit.py` 能给出规则库健康报告。
- `scripts/case_coverage.py` 能给出规则 case 覆盖与 expected-rule recall 报告。
- `scripts/review_shards.py` 能给出按文件分片与每片规则召回计划。
- `pytest tests/stage_2` 覆盖规则加载、召回、fixture 覆盖、case 覆盖和 audit。
- `typical_case` 至少 20 条；`bug_history` 入口存在,但真实数量不阻塞当前开发。
- Android APP/FWK 现有 case 全部可作为回归集运行。

### Stage 3 详细计划:结构化输出与噪音过滤

1. **生成侧强约束**
   - 已完成:保留 fenced YAML,增加 parse failure 后的一次 repair prompt。
   - 中期:实现 `report_finding` 工具或 PostToolUse hook,由 schema 强制字段类型。
2. **结果校验**
   - 已完成:`rule_id` 不在本次 recalled rules 中的 finding 直接丢弃。
   - 已完成:severity/category 必须等于规则定义,不允许模型自行升降级。
   - 已完成:line 必须落在 diff 的 `+` 行;不在 diff 内则丢弃。
3. **噪音过滤**
   - 已完成:`(rule_id,file,line)` 去重。
   - 已完成:低于配置阈值的 confidence 丢弃。
   - 已完成:linter-overlap denylist,避免格式、未使用变量、纯命名建议。
4. **报告增强**
   - 已完成:输出 `review.metadata.filtered_findings` 记录丢弃原因。
   - UI 展示"为什么没显示某条模型输出"只对 debug 模式开放。

Stage 3 完成标准:

- parser/validator/filter 三层都有单测。
- Agent 输出恶劣格式时不会把脏 finding 渲染到 UI。
- 同一条问题不会重复刷屏。

### Stage 4 详细计划:MR/PR 集成与回写

1. **DiffSource 完整化**
   - 已完成 GitHub:token/private repo 路径、错误提示、PR URL 回链。
   - 已完成 Gerrit:URL 识别、patch 拉取、revision 元数据与 metadata 降级。
   - GitLab:按需实现,优先级低于实际生产平台。
2. **Publisher 抽象**
   - 已完成 `ReviewPublisher` Protocol: `publish(report, mode=dry_run|draft|submit)`。
   - 已完成 GitHub publisher:幂等 PR summary comment。
   - 已完成 Gerrit publisher:review input payload,按文件+行号定位。
3. **工作流入口**
   - Webhook 接入:收到 PR/CL 事件后触发 review,后续生产化阶段再接。
   - 已完成 CLI/HTTP dry-run:本地先生成即将发布的 payload,不真正写回。
4. **幂等与安全**
   - 已完成 summary comment 稳定 fingerprint,GitHub 重复运行时 update 而不是重复发。
   - critical gating 默认不接入,真实 fail check 需要后续显式配置开启。

Stage 4 完成标准:

- 至少一个真实平台可以 dry-run + draft comment。当前 GitHub/Gerrit 均可 dry-run;Gerrit 可生成 draft payload。
- 失败时不影响源 PR/CL 状态。当前默认 dry-run,submit 失败仅返回错误。
- 回写内容与 UI report 一致。当前 payload 直接由 `review.json` findings/summary 生成。

### Stage 5 详细计划:UI 工作台去 mock 化

当前 UI 已经从原计划的静态 JSON 提前升级为本地 aiohttp server。Stage 5 目标改为"真实 reviewer 工作台"。

1. **数据源去 mock**
   - `data.js` 仅作为 demo fallback。
   - Result 页面全部从 `/api/review` 返回的 report 驱动。
   - History/Stats/Team 移除假业务数据,改为真实 runs 存储或明确 demo 标签。
2. **操作接实**
   - `copy summary`:复制当前 report summary/Gerrit summary。
   - `post to gerrit`:调用 Stage 4 publisher dry-run/submit。
   - Apply/Dismiss/Reply:先本地状态持久化,后续接平台评论线程。
3. **配置持久化**
   - Review language、rules_dir、默认 source、模型配置进入本地配置文件或 server state。
   - Settings 页面展示真实配置来源,不再展示不可用 host 假数据。
4. **Chat 工作流**
   - `/api/chat` 已可用,继续限制在当前 report/workspace 上下文。
   - 支持 Markdown 渲染,保留 HTML escape。
   - 后续支持"解释这条 finding 为什么触发"并展开原始案例。

Stage 5 完成标准:

- UI 不再把 demo 数据混入真实 review。
- 核心按钮有真实行为或显式 disabled。
- Chrome/Playwright 覆盖滚动、chat、summary、view mode、language。

---

## 六、目录结构（v1 初拟，Python）

```
ai-code-review/
├── docs/
│   ├── v1_plan.md                  # 本文档
│   ├── stages/                     # 每个开发环节的阶段说明文档(见 §9.5)
│   │   ├── stage_0_endpoint_check.md
│   │   ├── stage_1_spec.md
│   │   └── ...
│   └── templates/                  # 给团队复用的 prompt / 模板
│       └── rule_extraction_prompt.md  # 历史 bug / 规范 → 规则 YAML 的提取 prompt
├── pyproject.toml                  # 依赖 / ruff / black / mypy / pytest 配置
├── .pre-commit-config.yaml         # 提交前自动跑 lint + 单测
├── .env.example                    # ANTHROPIC_BASE_URL / API_KEY 模板
├── src/
│   └── ai_code_review/
│       ├── __init__.py
│       ├── pipeline/               # 6 个流程环节
│       │   ├── preprocess.py
│       │   ├── context_assemble.py
│       │   ├── review.py
│       │   ├── structurize.py
│       │   ├── filter.py
│       │   └── output.py
│       ├── tools/                  # 自定义工具(report_finding 等)
│       ├── hooks/                  # PostToolUse 等 hook
│       ├── rules/                  # 规则加载与召回逻辑
│       └── integrations/           # MR / PR 平台适配
├── skills/                         # 规范 skill 文件
│   ├── code_review.md              # 总 SKILL(角色/工作流/输出格式),Stage 1 直接用
│   ├── concurrency.md              # Stage 2+ 加,topic-specific 知识
│   ├── resource.md                 # Stage 2+ 加
│   └── ...
├── rules/                          # 规则库(YAML 文件)
│   ├── bug_history/                # 来自历史 bug
│   │   └── RULE-CONCUR-007.yaml
│   ├── typical_case/               # 跨模块通用陷阱
│   │   └── RULE-RESOURCE-001.yaml
│   ├── review_history/             # 可选
│   └── spec/                       # 可选
├── examples/                       # 各阶段 demo 输入(diff + 工作区代码)
│   └── stage_1_demo/
│       ├── cache_loader.py
│       └── change.diff
├── ui/                             # 前端(Claude Design 生成),消费 pipeline 出的 JSON
│   ├── index.html
│   ├── app.jsx
│   ├── data.js                     # Stage 5 前: mock; Stage 5 后: 由 pipeline 输出替换
│   └── ...
├── reviews/                        # Stage 5+ 出的 JSON 结果(gitignored)
│   └── <run-id>/review.json
├── scripts/
│   ├── step0_local_cli.py          # 第 0 步:本地 CLI 凭证 smoke
│   └── step0_endpoint_check.py     # 第 0 步:第三方端点 smoke
└── tests/
    ├── stage_0/                    # 按环节组织,与 docs/stages/ 一一对应
    ├── stage_1/
    ├── stage_2/
    ├── ...
    ├── integration/                # 慢测/外部依赖测试,单独跑
    └── fixtures/                   # 历史真实 diff 作为回归用例
```

---

## 七、关键技术决策（这些决定了 v1 不会走弯路）

1. **输入只接 diff，不接整仓**——token / 注意力 / 信噪比三杀
2. **代码不做 RAG，文档才做 RAG**——代码靠 agent grep 按需拉
3. **不和通用 linter 抢活**——规则库只覆盖"靠业务上下文才能发现"的问题
4. **每条意见必须能溯源**——无 rationale 的意见在过滤层直接丢
5. **模型 ID 不写死成常量**——配置化，避免后续退役一刀切
6. **第 2 步是护城河，资源向它倾斜**——做完工具才有差异化
7. **v1 只做缺陷审查,不做逻辑审查**——见下方"审查范围边界"

---

### 审查范围边界:缺陷审查 vs 逻辑审查

v1 **只做缺陷审查**(rule-driven defect review),不做逻辑/功能审查(logic review)。
两者区别:

| 维度 | 缺陷审查(v1 做) | 逻辑审查(v2 再考虑) |
|------|-----------------|---------------------|
| 输入 | diff + 规则库 | diff + 需求文档 + 相关代码 + 测试 |
| 判断 | 是否匹配已知不良模式 | 是否实现了应实现的功能 |
| 精度 | 高(有规则锚定) | 中低(依赖模型推理) |
| 误报代价 | 可控,有 rule_id 溯源 | 大,纯"模型直觉"易被打回 |

**为什么 v1 不开这个口子**:同一份输出里既有"规则锚定的缺陷"也有"模型猜的逻辑问题",
用户会因混合噪音劝退,整个工具的信噪比下降——这是 §五"信噪比是生死线"的直接对应。

**v2 时怎么开**:加独立的 `logic_review` subagent,输出标记为 `category: logic`,
UI 折叠显示并明确标注"低置信"。这样规则审查的护城河不被稀释。

---

## 八、v1 不做的事（明确边界）

- ❌ 自动修复 / 自动提交 patch（v1 只出意见，不动代码）
- ❌ 跨 MR 的全局架构分析（v1 只看本次 diff）
- ❌ 代码 RAG 向量库（让 agent grep 即可）
- ❌ 自定义训练 / 微调（用 prompt + skill + 规则即可）
- ❌ 实时 IDE 内审查（v1 走 MR 流程；IDE 版本是 v2）
- ❌ 多语言全覆盖（v1 锁定 1–2 个主力语言，把规则做深）

---

## 九、开发约束（Clean Code + TDD + 每阶段自审）

整个项目按"环节"推进（第 0 步、第 1 步……，以及每步内部的子模块），每个环节都遵守下面这套硬约束。

### 9.1 代码质量底线（Clean Code）

- **命名表意**：函数 / 变量名读出来就是它做的事，禁止 `data` / `info` / `handle` 这种空名
- **函数单一职责**：一个函数只做一件事，超过 ~30 行或两层嵌套就要考虑拆分
- **依赖倒置**：业务代码依赖抽象（接口 / Protocol），不依赖具体实现——便于 mock 单测
- **不写注释解释代码做了什么**，只在"为什么这样做"非显然时写一行；用好命名替代注释
- **错误处理在边界**：内部代码相信契约，只在系统边界（用户输入、外部 API、文件 IO）做校验
- **不预先设计未来功能**：YAGNI，不为想象中的需求加抽象

### 9.2 适用的设计模式（按场景选用，不强求覆盖）

- **Pipeline / Chain of Responsibility**：6 个流程环节天然是 pipeline，每个 stage 实现统一接口 `Stage.run(ctx) -> ctx`，方便插拔与单测
- **Strategy**：规则召回、模型选择、端点选择都用策略模式，便于切换
- **Adapter**：MR 平台适配（GitLab / GitHub / Gerrit）走 adapter，统一抽象 `MRClient`
- **Factory**：规则加载用 factory，根据 `source.type` 决定如何解析
- **Dependency Injection（用 Protocol / 构造器注入）**：所有 stage 的外部依赖（SDK client、规则库、文件系统）通过构造器传入，便于在测试里替换
- ⚠️ **禁止过度模式化**：单元素的 Strategy、只调用一次的 Factory 都是噪音，直接函数即可

### 9.3 TDD 工作流（每个环节强制遵守）

每个环节按以下 5 步推进，**禁止跳步**：

| 步骤 | 产出 | 验收 |
|------|------|------|
| **1. 定目标** | 在 `docs/stages/<stage>_goal.md` 写下：本环节的输入、输出、对外契约、非目标 | 一句话能说清楚做什么、不做什么 |
| **2. 写测试** | 在 `tests/<stage>/` 下写单元测试,覆盖：正常路径、边界、错误路径 | 测试运行后**全部 fail**（没实现） |
| **3. 最小实现** | 写最少的代码让测试**全部通过** | `pytest` 全绿；不允许"提前"实现测试没覆盖的能力 |
| **4. 重构 / 扩展** | 在测试保护下重构：抽接口、解耦、命名优化、补充模式 | 重构后测试仍全绿；测试数量可增加,但 step 3 的测试不允许删 |
| **5. 自审 + 阶段文档** | 见 9.4 / 9.5 | `docs/stages/<stage>_review.md` 落地 |

**关键纪律**：

- 测试先于实现。先写出"我希望它怎么被调用"，再去实现它——这会反过来逼出好的 API
- 一次只让一个测试变绿；多个测试同时绿往往意味着实现走在测试前面
- 测试要快：单测全集跑完 < 10s。慢的、依赖外部的放到 `tests/integration/`，单独命名标识
- **不允许为了让测试过而修改测试**（除非测试本身写错了，需先在 commit message 解释原因）

### 9.4 自审清单（每环节完成后，以"Python 资深 + 架构师"视角逐项核对）

- [ ] **可读性**：陌生人 10 分钟能看懂这个模块在做什么吗？
- [ ] **可测性**：每个公有函数都有单测吗？外部依赖都能 mock 吗？
- [ ] **耦合度**：本模块改动会波及多少别的模块？依赖方向是否单向？
- [ ] **错误处理**：边界处的异常是否被正确捕获 / 转换？内部是否在过度防御？
- [ ] **资源管理**：文件 / 网络 / 子进程是否都有 `with` / `try-finally` 保护？
- [ ] **性能**：有没有 O(n²) 隐藏在双层循环里？大对象有没有重复拷贝？
- [ ] **类型注解**：所有公有接口是否带类型注解？`mypy --strict` 能过吗？
- [ ] **命名一致性**：与项目其他模块用的术语对齐了吗？
- [ ] **YAGNI 检查**：有没有提前实现的"未来可能用到"的代码？删掉
- [ ] **依赖倒置**：业务逻辑是否依赖了具体的 SDK / 框架类型？应改成依赖 Protocol

发现问题就回到 step 4 修，修完重新自审。

### 9.5 阶段开发说明文档（每环节产出一份）

每完成一个环节，在 `docs/stages/` 下产出一份开发说明，**统一格式**：

```
docs/stages/
├── stage_0_endpoint_check.md
├── stage_1_minimum_loop.md
├── stage_2_rules.md
├── stage_3_structured_output.md
└── stage_4_mr_integration.md
```

每份文档包含以下章节（缺一不可）：

1. **本阶段目标**：从 9.3 step 1 的 `_goal.md` 摘要而来
2. **最终对外契约**：模块的公有 API（函数签名 / 类 / 配置项），含类型
3. **关键设计决策**：选了哪个模式 / 为什么没用某个看似明显的方案 / 替代方案的取舍
4. **测试覆盖**：列出主要测试用例，说明覆盖了哪些路径；附 `pytest --cov` 覆盖率
5. **自审记录**：9.4 清单的过程结果，**包含发现的问题与如何修复**（不允许只写"全部通过"）
6. **已知限制 / 待办**：本阶段没做但下个阶段或 v2 要做的事
7. **回归用例链接**：指向 `tests/fixtures/` 里跟本阶段相关的真实 diff 样本

### 9.6 工程化配套（一次性配好,后续每环节自动生效）

- `pyproject.toml`：依赖锁定，`ruff` + `black` + `mypy` 配置
- `pytest.ini` / `pyproject.toml[tool.pytest]`：单测目录、覆盖率阈值（v1 设 80%）
- `pre-commit`：提交前自动跑 `ruff` / `black` / `mypy` / `pytest -m "not integration"`
- CI（最简）：PR 时跑全量测试 + 覆盖率门禁
- **第 0 步就把这套配好**，不要拖到后面——基础设施越晚加越痛

---

## 十、成功判据（v1 验收）

- [ ] 给定一个真实历史 MR，工具能给出至少一条有 rule_id / bug 溯源的有效意见
- [ ] 在 30 个历史 MR 回归集上，意见的 precision ≥ 70%（被 reviewer 认可）
- [ ] 单 MR 审查耗时 < 2 分钟，成本 < 0.5 USD
- [ ] 接入一个真实仓库的 MR 流程，连续跑 1 周不被开发者关掉
