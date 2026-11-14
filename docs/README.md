# serein-diary 文档索引

Serein：独立、自托管的极简连续日记流应用（桌面与手机浏览器）。项目边界与约定在
`../AGENTS.md`；阶段状态在 `../tasks.csv`（本目录下的 `tasks.csv` 是早期分册）。

> ⚠ 本目录文件名风格**不统一**：`plan-v1.1.md`、`data-contract-v1.md` 等是长期有效的
> 设计文档；`p4-*`、`p5-*`、`01_*`、`02_*` 是按阶段产出的过程文档，其中一部分已被
> 后续阶段取代。请按下表的分组进入。

## 1. 架构与契约（权威，先读）

| 文档 | 内容 | 权威性 |
|---|---|---|
| [`plan-v1.1.md`](plan-v1.1.md) | 整体架构方案 v1.1 | 架构权威 |
| [`data-contract-v1.md`](data-contract-v1.md) | 数据契约 v1：P4 存储层的实现依据 | **权威** |
| [`backend-boundary.md`](backend-boundary.md) | P3 最小后端边界：从纯静态原型到"有后端外壳" | 权威 |
| [`p5-api-frontend-contract.md`](p5-api-frontend-contract.md) | P5 冻结的最小正式 API 契约 | **权威（当前 API）** |
| [`ai-writer.md`](ai-writer.md) | AI 写入接口：token 机制与由对话整理生成日记的边界 | 权威 |
| [`immich-integration.md`](immich-integration.md) | Immich 选片集成 | 权威 |
| [`moments-redesign-v2.md`](moments-redesign-v2.md) | 朋友圈式图文日记与 v2 可编辑契约 | 权威 |

## 2. 前端与视觉

| 文档 | 内容 |
|---|---|
| [`layout.md`](layout.md) | 静态前端的 HTML 嵌套结构，调整视觉对齐时优先改哪些位置 |
| [`theme-customization.md`](theme-customization.md) | 视觉参数在哪里集中 |
| [`visual-references.md`](visual-references.md) | 视觉与交互外部调研 |
| [`reference-shots/`](reference-shots/) | 调研用的参考截图（48 MB，非文档正文） |
| [`reference-gallery.html`](reference-gallery.html) | 参考册页面，与 `visual-references.md` 配套 |

## 3. 部署与迁移

| 文档 | 内容 | 备注 |
|---|---|---|
| [`deployment.md`](deployment.md) | 部署方式（Compose + Caddy 示例） | 手册 |
| [`migration.md`](migration.md) | 从 Portal Diary 原型迁移到 Serein 的约束 | 手册 |
| [`01_migration-inventory.md`](01_migration-inventory.md) / [`02_runtime-acceptance.md`](02_runtime-acceptance.md) | 目录迁移的盘点与运行时验收 | 冻结 |

## 4. 阶段过程文档（历史，按需查阅）

| 文档 | 内容 | 状态 |
|---|---|---|
| [`dev-handoff.md`](dev-handoff.md) | 2026-07-01 的开发交接 | 历史，结论多已过时 |
| [`notion-alternatives-research.md`](notion-alternatives-research.md) | "Notion 本地部署"方案调研（2026-10-28） | 调研结论 |
| [`tiptap-experiment.md`](tiptap-experiment.md) | Tiptap 静态实验 | 实验记录 |
| [`p4-entries-api-test.md`](p4-entries-api-test.md) | P4 最小 entries API 手动验证 | **已被 P5 取代**，见 `p5-entries-api-test.md` |
| [`p4-storage-handoff.md`](p4-storage-handoff.md) | P4 存储层测试与 P5 交接 | 历史交接 |
| [`p5-entries-api-test.md`](p5-entries-api-test.md) | P5 正式 entries API 手动验证 | 当前验证口径 |
| [`p5-frontend-adapter.md`](p5-frontend-adapter.md) | P5 前端统一数据适配层 | 实现记录 |
| [`p5a-readonly-browser-acceptance.md`](p5a-readonly-browser-acceptance.md) | P5A 真实只读接入的浏览器验收 | 验收脚本 |

## 5. 阅读顺序

1. 改后端或数据：`plan-v1.1.md` → `data-contract-v1.md` → `p5-api-frontend-contract.md`。
2. 改前端视觉：`layout.md` → `theme-customization.md`。
3. 新会话接续开发：**不要**从 `dev-handoff.md` 开始，先读 `../AGENTS.md` 与 `../tasks.csv`。

## 6. 维护规则

- 契约类文档（§1）只有一份，持续更新；如果要改契约，在原文档更新版本号，不要新开文件。
- 阶段过程文档冻结，被取代时在文首加一行指针。
