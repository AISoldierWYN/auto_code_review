# Stage 0 — SDK 可用性 + 端点切换验证（开发说明）

> 完成于 2026-05-20 · 模板：`v1_plan.md` §9.5

## 1. 本阶段目标(摘自 `stage_0_goal.md`)

回答两个 yes/no 问题:

1. `claude-agent-sdk` (Python) 在本机能否跑通最小 agent loop?
2. 能否通过 `ClaudeAgentOptions(env=...)` 让 SDK 走第三方 Anthropic 兼容端点,且**不修改本地 `~/.claude/` 用户配置**?

两个都通过才允许进入 Stage 1。

## 2. 最终对外契约

### 2.1 `EndpointConfig` (`src/ai_code_review/config/endpoint.py`)

```python
@dataclass(frozen=True)
class EndpointConfig:
    auth_token: str | None
    base_url: str | None
    default_haiku_model: str | None
    default_sonnet_model: str | None
    default_opus_model: str | None
    api_timeout_ms: int | None
    disable_nonessential_traffic: bool = False

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str]) -> EndpointConfig: ...
    def to_env_dict(self) -> dict[str, str]: ...
    def has_overrides(self) -> bool: ...
```

不变量:

- 不可变(`frozen=True`)
- 空串视为缺失,**不会**进入 `to_env_dict()` 输出
- `to_env_dict()` 的 dict 可以**直接**传给 `ClaudeAgentOptions(env=...)`
- 未设置的字段不会被发到子进程,因此**不会无意中覆盖父进程的 env**

### 2.2 Smoke 脚本

| 脚本 | 用途 | 退出码语义 |
|------|------|------------|
| `scripts/step0_local_cli.py` | 复用本地 CLI 凭证,跑 hello agent | 0=PASS, 2=无文本, 3=无 ResultMessage, 4=API 错误 |
| `scripts/step0_endpoint_check.py` | 注入第三方端点跑同一个 prompt + 检测本地配置文件不被改动 | 0=PASS, 2/3/4=同上, 5=SDK 异常, 10=本地配置文件被改动 |

## 3. 关键设计决策

### D1. SDK 子进程能否走第三方端点?——能,通过 `env` 参数

`claude-agent-sdk` 0.2.82 的 `ClaudeAgentOptions` 有 `env: dict[str, str]` 字段,会作为环境变量传给它拉起的 `claude` CLI 子进程。父进程的 `os.environ` 不受影响,本地 `~/.claude/.credentials.json` 也不受影响——这正是隔离要求。

### D2. 模型别名 env 不靠谱,改传直名

**最大发现**:用户给的配置里 `ANTHROPIC_DEFAULT_OPUS_MODEL=glm-5` 这套别名映射,**在 CLI v2.1.143 下没有生效**。

实测结果(同一 env,只改 `model` 参数):

| `model=` 传入 | CLI 实际发出的模型名 | 端点响应 |
|-------------|---------------------|----------|
| `None`(默认) | 内置 sonnet 真名 | 400 invalid model |
| `"sonnet"` | 内置 sonnet 真名 | 400 invalid model |
| `"opus"` | 内置 opus 真名 | 400 invalid model |
| `"tc-code-latest"` | `tc-code-latest` | ✅ PONG |
| `"glm-5"` | `glm-5` | ✅ PONG |

**结论**:CLI 把 `opus`/`sonnet` 别名展开成 Anthropic 官方名再发出,第三方端点不认。`ANTHROPIC_DEFAULT_*_MODEL` 环境变量没有被这个 CLI 版本读取(可能是更高级订阅或更新版的特性)。

**应对**:`step0_endpoint_check.py` 直接读 `.env` 里的 `ANTHROPIC_DEFAULT_OPUS_MODEL` 作为 `model` 参数,绕过 CLI 的别名展开。Stage 1+ 需要一个"端点 ↔ 模型直名"的映射策略。

### D3. "不修改本地配置" 用文件 snapshot 验证

不靠假设,**用代码验证**:smoke B 跑前后对 `~/.claude/{.credentials.json, settings.json, settings.claude.json}` 各做一次 `(size, mtime_ns)` 快照,任何变化就 fail(exit 10)。

故意不监控 `history.jsonl` / `sessions/` / `stats-cache.json` 这类会话日志——它们写入是预期的,与"用户配置不被污染"是两件事。

### D4. `frozen=True` + 工厂方法

`EndpointConfig` 是不可变 dataclass,所有解析逻辑放在 `from_mapping` 工厂,`__init__` 走默认构造器。好处:

- 测试里能不带任何 mapping,直接构造任意状态的 config
- 多线程 / 多端点切换时可以安全共享
- 单元测试覆盖了 frozen 行为(`TestImmutability`)

### D5. `to_env_dict()` 只 emit set 字段

如果把 `None` 字段也写成空串发到子进程,会把 CLI 从 inherited 环境里读到的 `ANTHROPIC_API_KEY` 等**清掉**——这是隐蔽 bug。所以严格"set 才 emit"。

### D6. 没有用到的设计模式(故意)

- 没引入 Strategy / Factory 抽象——只有一种 endpoint config 来源(`.env`),YAGNI
- 没引入 Adapter——Stage 4 接 MR 平台时再加
- 没引入 Pipeline——Stage 1 再加

## 4. 测试覆盖

```
tests/stage_0/
└── test_endpoint_config.py    15 passed in 0.01s
```

主要用例:

| 用例 | 覆盖 |
|------|------|
| `test_parses_all_known_fields` | 全字段正常解析 |
| `test_missing_fields_become_none` | 空 mapping → 全 None |
| `test_empty_string_treated_as_missing` | `KEY=` 这种 .env 常见写法 |
| `test_disable_flag_truthy_values` | `1` / `true` / `TRUE` / `yes` |
| `test_disable_flag_falsy_values` | `0` / `false` / `FALSE` / `no` / `""` |
| `test_invalid_timeout_raises` | 非整数 timeout 抛 ValueError |
| `test_only_emits_non_none_fields` | 不污染父进程 env |
| `test_disable_flag_omitted_when_false` | bool false 不 emit |
| `test_full_roundtrip` | `from_mapping ∘ to_env_dict` 等价于恒等(对完整输入) |
| `test_is_frozen` | 不可变 |
| `test_has_overrides_*` | 注入决策的边界 |

`coverage`:本阶段 `endpoint.py` 100%(无未走到分支)。

## 5. 自审记录(§9.4 清单逐项)

| 项 | 结果 | 说明 |
|----|------|------|
| 可读性 | ✅ | 命名表意,无注释解释 what,只在 `to_env_dict` / `D5` 解释了 why |
| 可测性 | ✅ | 所有公有 API 有单测,无外部依赖 |
| 耦合度 | ✅ | `EndpointConfig` 0 外部依赖;smoke 脚本依赖 SDK + dotenv,通过 import 隔离 |
| 错误处理 | ✅ | 边界(`.env` 缺失 / timeout 非数字 / 必填缺失)都有显式抛错 |
| 资源管理 | ✅ | `async for` 完整 drain query 流;无文件句柄泄漏 |
| 性能 | N/A | smoke 阶段 |
| 类型注解 | ✅ | 全公有 API 注解,`from __future__ import annotations` 启用 PEP 604 |
| 命名一致 | ✅ | `from_*` / `to_*` / `has_*` 动宾对称 |
| YAGNI | ✅ | 没有提前抽 Strategy / Factory;两个 smoke 脚本有重复的"drain async generator"逻辑,**故意不**抽,Stage 1 出现第 3 处时再抽 |
| 依赖倒置 | ✅ | `EndpointConfig` 是纯数据,smoke 脚本在边界引入 SDK |

### 实际踩过的坑(必须记)

1. **模型别名 env 失效** — 见 D2。第一次 smoke B 跑直接 400,差点以为端点配置错;debug 时把 `model` 列举 4 种才定位。
2. **`pytest-asyncio` 没装** — `pyproject.toml` 里 `asyncio_mode = "auto"` 但没把 pytest-asyncio 列进 dependencies,首次 `pytest` 报 unknown config option。装上后 OK。后续要在 dev extras 加上。
3. **`dotenv_values` 返回 `dict[str, str | None]`** — 有些 key 可能是 `None`。`from_mapping` 接收 `Mapping[str, str]`,所以在 smoke B 里显式过滤了 None,避免类型 mismatch。

### 修复

- 坑 1:在 `step0_endpoint_check.py` 强制使用 `.env` 里的直名(`default_opus_model`),并在代码注释 + 本文 D2 留档。
- 坑 2:已装 `pytest-asyncio`。**TODO**:把它写进 `pyproject.toml` 的 `[project.optional-dependencies].dev`。
- 坑 3:在 `load_endpoint_config()` 用 `{k: v for k, v in dotenv_values(...).items() if v is not None}` 过滤。

## 6. 已知限制 / 待办

- ⚠️ **模型别名映射不可用**:Stage 1 在调用 SDK 时不能假设 `model="opus"` 能跨端点工作。需要建一个 `EndpointProfile` 抽象,把"端点 + 默认 review 模型直名"绑在一起。下个阶段做。
- ⚠️ **未验证 tool_use 支持**:smoke 跑的是纯文本回答,没用到 `Read`/`Bash`/`Glob` 等工具。Stage 1 喂 diff 时会用到,届时如果第三方端点不支持工具调用,要立刻发现。建议 Stage 1 第一个测试就是"让 agent 用 Read 工具读一个文件"。
- ⚠️ `pyproject.toml` 的 dev extras 还没加 `pytest-asyncio`、`ruff`、`mypy` 没在 CI 里跑。Stage 1 开工前补。
- ⚠️ 没接 pre-commit。Stage 1 开工前补。
- ⚠️ 没有 CI。可以放到 Stage 4 之前补。

## 7. 回归用例

- `tests/stage_0/test_endpoint_config.py` — 15 个单测,提交即跑
- `scripts/step0_local_cli.py` — 手动跑,验证本地 CLI 凭证仍可用
- `scripts/step0_endpoint_check.py` — 手动跑,验证第三方端点 + 隔离性

后续如果改 `EndpointConfig` 字段或 `ClaudeAgentOptions` 的 env 传递行为,**两个 smoke 都要重跑**。
