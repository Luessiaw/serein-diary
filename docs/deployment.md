# 部署方式

Serein 不要求使用 Docker 或 Caddy。当前 Compose 文件只是便于开发和自托管的
示例部署：`web` 发布静态前端，`api` 运行 FastAPI，Caddy 将 `/api/v1/*`
反向代理到 API。

## 方式一：Docker Compose + Caddy

在仓库根目录运行：

```bash
cp .env.example .env
# 然后编辑 .env，至少修改 DIARY_ADMIN_PASSWORD、DIARY_SESSION_SECRET
docker compose up -d --build
```

Compose 会自动读取同目录下的 `.env`。如果没有 `.env`，配置仍可解析，但 API 会因
默认密码或默认 session secret 不安全而拒绝启动；这是预期的安全保护。

该示例仅将 `web` 绑定到 `127.0.0.1:8088`。在宿主机打开
`http://127.0.0.1:8088` 可访问静态前端；访问
`http://127.0.0.1:8088/api/v1/health` 可验证 API 代理。`api` 服务只在
Compose 内部网络中暴露，不直接绑定宿主机端口。

前端默认通过同源 `/api/v1` 访问后端，并在启动时请求
`GET /api/v1/auth/session`。如果部署到子路径，可修改
`frontend/index.html` 中的：

```html
<meta name="serein-api-base" content="/api/v1">
```

例如挂载到 `/diary/` 且后端代理为 `/diary/api/v1` 时，可改为
`content="/diary/api/v1"`。

Compose 会把 `.env` 中的 `DIARY_HOST_DATA_DIR` 挂载为容器内的 `/data`，并让
API 使用 `DIARY_DATA_DIR=/data`。快速本机测试可以使用默认的 `./data`；真实
部署时建议将 `DIARY_HOST_DATA_DIR` 指向仓库外的数据目录，例如：

```env
DIARY_HOST_DATA_DIR=/home/you/storage/data/diary
```

P3 阶段 API 只提供健康检查、锁屏认证和受保护接口骨架，不读取或写入真实日记。

可用下面的命令查看服务状态或停止示例部署：

```bash
docker compose ps
docker compose down
```

## 方式二：任意静态服务器

`frontend/` 是原生 HTML、CSS 与 JavaScript。无需 Docker，即可通过已有的
Nginx、Caddy、Apache、开发服务器或静态托管服务发布。进入 P3 后，如果希望
同时使用后端 API，需要让反向代理保留 `/api/v1/*` 路径并转发到 FastAPI 服务。

### 本机 Portal 集成

在 luessiaw-server 上，Serein 现阶段作为静态前端挂载到 Portal 的 `/diary/`
路径。父级运维仓库的脚本会在检测到
`/home/luessiaw/storage/srv/serein-diary/frontend` 时，将其同步到
`/var/www/luessiaw-portal/diary/`：

```bash
sudo /home/luessiaw/storage/srv/scripts/portal/deploy_portal.sh
```

这是本机运维集成，不是 Serein 对 Portal 的运行时依赖。公开发布给其他用户时，
他们仍可选择任意静态服务器、Docker Compose 或自己的反向代理路径。

## 应用部署边界

Compose/Caddy 仍只是部署便利措施，而不是前端或后端的运行时依赖：运维者可使用
其他容器运行时、进程管理器或已有反向代理。关键边界只有两条：

- 静态前端需要能访问同源的 `/api/v1/*`。
- FastAPI 需要收到有效的 `DIARY_*` 环境变量，并能访问外部数据目录。
