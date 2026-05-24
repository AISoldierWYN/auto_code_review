# Stage 4 - MR/PR 集成与回写

## 1. 本阶段目标

Stage 4 把 `review.json` 从本地报告推进到可接平台工作流的形态:

- 补齐 Gerrit DiffSource,让 CL URL 可以被解析并拉取 unified patch。
- 新增统一的 ReviewPublisher 抽象,让 GitHub/Gerrit 回写走同一契约。
- 提供 CLI 和本地 HTTP dry-run 入口,先生成即将发布的平台 payload。
- 保证回写幂等,重复运行时尽量 update 已有 AI review 评论,而不是刷屏。

## 2. 最终对外契约

DiffSource:

```python
from ai_code_review.diff.sources import GerritDiffSource, select_source

source = select_source("https://gerrit.example.com/c/project/+/123/4")
bundle = await source.afetch("https://gerrit.example.com/c/project/+/123/4")
```

Publisher:

```python
from ai_code_review.publish import create_publisher

publisher = create_publisher("gerrit", target="https://gerrit.example.com/c/project/+/123")
result = await publisher.publish(review_json, mode="dry_run")
```

CLI:

```powershell
python scripts\publish_review.py --review reviews\demo\review.json --platform gerrit
python scripts\publish_review.py --review reviews\demo\review.json --platform github --mode submit
```

HTTP:

```http
POST /api/publish
{
  "review": { "...": "review.json" },
  "platform": "gerrit",
  "target": "https://gerrit.example.com/c/project/+/123",
  "mode": "dry_run"
}
```

返回值是 `PublishResult` 的 JSON 形态,包含 `platform`、`mode`、`fingerprint`、
`target`、`action`、`submitted` 和 `payloads`。

## 3. 关键设计决策

### D1. dry-run 是默认安全路径

CLI 和 HTTP endpoint 默认 `mode=dry_run`。`dry_run` 和 GitHub 的 `draft`
都不会触网写回;Gerrit 的 `draft` 返回 draft payload。真正写回必须显式传
`mode=submit`。

### D2. GitHub 先做 summary comment

GitHub publisher 当前发布一个 PR conversation summary comment。评论正文带
`<!-- ai-code-review:fingerprint=... -->` marker。提交时会先查找已有 AI
review comment,找到则 PATCH,否则 POST 新评论。

### D3. Gerrit 按文件和行号生成 review input

Gerrit publisher 使用 `/changes/{change}/revisions/{revision}/review`,
把 finding 转成 `comments[path][]` 中的 unresolved 行内评论,并附带同一份
summary message。

### D4. Gerrit metadata 可降级

Gerrit patch 是运行 review 的硬依赖;detail metadata 只是标题、作者、分支等 UI
信息。metadata 请求失败时返回 diff-only `ChangeBundle`,不阻断 review。

## 4. 测试覆盖

- `tests/stage_4/test_gerrit_source.py`:Gerrit URL 解析、REST id 编码、XSSI strip、base64 patch decode、metadata 填充。
- `tests/stage_4/test_publish_format.py`:summary/inline comment 格式、fingerprint 稳定性、marker。
- `tests/stage_4/test_publishers.py`:GitHub dry-run/create/update,Gerrit dry-run/submit payload。
- `tests/stage_4/test_publish_cli.py`:CLI dry-run 输出 payload。
- `tests/stage_4/test_publish_api.py`:`/api/publish` dry-run 与错误路径。

当前验证:

```text
pytest tests/stage_4
19 passed
```

## 5. 自审记录

- 可读性:平台无关格式化集中在 `publish/format.py`,平台写回逻辑分别在
  `publish/github.py` 和 `publish/gerrit.py`。
- 可测性:DiffSource 和 Publisher 都支持注入 `session_factory`,测试不触网。
- 耦合度:Publisher 消费普通 `review.json` dict,不依赖 UI 或 pipeline 内部对象。
- 错误处理:平台解析错误统一转成 `ReviewPublisherError`;Gerrit metadata 失败降级。
- 资源管理:真实 HTTP session 都通过 `async with` 关闭。
- YAGNI:没有提前做 GitLab、check-run gating 或复杂评论线程管理。

## 6. 已知限制 / 待办

- GitHub 当前只发 summary comment,还没有按 diff position 生成 inline review comments。
- GitHub 查重只扫描前 100 条 issue comments;大型 PR 后续需要分页。
- Gerrit 已有 REST patch/review payload,但内部 Gerrit 真实认证和 live 写回还需要在可达网络里验。
- Webhook 触发、GitLab publisher、critical gating 都保留到后续生产化阶段。
- `mode=submit` 是显式操作,当前没有额外的审批/二次确认层。

## 7. 回归用例链接

- `tests/stage_4/test_gerrit_source.py`
- `tests/stage_4/test_publish_format.py`
- `tests/stage_4/test_publishers.py`
- `tests/stage_4/test_publish_cli.py`
- `tests/stage_4/test_publish_api.py`
