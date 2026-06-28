# P4 存储层测试与 P5 交接说明

本文档面向 P5 开发：说明 P4 已经稳定下来的事实文件、存储模块、索引、dry-run 和
最小验证 API。它不是新的数据契约；数据契约仍以
[`data-contract-v1.md`](data-contract-v1.md) 为准。

## P4 已完成的边界

P4 的目标是让后端能安全读写当前 v1 文件结构，并为后续正式 API 提供可复用基础。
当前已完成：

- v1 条目目录与事实文件校验。
- 扁平 `entries/YYYYMMDDHHmm-<uuid>/` 扫描。
- 不可变条目创建。
- `metadata.deleted_at` 软删除。
- 可删除、可重建的 SQLite 索引。
- 只读 dry-run 检查。
- 一个临时的受认证 `/api/v1/entries` 最小验证 API。

P4 不包含：

- 已保存条目的正文或标题编辑。
- 草稿持久化。
- 评论新增/删除 API。
- 媒体上传、缩略图生成或媒体读取 API。
- 正式连续流分页游标。
- legacy 目录转换；早期结构会被视为非法目录。

## 事实源与衍生物

`DIARY_DATA_DIR/entries/` 下的四类文件是事实源：

```text
metadata.json
content.md
comments.json
media-manifest.json
```

SQLite 索引、内容摘要、日期统计、渲染 HTML、缩略图和未来 Tiptap 状态都只是衍生物。
P5 写入任何事实文件后，必须能通过重建索引恢复列表与统计能力。不要把索引用作唯一
事实来源。

## 可复用模块

| 模块 | P5 可复用能力 | 注意事项 |
|---|---|---|
| `serein.storage.entry` | `read_entry()`、Pydantic 数据模型、目录名/metadata/content/comments/media 校验 | 抛出 `EntryValidationError`；错误信息不能包含正文内容。 |
| `serein.storage.repository` | `create_entry()`、`scan_entry_summaries()`、`find_entry_by_id()`、`mark_entry_deleted()` | 创建与删除会修改事实文件；扫描按 `created_at` 正序返回。 |
| `serein.storage.index` | `rebuild_index()`、`list_indexed_entries()`、`count_entries_by_date()` | 索引位于 `.serein/index.sqlite3`，是可删除衍生物；P5 需要决定写入后是增量更新还是重建。 |
| `serein.storage.migration` | `dry_run_migration()` | 只读检查；只支持当前 v1 条目目录或单个 v1 条目目录。 |
| `serein.api.entries` | P4 浏览器/curl 验证用 entries API | 临时验证接口，不等同于 P5 正式连续流 API。 |

## P5 API 设计建议

P5 的正式 API 与前端 adapter 契约见
[`p5-api-frontend-contract.md`](p5-api-frontend-contract.md)。下面保留的是从
P4 存储层过渡到 P5 服务层的设计提示。

P5 可以在现有 storage 模块上新增正式服务层，而不是让路由直接拼装文件系统逻辑。
建议边界：

- `EntryService.list_page(...)`
  - 优先使用 SQLite 索引返回摘要。
  - 支持“更早内容”游标分页和 `has_more`。
  - 不把索引中的摘要当正文事实；详情仍从条目事实文件读取。
- `EntryService.create_entry(...)`
  - 调用 `repository.create_entry()`。
  - 创建后更新或重建索引。
  - 返回新条目的详情和新的分页/日期统计影响。
- `EntryService.get_entry(id)`
  - 调用 `repository.find_entry_by_id()`。
  - 返回 `content.md`、评论摘要、媒体 manifest。
- `EntryService.delete_entry(id)`
  - 调用 `repository.mark_entry_deleted()`。
  - 删除后更新或重建索引。
- `CommentService.add_comment/delete_comment`
  - P4 尚未实现；P5 应继续保持评论“只新增/删除，不编辑”。
  - 评论写入后需要更新索引中的 `comment_count` 或重建索引。
- `MediaService`
  - P4 尚未实现；P5 应继续通过 `media-manifest.json` 管理媒体 ID 与相对路径。

正式 API 仍应全部位于 `/api/v1/*`，并继续使用 P3 的锁屏认证依赖。

## 错误处理约定

P4 当前用 `EntryValidationError` 表示存储与契约错误。P5 路由层应把它转换成稳定的
HTTP 响应：

- 未找到条目：`404`
- 非法输入、非法目录、契约不匹配：`400`
- 未认证：沿用 P3 认证层的 `401`

当前 P4 最小 API 仍使用字符串 detail；P5 正式 API 可以进一步封装为稳定错误码，
例如 `entry_not_found`、`entry_invalid`、`storage_contract_error`。

无论是日志、HTTP 错误还是 dry-run 报告，都不应打印 `content.md` 正文内容。

## 自动测试

从仓库根目录运行：

```bash
backend/.venv/bin/python -m unittest discover -s backend/tests
```

辅助检查：

```bash
backend/.venv/bin/python -m compileall -q backend/serein backend/tests
git diff --check
```

测试覆盖索引见 [backend/tests/README.md](../backend/tests/README.md)。

## 手动验证

P4 提供一个最小 entries API，方便在浏览器或 curl 中验证真实文件写入。说明见
[`p4-entries-api-test.md`](p4-entries-api-test.md)。

手动验证前，建议将 `.env` 中的 `DIARY_HOST_DATA_DIR` 指向临时目录，避免把测试条目
写入真实日记目录。

## P5 开始前检查清单

- 后端测试全部通过。
- `DIARY_DATA_DIR` 指向仓库外目录。
- 确认是否采用索引增量更新；若暂不实现，写操作后先重建索引也可以。
- 确认正式列表 API 的游标格式和 `has_more` 响应字段。
- 确认评论 API 与媒体 API 的最小范围。
- 确认前端连续流只通过 API 适配器取数据，不读取本地路径。
