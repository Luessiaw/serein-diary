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

### 受限网络下构建

若服务器 Docker daemon 通过本机反向代理访问网络，可在保持该隧道在线时构建。Compose
默认将构建阶段使用 `http://127.0.0.1:17897`，并采用 host build network，使构建容器
能访问宿主机代理；如代理地址不同，可通过 `DIARY_BUILD_HTTP_PROXY`、
`DIARY_BUILD_HTTPS_PROXY` 和 `DIARY_BUILD_NO_PROXY` 覆盖。代理地址不写入镜像。

该示例仅将 `web` 绑定到 `127.0.0.1:8088`。在宿主机打开
`http://127.0.0.1:8088` 可访问静态前端；访问
`http://127.0.0.1:8088/api/v1/health` 可验证 API 代理。`api` 服务只在
Compose 内部网络中暴露，不直接绑定宿主机端口。

前端默认通过相对路径 `api/v1` 访问后端，并在启动时请求
`GET /api/v1/auth/session`。如果部署到子路径，可修改
`frontend/index.html` 中的：

```html
<meta name="serein-api-base" content="api/v1">
```

相对路径的好处是：部署在站点根目录时会请求 `/api/v1/...`；部署在 `/diary/`
时会请求 `/diary/api/v1/...`。如果你的反向代理使用了完全不同的 API 路径，也可
将它改成绝对路径，例如 `content="/api/v1"`。

Compose 会把 `.env` 中的 `DIARY_HOST_DATA_DIR` 挂载为容器内的 `/data`，并让
API 使用 `DIARY_DATA_DIR=/data`。快速本机测试可以使用默认的 `./data`；真实
部署时建议将 `DIARY_HOST_DATA_DIR` 指向仓库外的数据目录，例如：

```env
DIARY_HOST_DATA_DIR=/home/you/storage/data/diary
```

为了避免容器在宿主机数据目录中写出 `root:root` 文件，Compose 示例默认让 `api`
服务以 `DIARY_API_UID:DIARY_API_GID` 运行。请把这两个值设为应拥有日记文件的宿主
用户：

```bash
id -u luessiaw
id -g luessiaw
```

```env
DIARY_API_UID=1000
DIARY_API_GID=1000
```

修改 `.env` 后需要重建并重启 API 容器：

```bash
docker compose up -d --build api
```

如果此前已经由 root 写入过条目，新的配置只影响之后创建的文件；已有文件需要操作者
在宿主机上修正所有者，例如：

```bash
sudo chown -R luessiaw:luessiaw /home/you/storage/data/diary
```

P3 阶段 API 只提供健康检查、锁屏认证和受保护接口骨架，不读取或写入真实日记。
P4-T04A 起，项目额外提供最小 entries API 供存储层调试；手动验证方式见
[`p4-entries-api-test.md`](p4-entries-api-test.md)。

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
`/home/luessiaw/storage/srv/projects/serein-diary/frontend` 时，将其同步到
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

### 文件权限：容器 uid 与宿主权限不一致

`compose.yaml` 里两个服务以不同的身份运行，这一点直接决定文件权限要求：

| 服务 | 运行身份 | 需要的权限 |
|---|---|---|
| `api` | `user: ${DIARY_API_UID:-1000}:${DIARY_API_GID:-1000}` | 源码与数据目录的 **other** 位 |
| `web` | 未指定 → **root** | 不受权限位限制 |

`api` 以 uid 1000 运行，它在容器里不对应宿主机上的 `luessiaw` 用户，也不在
`srv-agents` 组里，所以**只能靠 other 位**：

- 源码文件（`backend/serein/**/*.py`）需要 `o+r`。
- 源码目录需要 `o+r` **和** `o+x`。两者缺一不可：`o+x` 只够按已知文件名打开
  文件，而 `import` 一个包要**列目录**才能发现子模块。目录只有 `x` 没有 `r` 时，
  容器会在 `from . import auth` 处报
  `ImportError: cannot import name 'auth' from partially initialized module`，
  而宿主上 `ls` 和以 root 运行的 `docker run` 都看不出问题。

`web` 目前以 root 运行，所以前端文件即使 `o` 位不可读也仍能发布。这是**隐含
前提**：一旦给 `web` 加上 `user:`（与 `api` 对齐更安全），前端文件与目录必须
补齐 `o+rX`，否则整站立刻 404。

排查现成工具：

```bash
bash scripts/diagnose-api.sh
```

第 8 段检查构建上下文的 other 位，第 9 段以容器真实 uid 在镜像内导入一次。
只信任第 9 段——`docker run` 默认是 root，它能导入成功并不说明容器能起来。

## 可选 Immich 选片器

Immich 选片器默认关闭。启用时需要内部 Docker 网络、最小权限 API Key
文件和三个 `DIARY_IMMICH_*` 配置。完整的密钥权限、网络创建、验证与回退步骤见
[`immich-integration.md`](immich-integration.md)。不得把 API Key 写入 `.env`、Compose 或聊天记录。
