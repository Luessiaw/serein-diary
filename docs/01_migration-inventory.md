# Serein Diary 迁移 P1 盘点

本文件记录将独立仓库从 `/home/luessiaw/storage/srv/serein-diary` 移至
`/home/luessiaw/storage/srv/projects/serein-diary` 前的引用、Compose 运行边界和
Git 证据。P1 不移动源码、不停止或重建容器，也不读取 `.env` 或真实日记内容。

## 迁移前仓库证据

| 项目 | 迁移前值 |
|---|---|
| 分支 | `dev` |
| HEAD | `a391792cb48d7898df6cdf077df8dec2fbbb6299` |
| HEAD tree | `407d1cc41667c87eb336b6a573ca507595793fc8` |
| 历史提交数 | 174 |
| 跟踪文件数 | 61 |
| origin | `git@github.com:Luessiaw/serein-diary.git` |
| 工作区修改 | `frontend/styles/tokens.css`，1 行增加、1 行删除 |
| 受保护文件 SHA-256 | `3d4c67229e962697a2091e3f00cac3bf84165ebec914b542c88dce89ee1b0e3e` |

`AGENTS.md`、`tasks.csv`、`.env` 和 `backend/.venv/` 均由 Serein 自身
`.gitignore` 忽略。正式移动必须保留这些本地资产，但不能把它们加入 Git。

父级 `srv` 和 Portal 独立仓库在 P1 开始时均为干净状态。Serein 唯一工作区
修改是上表中的 `tokens.css`；迁移期间不得打印其差异内容、提交、暂存、stash、
格式化或还原。

## 父仓库及跨仓库引用

### 必须更新

| 文件 | P2 处理 |
|---|---|
| 父级 `.gitignore` | 删除只针对旧根目录的 `/serein-diary/`；保留 `projects/` 整体忽略 |
| 父级 `AGENTS.md`、`README.md` | 将 Serein 路由和顶层结构改为 `projects/serein-diary` |
| `scripts/portal/deploy_portal.sh` | 将 Serein 前端源改为 `${SRV_ROOT}/projects/serein-diary/frontend` |
| `scripts/portal/README.md` | 更新 Serein 源码、Compose 和发布说明中的规范路径 |
| `scripts/serein_diary_migration/README.md` | 更新数据契约、计划和后端验证器解释器路径 |
| `docs/02_projects-directory-migration.md` | 更新当前路径、原则和实施状态 |
| Portal `docs/caddy-deployment.md` | 更新当前 Diary 前端来源和发布清单 |
| Serein `docs/deployment.md` | 更新本机 Portal 集成源路径 |
| Serein `docs/dev-handoff.md` | 更新规范项目路径及所有 `cd` 命令 |

### 历史记录

Portal 的 `docs/01_migration-inventory.md`、`docs/02_runtime-acceptance.md` 和
`tasks.csv` 记录 Portal 迁移时 Serein 尚未移动的事实。应保留其历史语义；如需
避免误导，只补充后续迁移结果，不机械改写当时证据。

### 无需修改

- 父级 `configs/caddy/Caddyfile` 只引用 `127.0.0.1:8088` 和公开路由，不依赖
  Serein 源码路径。
- Serein `compose.yaml` 的 build context、Caddyfile、frontend 和默认 data 均为
  项目相对路径；文件内容无需因目录加深而改变。
- Serein `deploy/Caddyfile` 只使用容器内路径和服务名。
- 后端配置要求显式 `DIARY_DATA_DIR`，未发现从源码目录层级推导宿主数据路径的
  逻辑，因此不存在 Portal 迁移时同类的父目录层级问题。

## Compose 运行状态

P1 只读取安全摘要：

| 服务 | 容器 | 状态 | 发布端口 |
|---|---|---|---|
| `api` | `serein-diary-api-1` | running，已持续约 9 天 | 仅容器网络 `8000/tcp` |
| `web` | `serein-diary-web-1` | running，已持续约 9 天 | `127.0.0.1:8088 -> 80/tcp` |

Compose 项目名为 `serein-diary`。两个容器的标签仍指向：

```text
working_dir=/home/luessiaw/storage/srv/serein-diary
config_files=/home/luessiaw/storage/srv/serein-diary/compose.yaml
```

`docker compose config --quiet` 已通过。Compose 使用相对 bind mount，因此运行中
容器不会自动采用新宿主路径；迁移后必须从新目录以相同项目名重建服务，刷新
working directory、config file 和 bind mount 来源。

推荐顺序：

1. P2 保持当前容器运行，完整移动仓库及其 `.git`、`.env`、`backend/.venv` 和
   用户修改，避免在目录切换期间主动中断服务。
2. P3 从新目录完成只读静态验证及 `docker compose config --quiet`。
3. P4 由管理员从新目录运行带显式项目名的重建命令：

   ```bash
   docker compose -p serein-diary up -d --build --force-recreate
   ```

4. 验证容器标签已改为新工作目录、本机 `127.0.0.1:8088`、Portal `/diary/` 和
   `/diary/api/v1/health` 后，再完成提交与临时资产清理。

该流程不会执行 `down -v`，不会删除卷或外部日记数据。Compose API 继续通过
现有外部数据 bind mount 使用真实数据；验收只检查服务级状态，不读取条目正文。

## 本地未跟踪资产与权限

- `.env` 存在且会随完整目录移动；P1 未读取其内容。
- `.env` 当前权限是 `664`，属主为 `luessiaw:luessiaw`。该文件可能包含密码和
  session secret，权限过宽；建议管理员在运行时切换前执行：

  ```bash
  chmod 600 /home/luessiaw/storage/srv/projects/serein-diary/.env
  ```

- `backend/.venv/` 存在且被忽略。完整目录移动会保留它；P3 需要验证解释器和
  测试是否仍能从新路径运行。
- 真实日记数据位于仓库外，由 `.env` 中的 `DIARY_HOST_DATA_DIR` 选择。本次迁移
  不读取、不移动、不重命名该目录。

## P2 移动策略

Serein 已是独立 Git 仓库，因此不使用 `subtree split`、clone、init 或历史重写。
P2 应先将本准备目录移到精确的临时位置，再把整个现有
`/home/luessiaw/storage/srv/serein-diary` 目录原子移动到 `projects/`，最后合并
协作文件：

- 现有 Serein `AGENTS.md` 与本迁移指南合并为新项目入口；
- 现有产品 `tasks.csv` 保存为本地 `docs/tasks.csv`，作为独立的产品任务记录；
- 本迁移 `tasks.csv` 继续跟踪目录迁移；
- 本盘点文档进入新仓库 `docs/`。

移动后立即对照 P1 证据检查分支、HEAD、tree、历史数、tracked 文件数、origin、
`tokens.css` 状态和 SHA-256。全部一致前不更新父级脚本，也不删除临时准备副本。

## P2 实施结果

P2 已将完整独立仓库原样移动到
`/home/luessiaw/storage/srv/projects/serein-diary`。旧根目录入口已消失，未创建
兼容软链接。以下迁移前证据逐项保持一致：

- `dev` 分支；
- HEAD `a391792cb48d7898df6cdf077df8dec2fbbb6299`；
- tree `407d1cc41667c87eb336b6a573ca507595793fc8`；
- 174 个历史提交与 61 个跟踪文件；
- GitHub `origin`；
- `frontend/styles/tokens.css` 仍为 1 行增加、1 行删除，SHA-256 仍为
  `3d4c67229e962697a2091e3f00cac3bf84165ebec914b542c88dce89ee1b0e3e`。

`.git`、`.env` 和 `backend/.venv/` 均随目录移动；真实数据、Compose 容器、
`/var/www` 和系统配置均未移动。`.env` 权限仍为迁移前的 `664`，留待 P4 运行时
切换前按计划收紧。

现有项目规则已与迁移保护边界合并到根 `AGENTS.md`。迁移任务继续保存在根
`tasks.csv`，原产品任务保存为被忽略的本地 `docs/tasks.csv`。准备骨架暂存于
`/tmp/serein-diary-p2/scaffold`，运行时验收前不清理。

父仓库的 Portal 发布脚本、脚本说明、Serein 数据迁移工具文档、根索引和目录迁移
方案已切换到新路径；Portal 的当前 Caddy 部署文档也已更新。Serein 当前部署与
开发交接文档已使用新规范路径。Portal 自身的旧迁移盘点、运行时验收和任务表保留
当时 Serein 尚未移动的历史证据，不作为当前操作入口。

## P3 静态验证结果

P3 复查确认，旧绝对源码路径只存在于明确标注原路径、旧 Compose 标签或当时事实
的迁移记录中；当前脚本、部署文档和操作命令均不依赖旧目录。

目录移动暴露了一个本地环境问题：`backend/.venv` 中的 editable-install finder
仍指向旧源码目录，因此从仓库根直接运行旧测试命令会报 `ModuleNotFoundError`。
尝试本地重新安装 editable 包时，环境缺少 `setuptools.build_meta`；未擅自联网
安装构建工具。测试入口已统一改为从 `backend/` 目录运行：

```bash
cd /home/luessiaw/storage/srv/projects/serein-diary/backend
.venv/bin/python -m unittest discover -s tests
```

该入口不依赖旧 editable 路径，87 个后端测试全部通过。README、AGENTS、后端测试
说明、P4 交接文档和开发交接文档均已同步新命令；开发交接中的测试数也由旧记录
85 更新为实测 87。

其余静态验证结果：

- Python `compileall` 通过；
- 全部前端 JavaScript 通过 Node.js 语法检查；
- 前端 HTML 基础解析通过；
- 父级 Portal 发布脚本通过 `bash -n`，帮助输出显示新 Serein 前端路径；
- 父级 Serein 数据迁移 Python 脚本通过编译；
- 新目录的 `docker compose -p serein-diary config --quiet` 通过；
- Serein、父级实际配置和 Portal 示例三份 Caddyfile 均为有效配置；Serein 示例
  只有迁移前已有的格式警告，不影响解析；
- Git whitespace、迁移任务 CSV 和修改文档的相对链接检查通过。

Git 及数据边界再次通过 P1 全部证据：`dev`、HEAD、tree、174 个提交、61 个跟踪
文件、GitHub origin，以及 `tokens.css` 的 1 增 1 删和 SHA-256 均未变化。父仓库
仍忽略整个目标项目，旧路径不存在。`.env` 仍被忽略、未读取且权限仍为 `664`；
真实日记数据未检查或移动。

两个运行中容器仍正常服务，Compose 标签仍指向旧工作目录。这是 P4 强制重建前的
预期状态，不是静态验证失败。

## P4-T01 准备

`.env` 权限已在不读取内容的前提下从 `664` 收紧为 `600`。新目录 Compose 配置
再次通过 `config --quiet`，父级 Portal 发布脚本帮助输出确认 Serein 来源为
`projects/serein-diary/frontend`。管理员重建、标签核对、本机入口、Portal 发布和
认证边界检查命令见 `docs/02_runtime-acceptance.md`。

首次运行带 `--build` 的重建命令时，镜像构建停在 `pip install .` 的隔离构建依赖
下载；`buildx` 警告不是根因，两个旧容器仍正常运行。由于迁移没有后端源码改动，
运行时切换改为复用现有 API 镜像的 `--no-build --force-recreate`，只刷新容器标签
和 bind mount。

P4-T02 已确认两个容器从新工作目录运行，本机首页与健康接口正常，未认证 entries
保持 `401`。Portal 以资源版本 `20260804221720` 从新 Serein 前端路径重新发布；
`/diary/`、代理健康接口和未认证边界全部通过。完整安全证据见
`docs/02_runtime-acceptance.md`。

## P4 完成与提交边界

2026-08-04 已完成源码移动、静态验证、Compose 工作目录切换、Portal 重新发布和
运行时验收。Serein Diary 的规范路径现为
`/home/luessiaw/storage/srv/projects/serein-diary`，旧路径和兼容软链接均不存在。

提交顺序：

1. 先提交 Serein 独立仓库的路径文档、测试入口修正和迁移证据，明确排除迁移前
   已存在的 `frontend/styles/tokens.css` 用户修改；
2. 再提交 Portal 独立仓库中的 Serein 前端来源文档更新；
3. 最后提交父级 `srv` 仓库中的旧忽略规则删除、项目索引、Portal 发布脚本、
   Serein 数据迁移工具路径和服务器迁移状态。

Serein 仍使用原 `dev` 分支和 GitHub `origin`。迁移提交之后，受保护的
`frontend/styles/tokens.css` 应继续显示为未暂存修改，其内容、1 增 1 删状态和
SHA-256 不变。

Git 级回滚依据包括：Serein 迁移前 HEAD 与完整独立历史、Portal 独立历史及父仓库
迁移前提交。运行服务已从新路径重建，因此不再依赖 `/tmp` 准备骨架。

P4-T03 已删除 `/tmp/serein-diary-p2`。可恢复内容继续存在于三个仓库的 Git 历史
中，无临时迁移资产残留。
