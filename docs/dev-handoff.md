# Serein 开发交接文档

更新时间：2026-07-01

本文用于在新对话中接续 Serein Diary 开发。建议新对话先阅读：

1. `AGENTS.md`
2. `tasks.csv`
3. `docs/plan-v1.1.md`
4. `docs/data-contract-v1.md`
5. `docs/p5-api-frontend-contract.md`
6. 本文档

## 当前状态

Serein 是独立自托管日记仓库，位于：

```text
/home/luessiaw/storage/srv/projects/serein-diary
├── backend/        # FastAPI 后端
├── frontend/       # 原生 HTML/CSS/JS 前端
├── deploy/         # Caddy 示例配置
├── docs/           # 设计、契约、交接文档
├── compose.yaml    # 可选 Docker Compose 示例
└── tasks.csv       # 本地任务表，不需要纳入 Git 跟踪
```

真实日记数据不进入仓库。Compose 示例中，`.env` 的 `DIARY_HOST_DATA_DIR` 映射到容器
`/data`，后端通过 `DIARY_DATA_DIR=/data` 读取。
API 容器通过 `DIARY_API_UID:DIARY_API_GID` 写入该目录，避免新条目在宿主机上归属
`root:root`。luessiaw-server 当前 UID/GID 为 `1000:1000`。

阶段进度：

- P0--P4 已完成。
- P5P 已完成：正式 entries API、日期统计 API、前端 adapter 已建立。
- P5A 已完成到 `P5A-T04`：真实只读流、日期统计、日历跳转、双向窗口加载、窗口裁剪和浏览器验收准备均已完成。
- P5B 已完成到 `P5B-T02`：
  - backend 正式写作固定为离线 `Textarea`，不依赖 Tiptap CDN。
  - 设置页有受认证的“重建索引”按钮，用于手动迁移 entries 后刷新 SQLite 衍生索引。
  - 新建区保存按钮已接入 `SereinDataAdapter.createEntry()`。
  - 保存中禁用输入和按钮；失败保留输入；成功后插入当前最新阅读流。
  - 新建卡片使用独立 `sortAt` 未来哨兵值，保证始终排在已保存条目之后。
- 下一步是 `P5B-T03`：真实写入闭环浏览器验收。

## 协作规则

- 不要在聊天中打印真实日记正文、完整条目内容、密码、Cookie、session、私有宿主路径。
- 可以打印数量、布尔值、接口状态、错误码、排序检查结果等安全摘要。
- 前后端联调时，可以加可复制的 console debug，但不能打印正文或秘密。
- `tasks.csv` 和 `AGENTS.md` 是本地协作文件，不需要 Git 跟踪。
- 用户偏好每次修改后给出一行提交建议：

```bash
git add . && git commit -m "Add: 中文说明"
```

## 数据契约

事实源结构：

```text
entries/
└── YYYYMMDDHHmm-<uuid>/
    ├── metadata.json
    ├── content.md
    ├── comments.json
    ├── media-manifest.json
    └── media/
```

核心规则：

- `created_at` 是唯一时间事实源。
- 不使用 `date`、`updated_at`、`revision`。
- 已保存日记标题和正文不可编辑。
- 日记允许新增和软删除；评论只允许新增和删除。
- 删除使用 `metadata.deleted_at`，不物理删除正文。
- SQLite 索引是可删除、可重建的衍生物；事实文件才是数据事实。
- `content.md` 是语义 Markdown，不保存任意 HTML、CSS、Tiptap JSON 或字体样式。

## 当前后端能力

公开 API 统一在 `/api/v1/*`，均需锁屏会话认证，除健康检查外。

```text
GET    /api/v1/health
GET    /api/v1/auth/session
POST   /api/v1/auth/login
POST   /api/v1/auth/logout

GET    /api/v1/entries
GET    /api/v1/entries/window
GET    /api/v1/entries/dates
POST   /api/v1/entries/rebuild-index
GET    /api/v1/entries/{entry_id}
POST   /api/v1/entries
DELETE /api/v1/entries/{entry_id}
```

已实现服务边界：

- `GET /entries` 支持 `limit`、`older_than`、`newer_than`、`include_deleted`。
- `GET /entries/window` 支持按日期获取目标日及上下文窗口。
- `GET /entries/dates` 支持日历日期统计。
- `POST /entries` 创建不可变 v1 条目，写入事实文件并增量更新索引。
- `DELETE /entries/{id}` 写入 `metadata.deleted_at` 软删除并增量更新索引。
- `POST /entries/rebuild-index` 从事实文件重建 SQLite 索引，只返回数量摘要。

创建和删除在索引存在时只更新单条摘要；索引缺失或外部手动添加
entries 后，可以使用重建索引接口刷新列表和日历：

```js
await SereinDataAdapter.rebuildIndex()
```

## 当前前端能力

主要文件：

- `frontend/scripts/app.js`
- `frontend/scripts/data-adapter.js`
- `frontend/scripts/api-client.js`
- `frontend/styles/base.css`
- `frontend/styles/tokens.css`

当前能力：

- 锁屏认证接入后端。
- 首页默认使用后端真实 entries，不再回退 mock。
- 连续流按年/月/日分组，支持 sticky label、折叠、向上加载更早、向下加载更新。
- 日历读取后端日期统计；点击深色日期调用日期窗口 API 并跳转。
- “回到此刻”是中央滚动区域右下角圆形按钮。
- 日历跳转和回到此刻有轻量过渡遮罩。
- 窗口裁剪已实现但默认关闭：

```css
--window-trim-enabled: 0;
--window-trim-max-entries: 120;
--window-trim-keep-before: 48;
--window-trim-keep-after: 48;
```

- P5B 正式写作只使用离线 Textarea。
- Textarea 高度调整与页面跟随已分离：`SereinTypingFocus` 在光标首次越过可见视口
  65% 后启用 55%--65% 焦点带，并以 60% 为回落位置。
- 手动滚动会暂停焦点跟随，下一次非输入法组合输入恢复；移动端以
  `visualViewport` 排除软键盘遮挡区域。
- Tiptap demo 只保留在 `mock` 数据源中；backend 模式忽略 Tiptap 偏好，不加载 `esm.sh`。
- 保存成功后：
  - 后端返回的 `EntryDetail` 转为阅读态 sample。
  - 新条目插入当前 latest feed window。
  - 页面滚动到刚保存条目，并短暂淡高亮。
  - 日历日期缓存失效，下次打开日历会重新读取。

新建卡片排序注意点：

- `createdAt` 用于分组语义。
- `sortAt` 用于 feed 排序。
- 新建卡片 `sortAt = "9999-12-31T23:59:59+00:00"`，确保永远在已保存条目之后。

## 诊断工具

浏览器 console 可用：

```js
SereinDebugLoad.dumpReport()
```

用于滚动、分页、窗口状态、保存后插入等排查。报告不包含正文、密码、Cookie、session 或私有路径。

长文写作焦点带排查：

```js
SereinTypingDebug.inspect()
SereinTypingDebug.setEnabled(true)
SereinTypingDebug.dumpReport()
```

报告会记录真实可见视口、焦点带、光标高度、暂停/组合输入状态和最近一次滚动量，
但不会记录日记正文。纯几何决策测试可在装有 Node.js 的环境运行：

```bash
node --test frontend/tests/typing-focus.test.js
```

索引重建排查：

```js
SereinDebugIndex.dumpReport()
```

如果 `POST /entries/rebuild-index` 返回 `405 Method Not Allowed`，通常说明前端已更新但 API 容器仍是旧版本，需要重建 api 容器。

编辑器实验排查：

```js
SereinEditorExperiment.getMode()
SereinEditorExperiment.setTiptapEnabled(false)
```

backend 数据源下强制 Textarea，`setTiptapEnabled(true)` 不会生效。

## 常用验证命令

后端测试：

```bash
cd /home/luessiaw/storage/srv/projects/serein-diary/backend
.venv/bin/python -m unittest discover -s tests
```

当前后端测试为 87 个。

前端 JS 语法检查：

```bash
cd /home/luessiaw/storage/srv/projects/serein-diary
node --check frontend/scripts/api-client.js
node --check frontend/scripts/data-adapter.js
node --check frontend/scripts/mock-entries.js
node --check frontend/scripts/app.js
```

Git 空白检查：

```bash
cd /home/luessiaw/storage/srv/projects/serein-diary
git diff --check
```

Compose 示例更新后端 API：

```bash
cd /home/luessiaw/storage/srv/projects/serein-diary
docker compose up -d --build api
```

如果更新了 `.env` 中的 `DIARY_API_UID` / `DIARY_API_GID`，也需要运行上面的命令。
已有 root-owned 条目不会自动改 owner，需要操作者在宿主机上执行一次 `sudo chown -R`。

前端由 Caddy 挂载 `./frontend`，一般修改前端文件后强制刷新浏览器即可。若 Caddy 状态异常，可由操作者运行：

```bash
cd /home/luessiaw/storage/srv/projects/serein-diary
docker compose up -d web
```

## 最近排查记录

- 重建索引按钮一度返回 `405 Method Not Allowed`。日志显示请求路径正确，原因是运行中的后端未加载新路由；重建 api 容器即可。
- 保存后新日记最初没有立刻可见，原因是保存后滚到了“新建日记”卡片；已改为滚动到刚保存条目。
- 保存后新日记曾排到“新建日记”下方，原因是新建卡片 `draftCreatedAt` 早于后端 `created_at`；已引入 `sortAt` 未来哨兵值修正。
- 移动端 year/month sticky label 曾有层级问题；已将 year label z-index 高于 month label。

## 下一步

推荐顺序：

1. `P5B-T03`：真实写入闭环浏览器验收。
2. 验收重点：
   - 桌面和手机均可保存测试日记。
   - 保存成功后新条目立即出现在“新建日记”上方。
   - 刷新页面后新条目仍存在。
   - 数据目录中生成 `entries/YYYYMMDDHHmm-uuid/metadata.json` 与 `content.md`。
   - 保存失败时不丢标题和正文。
3. 验收通过后进入 `P5C-T01`：已保存日记显示删除入口。

不要先做评论或媒体；当前优先让“真实写入 + 刷新恢复 + 后续删除”主循环稳定。
