# Serein 开发交接文档

本文用于在新对话中接续 Serein Diary 开发。新对话开始时，建议先阅读：

1. `AGENTS.md`
2. `tasks.csv`
3. `docs/plan-v1.1.md`
4. `docs/data-contract-v1.md`
5. `docs/p5-api-frontend-contract.md`
6. 本文档

## 当前项目状态

Serein 已从 Portal 原型迁移为独立仓库：

```text
/home/luessiaw/storage/srv/serein-diary
├── backend/        # FastAPI 后端
├── frontend/       # 原生 HTML/CSS/JS 前端
├── deploy/         # Caddy 示例配置
├── docs/           # 设计、契约、交接文档
├── compose.yaml    # 可选 Docker Compose 示例
└── tasks.csv       # 本地任务表，不需要纳入 Git 跟踪
```

真实日记数据不进入仓库，由 `.env` 中的 `DIARY_HOST_DATA_DIR` 映射到容器 `/data`，
后端通过 `DIARY_DATA_DIR=/data` 读取。

目前的功能状态：

- P0--P4 已完成。
- P5P 已完成：后端正式 entries API、日期统计 API、前端 data adapter 已建立。
- P5A 已完成到 `P5A-T03D`：
  - 连续流可读取后端真实 entries。
  - 日历可读取后端日期统计。
  - 点击日历深色日期可请求后端日期窗口 API，并跳转到目标日期附近片段。
  - 前端阅读流已收敛为统一 feed window 状态，并使用 `older_than` / `newer_than` 方向游标。
- 窗口裁剪与内存控制已实现，默认在 `tokens.css` 中关闭。
- `P5A-T04` 浏览器综合验收已进入准备阶段，验收清单见 `docs/p5a-readonly-browser-acceptance.md`。
- P5B 真实写入闭环尚未开始。

## 重要协作规则

- 不要在聊天中打印真实日记正文、完整条目内容、密钥、Cookie、session、私有路径细节。
- 可以打印数量、布尔值、接口状态、错误码、排序检查结果等安全摘要。
- 后端/前端联调时，可以加入小范围、可开关的 console debug，但不要打印正文或秘密。
- 阅读流滚动问题可请助手加入“可复制的前端诊断日志”或“临时 debug probes”。
  浏览器 console 中可运行 `SereinDebugLoad.dumpReport()`，复制输出 JSON 供排查。
- `tasks.csv` 和 `AGENTS.md` 是本地协作文件，不需要 Git 跟踪。
- 用户希望每次修改后给出一行 commit 建议，格式：

  ```bash
  git add . && git commit -m "Add: 中文说明"
  ```

## 数据契约摘要

事实源结构为：

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
- 不再使用 `date`、`updated_at`、`revision`。
- 已保存日记标题和正文不可编辑。
- 日记只允许新增、软删除；评论只允许新增、删除。
- 删除使用 `metadata.deleted_at` 软删除，不物理删除正文。
- SQLite 索引是衍生物，可以删除后从事实文件重建。

## 当前后端能力

主要入口：

```text
GET    /api/v1/health
GET    /api/v1/auth/session
POST   /api/v1/auth/login
POST   /api/v1/auth/logout

GET    /api/v1/entries
GET    /api/v1/entries/window
GET    /api/v1/entries/dates
GET    /api/v1/entries/{entry_id}
POST   /api/v1/entries
DELETE /api/v1/entries/{entry_id}
```

当前 P5A 只读浏览主要依赖：

- `GET /api/v1/entries?limit=...`
- `GET /api/v1/entries?older_than=...`
- `GET /api/v1/entries?newer_than=...`
- `GET /api/v1/entries/window?date=YYYY-MM-DD&older_count=N&newer_count=N`
- `GET /api/v1/entries/dates?from=YYYY-MM-DD&to=YYYY-MM-DD`

`older_than` 用于加载更早内容，`newer_than` 用于加载更新内容。`older_than` 与 `newer_than`
不可同时传。

## P5A-T03C 详细交接：统一阅读窗口模型

P5A-T03C 后，前端不再把阅读流拆成 `latest` / `window` 两套模式，而是统一为一个 feed window：当前页面只持有一段连续的 `entries`，并用窗口两端的方向游标继续向上或向下加载。

### 核心状态

主要状态在 `frontend/scripts/app.js` 中：

```js
const feedState = {
  entries: [],
  olderCursor: null,
  newerCursor: null,
  hasOlder: false,
  hasNewer: false,
  atLatest: true,
  targetDate: null,
};
```

约定：

- `entries`：当前已加载并渲染的一段连续日记，不是全部日记。
- `olderCursor`：当前窗口最早条目的边界游标，用于继续加载更早内容。
- `newerCursor`：当前窗口最新条目的边界游标，用于继续加载更新内容。
- `hasOlder`：顶部是否还能继续向上加载。
- `hasNewer`：底部是否还能继续向下加载。
- `atLatest`：当前窗口是否已经抵达最新日记；为 `true` 时底部显示“此刻”新建区。
- `targetDate`：日历跳转目标日期；不为空时显示“回到此刻”提示。

游标是服务端不透明字符串，当前由 `created_at + id` 编码。前端只保存和回传，不解析。

### 初次进入的数据流

默认启动后：

1. 前端完成锁屏 session 检查。
2. 调用 `initializeBackendLoadedWindow()`。
3. 通过 `dataAdapter.listEntries({ limit })` 请求后端最近 N 篇。
4. 后端返回最近 N 篇，但 `items` 内部仍按 `created_at` 正序排列。
5. 前端把 summaries 转为可渲染 sample。
6. 同步窗口状态：

   ```js
   feedState.entries = samples;
   feedState.olderCursor = page.page.older_cursor;
   feedState.newerCursor = page.page.newer_cursor;
   feedState.hasOlder = page.page.has_older;
   feedState.hasNewer = page.page.has_newer;
   feedState.atLatest = !feedState.hasNewer;
   feedState.targetDate = null;
   ```

7. `renderFeed()` 渲染连续流；当 `atLatest=true` 时保留末尾“此刻”新建区。

### 日历跳转的数据流

日历点击深色日期时进入：

```js
jumpToCalendarDate(date)
```

核心流程：

1. 校验 `date` 是 `YYYY-MM-DD`。
2. 设置 `feedState.targetDate = targetDate`，并临时进入加载状态。
3. 读取 tokens 中的窗口参数：
   - `--jump-before-count`：传给 adapter 时映射为 `olderCount`。
   - `--jump-after-count`：传给 adapter 时映射为 `newerCount`。
   - `--jump-target-scroll-offset`。
4. 调用：

   ```js
   dataAdapter.getEntryWindow({
     date: targetDate,
     olderCount: settings.jumpBeforeCount,
     newerCount: settings.jumpAfterCount,
   })
   ```

5. 后端返回目标日期当天条目及前后窗口：

   ```json
   {
     "items": [],
     "window": {
       "target_date": "YYYY-MM-DD",
       "older_count": 12,
       "newer_count": 12,
       "target_count": 1,
       "has_older": true,
       "has_newer": true,
       "older_cursor": "...",
       "newer_cursor": "..."
     }
   }
   ```

6. 前端将 `items` 转成可渲染 sample，并替换当前窗口：

   ```js
   feedState.entries = samples;
   feedState.hasOlder = windowInfo.has_older;
   feedState.hasNewer = windowInfo.has_newer;
   feedState.olderCursor = windowInfo.older_cursor;
   feedState.newerCursor = windowInfo.newer_cursor;
   feedState.atLatest = !feedState.hasNewer;
   ```

7. `renderFeed({ scrollToDate: targetDate })` 渲染窗口片段，并滚动到目标日期第一篇日记。

### 双向加载

向上加载更早内容：

- 触发 `loadEarlierEntries()`。
- 使用 `feedState.olderCursor`。
- 请求 `/entries?older_than=...`。
- 新条目插入当前 `feedState.entries` 前方。

向下加载更新内容：

- 只在 `feedState.hasNewer=true` 且 `atLatest=false` 时启用。
- 用户接近当前窗口底部时调用 `loadLaterEntries()`。
- 使用 `feedState.newerCursor` 请求：

  ```js
  dataAdapter.listEntries({
    limit: settings.pageSize,
    newerThan: feedState.newerCursor,
  })
  ```

- 新条目追加到 `feedState.entries` 后方。
- 如果 `page.page.has_newer` 为 false，则 `atLatest = true`，底部显示“此刻”新建区。

### 回到此刻

日期窗口提示中的“回到此刻”调用：

```js
returnToLatestFeed()
```

它会：

1. 重置目标日期窗口状态。
2. 重新请求最近 N 篇。
3. 渲染最新窗口。
4. 滚动到新建区。

后续如果要做浏览器历史、返回键或 URL 状态，可以把窗口切换抽象成更明确的
`loadFeedWindow()` 控制层。

### P5A-T03C 涉及的主要文件

前端：

- `frontend/scripts/app.js`
  - `feedState.entries`
  - `feedState.olderCursor` / `feedState.newerCursor`
  - `feedState.hasOlder` / `feedState.hasNewer`
  - `feedState.atLatest`
  - `jumpToCalendarDate()`
  - `returnToLatestFeed()`
  - `loadEarlierEntries()`
  - `loadLaterEntries()`
  - `renderFeed()`
  - 日历点击事件
- `frontend/scripts/data-adapter.js`
  - `listEntries({ olderThan, newerThan })`
  - `getEntryWindow({ date, olderCount, newerCount })`
- `frontend/styles/tokens.css`
  - `--jump-before-count`
  - `--jump-after-count`
  - `--jump-target-scroll-offset`
  - `--load-later-trigger-distance`
- `frontend/styles/base.css`
  - 窗口提示、回到此刻按钮、加载状态相关样式

后端：

- `backend/serein/api/entries.py`
  - `GET /api/v1/entries/window`
  - `GET /api/v1/entries` 支持 `newer_than`
- `backend/serein/services/entries.py`
  - `EntryService.list_entries()`
  - `EntryService.get_entry_window()`
  - 游标编码/解析
- `backend/tests/test_entries_api.py`
- `backend/tests/test_entry_service.py`

文档：

- `docs/p5-api-frontend-contract.md`
- `tasks.csv`

### 当前实现的设计风险与后续修改建议

`P5A-T03C` 已收敛状态模型，但它仍是从现有静态滚动逻辑演进来的，因此有几个地方未来适合整理：

1. 窗口状态转换仍散落在 `app.js` 多个函数中。
   - 后续可抽出 `FeedController` 或至少集中成一组函数。
   - 建议先不要引入框架，继续保持原生 JS，但把状态转换写清楚。

2. `loadState` 仍管理上下方向、mock/backend 和加载状态，职责偏多。
   - 后续可拆成：
     - `earlierPagination`
     - `laterPagination`
     - `initialLoad`
     - `windowJump`

3. 阅读窗口已具备 DOM 裁剪能力。
   - `P5A-T03D` 已围绕当前视线锚点实现窗口裁剪。
   - 默认在 `frontend/styles/tokens.css` 中关闭，真实长窗口使用确认需要后可启用。

4. 日历跳转目前只保留在内存状态中。
   - 后续如需刷新后保持目标日期，可考虑 URL query/hash。
   - 但这会影响锁屏、隐私和分享语义，需单独设计。

5. 新建区只在 `atLatest=true` 时显示。
   - 这是当前有意设计：点击日记页面默认写“此刻”；查看历史窗口时不混入新建区。
   - 如果用户希望在历史窗口也能快速回到写作，应通过“回到此刻”解决。

## 当前前端能力

- 锁屏认证接入后端。
- 已认证后渲染连续日记流。
- 支持年/月分组、折叠状态保持、sticky 标签。
- 支持布局调试开关。
- 支持 Tiptap 静态 demo 开关。
- 支持侧边卡片：
  - 日历
  - 统计占位
  - 设置
- 日历：
  - 读取后端日期统计。
  - 有日记日期显示深色。
  - 点击深色日期进入目标日期窗口并跳转。
- 阅读态 Markdown 使用轻量内置 renderer，不是完整 CommonMark。
- 新建区目前还未正式写入后端；P5B 才开始真实写作闭环。

## 常用验证命令

后端测试：

```bash
cd /home/luessiaw/storage/srv/serein-diary
backend/.venv/bin/python -m unittest discover -s backend/tests
```

前端 JS 语法检查。用户已安装 Node.js 后可执行：

```bash
cd /home/luessiaw/storage/srv/serein-diary
node --check frontend/scripts/api-client.js
node --check frontend/scripts/data-adapter.js
node --check frontend/scripts/mock-entries.js
node --check frontend/scripts/app.js
```

Git 空白检查：

```bash
cd /home/luessiaw/storage/srv/serein-diary
git diff --check
```

重建 API 容器：

```bash
cd /home/luessiaw/storage/srv/serein-diary
docker compose up -d --build api
```

前端由 Compose 中的 Caddy 将 `./frontend` 只读挂载到 `/srv`，通常修改前端文件后无需重建镜像，
浏览器强制刷新即可。若 Caddy 配置或容器状态异常，可重启 web：

```bash
cd /home/luessiaw/storage/srv/serein-diary
docker compose up -d web
```

## 浏览器验收建议

当前已进入 `P5A-T04`，不要急着进入 P5B 写入。原因是统一阅读窗口和窗口裁剪刚调整完成，
应先让用户在浏览器中确认真实只读主循环可理解、可控、不卡顿。

完整清单见：

```text
docs/p5a-readonly-browser-acceptance.md
```

建议验收路径：

1. 无痕窗口打开 `/diary/`，确认锁屏出现。
2. 登录后确认默认进入最新窗口，并定位到“此刻”附近。
3. 向上滚动，确认能加载更早日记，且视觉位置不跳。
4. 打开侧边卡片的日历页。
5. 确认有日记日期变深色。
6. 点击一个较早日期，确认快速跳转到该日期附近，不需要一路向上加载。
7. 在目标日期窗口中：
   - 向上滚动可继续加载更早内容。
   - 向下滚动可继续加载更新内容。
   - 未抵达最新日记前不显示“此刻”新建区。
   - “回到此刻”能回到最新窗口。
8. 在手机窄屏下重复 4--7。

如果验收中出现问题，优先处理 P5A-T03C 的状态/滚动/游标问题，再进入 P5B。

## 下一步建议

推荐顺序：

1. 完成 `P5A-T04`：真实只读接入浏览器验收。
2. 视验收结果，修正统一阅读窗口、裁剪或视觉过渡问题。
3. 进入 `P5B-T00`：收敛正式新建编辑器为离线 Textarea。
4. 进入 `P5B-T01`：新建日记保存到后端。

不建议下一步立刻做评论或媒体。当前最重要的是让“真实数据阅读 + 日期跳转 + 回到此刻”这个主循环稳定。
