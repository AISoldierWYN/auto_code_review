# `tests/cases/` — 用户提供的端到端测试用例

每一个 `case_<name>/` 子目录是一个独立的端到端测试用例。pytest 会自动发现并
parametrize,无需改测试代码。

## 目录结构

```
tests/cases/case_<name>/
├── case.yaml          # 必填:元数据 + 期望结果
├── change.diff        # 必填:unified diff(标准 git diff 格式)
├── workspace/         # 必填:after-state 文件,镜像仓库路径
│   └── <repo-relative-path>
└── rules/             # 可选:本用例参与的规则 YAML
    └── *.yaml
```

### `case.yaml` 字段

```yaml
name: case_<name>                      # 必填,必须等于目录名
description: 一句话说明
language_hint: python                  # 可选,加速规则召回
expected:
  findings:                            # 必填,期望命中的 finding
    - rule_id: RULE-RESOURCE-001
      file: path/to/file.py
      line_range: [10, 12]             # int 或 [start, end];finding.line 必须在此区间
  forbid_other_critical: false         # 可选,true 时不允许有此用例之外的 critical
  summary_substring: "open"            # 可选,review.summary 应包含此子串
```

## 工作区状态来源(Stage 1)

只支持 `workspace/`(after state)。**不支持** `before/` + 自动 apply。

如何获取 after-state 文件:

```bash
# 假设你正在还原历史 commit <fix-sha>
git checkout <fix-sha>
# 复制你关心的文件到 tests/cases/case_xxx/workspace/<repo-relative-path>
```

或者直接手工编辑 workspace 下的文件,匹配 change.diff 的 after 状态即可。

`before/` 目录 → `workspace/` 自动 apply 计划在 Stage 1.5 加。

## 跑端到端测试

```bash
# 跑所有用例(慢,会调真实 agent SDK)
pytest tests/ -m integration

# 跑单元测试(快,不调用 SDK)
pytest tests/ -m "not integration"
```
