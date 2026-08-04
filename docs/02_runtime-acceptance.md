# Serein Diary 目录迁移运行时验收

本文档用于 P4 运行时切换。规范项目路径是：

```text
/home/luessiaw/storage/srv/projects/serein-diary
```

现有 `api` 和 `web` 容器仍在运行，但其 Compose 标签和 bind mount 来源创建于旧
工作目录。P4 使用相同项目名原地重建容器，不删除卷或外部日记数据。

## P4-T01：管理员命令

### 1. 确认秘密文件权限

迁移准备阶段已将 `.env` 从 `664` 收紧为 `600`，且未读取其内容。管理员可只读
复核权限：

```bash
stat -c '%a %U:%G %n' /home/luessiaw/storage/srv/projects/serein-diary/.env
```

预期权限开头为 `600`。不要使用 `cat`、`grep` 或完整 Compose 配置输出检查该文件。

### 2. 从新目录重建 Compose 服务

```bash
cd /home/luessiaw/storage/srv/projects/serein-diary
docker compose -p serein-diary up -d --no-build --force-recreate
docker compose -p serein-diary ps
```

显式 `-p serein-diary` 会接管同名现有 Compose 项目。该命令不执行 `down -v`，
不删除数据卷，也不移动 `.env` 所指向的外部数据目录。本次迁移未修改后端代码，
`--no-build` 会复用当前已验证运行的 `serein-diary-api` 镜像，只重建容器以刷新
Compose 标签和 bind mount 来源。

首次尝试使用 `--build` 时，Dockerfile 的 `pip install .` 长时间停在隔离构建依赖
下载；`buildx` 缺失警告本身不是错误。旧容器在构建阶段始终保持运行。遇到该状态
可按 `Ctrl+C` 取消构建，再执行上面的 `--no-build` 命令；不要删除旧镜像。

如果重建失败，请保留完整命令输出并停止后续步骤；不要删除容器、卷、外部数据或
SQLite 索引来尝试修复。

### 3. 验证 Compose 标签已切换

```bash
docker inspect --format '{{.Name}} running={{.State.Running}} working_dir={{index .Config.Labels "com.docker.compose.project.working_dir"}} config={{index .Config.Labels "com.docker.compose.project.config_files"}}' serein-diary-api-1 serein-diary-web-1
```

两个容器都应显示 `running=true`，且 `working_dir`、`config` 应分别指向新项目目录
和新 `compose.yaml`。

### 4. 验证本机 Serein 入口

```bash
curl -fsSI http://127.0.0.1:8088/
curl -fsS http://127.0.0.1:8088/api/v1/health
curl -sS -o /dev/null -w 'local entries without session: %{http_code}\n' http://127.0.0.1:8088/api/v1/entries
```

首页应返回 `200`，健康检查应返回安全状态 JSON，未携带会话访问 entries 应返回
`401`。这些检查不读取日记正文。

### 5. 重新发布 Portal 的 Diary 静态文件

```bash
sudo /home/luessiaw/storage/srv/scripts/portal/deploy_portal.sh
```

脚本应明确显示 Serein 来源为
`/home/luessiaw/storage/srv/projects/serein-diary/frontend`。本次未修改 Caddyfile，
不要添加 `--caddy`，也不要用 `--no-verify` 绕过失败。

### 6. 验证 Portal 集成与认证边界

```bash
curl -fsSI http://100.79.195.9/diary/
curl -fsS http://100.79.195.9/diary/api/v1/health
curl -sS -o /dev/null -w 'portal entries without session: %{http_code}\n' http://100.79.195.9/diary/api/v1/entries
```

预期为 Diary 首页 `200`、健康检查安全 JSON、未认证 entries `401`。公开路由仍是
`/diary/` 和 `/diary/api/v1/*`，源码目录迁移不改变 API 契约。

## 结果交接

P4-T02 需要以下安全输出：

1. Compose 重建结果和 `docker compose ps`；
2. 两个容器的新 Compose 标签；
3. 本机首页/health/未认证 entries 的结果；
4. Portal 发布脚本结果；
5. Portal Diary 首页/health/未认证 entries 的结果。

不要发送 `.env`、Cookie、session、登录密码、真实日记正文或私有媒体路径。

## P4-T02：验收结果

2026-08-04 已完成运行时切换与验收：

- 首次带 `--build` 的命令停在隔离构建依赖下载，旧容器未被替换；取消后改用
  `--no-build --force-recreate`，复用现有 API 镜像成功重建两个服务。
- `serein-diary-api-1` 与 `serein-diary-web-1` 均为 `running=true`。
- 两个容器的 `working_dir` 均已更新为
  `/home/luessiaw/storage/srv/projects/serein-diary`，`config_files` 均已更新为新目录的
  `compose.yaml`。
- 本机 `http://127.0.0.1:8088/` 返回 `200 OK`。
- 本机 `/api/v1/health` 返回 `status=ok`、`config.ready=true`、
  `data_dir=configured` 和 `timezone=Asia/Shanghai`。
- 本机未携带 session 访问 `/api/v1/entries` 返回预期 `401`。
- Portal 发布脚本从 `projects/portal` 发布首页，并从
  `projects/serein-diary/frontend` 发布 Diary；资源版本为 `20260804221720`，内置
  Caddy 响应验证通过。
- Portal `http://100.79.195.9/diary/` 返回 `200 OK`。
- Portal `/diary/api/v1/health` 返回与本机一致的安全健康状态。
- Portal 未携带 session 访问 `/diary/api/v1/entries` 返回预期 `401`。

因此 Compose 工作目录、bind mount 来源、Serein 本机入口、Portal 静态集成、API
代理和认证边界均已切换到新项目路径，未发现目录迁移回归。验收没有读取日记正文、
Cookie、session 或 `.env` 内容。
