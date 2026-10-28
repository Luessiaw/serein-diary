# “Notion 本地部署”方案调研

- 调研日期：2026-10-28
- 调研动机：Serein 的视觉/交互动机部分来自 Notion，但 Notion 必须连外网（不稳定、
  限速）、数据不在本地，且其若干设计取向与 Serein 的“简约 / 流畅 / 模块化”原则相悖。
- 调研问题：**是否存在可自托管、可离线、数据在本地、且风格接近 Notion 的现成方案？**
- 本文只做选型结论，不改变 Serein 的技术路线。

## 0. 结论先行

1. **Notion 没有官方自托管版本**，也不存在“把 Notion 搬到本地”的合法途径。所有候选
   都是第三方重写 Notion 的部分能力。
2. 候选可分成三个族：**块编辑器工作区**（AFFiNE、AppFlowy、SiYuan）、**团队 wiki**
   （Docmost、Outline、BookStack）、**纯 Markdown 本地应用**（Obsidian、TriliumNext）。
3. 2026 年的关键变化：**AppFlowy 自托管已不再开源**（`AppFlowy-Cloud` 于 2026-09-11
   归档，自托管改由商业许可的 `AppFlowy-SelfHost-Commercial` 承载，免费档 1 个
   用户席位）；AFFiNE 自托管仍免费但**默认限制 10 个席位**；Docmost 等为 open-core
   （AGPL 核心 + 付费 Business/Enterprise）。
4. **对本项目的判断：没有任何一个候选能当 Serein 的替代品，但 AFFiNE 与 Docmost
   值得在 2 GB 以内的隔离环境里各跑一次**，目的不是替换，而是把“想要的 Notion 手感”
   具体化。Serein 的主线仍是自建：`content.md` 语义 Markdown 是事实，编辑器/索引是可
   重建派生物。
5. **Serein 可以合法直接复用的唯一“Notion 本体”是编辑器框架**：Tiptap OSS 为 MIT，
   BlockNote 亦为开源块编辑器。借鉴 Notion 的交互不需要许可，也不需要引入其数据模型。

## 1. 候选对比

### 1.1 块编辑器工作区（最接近 Notion 手感）

| 项目 | 形态 | 许可 / 商业模式 | 自托管栈 | 数据落点 | 与 Serein 原则的冲突 |
|---|---|---|---|---|---|
| **AFFiNE** | 文档 + 无限白板同源（BlockSuite） | 开源（AGPL 系），自托管免费，**默认 10 席位**，超出需 Team 许可 | 4 容器：app、一次性迁移 job、`pgvector/pgvector:pg16`、Redis；官方要求 ≥4 核 / 2 GB，长文 ≥4 GB | Postgres + blob 目录（bind mount） | 数据是 Postgres 行 + 二进制快照，**不是人可读的 Markdown 文件**；同步系统重，合并长文可峰值 ~1 GB |
| **AppFlowy** | Notion 数据模型（页面/网格/看板/日历） | **自托管已非开源**：`AppFlowy-Cloud` 2026-09-11 归档，现由 `AppFlowy-SelfHost-Commercial` 承载，商业许可，免费档 1 席位 + 3 访客 | ~11 容器：nginx、Postgres+pgvector、Redis、MinIO、GoTrue、cloud、worker、search、admin、web、ai | Postgres + MinIO | 许可与“自主可控”原则直接冲突；体量最大；厂商 README 与许可文本对免费档表述不一致 |
| **SiYuan 思源** | 块级引用 + Markdown 所见即所得，本地优先 | 开源 | **单容器** `b3log/siyuan`，6806 端口，挂一个 workspace 目录 | 宿主机 workspace 内的 Markdown/JSON 文件 | 风格是“中文知识管理”而非 Notion 的克制留白；Docker 模式下仅浏览器（不支持官方客户端连自建、不支持 PDF/HTML/Word 导出、不支持导入 Markdown，以官方限制说明为准） |

### 1.2 团队 wiki（文档优先，没有数据库视图）

| 项目 | 许可 | 自托管栈 | 认证 | 备注 |
|---|---|---|---|---|
| **Docmost** | AGPL-3.0 核心；Business / Enterprise 付费（Bases、SSO、AI、审计等） | 3 容器：app、Postgres、Redis；WebSocket 必需 | **内置邮箱 + 密码** | 上手最快；后端 Go、前端 TS；没有 Notion 的数据库/多视图概念 |
| **Outline** | BSL/企业版 | 3 容器：app、Postgres、Redis | **没有本地账号密码登录**，必须接 Google/Microsoft/Slack/OIDC 之一 | 写作与搜索体验最好的一档，但单人要额外自建一个 IdP |
| **BookStack** | MIT | app + MySQL/MariaDB（无官方镜像，惯例用 linuxserver 社区镜像） | 本地账号 | 固定层级 shelf/book/chapter/page，不是 Notion 形态 |

### 1.3 纯 Markdown 本地应用（“本地优先”最彻底）

- **Obsidian**：本地 Markdown 文件夹，无服务器；同步可自选官方付费服务、CouchDB
  LiveSync、Syncthing 或 WebDAV；**没有实时多人协作**；Bases 提供表/看板视图。商业
  软件但文件格式开放。
- **TriliumNext**（Trilium 的社区续作）：单实例、层级笔记，自托管轻量，但不是
  块式 Notion 手感。

### 1.4 编辑器框架（可直接用于 Serein）

- **Tiptap OSS Editor**：MIT，headless，React/Vue/Svelte 均可；官方把协作核心
  Hocuspocus 也以 MIT 开源，商业部分是托管的 AI/协作/排版平台。
- **BlockNote**：开源块式编辑器（React），开箱即是“Notion 的块手感”。

## 2. 与 Serein 原则的对照

| 原则 | AFFiNE / AppFlowy | SiYuan | Docmost / Outline | 结论 |
|---|---|---|---|---|
| **简约** | 块 + 数据库 + 白板/多视图，能力必然外溢成常驻 UI | 功能密度高 | 侧栏 + 空间层级常驻 | 都偏离“只留写作”
| **流畅** | 同步/合并是重心，弱网与长文是性能天花板 | 单进程，轻 | 需要 WebSocket | Serein 的“本地读写 + 可重建索引”更稳 |
| **模块化** | 数据是数据库中的私有结构快照 | 文件可读但结构私有 | 数据库内容，导出是二次加工的 Markdown | **只有 Serein 的 `content.md` 是事实、索引可重建这一条是真正满足的** |

关键差异点：候选方案都把“数据库/工作区”作为核心抽象，而 Serein 把**一篇连续长文 +
时间轴**作为核心抽象。Notion 值得借鉴的是**块级编辑的交互细节与悬停操作**，而不是它的
页面树与数据库视图——后者正是与“简约”相悖的部分。

## 3. 建议

1. **不做替换。** 上表的候选都不能承载 Serein 的数据契约，替换会把“语义 Markdown
   是事实”这条底线交出去。
2. **做一次对照实验（可选）**：在隔离目录、`127.0.0.1` 绑定、2 GB 内存上限下运行
   Docmost（3 容器，最快）与 AFFiNE（4 容器，最像 Notion），各花半天记录
   “哪些交互想搬进 Serein”。实验产物只进 `docs/reference-shots/`，不进入运行时。
   - AFFiNE 首次 `/admin` 注册即成为管理员，**必须先绑定 loopback 再注册**；自托管
     文档的 Compose 默认把 3010 绑到所有网卡。
   - 两家都依赖 WebSocket，反向代理必须透传 upgrade，否则编辑静默不同步。
3. **把“Notion 手感”限定在编辑器层**：继续走 `docs/tiptap-experiment.md` 的 Tiptap
   路线（MIT），块级 hover 工具、slash 命令、块拖拽这三项是最值得复刻的交互；页面树、
   数据库视图、工作区协作不引入。
4. **顺带固定一条测试基线**：若将来接受外部导入，AFFiNE 的 `.affine`/Markdown 导出与
   SiYuan 的 `.sy` 导出应各写一个只读适配器评审，而不是把它们的结构变成 Serein 的存储。

## 4. 资料来源

- AFFiNE 自托管文档（安装、要求、席位）：[overview](https://docs.affine.pro/self-host-affine/)、
  [requirements](https://docs.affine.pro/self-host-affine/install/requirements)、
  [docker compose](https://docs.affine.pro/self-host-affine/install/docker-compose-recommended)、
  [basic user quota](https://docs.affine.pro/self-host-affine/features/basic-user-quota)
- Docmost：[installation](https://docmost.com/docs/installation)、[editions](https://docmost.com/docs/editions)
- AppFlowy 自托管现状：[自托管 AppFlowy 指南（含商业许可与单席位说明）](https://www.ssdnodes.com/learn/self-host-appflowy-on-a-vps)
- 横向对比：[自托管 Notion 替代方案对比](https://www.ssdnodes.com/learn/self-hosted-notion-alternatives)、
  [AFFiNE 部署要点](https://www.ssdnodes.com/learn/self-host-affine-notion-alternative)
- SiYuan 容器化：[Docker 伺服（官方社区文档）](https://pipe.b3log.org/blogs/onemo/articles/2025/04/04/1743759683595)
- Tiptap 许可：[Tiptap OSS](https://tiptap.dev/open-source-to-platform)

> 未能取得第一手证据的部分：GitHub 仓库页（`github.com`、`raw.githubusercontent.com`）
> 在本机网络下不可达，AppFlowy 官方定价页返回 Cloudflare 403。因此 AppFlowy 的许可
> 细节与免费档席位来自第三方指南的转述，若真要采用需自行核对仓库内的
> `SELF_HOST_LICENSE_AGREEMENT.md`。
