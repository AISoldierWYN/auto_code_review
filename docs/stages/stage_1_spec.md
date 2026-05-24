# Stage 1 输入规范(开工前确认)

> 这份文档是 Stage 1 **开工前**的契约。所有 artifact 在此固化下来,Stage 1 实现
> 不允许偏离;若发现规范本身有问题,先改本文档再继续。

## 1. Diff 输入规范

### 1.1 格式

- **标准 unified diff**(`git diff` / `git diff --staged` / `git show <commit>`
  / GitLab/GitHub MR API export 的格式都直接兼容)
- 编码 UTF-8,行尾 LF(CRLF 在 Windows 上读取时归一化)
- 路径形如 `a/<path>` / `b/<path>`,POSIX 分隔符
- 必须含 `--- a/...` 和 `+++ b/...` 头与至少一个 `@@ ... @@` hunk header
- 新增文件:`--- /dev/null` + `+++ b/<path>`;删除文件相反

### 1.2 范围(Stage 1 演示 vs. 最终产品)

| 维度 | Stage 1 (本阶段) | 最终 v1 产品 |
|------|------------------|--------------|
| 文件数 | ≤ 5(演示用) | **无硬限**,按文件分片处理 |
| 净行变更 | ≤ 200(演示用) | **无硬限**,超大文件按 hunk 切片 |
| rename / mode-change | 不处理 | Stage 4 接 MR 时支持 |
| 生成 / vendored / lock 文件 | 不区分 | 按 glob 排除清单跳过 |

**分片策略(最终产品)**:

1. **默认按文件分片**:一次 agent 调用看一个文件,findings 在最外层聚合
2. **超大文件按 hunk 分片**:单文件变更 > 阈值(默认 500 行)时再切
3. **跳过非业务代码**:`*.lock`、`*.min.js`、`vendor/**`、`*generated*` 等
4. **token 预算管理**:每片预算 ≤ 模型上限的 60%,留余量给规则注入
5. **结果聚合 + 去重**:跨片 findings 按 `(rule_id, file, line)` 去重

Stage 1 不做分片,只跑单文件 demo。Stage 2 引入"按文件分片",Stage 4 接 MR 时补预算管理。

### 1.3 工作区契约 — 用 checkout,不用 apply

**关键澄清**:pipeline 不解析 / 不 apply diff 来构造工作区。约定:

```
required: diff_file (unified diff), repo_root (工作区根目录)
契约:    repo_root 当前状态 == diff 的 after 状态  (调用方保证一致)
```

调用方按场景选择 checkout 方式:

| 场景 | 调用方做的事 | pipeline 收到的 |
|------|--------------|----------------|
| 本地未提交改动 | 啥也不做 | `git diff` 出来的内容 + 当前工作区 |
| GitHub PR | `gh pr checkout <num>` | `gh pr diff <num>` + 工作区 |
| Gerrit 改动 | `git fetch refs/changes/XX/YYY/Z && git checkout FETCH_HEAD` | `git show FETCH_HEAD` + 工作区 |
| 历史 commit | `git checkout <sha>` | `git show <sha>` + 工作区 |
| 孤儿 `.patch` 文件 | 自己 `git apply` 后再调 | 同本地未提交改动 |

agent 拿 `Read` / `Glob` / `Grep` 直接读工作区,读到的就是 after 状态。
pipeline 不动 git,YAGNI;Stage 4 之前都不需要内置 fetch+checkout。

### 1.4 输入来源(工程上可接的形态,Stage 1 不实现采集)

- 本地:`git diff` / `git diff --staged` / `git show <commit>` 重定向到文件
- 远端:GitHub PR API `application/vnd.github.diff` media type
- 远端:GitLab MR API `/projects/:id/merge_requests/:iid/diffs`
- 远端:Gerrit `/changes/<id>/revisions/<rev>/patch`(待 Stage 4 用户补识别逻辑)

### 1.5 Demo artifact

- `examples/stage_1_demo/cache_loader.py` — 工作区文件(after 状态)
- `examples/stage_1_demo/change.diff` — 该文件对应的 unified diff
- 引入了一处资源泄漏 bug(open 无 with),用于触发 `RULE-RESOURCE-001`

---

## 2. 规则模板规范

### 2.1 文件布局

```
rules/
├── bug_history/                   # 来自历史 bug
│   └── RULE-XXX-NNN.yaml
├── typical_case/                  # 跨模块通用陷阱
│   └── RULE-XXX-NNN.yaml
├── review_history/                # 可选
└── spec/                          # 可选
```

一个 YAML 文件一条规则,文件名 = `rule_id` + `.yaml`。loader 用
`rules/**/*.yaml` glob 加载。

### 2.2 YAML schema

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `rule_id` | str | ✅ | 全局唯一。形如 `RULE-<CATEGORY>-<NNN>` |
| `title` | str | ✅ | 一句话规则标题 |
| `category` | str | ✅ | 与 finding.category 对齐;v1 常用值:`resource` / `concurrency` / `error_handling` / `naming` / `business` |
| `severity` | enum | ✅ | `blocker` / `suggestion` / `nit` |
| `source.type` | enum | ✅ | `bug_history` / `typical_case` / `review_history` / `spec` |
| `source.refs` | list[str] | ✅ | bug 单号 / URL / 文档锚点;至少 1 个 |
| `applies_to.languages` | list[str] | ✅ | 小写语言名,例如 `[python]` |
| `applies_to.paths` | list[glob] | ✅ | 命中范围,glob 语法 |
| `applies_to.exclude_paths` | list[glob] | 可选 | 排除范围(测试目录通常排除) |
| `trigger.description` | str (multiline) | ✅ | 自然语言描述"什么样的代码会触发" |
| `trigger.signals` | list[str] | ✅ | 给 agent 的检索线索,**不强求正则**,让模型理解 |
| `risk` | str (multiline) | ✅ | 触发后可能的后果 |
| `suggestion` | str (multiline) | ✅ | 修复建议(允许包含示例代码) |
| `original_case.bug_link` | str / null | 可选 | typical_case 可为 null |
| `original_case.minimal_repro` | str (multiline) | 可选 | 默认不进 prompt(详见 §2.3) |
| `original_case.fix_diff` | str (multiline) | 可选 | 同上 |

### 2.3 `original_case` 注入策略

- **默认不进 prompt**,避免 token 浪费和噪音
- 仅在 agent 表达"不确定" / 用户点开"为什么这条规则触发"时再注入
- Stage 1 不做不确定性检测,所有 `original_case` 都不注入

### 2.4 规则加载原则 — filter first, never load all

规则会越积越多(目标 50→200→数百条),**禁止**一次性把全部规则塞进 prompt。
加载管线:

```
全部规则 (rules/**/*.yaml)
  │
  ├─[L1] 语言过滤   applies_to.languages ∩ diff 语言集 = ∅  → 丢
  ├─[L2] 路径过滤   applies_to.paths 不命中 diff 任何文件,或被 exclude_paths 命中 → 丢
  ├─[L3] 粗信号过滤 (Stage 2+,可选)  规则带 keyword/regex 预筛,diff 文本不含 → 丢
  └─[L4] 优先级裁剪  剩余 > 上限(默认 50)按以下顺序裁剪:
                    severity:        critical > warning > suggestion
                    source.type:     bug_history > typical_case > review_history > spec
  │
  ▼
注入到 prompt 的规则集合 (瘦身字段,见下表)
```

**注入时的字段瘦身**:

| 规则字段 | 注入 | 原因 |
|---------|------|------|
| `rule_id` / `title` / `severity` / `category` | ✅ | finding 溯源必需 |
| `trigger.description` / `trigger.signals` | ✅ | agent 判定核心依据 |
| `risk` / `suggestion` | ✅ | 写 finding body 用 |
| `source.type` | ✅(单字段) | 显示规则可信度 |
| `applies_to.*` | ❌ | 已在过滤阶段消化,不再注入 |
| `source.refs` | ❌ | 留给 UI 出链接,agent 不需要 |
| `original_case.*` | ❌ | 见 §2.3,默认不注入 |

**边界**:

- 单次注入命中 0 条规则 → pipeline **不调用 agent**,直接输出 `NO_FINDINGS`(省 token + 成本)
- 命中 > 上限 → 触发 L4 裁剪,在 review metadata 里记录裁掉的 rule_id 清单(便于审计)
- Stage 1 实现 L1/L2;L3 / L4 / metadata 记录是 Stage 2 工作

### 2.5 示例

见 `rules/typical_case/RULE-RESOURCE-001.yaml`(可直接作为 Stage 1 单测 fixture)

---

## 3. SKILL 模板规范

### 3.1 文件布局

```
skills/
├── code_review.md          # 角色 + 工作流 + 输出格式 + 硬约束 (本 stage 的核心 SKILL)
├── concurrency.md          # Stage 2+ 加,topic-specific 知识
└── resource.md             # Stage 2+ 加
```

`code_review.md` 是**总 SKILL**,Stage 1 总是注入到 system_prompt。
其他 topic skill 是按需挂载的领域知识(Stage 2+)。

### 3.2 SKILL 文件结构

每个 SKILL 是 markdown,顶部带 YAML frontmatter:

```markdown
---
name: <kebab-case-id>
description: <一两句话,说明这个 skill 干什么 / 何时挂载>
version: <semver>
stage: <最早可用的 stage 编号>
---

# Role
# Inputs you will receive
# Workflow (follow this order)
# Output format
# Hard constraints
# Examples
```

固定 6 段,目的:

| 段 | 作用 |
|----|------|
| Role | 明确角色与边界(你不是什么) |
| Inputs | 列出运行时会注入的上下文,模型知道去哪里看 |
| Workflow | 顺序步骤,降低跳步概率 |
| Output format | **精确格式**,让 Stage 3 的 parser 可靠工作 |
| Hard constraints | "禁止"清单,堵高频偏离 |
| Examples | 1-2 个极简示例,锚定预期行为 |

### 3.3 SKILL 如何"强制"规则检查 — 三层

L1 的具体手段(在 `code_review.md` 里体现):

1. **"无 rule_id 则不发"** — 输出格式里 rule_id 是必填,模型自己会校
2. **格式精确** — fenced code block + 哨兵 `END_OF_FINDINGS`/`NO_FINDINGS`,
   离开格式就是错
3. **正面工作流 + 负面禁止清单** 双向锚定
4. **示例锚定行为** — 两个最小例子,告诉模型"什么时候 NO_FINDINGS"
5. **明确边界** — "你不是 linter""你不是 chatbot""你不是 freelancer"

L2(Stage 3 加):自定义工具 `report_finding(rule_id, file, line, ...)`,模型
只能通过工具发 finding,工具内部校验 rule_id 是否在白名单。

L3(Stage 3 加):pipeline 后过滤,丢掉 rule_id 不在白名单的 finding,以及
line 不在 diff `+` 区域的 finding。

### 3.4 示例

见 `skills/code_review.md`(Stage 1 直接用)

---

## 4. Pipeline 输出 JSON Schema(供 UI 消费)

SKILL 让 agent 输出 fenced YAML(`finding` + `summary` 块);pipeline 解析后
转成下面的 JSON,UI 直接读取(替代 `ui/data.js` 的 `MOCK_*`)。

### 4.1 顶层结构

```jsonc
{
  "schema_version": "1.0",
  "review": {
    "diff_path": "examples/stage_1_demo/change.diff", // 暂用本地 diff 文件路径;Stage 4 接 MR 时可替换为 cl / pr_url
    "title": "Loads key=value cache file",            // 来自 commit msg / CLI 参数 / 调用方
    "branch": "feature/foo",                          // optional
    "target": "main",                                 // optional
    "author": { "name": "Lin Wei", "role": "L4 · Payments", "initials": "LW" }, // optional
    "repo": "platform/payments-svc",                  // optional
    "model": "glm-5",                                 // 实际请求的模型名
    "scanned_seconds": 12.3,
    "files_changed": 1,
    "additions": 11,
    "deletions": 0,
    "summary": "<来自 agent 的 summary 块,纯文本>",
    "metadata": {
      "rules_total": 134,                             // 仓库内规则总数
      "rules_after_filter": 3,                        // 过滤后真正注入的规则数
      "rules_dropped_by_l4": ["RULE-FOO-002", ...]    // L4 优先级裁剪掉的(审计用)
    }
  },
  "files": [/* §4.2 */],
  "findings": [/* §4.3 */]
}
```

### 4.2 `files[]` — 每文件聚合 + 结构化 hunks

```jsonc
{
  "path": "examples/stage_1_demo/cache_loader.py",
  "lang": "python",
  "add": 11,
  "del": 0,
  "severity_counts": { "critical": 1, "warning": 0, "suggestion": 0 },
  "diff_hunks": [                                     // 结构化形式,UI 直接渲染
    { "type": "hunk", "text": "@@ -1,8 +1,19 @@" },
    { "type": "ctx",  "old": 1, "new": 1, "text": "\"\"\"Demo module...\"\"\"" },
    { "type": "add",  "old": null, "new": 10, "text": "    f = open(path, \"r\", encoding=\"utf-8\")" },
    // ...
    { "type": "comment", "anchorNew": 10, "id": "c1" }  // pipeline 在 finding 锚点处插入,UI 用 id 关联到 findings[]
  ]
}
```

`severity_counts` 由 pipeline 从 `findings[]` 聚合得到,不让 agent 自己算。
`diff_hunks` 由 pipeline 解析 unified diff(用现成库,例如 `unidiff`)生成。

### 4.3 `findings[]`

```jsonc
{
  "id": "c1",                                         // pipeline 分配,与 diff_hunks 里的 comment 锚点一一对应
  "rule_id": "RULE-RESOURCE-001",
  "severity": "critical",                             // critical | warning | suggestion
  "category": "resource",
  "file": "examples/stage_1_demo/cache_loader.py",
  "line": 10,                                         // NEW 文件行号,锚定到一个 + 行
  "confidence": 0.92,
  "title": "open() 调用没有被 with 包裹",
  "body": "新引入的 <code>load_cache</code> 函数用 <code>open()</code> 打开文件后未通过 <code>with</code> 管理...",
  "suggestion": {
    "kind": "patch",                                  // "patch" | "text" | null
    "remove": ["    f = open(path, \"r\", encoding=\"utf-8\")"],
    "add":    ["    with open(path, \"r\", encoding=\"utf-8\") as f:"]
  },
  "rationale": {
    "rule_source_type": "typical_case",               // 显示规则可信度档位
    "source_refs": ["https://docs.python.org/3/library/functions.html#open", "PEP-343"]
                                                       // UI 可链接,从规则 source.refs 透传
  }
}
```

### 4.4 SKILL 输出 → JSON 的字段映射

| SKILL fenced YAML 字段 | JSON 路径 | 转换 |
|----------------------|-----------|------|
| `rule_id` / `severity` / `category` / `file` / `line` / `confidence` | `findings[].*` | 直接 |
| `title` / `body` | `findings[].title` / `findings[].body` | 直接(body 允许 `<code>`) |
| `suggestion_kind` = `patch` | `findings[].suggestion.kind` | 直接 |
| `suggestion_remove` / `suggestion_add` | `findings[].suggestion.{remove,add}` | 直接 |
| `suggestion_kind` = `text` | `findings[].suggestion = {kind:"text", text:...}` | 改 shape |
| `suggestion_kind` = `none` | `findings[].suggestion = null` | 直接 |
| `summary.text` (那个独立 summary 块) | `review.summary` | 直接 |
| (新分配) | `findings[].id` = `"c<N>"` | pipeline 按顺序分配 |
| (来自规则) | `findings[].rationale.source_refs` | 透传规则的 `source.refs` |

### 4.5 暂位:`diff_path` 替代 `cl`

UI 顶部目前显示 Gerrit `cl` 单号。v1 先用 **`diff_path`(本地 diff 文件路径)** 顶位渲染;
Stage 4 用户加上 Gerrit / PR 识别逻辑后,在 JSON 里新增 `cl` / `pr_url` 字段,
UI 优先用这些,fallback 到 `diff_path`。

---

## 5. Stage 1 流程草图(spec 阶段,不实现)

```
┌─────────────────────────────────────────────────────────────┐
│                       Stage 1 Pipeline                       │
└─────────────────────────────────────────────────────────────┘

  change.diff ─┐
               ├─► [preprocess]
  rules/*.yaml ┤      ├─ parse diff (paths, hunks)
               │      └─ rule recall (applies_to filter)
               │
   skills/     │
   code_review─┴─► [context_assemble]
                   └─ build system_prompt = SKILL + applicable rules
                                                  ↓
                                             [review agent]
                                          (Claude Agent SDK
                                           with Read/Glob/Grep)
                                                  ↓
                                            findings (text)
                                                  ↓
                                          [parse output]
                                          (fenced YAML blocks
                                           until END_OF_FINDINGS)
                                                  ↓
                                            list[Finding]
                                                  ↓
                                              stdout / file
```

## 6. Stage 1 验收(参考,实现时确认)

- 喂 `examples/stage_1_demo/change.diff` + `RULE-RESOURCE-001.yaml`,
  agent 必须返回**至少 1 条 finding**,`rule_id=RULE-RESOURCE-001`,
  `file=examples/stage_1_demo/cache_loader.py`,line 指向 `f = open(...)` 那一行
- 喂一个无问题的 diff(例如只改注释),必须返回 `NO_FINDINGS`
- agent **至少使用一次 Read 工具**(验证 tool_use 在第三方端点上可用)—
  对应 Stage 0 review 文档里的红线
- 整体耗时单 MR < 2 分钟,成本 < 0.5 USD
