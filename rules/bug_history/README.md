# Bug History Rules

This directory is the Stage 2 intake point for rules extracted from real
project bugs, incidents, postmortems, or historically accepted review comments.

It is allowed to be empty while the team is still collecting source material.
When a real case is available, create one YAML rule per root cause:

```yaml
rule_id: RULE-ANDROID-BUG-001
title: Short concrete risk title
category: resource
severity: critical
source:
  type: bug_history
  refs:
    - BUG-12345
    - https://internal.example/bugs/BUG-12345
applies_to:
  languages: [java]
  paths: ["app/src/main/java/**/*.java"]
  exclude_paths: ["**/*Test.java"]
trigger:
  description: |
    Explain the pattern that should trigger this rule.
  signals:
    - "specific API or code shape to look for"
risk: |
  Explain why this caused or can cause a real defect.
suggestion: |
  Explain the safe fix pattern.
recall:
  keywords:
    - "cheap token used by L3 recall"
  regexes: []
original_case:
  bug_link: https://internal.example/bugs/BUG-12345
  minimal_repro: |
    Smallest code shape that reproduces the issue.
  fix_diff: |
    Key lines from the historical fix.
```

Run the inventory after adding rules:

```powershell
.\.venv\Scripts\python.exe scripts\rules_audit.py --rules-dir rules
```
