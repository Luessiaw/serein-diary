# P3 最小后端边界

P3 的目标是让 Serein 从纯静态原型进入“有后端外壳”的状态：应用可以启动、
读取配置、暴露版本化 API、完成单管理员认证，并通过 Compose/Caddy 示例连通。

P3 不负责真实日记数据读写。这个限制是刻意的：先把安全边界和部署边界立住，再
进入文件存储、索引和正式写作 API。

## 本阶段要做

P3 只包含以下能力：

- FastAPI 应用骨架，公开 API 统一挂载在 `/api/v1`。
- 配置读取与启动校验，覆盖必要的 `DIARY_*` 环境变量。
- 未认证可访问的健康检查接口。
- 单管理员登录、登出、当前会话检查。
- HttpOnly Cookie 会话，使用 `DIARY_SESSION_SECRET` 签名或加密。
- 可复用的认证依赖，用于保护后续写入 API。
- 一个最小受保护接口，用于验证认证链路。
- Compose 中的 `api` 服务。
- Caddy 示例中 `/api/v1/*` 到 `api` 的反向代理。
- 最小测试与文档。

## 本阶段不做

P3 明确不实现：

- 不创建、读取、删除真实日记条目。
- 不写 `entries/` 目录。
- 不创建 SQLite 索引。
- 不实现迁移或 dry-run。
- 不实现评论、媒体、导出、搜索、PWA 或 AI。
- 不把前端新建日记接到真实保存 API。
- 不保存或修改 `tokens.css`。页面名称等设置仍停留在前端本地覆盖；后端持久化
  配置留到后续单独设计。

## 目录边界

建议 P3 后端目录保持窄而清晰：

```text
backend/
├── pyproject.toml
├── serein/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory / app instance
│   ├── config.py            # DIARY_* 配置读取与校验
│   ├── security.py          # 密码校验、会话签名、Cookie 工具
│   └── api/
│       ├── __init__.py
│       ├── health.py        # /api/v1/health
│       └── auth.py          # /api/v1/auth/*
└── tests/
    ├── test_health.py
    ├── test_config.py
    └── test_auth.py
```

后续条目、评论、媒体和存储模块可以继续放在 `serein/api/`、`serein/services/`
和 `serein/storage/` 下，但不应在 P3 提前实现。

## 配置边界

P3 需要识别这些环境变量：

- `DIARY_DATA_DIR`：仓库外的数据目录。P3 只校验路径存在、是目录、进程可访问；
  不创建真实条目，不写 entries。
- `DIARY_TIMEZONE`：应用时区，例如 `Asia/Shanghai`。
- `DIARY_ADMIN_PASSWORD`：单管理员登录密码。不得写入日志。
- `DIARY_SESSION_SECRET`：会话签名密钥。不得写入日志；应要求足够长度。

可选配置可后续加入，例如 Cookie 名称、Cookie secure 策略、CORS、日志级别等。
如果 P3 需要添加，也应保持默认安全、文档清晰。

## API 边界

P3 只提供以下接口：

```text
GET  /api/v1/health
POST /api/v1/auth/login
POST /api/v1/auth/logout
GET  /api/v1/auth/session
GET  /api/v1/protected      # 可选：仅用于认证链路验证
```

约束：

- `/api/v1/health` 不需要认证。
- 认证失败返回 `401`，不得泄露密码是否存在、secret、数据目录或日记内容。
- 登录成功设置 HttpOnly Cookie。
- 登出清除 Cookie。
- 当前会话检查只返回最小状态，例如 `authenticated: true` 和固定的单用户身份。
- API 响应不返回真实日记正文、真实文件路径或敏感配置。

P3 不提供 `/api/v1/entries`、`/api/v1/comments`、`/api/v1/media` 的真实实现。
如果为了前端占位需要保留路径，也必须返回明确的未实现状态，而不是假装读写成功。

## 部署边界

Compose 示例在 P3 增加 `api` 服务：

- `web` 继续发布 `frontend/`。
- `web` 将 `/api/v1/*` 反向代理到 `api`。
- `api` 不直接暴露公网端口。
- Docker Compose 和 Caddy 仍只是可选部署示例；用户可以用其他反向代理或进程管理器。

本机 Portal 的 `/diary/` 集成仍属于父级运维仓库的部署 glue，不是 Serein 运行时依赖。

## 安全与日志

- 不在日志中打印密码、session secret、Cookie 值或日记正文。
- 不把 `DIARY_DATA_DIR` 下的内容复制进仓库。
- 不接受任意文件路径参数。
- Cookie 至少应设置 `HttpOnly`、`SameSite=Lax`；`Secure` 策略可根据部署环境配置，
  但公开部署文档应推荐 HTTPS 下启用。
- 认证保护是应用自身边界；Tailscale、Caddy basic auth 或其他反向代理认证只能作为
  额外保护，不能替代应用认证。

## P3 验收

P3 完成时应满足：

- 本地测试可以导入 FastAPI app。
- 合法配置下应用可启动。
- 缺少必需配置时启动失败，并给出不泄密的错误。
- `GET /api/v1/health` 未认证可访问。
- 正确密码可登录，错误密码被拒绝。
- 登录后可访问受保护接口，登出后不可访问。
- Compose 可启动 `web` 与 `api`。
- 通过 `web` 端口访问 `/api/v1/health` 成功。
- 静态前端仍可通过 `web` 访问。

满足这些条件后，才进入 P4 的存储、索引和迁移工作。
