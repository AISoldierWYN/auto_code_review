# Android 典型规则种子

这批规则是基于 Android 官方文档和常见 APP/FWK review 经验沉淀的
`typical_case` 规则,不是内部历史 bug。后续如果你提供真实 review 案例,
优先把命中的规则升级或复制为 `bug_history` 规则,并在 `source.refs`
中记录内部 bug/MR 链接。

## 覆盖范围

- APP Java/Kotlin: 主线程阻塞、Cursor/WakeLock 资源释放、PendingIntent、
  WebView bridge、SQLite 注入、动态 receiver、前台服务、明文 HTTP、
  静态 Context 泄漏、Kotlin Flow/Coroutine 生命周期。
- FWK Java/Kotlin: Binder identity、权限校验、锁内远端调用、
  RemoteCallbackList、DeathRecipient、跨用户 userId 校验。

## 使用建议

1. 先用这批规则跑你手头现有 diff,观察误报和漏报。
2. 对误报高的规则,收窄 `applies_to.paths` 或 `recall.regexes`。
3. 对真实命中过线上问题的规则,复制到 `rules/bug_history/` 并补内部来源。
4. 每补一条真实案例,在 `tests/cases/` 加对应 regression case。

