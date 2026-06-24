# 部署方式

Serein 不要求使用 Docker 或 Caddy。当前 Compose 文件只是便于开发和自托管的
静态前端示例。

## 方式一：Docker Compose + Caddy

在仓库根目录运行：

```bash
docker compose up -d web
```

该示例仅绑定 `127.0.0.1:8088`。在宿主机打开 `http://127.0.0.1:8088`；它只
发布 `frontend/`，不包含 API、认证、数据卷，也不依赖服务器范围的 Caddy 实例。

## 方式二：任意静态服务器

`frontend/` 是原生 HTML、CSS 与 JavaScript。无需 Docker，即可通过已有的
Nginx、Caddy、Apache、开发服务器或静态托管服务发布。当前静态阶段不要求特殊
的服务器重写或代理规则。

## 后续应用部署

P3 会为 Compose 示例增加独立 API 服务及可选的 `/api/v1/*` 反向代理规则。这
仍只是部署便利措施，而不是前端或后端的运行时依赖：运维者可使用其他容器运行时、
进程管理器或已有反向代理。
