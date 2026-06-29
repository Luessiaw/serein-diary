# P5 API 与前端适配契约

本文档冻结 P5 的最小正式契约：后端 API 如何提供连续日记流、日历统计、评论和媒体；
前端如何通过 adapter 消费这些接口。它承接
[`p4-storage-handoff.md`](p4-storage-handoff.md)，但不替代
[`data-contract-v1.md`](data-contract-v1.md)。

P5 的实现原则：

- 公开端点统一在 `/api/v1/*` 下。
- 所有日记、评论和媒体接口都需要 P3 锁屏会话认证。
- 已保存条目的标题和正文不可编辑；只允许软删除、评论新增/删除和媒体读取。
- 文件事实源仍是 `metadata.json`、`content.md`、`comments.json`、
  `media-manifest.json`。
- SQLite 索引是可重建衍生物；P5 可以先采用“写入后重建索引”的保守策略。
- 前端组件不直接散落 `fetch()`；统一通过 API adapter。

## 通用约定

### 时间与顺序

- 所有 API 时间字段使用带 UTC 偏移量的 ISO 8601 字符串。
- `created_at` 是排序、分组和目录命名的唯一时间事实源。
- 列表 API 返回的 `items` 始终按 `created_at` 正序排列，即从旧到新。
- “加载更早内容”通过 `before` 游标请求比当前最早条目更早的一页；响应仍按正序返回。

### 分页参数

列表端点使用：

```text
limit: 1..100，默认读取前端配置值，后端可设安全上限
before: 可选游标，表示只返回早于该游标的条目
after: 可选游标，表示只返回晚于该游标的条目
include_deleted: 默认 false
```

首屏请求不传 `before`，后端返回“最近 N 篇”，但 `items` 内部仍按正序排列。继续向上
加载时，前端使用当前最早条目的 `cursor` 作为 `before`。
日期窗口模式向下加载更晚内容时，前端使用当前最晚条目的 `cursor` 作为 `after`。
`before` 与 `after` 不可同时传入。

### 游标格式

P5 使用不透明游标字符串。前端只保存和回传，不解析。

建议后端初版使用：

```text
base64url("<created_at>|<entry_id>")
```

服务端解析失败时返回 `400 invalid_cursor`。后续如果游标格式变化，前端不需要改动。

### 通用错误响应

正式 API 使用稳定错误码：

```json
{
  "error": {
    "code": "entry_not_found",
    "message": "Entry not found."
  }
}
```

建议状态码：

| 状态码 | code | 用途 |
|---|---|---|
| 400 | `invalid_request` | 参数缺失、字段非法、正文为空等。 |
| 400 | `invalid_cursor` | 分页游标无法解析或不属于当前契约。 |
| 400 | `storage_contract_error` | 事实文件不符合 v1 契约。 |
| 401 | `unauthenticated` | 未通过锁屏会话。 |
| 404 | `entry_not_found` | 条目不存在或已不可访问。 |
| 404 | `comment_not_found` | 评论不存在。 |
| 404 | `media_not_found` | 媒体不存在。 |
| 409 | `entry_deleted` | 对已删除条目执行不允许的写操作。 |
| 413 | `media_too_large` | 上传文件超过限制。 |
| 415 | `unsupported_media_type` | 不支持的媒体类型。 |
| 500 | `internal_error` | 未预期错误；不得泄露路径、正文或 secret。 |

错误消息可以本地化，但前端逻辑只依赖 `code`。

## 数据形状

### EntrySummary

用于列表和日历附近跳转：

```json
{
  "id": "0b6d2ebd-74f8-4a5c-9515-aaf4076b6189",
  "created_at": "2026-06-23T00:14:23+08:00",
  "cursor": "opaque-cursor",
  "title": "夜雨",
  "content_excerpt": "今天下了一场很轻的雨。",
  "comment_count": 0,
  "media_count": 0,
  "deleted": false
}
```

列表摘要不返回完整正文。前端如需正文，可使用详情端点，或正式列表端点在 P5-T03
明确加入 `content` 字段。为减少首版复杂度，P5-T03 可以让列表直接返回 `content`，
但 adapter 对外仍应分成 summary/detail 概念，方便后续优化。

### EntryDetail

```json
{
  "id": "0b6d2ebd-74f8-4a5c-9515-aaf4076b6189",
  "created_at": "2026-06-23T00:14:23+08:00",
  "cursor": "opaque-cursor",
  "title": "夜雨",
  "content": "今天下了一场很轻的雨。\n",
  "comments": [],
  "media": [],
  "deleted": false
}
```

`content` 是 Markdown 字符串，不是 HTML 或 Tiptap JSON。

### Comment

```json
{
  "id": "55c4e14d-0506-45fd-9e0f-3e8a6d6aa40b",
  "created_at": "2026-06-23T00:20:00+08:00",
  "content": "这里是一条评论。",
  "anchor": null
}
```

引文评论：

```json
{
  "id": "55c4e14d-0506-45fd-9e0f-3e8a6d6aa40b",
  "created_at": "2026-06-23T00:20:00+08:00",
  "content": "这里是一条引文评论。",
  "anchor": {
    "type": "quote",
    "selected_text": "被选中的原文",
    "prefix": "前文上下文",
    "suffix": "后文上下文"
  }
}
```

评论只新增/删除，不编辑。

### MediaItem

```json
{
  "id": "8c21d9b4-77c8-4eb2-8ea9-2c72d7c76f13",
  "kind": "image",
  "url": "/api/v1/entries/<entry_id>/media/<media_id>",
  "alt": "雨后的树",
  "created_at": "2026-06-23T00:18:00+08:00"
}
```

前端永远使用 API URL 读取媒体，不使用宿主机路径。

## 正式 API 端点

### 会话

沿用 P3：

```text
GET  /api/v1/auth/session
POST /api/v1/auth/login
POST /api/v1/auth/logout
```

前端启动时先检查 session。未认证时显示锁屏，不渲染日记流。

### 条目列表

```text
GET /api/v1/entries?limit=30&before=<cursor>&include_deleted=false
```

响应：

```json
{
  "items": [],
  "page": {
    "limit": 30,
    "has_more": false,
    "next_before": null,
    "next_after": null
  }
}
```

约定：

- 首次请求返回最近 N 篇，内部正序。
- `has_more=true` 表示仍可继续请求更早内容。
- `next_before` 是下一次加载更早内容时要传回的游标；通常等于当前响应最早条目的游标。
- 使用 `after` 请求更晚内容时，`next_after` 是下一次加载更晚内容时要传回的游标；
  通常等于当前响应最晚条目的游标。
- 默认过滤软删除条目。

### 日期窗口

用于日历点击跳转，不要求前端从当前窗口一路分页到目标日期。

```text
GET /api/v1/entries/window?date=2026-06-23&before_count=12&after_count=12&include_deleted=false
```

响应：

```json
{
  "items": [],
  "window": {
    "target_date": "2026-06-23",
    "before_count": 12,
    "after_count": 12,
    "target_count": 0,
    "has_earlier": false,
    "has_later": false,
    "earlier_before": null,
    "later_after": null
  }
}
```

约定：

- `date` 是目标本地日期，由 `created_at` 的本地日期派生。
- 返回目标日期当天所有条目、之前最多 `before_count` 篇、之后最多 `after_count` 篇。
- `items` 始终按 `created_at` 正序返回。
- `has_earlier` / `earlier_before` 用于继续向上加载更早内容。
- `has_later` / `later_after` 用于后续实现向下加载更晚内容。
- 目标日期没有条目时返回空窗口，不报错。
- 默认过滤软删除条目。

### 条目详情

```text
GET /api/v1/entries/{entry_id}
```

响应为 `EntryDetail`。

### 创建条目

```text
POST /api/v1/entries
```

请求：

```json
{
  "title": "夜雨",
  "content": "今天下了一场很轻的雨。\n"
}
```

约定：

- `title` 可省略或为空。
- `content` 必须非空，使用 UTF-8/LF Markdown。
- 服务端生成 `id` 与 `created_at`。
- 成功后返回 `201 EntryDetail`。
- 保存成功后标题和正文封存，不提供更新接口。
- 写入后必须刷新索引；P5 初版可直接重建索引。

### 删除条目

```text
DELETE /api/v1/entries/{entry_id}
```

约定：

- 执行软删除：写入 `metadata.deleted_at`。
- 不删除 `content.md`、评论或媒体文件。
- 成功后返回删除后的 `EntryDetail`，其中 `deleted` 为 `true`。
- 写入后必须刷新索引。

### 日期统计

```text
GET /api/v1/entries/dates?from=2026-01-01&to=2026-12-31&include_deleted=false
```

响应：

```json
{
  "dates": [
    {
      "date": "2026-06-23",
      "count": 2
    }
  ]
}
```

约定：

- 日期按 `created_at` 的本地日期派生。
- 默认不统计软删除条目。
- `include_deleted=true` 时统计软删除条目，主要用于调试或管理视图。
- `from` / `to` 可选；后端可设置最大范围以保护性能。
- 前端日历只使用 `date` 和 `count` 判断深色日期。

### 评论

```text
GET    /api/v1/entries/{entry_id}/comments
POST   /api/v1/entries/{entry_id}/comments
DELETE /api/v1/entries/{entry_id}/comments/{comment_id}
```

POST 请求：

```json
{
  "content": "这里是一条评论。",
  "anchor": null
}
```

约定：

- 评论 `content` 必须非空。
- 评论只新增/删除，不编辑。
- 对已软删除条目新增评论返回 `409 entry_deleted`。
- 写入后必须刷新索引中的 `comment_count`，或重建索引。

### 媒体

```text
POST /api/v1/entries/{entry_id}/media
GET  /api/v1/entries/{entry_id}/media/{media_id}
```

P5 首个媒体闭环先支持 `image`。上传使用 `multipart/form-data`：

```text
file: binary
alt: optional string
```

约定：

- 服务端校验 MIME、扩展名、大小和路径。
- 媒体事实写入 `media-manifest.json`。
- 读取媒体必须认证。
- 前端正文使用 `media:<uuid>` 引用，不保存真实文件路径。

## 前端 API adapter

前端新增单一 adapter 层，建议文件：

```text
frontend/scripts/api-client.js
frontend/scripts/data-adapter.js
```

adapter 对组件暴露的方法：

```js
adapter.getSession()
adapter.login(password)
adapter.logout()
adapter.listEntries({ limit, before, after, includeDeleted })
adapter.getEntryWindow({ date, beforeCount, afterCount, includeDeleted })
adapter.getEntry(entryId)
adapter.createEntry({ title, content })
adapter.deleteEntry(entryId)
adapter.getEntryDates({ from, to })
adapter.listComments(entryId)
adapter.createComment(entryId, { content, anchor })
adapter.deleteComment(entryId, commentId)
adapter.uploadMedia(entryId, { file, alt })
adapter.getMediaUrl(entryId, mediaId)
```

adapter 必须隐藏 mock/backend 差异。组件只接收统一形状：

- `EntrySummary`
- `EntryDetail`
- `Comment`
- `MediaItem`
- `ApiError`

### mock 与 backend 切换

P5 保留 mock 模式用于公开展示和无后端开发。建议读取：

```html
<meta name="serein-data-source" content="backend">
```

取值：

- `mock`：使用 `mock-entries.js` 和本地模拟分页。
- `backend`：使用 `/api/v1/*`。

当前默认值为 `backend`，以保持锁屏认证行为；公开静态展示时可显式改为 `mock`。
API base 继续读取：

```html
<meta name="serein-api-base" content="/api/v1">
```

### 前端状态约定

- 未认证：显示锁屏，不渲染日记流。
- 已认证但列表失败：显示轻量错误与重试，不清空新建区输入。
- 创建失败：保留标题和正文。
- 创建成功：将服务端返回条目插入连续流，并重置新建区。
- 删除成功：从当前流移除或标记删除，并刷新日期统计；具体 UI 在 P5-T08 收窄。
- `has_more=false`：顶部控件显示“已加载所有日记内容”，不再触发加载。

## 索引刷新策略

P5 初版采用简单可靠策略：

- 创建条目后重建索引。
- 删除条目后重建索引。
- 新增/删除评论后重建索引。
- 媒体 manifest 更新后重建索引。

后续如果性能需要，可以替换为增量更新；API 契约不因此变化。

## P5-T01 不实现的内容

本任务只冻结边界，不实现代码：

- 不重构 `/api/v1/entries`。
- 不新增 service 层。
- 不改前端数据流。
- 不实现评论或媒体写入。
- 不改变当前 mock 静态体验。
