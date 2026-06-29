# P5 正式 entries API 手动验证

P5-T03 将 `/api/v1/entries` 从 P4 临时验证接口升级为正式 entries API。它仍然需要
锁屏会话认证，并会写入 `DIARY_HOST_DATA_DIR` 指向的数据目录。

如果只是测试，建议先把 `.env` 中的 `DIARY_HOST_DATA_DIR` 指向临时目录，避免把测试
条目写入真实日记目录。

## 登录

```bash
curl -i -c /tmp/serein-cookie.txt \
  -H "Content-Type: application/json" \
  -d '{"password":"你的锁屏密码"}' \
  http://127.0.0.1:8088/api/v1/auth/login
```

## 首屏列表

```bash
curl -sS -b /tmp/serein-cookie.txt \
  'http://127.0.0.1:8088/api/v1/entries?limit=30'
```

响应形状：

```json
{
  "items": [],
  "page": {
    "limit": 30,
    "has_older": false,
    "has_newer": false,
    "older_cursor": null,
    "newer_cursor": null
  }
}
```

如果 `has_older` 为 `true`，复制 `page.older_cursor`，继续请求更早内容：

```bash
curl -sS -b /tmp/serein-cookie.txt \
  'http://127.0.0.1:8088/api/v1/entries?limit=30&older_than=<older_cursor>'
```

## 创建条目

```bash
curl -sS -b /tmp/serein-cookie.txt \
  -H "Content-Type: application/json" \
  -d '{"title":"P5 API 测试","content":"这是一条通过正式 entries API 创建的测试日记。\n"}' \
  http://127.0.0.1:8088/api/v1/entries
```

预期返回 `EntryDetail`，包含：

- `id`
- `created_at`
- `cursor`
- `content`
- `comments`
- `media`
- `deleted: false`

## 读取单条

从创建响应中复制 `id`：

```bash
curl -sS -b /tmp/serein-cookie.txt \
  http://127.0.0.1:8088/api/v1/entries/<id>
```

## 日期统计

查看有日记的日期：

```bash
curl -sS -b /tmp/serein-cookie.txt \
  'http://127.0.0.1:8088/api/v1/entries/dates?from=2026-01-01&to=2026-12-31'
```

响应形状：

```json
{
  "dates": [
    {
      "date": "2026-06-23",
      "count": 1
    }
  ]
}
```

默认不统计软删除条目。如需调试：

```bash
curl -sS -b /tmp/serein-cookie.txt \
  'http://127.0.0.1:8088/api/v1/entries/dates?include_deleted=true'
```

## 软删除

```bash
curl -sS -b /tmp/serein-cookie.txt \
  -X DELETE \
  http://127.0.0.1:8088/api/v1/entries/<id>
```

预期返回删除后的 `EntryDetail`，其中 `deleted` 为 `true`，正文仍保留。

默认列表会过滤软删除条目。如需查看：

```bash
curl -sS -b /tmp/serein-cookie.txt \
  'http://127.0.0.1:8088/api/v1/entries?include_deleted=true'
```

## 错误响应

正式 API 使用稳定错误码：

```json
{
  "error": {
    "code": "entry_not_found",
    "message": "Entry not found"
  }
}
```

前端逻辑应依赖 `error.code`，不要解析自然语言 `message`。
