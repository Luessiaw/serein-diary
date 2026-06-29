# Serein

Serein 是一款自托管的个人日记应用，名称取自雨后清澈宁静的空气。本仓库独立
于父级服务器运维仓库。

## 视觉原则

- **简约：** 隐藏与当前写作无关的常驻界面，让写作保持在中心。
- **流畅：** 加载与保存不应打断思路或视觉流动。
- **模块化：** 日记数据、布局、前端模块和后端服务保持分离，使数据可迁移、
  界面可调整。

## 边界

- 应用代码、Compose 部署文件、迁移工具和公开文档均位于本仓库。
- 个人日记数据位于仓库外部：通过 `DIARY_DATA_DIR` 指向其宿主目录。
- 应用不得依赖 Portal 路由、`PORTAL_*` 变量或父仓库中的文件。

## 外观

视觉参数集中在 `frontend/styles/tokens.css`。参阅[主题定制](docs/theme-customization.md)，
可在不使用构建工具、也不将呈现与日记数据耦合的前提下调整或分享主题。

## 当前状态

当前已进入 P5A 真实只读接入的浏览器验收：

- `frontend/` 提供连续日记流、极简锁屏、侧边日历、真实日期统计、日期窗口跳转、
  双向滚动加载、回到此刻和阅读窗口裁剪能力。
- `backend/` 提供 FastAPI 应用、`DIARY_*` 配置校验、锁屏认证、v1 日记事实文件读取、
  可重建 SQLite 索引、正式 entries API、日期统计 API 和日期窗口 API。
- `compose.yaml` 与 `deploy/Caddyfile` 提供可选的 Docker Compose + Caddy 示例：
  `web` 发布静态前端，`api` 在内部网络运行，`/api/v1/*` 经 `web` 反向代理。

P5A 仍是只读阶段；真实新建、删除、评论和媒体闭环属于后续 P5B--P5E。
浏览器验收清单见 [P5A 真实只读接入浏览器验收](docs/p5a-readonly-browser-acceptance.md)。

## 后端快速检查

安装后端依赖后，可运行：

```bash
backend/.venv/bin/python -m unittest discover -s backend/tests
```

也可以复制 `.env.example` 为 `.env`，修改管理员密码、session secret 和数据目录后
使用 Compose 示例：

```bash
docker compose up -d --build
```

然后检查：

```text
http://127.0.0.1:8088
http://127.0.0.1:8088/api/v1/health
```
