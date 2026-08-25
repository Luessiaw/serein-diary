# Immich 选片集成

## 边界

Immich 是只读选片来源。Serein 后端代理搜索和缩略图，并在保存时把所选图片复制到
条目自己的 `media/original` 与 `media/preview`。复制后撤销 API Key、删除 Immich
资产或停止 Immich 都不影响已有日记。

浏览器只访问 `/api/v1/integrations/immich/*`，不得收到 API Key、Immich 内部路径或
可绕过 Serein 锁屏认证的 URL。第一版只支持图片，不导入视频、RAW 或 Live Photo
的视频部分。

## 部署

先创建只供两个 Compose 项目使用的内部网络：

```bash
docker network create --internal serein-immich
```

在需要访问其图库的普通 Immich 账户中创建 API Key，只授予：

```text
asset.read
asset.view
asset.download
album.read
```

将 Key 单独写入仓库外文件并限制权限，例如：

```bash
install -d -m 700 /home/luessiaw/storage/services/serein-diary/secrets
printf '%s\n' 'PASTE_KEY_INTERACTIVELY' > /home/luessiaw/storage/services/serein-diary/secrets/immich-api-key
chmod 600 /home/luessiaw/storage/services/serein-diary/secrets/immich-api-key
```

密钥文件必须在创建或重建 API 容器前存在。Compose 对该挂载设置了
`create_host_path: false`；路径缺失时会直接报错，避免 Docker 以 root 身份
自动创建同名目录。

不要把真实 Key 放入命令历史、文档或 `.env`。上面的 `printf` 仅说明文件格式；实际
操作应使用不会记录 secret 的交互式编辑方式。Serein `.env` 只配置文件路径：

```env
DIARY_IMMICH_ENABLED=true
DIARY_IMMICH_BASE_URL=http://immich-api:2283/api
DIARY_IMMICH_API_KEY_HOST_FILE=/home/luessiaw/storage/services/serein-diary/secrets/immich-api-key
```

两个 Compose 文件都把对应服务接入 `serein-immich`，Immich 在该网络上的别名固定为
`immich-api`。验证和重建：

```bash
docker compose config --quiet
docker compose up -d --build api
```

Immich 项目应先运行自己的 `docker compose config --quiet`，再重建
`immich-server` 以接入网络。不要重建数据库或 Redis。

## 复制策略与故障

- JPEG、PNG、WebP 且不超过 20 MiB/4000 万像素时复制原图。
- HEIC、其他浏览器不友好格式、超大原图改取 Immich `fullsize`，之后仍通过 Serein
  图片校验。
- 一批最多 20 张，全部准备成功后才更新 manifest，整批只增加一次 revision。
- `immich_disabled`、`immich_forbidden`、`immich_timeout` 等错误只暴露安全错误码，
  不转发 Immich 响应正文。

若内部网络暂时不可用，可把 `DIARY_IMMICH_BASE_URL` 改为 Tailnet HTTPS 地址的
`/api`，其余接口和安全边界不变。
