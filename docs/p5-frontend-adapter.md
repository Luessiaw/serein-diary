# P5 前端 API adapter

P5-T05 新增前端统一数据适配层。它的目标不是立即替换整个日记流，而是先把前端组件
未来需要的数据方法集中起来，避免后续在各处散落 `fetch()`。

## 文件

```text
frontend/scripts/api-client.js     # 统一 fetch、JSON、错误解析
frontend/scripts/data-adapter.js   # mock/backend 双数据源 adapter
```

`frontend/index.html` 需要按顺序加载：

```html
<script src="scripts/mock-entries.js" defer></script>
<script src="scripts/api-client.js" defer></script>
<script src="scripts/data-adapter.js" defer></script>
<script src="scripts/app.js" defer></script>
```

## 数据源切换

通过 meta 指定：

```html
<meta name="serein-data-source" content="backend">
```

取值：

- `backend`：使用 `/api/v1/*`，保持锁屏认证。
- `mock`：使用 `mock-entries.js`，认证直接返回 mock session，适合纯静态展示。

API base 仍由以下 meta 指定：

```html
<meta name="serein-api-base" content="api/v1">
```

## Adapter 方法

浏览器中当前 adapter 暴露为：

```js
window.SereinDataAdapter
```

当前已提供：

```js
SereinDataAdapter.getSession()
SereinDataAdapter.login(password)
SereinDataAdapter.logout()
SereinDataAdapter.listEntries({ limit, before, includeDeleted })
SereinDataAdapter.getEntry(entryId)
SereinDataAdapter.createEntry({ title, content })
SereinDataAdapter.deleteEntry(entryId)
SereinDataAdapter.getEntryDates({ from, to, includeDeleted })
SereinDataAdapter.listComments(entryId)
SereinDataAdapter.createComment(entryId, { content, anchor })
SereinDataAdapter.deleteComment(entryId, commentId)
SereinDataAdapter.uploadMedia(entryId, { file, alt })
SereinDataAdapter.getMediaUrl(entryId, mediaId)
```

评论和媒体的正式后端实现留到 P5-T09/P5-T11；adapter 先保留方法边界。

## Console 验证

登录后在浏览器开发者工具运行：

```js
await SereinDataAdapter.listEntries({ limit: 3 })
await SereinDataAdapter.getEntryDates({ from: "2026-01-01", to: "2026-12-31" })
```

切到 mock 模式后，以上方法应不依赖后端也可返回数据。

## 后续接入

- P5-T06：日记流向上加载改为使用 `listEntries()`。
- P5-T07：新建保存改为使用 `createEntry()`。
- P5-T08：删除和日历跳转使用 `deleteEntry()` 与 `getEntryDates()`。
