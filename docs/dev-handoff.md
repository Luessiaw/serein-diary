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
- P5A 已完成到 `P5A-T03B`：
  - 连续流可读取后端真实 entries。
  - 日历可读取后端日期统计。
  - 点击日历深色日期可请求后端日期窗口 API，并跳转到目标日期附近片段。
  - 前端阅读流已引入 `latest` / `window` 两种模式。
- `P5A-T03C` 窗口裁剪与内存控制尚未实现。
- `P5A-T04` 浏览器综合验收尚未完成。
- P5B 真实写入闭环尚未开始。

## 重要协作规则

- 不要在聊天中打印真实日记正文、完整条目内容、密钥、Cookie、session、私有路径细节。
- 可以打印数量、布尔值、接口状态、错误码、排序检查结果等安全摘要。
- 后端/前端联调时，可以加入小范围、可开关的 console debug，但不要打印正文或秘密。
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
- `GET /api/v1/entries?before=...`
- `GET /api/v1/entries?after=...`
- `GET /api/v1/entries/window?date=YYYY-MM-DD&before_count=N&after_count=N`
- `GET /api/v1/entries/dates?from=YYYY-MM-DD&to=YYYY-MM-DD`

`before` 用于加载更早内容，`after` 用于窗口模式中加载更晚内容。`before` 与 `after`
不可同时传。

## P5A-T03B 详细交接：前端阅读流 latest/window 两种模式

### 为什么引入两种模式

原来的阅读流只有“从最近日记开始，向上加载更早内容”的逻辑。日历跳转引入后，如果用户点击
一个很早的日期，不能从当前最新日记一路向上分页到目标日期，否则会很慢、占内存，也会让交互
显得笨重。

因此当前前端阅读流有两种模式：

- `latest`：默认模式，打开页面后读取最近若干篇，并滚动到末尾的“此刻”新建区。
- `window`：日历跳转模式，只加载某个目标日期附近的片段，替换当前阅读窗口，并滚动到目标日期。

### 核心状态

主要状态在 `frontend/scripts/app.js` 中。

`feedState` 表示当前阅读流内容和模式：

```js
const feedState = {
  mode: "latest",
  samples: [],
  targetDate: null,
};
```

约定：

- `mode === "latest"`：
  - 表示正常首页阅读流。
  - 读取最近 N 篇真实条目。
  - 渲染“此刻”新建区。
  - 打开后应滚动到新建区。
- `mode === "window"`：
  - 表示日历跳转后的日期窗口。
  - `samples` 是目标日期附近的有限条目片段。
  - `targetDate` 是 `YYYY-MM-DD`。
  - 不渲染“此刻”新建区。
  - 页面顶部显示窗口模式提示和“回到此刻”按钮。

`loadState` 管理分页状态，既服务于 latest，也服务于 window：

```js
const loadState = {
  status: "idle",
  nextBefore: null,
  laterStatus: "idle",
  nextAfter: null,
  ...
};
```

约定：

- `status` / `nextBefore`：向上加载更早内容。
- `laterStatus` / `nextAfter`：窗口模式下向下加载更晚内容。
- `latest` 模式通常只使用 `before` 方向。
- `window` 模式同时可能使用 `before` 和 `after` 方向。

### latest 模式的数据流

默认启动后：

1. 前端完成锁屏 session 检查。
2. 调用 `loadInitialBackendEntries()`。
3. 通过 `dataAdapter.listEntries({ limit })` 请求后端最近 N 篇。
4. 后端返回最近 N 篇，但 `items` 内部仍按 `created_at` 正序排列。
5. 前端把 summaries 转为可渲染 sample。
6. 设置：

   ```js
   feedState.mode = "latest";
   feedState.targetDate = null;
   feedState.samples = samples;
   loadState.nextBefore = page.page.next_before;
   loadState.status = page.page.has_more ? "idle" : "complete";
   ```

7. `renderFeed()` 渲染连续流，并保留末尾“此刻”新建区。

latest 模式的继续加载：

- 用户向上接近顶部时，调用 `loadEarlierEntries()`。
- backend 模式下进入 `loadEarlierBackendEntries()`。
- 使用 `loadState.nextBefore` 请求：

  ```js
  dataAdapter.listEntries({
    limit: settings.pageSize,
    before: loadState.nextBefore,
  })
  ```

- 新条目插入 `feedState.samples` 前方。
- 通过锚点计算保持视觉位置，避免加载完成后跳动。
- 后端表示没有更早内容时，顶部显示“已加载所有日记内容”。

### window 模式的数据流

日历点击深色日期时进入：

```js
jumpToCalendarDate(date)
```

核心流程：

1. 校验 `date` 是 `YYYY-MM-DD`。
2. 立即将阅读流切到窗口意图：

   ```js
   feedState.mode = "window";
   feedState.targetDate = targetDate;
   ```

3. 读取 tokens 中的窗口参数：

   - `--jump-before-count`
   - `--jump-after-count`
   - `--jump-target-scroll-offset`

4. 调用：

   ```js
   dataAdapter.getEntryWindow({
     date: targetDate,
     beforeCount: settings.jumpBeforeCount,
     afterCount: settings.jumpAfterCount,
   })
   ```

5. 后端返回：

   ```json
   {
     "items": [],
     "window": {
       "target_date": "YYYY-MM-DD",
       "before_count": 12,
       "after_count": 12,
       "target_count": 1,
       "has_earlier": true,
       "has_later": true,
       "earlier_before": "...",
       "later_after": "..."
     }
   }
   ```

6. 前端将 `items` 转成可渲染 sample，并替换当前窗口：

   ```js
   feedState.mode = "window";
   feedState.targetDate = targetDate;
   feedState.samples = samples;
   ```

7. 同步双向游标：

   ```js
   loadState.status = windowInfo.has_earlier ? "idle" : "complete";
   loadState.nextBefore = windowInfo.earlier_before || null;

   loadState.laterStatus = windowInfo.has_later ? "idle" : "complete";
   loadState.nextAfter = windowInfo.later_after || null;
   ```

8. `renderFeed({ scrollToDate: targetDate })` 渲染窗口片段，并滚动到目标日期第一篇日记。

window 模式下的渲染差异：

- 不显示“此刻”新建区。
- 顶部显示窗口模式提示：
  - 正在查看某日期附近的日记。
  - 提供“回到此刻”按钮。
- 年/月/日分组逻辑仍复用同一套 `created_at` 分组。
- 年/月折叠状态仍按 key 恢复。

### window 模式的双向加载

向上加载更早内容：

- 与 latest 类似，仍走 `loadEarlierEntries()`。
- 使用 `loadState.nextBefore`。
- 请求 `/entries?before=...`。
- 新条目插入当前 `feedState.samples` 前方。

向下加载更晚内容：

- 只在 `feedState.mode === "window"` 时启用。
- 用户接近当前窗口底部时调用 `loadLaterEntries()`。
- 使用 `loadState.nextAfter` 请求：

  ```js
  dataAdapter.listEntries({
    limit: settings.pageSize,
    after: loadState.nextAfter,
  })
  ```

- 新条目追加到 `feedState.samples` 后方。
- 如果 `page.page.has_more` 为 false，则 `laterStatus = "complete"`。

注意：latest 模式底部是“此刻”写作区，不应触发向下加载更晚内容。

### 回到此刻

窗口模式提示中的“回到此刻”调用：

```js
returnToLatestFeed()
```

它会：

1. 重置窗口模式。
2. 重新请求最近 N 篇。
3. 渲染 latest 模式。
4. 滚动到新建区。

后续如果要做浏览器历史、返回键或 URL 状态，可以把这个模式切换抽象成更明确的
`setFeedMode()` / `loadFeedWindow()` 控制层。

### P5A-T03B 涉及的主要文件

前端：

- `frontend/scripts/app.js`
  - `feedState.mode`
  - `jumpToCalendarDate()`
  - `returnToLatestFeed()`
  - `loadEarlierEntries()`
  - `loadLaterEntries()`
  - `renderFeed()`
  - 日历点击事件
- `frontend/scripts/data-adapter.js`
  - `listEntries({ before, after })`
  - `getEntryWindow({ date, beforeCount, afterCount })`
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
  - `GET /api/v1/entries` 支持 `after`
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

`P5A-T03B` 已能工作，但它是从现有静态滚动逻辑演进来的，因此有几个地方未来适合整理：

1. latest/window 模式逻辑仍散落在 `app.js` 多个函数中。
   - 后续可抽出 `FeedController` 或至少集中成一组函数。
   - 建议先不要引入框架，继续保持原生 JS，但把状态转换写清楚。

2. `loadState` 同时管理上下方向、mock/backend、latest/window，职责偏多。
   - 后续可拆成：
     - `earlierPagination`
     - `laterPagination`
     - `initialLoad`
     - `windowJump`

3. window 模式尚未做 DOM 裁剪。
   - `P5A-T03C` 负责解决窗口过长时内存和 DOM 节点过多的问题。
   - 默认可以先关闭裁剪，只保留参数和结构。

4. 日历跳转目前只保留在内存状态中。
   - 后续如需刷新后保持目标日期，可考虑 URL query/hash。
   - 但这会影响锁屏、隐私和分享语义，需单独设计。

5. 新建区只在 latest 模式显示。
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
  - 点击深色日期进入 window 模式并跳转。
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

下一步建议先做 `P5A-T04`，不要急着进入 P5B 写入。原因是 latest/window 阅读流刚变复杂，
应先让用户在浏览器中确认可理解、可控、不卡顿。

建议验收路径：

1. 无痕窗口打开 `/diary/`，确认锁屏出现。
2. 登录后确认默认进入 latest 模式，并定位到“此刻”附近。
3. 向上滚动，确认能加载更早日记，且视觉位置不跳。
4. 打开侧边卡片的日历页。
5. 确认有日记日期变深色。
6. 点击一个较早日期，确认快速跳转到该日期附近，不需要一路向上加载。
7. 在 window 模式中：
   - 向上滚动可继续加载更早内容。
   - 向下滚动可继续加载更晚内容。
   - 不显示“此刻”新建区。
   - “回到此刻”能回到 latest 模式。
8. 在手机窄屏下重复 4--7。

如果验收中出现问题，优先处理 P5A-T03B 的状态/滚动/模式问题，再进入 P5B。

## 下一步建议

推荐顺序：

1. `P5A-T04`：真实只读接入浏览器验收。
2. 视验收结果，修正 latest/window 阅读流问题。
3. 如果窗口模式在真实数据中条目过多，再进入 `P5A-T03C` 做窗口裁剪。
4. 进入 `P5B-T01`：新建日记保存到后端。

不建议下一步立刻做评论或媒体。当前最重要的是让“真实数据阅读 + 日期跳转 + 回到此刻”这个主循环稳定。


