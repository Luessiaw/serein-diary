# P4 最小 entries API 手动验证

> P5-T03 已将 `/api/v1/entries` 升级为正式分页 API。新的手动验证请优先阅读
> [`p5-entries-api-test.md`](p5-entries-api-test.md)。本文仅保留 P4 阶段的历史
> 验证背景。

P4-T04A 提供一组临时但真实的受保护 API，用于在进入 SQLite 索引前验证文件系统
存储层已经可用。它不是最终的连续流 API，也不包含评论、媒体上传、搜索或分页游标。

## 前提

启动 Compose 示例，并确认浏览器能打开锁屏：

```bash
docker compose up -d --build
```

以下命令会向 `DIARY_HOST_DATA_DIR` 指向的数据目录写入真实条目。若只是测试，建议
先把 `.env` 中的 `DIARY_HOST_DATA_DIR` 指向临时目录。

## curl 闭环

保存 cookie：

```bash
curl -i -c /tmp/serein-cookie.txt \
  -H "Content-Type: application/json" \
  -d '{"password":"你的锁屏密码"}' \
  http://127.0.0.1:8088/api/v1/auth/login
```

查看列表：

```bash
curl -sS -b /tmp/serein-cookie.txt \
  http://127.0.0.1:8088/api/v1/entries
```

创建条目：

```bash
curl -sS -b /tmp/serein-cookie.txt \
  -H "Content-Type: application/json" \
  -d '{"title":"P4 API 测试","content":"这是一条通过最小 entries API 创建的测试日记。\n"}' \
  http://127.0.0.1:8088/api/v1/entries
```

从返回 JSON 中复制 `id`，然后读取单条：

```bash
curl -sS -b /tmp/serein-cookie.txt \
  http://127.0.0.1:8088/api/v1/entries/<id>
```

软删除：

```bash
curl -sS -b /tmp/serein-cookie.txt \
  -X DELETE \
  http://127.0.0.1:8088/api/v1/entries/<id>
```

再次读取同一条，预期 `deleted` 为 `true`，且 `content` 仍保留。

## 浏览器验证

登录锁屏后，可直接在浏览器地址栏打开：

```text
http://127.0.0.1:8088/api/v1/entries
```

如果通过 Portal 子路径访问，则路径是：

```text
http://luessiaw-server/diary/api/v1/entries
```

浏览器地址栏只能方便验证 `GET`；创建和删除建议用 `curl` 或浏览器开发者工具的
`fetch()`。
