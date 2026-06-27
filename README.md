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

当前已完成 P3 的独立应用基础：

- `frontend/` 提供静态连续日记流原型、设置卡片、日历占位和 Tiptap/Markdown
  前端实验，并已接入极简锁屏流程。
- `backend/` 提供 FastAPI 外壳、`DIARY_*` 配置校验、健康检查、极简锁屏认证和
  一个受保护 API 骨架。
- `compose.yaml` 与 `deploy/Caddyfile` 提供可选的 Docker Compose + Caddy 示例：
  `web` 发布静态前端，`api` 在内部网络运行，`/api/v1/*` 经 `web` 反向代理。

P3 仍不读取或写入真实日记。锁屏只决定是否显示前端日记界面；条目存储、可重建
索引、迁移 dry-run 和正式写作 API 属于 P4/P5。

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
