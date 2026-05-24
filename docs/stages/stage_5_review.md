# Stage 5 - UI reviewer 工作台去 mock 化

## 1. 本阶段目标

Stage 5 把前端从 demo review 面板推进到真实 reviewer 工作台:

- Review 首屏默认进入 Empty,不再把 demo payment 数据当成当前 review。
- 真正跑 `/api/review` 后才填充 `CURRENT_*` 运行时状态。
- `copy summary` 和 `post to gerrit` 接到真实行为或明确 disabled。
- History/Stats 只展示本浏览器真实运行记录;未接入的 Team/组织数据不再显示假数据。
- 用 Playwright 覆盖滚动、chat Markdown、summary、view mode、language、copy/post 行为。

## 2. 最终对外契约

前端 runtime 状态:

```js
window.CURRENT_PR
window.CURRENT_FILES
window.CURRENT_DIFF
window.CURRENT_COMMENTS
window.CURRENT_ALL_COMMENTS
window.CURRENT_REVIEW_RAW
window.CURRENT_HISTORY
```

前端动作:

```js
await window.runRealReview(identifier, { reviewLanguage: "zh" })
await window.askReviewChat(question, { reviewLanguage: "zh" })
await window.copyCurrentSummary()
await window.publishCurrentReview({ platform: "gerrit", mode: "draft" })
```

验证入口:

```powershell
npm run verify:stage5
```

## 3. 关键设计决策

### D1. Demo 数据保留但不自动渲染

`data.js` 仍保留 `DEMO_*` 作为视觉 fallback 和人工调试素材,但 App 默认不读取它们。
当前工作台只渲染 `CURRENT_*`;没有真实 review 时显示 Empty。

### D2. History/Stats 先做本地真实记录

还没有后端 run store。Stage 5 先把每次真实 review 写入 `localStorage`
中的 `kit.reviewHistory.v1`,History/Stats 基于这些记录展示。这样不会再混入虚构团队数据,
也给后续后端持久化留出清晰替换点。

### D3. Publish 默认生成 draft payload

`post to gerrit` 只有当前 target 是 Gerrit 时可点击,点击后调用 `/api/publish`
的 `mode=draft`。这一步生成 Gerrit review payload,不提交真实评论。真实 `submit`
仍留给显式配置后的生产化步骤。

### D4. 未接入能力显式空态

Team 和组织级指标需要真实目录/平台 API。Stage 5 不继续展示假成员、假接受率和假趋势,
而是显示空态,避免和真实 review 混淆。

## 4. 测试覆盖

Playwright 脚本 `scripts/verify_stage5_ui.js` 覆盖:

- 初始 Review 页面为空态,不显示 demo `PaymentProcessor` 内容。
- 加载真实 review 后 diff column 可滚动。
- `by severity` 视图能显示当前 finding。
- `copy summary` 写入剪贴板,内容来自当前 review。
- local diff 下 `post to gerrit` disabled;Gerrit target 下启用并调用 `/api/publish`。
- Summary tab 显示当前 review 摘要和 finding。
- Chat Markdown 渲染 heading、strong、inline code、table、code block、ordered list。
- Settings 中切换 English 后 chat placeholder 生效。
- History/Stats 基于真实运行记录显示。

当前验证:

```text
npm run verify:stage5
ok: true
```

## 5. 自审记录

- 可读性:`glue.js` 负责后端 API 和 runtime 状态转换,React 组件只消费 `CURRENT_*`。
- 可测性:Playwright 内置 mock server,不依赖真实模型或外部 Gerrit/GitHub。
- 耦合度:Stage 5 复用 Stage 4 `/api/publish`,没有在 UI 里拼平台 payload。
- 错误处理:review/chat/publish 失败会显示错误或本地 fallback,不会污染当前 review。
- 资源管理:浏览器端 history 限制到最近 40 条。
- YAGNI:未提前实现组织目录、后端 run DB、真实 submit 和 gating。

## 6. 已知限制 / 待办

- History/Stats 目前是浏览器本地记录,刷新服务器或换浏览器不会共享。
- `post to gerrit` 仍是 draft payload/dry-run 路径,真实提交需要显式启用。
- Team 页面还没有组织数据源。
- Apply/Dismiss/Reply 仍是本地 UI 状态,还没有回写平台评论线程。
- Settings 只控制前端显示偏好;模型和 token 仍由 server `.env` 管理。

## 7. 回归用例链接

- `scripts/verify_stage5_ui.js`
- `scripts/verify_ui_scroll.js`
