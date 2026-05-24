# Stage 0 目标 — SDK 可用性 + 端点切换验证

## 一、本阶段目标

在写任何业务代码前,先回答两个问题：

1. **`claude-agent-sdk` (Python) 在本机能否正常跑通最小 agent loop?**
2. **能否通过 `ClaudeAgentOptions(env=...)` 让 SDK 走第三方 Anthropic 兼容端点,且不影响本地 `~/.claude` 的 CLI 配置?**

只有两个问题都得到肯定答案,后续 Stage 1+ 的工作才有意义。

## 二、对外契约(本阶段产出物)

| 产出 | 路径 | 用途 |
|------|------|------|
| 项目骨架 | `pyproject.toml`, `src/ai_code_review/__init__.py`, `tests/` | Stage 1+ 直接复用 |
| 第三方端点配置加载器 | `src/ai_code_review/config/endpoint.py` | 抽象出 `EndpointConfig` 数据类与 `load_from_env_file()` |
| 验证脚本 A | `scripts/step0_local_cli.py` | 复用本机 CLI 凭证,跑最小 hello agent |
| 验证脚本 B | `scripts/step0_endpoint_check.py` | 注入第三方 env,跑同一个 hello agent |
| `.env.example` + `.gitignore` | 项目根 | 第三方凭证模板;真实 `.env` 不入库 |
| 单元测试 | `tests/stage_0/` | 覆盖 `EndpointConfig` 的加载、校验、env dict 输出 |

### `EndpointConfig` 设计草案

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

    def to_env_dict(self) -> dict[str, str]:
        """转换为 ClaudeAgentOptions.env 接受的 dict[str, str]"""
        ...

    @classmethod
    def from_mapping(cls, m: Mapping[str, str]) -> "EndpointConfig":
        """从环境变量或 .env 解析"""
        ...
```

**关键设计原则**：

- 配置类 `frozen=True`,不可变,便于线程安全与单测
- `to_env_dict()` 只输出**非 None 字段**,避免覆盖本地配置时把空值写进去
- 验证脚本通过依赖注入接受 `EndpointConfig`,便于在测试里替换

## 三、验证清单(两路 smoke test 各自必须通过)

### 路径 A:本地 CLI 凭证

- [ ] SDK 能成功启动 agent
- [ ] 能收到模型的非空响应
- [ ] 退出码 0,无异常

### 路径 B:第三方端点(腾讯 lkeap)

- [ ] SDK 能用注入的 env 启动 agent
- [ ] 能收到模型的非空响应
- [ ] 抓包或日志能看到请求打到 `api.lkeap.cloud.tencent.com`,不是 `api.anthropic.com`
- [ ] **跑完之后,本机 `~/.claude/` 下的配置文件未被修改**(用 mtime 对比验证)
- [ ] 同一进程内,A 和 B 切换不串

## 四、非目标(本阶段不做)

- ❌ 不接 diff 输入(Stage 1)
- ❌ 不加载 skill / 规则库(Stage 2)
- ❌ 不强制结构化输出(Stage 3)
- ❌ 不接 MR 平台(Stage 4)
- ❌ 不做完整的 retry / 错误恢复(只验证 happy path)
- ❌ 不评估第三方端点的模型质量(只验证连通性)

## 五、退出标准

只要两路 smoke test 任一失败,**本阶段不结束**,要么修方案,要么换接入方式。
全部通过后,进入 `docs/stages/stage_0_endpoint_check.md` 写阶段 review。
