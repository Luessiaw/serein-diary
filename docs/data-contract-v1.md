# Serein 数据契约 v1

本文档是 P4 存储层的实现依据。`docs/plan-v1.1.md` 说明整体架构；本文件只定义
后端必须接受、创建、校验和拒绝的数据结构。

## 数据根目录

`DIARY_DATA_DIR` 必须位于仓库外。P4 只在该目录下读写受控路径：

```text
DIARY_DATA_DIR/
├── entries/
│   └── YYYYMMDDHHmm-<uuid>/
│       ├── metadata.json
│       ├── content.md
│       ├── comments.json
│       ├── media-manifest.json
│       └── media/
│           ├── original/
│           └── preview/
└── field-definitions.json        # 后续自定义字段定义，可选
```

条目目录名格式为：

```text
YYYYMMDDHHmm-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

示例：

```text
202606230014-0b6d2ebd-74f8-4a5c-9515-aaf4076b6189
```

目录名前 12 位是由 `metadata.created_at` 在其自身偏移量下派生的本地时间，
格式为 `YYYYMMDDHHmm`。它用于人类可读、文件排序和迁移检查；权威事实源仍是
`metadata.created_at`。秒、微秒和时区只保存在 `metadata.json` 中，不进入目录名。

P4 存储层必须拒绝：

- 年度子目录式条目，例如 `entries/2026/2026-06-23-<uuid>/`。
- 不符合 `^\d{12}-<uuid>$` 的条目目录。
- 目录时间与 `metadata.created_at` 不一致到分钟级的条目。
- 目录 UUID 与 `metadata.id` 不一致的条目。
- 任意路径穿越、符号链接逃逸或由 API 传入的自由文件路径。

## 条目不可变规则

Serein 的首个版本不允许补写，也不允许修改已保存正文。

- 条目创建时由服务端生成 UUID 与 `created_at`。
- 创建成功后，`metadata.json` 和 `content.md` 不提供更新接口。
- 标题属于 `metadata.json`，与正文一样在保存后封存。
- 已保存条目仅允许后续新增/删除评论，或通过 `deleted_at` 进行软删除标记。
- `updated_at`、`revision` 和独立 `date` 字段不属于 v1 契约。

## metadata.json

必需字段：

```json
{
  "schema_version": 1,
  "id": "0b6d2ebd-74f8-4a5c-9515-aaf4076b6189",
  "created_at": "2026-06-23T00:14:23+08:00"
}
```

可选字段：

```json
{
  "title": "夜雨",
  "location": {
    "name": "home"
  },
  "fields": {
    "custom-field-id": {
      "type": "text",
      "value": "可选结构化字段"
    }
  },
  "deleted_at": "2026-06-24T09:30:00+08:00"
}
```

约束：

- `schema_version` 必须为 `1`。
- `id` 必须是 UUID 字符串，并与目录名 UUID 一致。
- `created_at` 必须是带 UTC 偏移量的 RFC 3339 / ISO 8601 时间字符串。
- `title` 如存在，必须是字符串；空字符串等同于不存在。
- `deleted_at` 如存在，必须是带 UTC 偏移量的时间字符串，表示该条目已被软删除。
- 顶层未知字段必须被拒绝。尤其拒绝旧字段：`date`、`updated_at`、`revision`、
  `tags`、`mood`、`weather`、`time_range`、`is_favorite`。

## content.md

`content.md` 是 UTF-8 / LF Markdown 文件，也是正文事实源。

约束：

- 不保存 HTML、CSS、主题设置、Tiptap JSON 或临时编辑器状态。
- 不允许空正文创建正式条目；草稿能力不属于 P4。
- 图片引用使用 `![alt](media:<uuid>)`。
- 视频和音频使用 `diary-media` 围栏块，并通过 `media-manifest.json` 解析。
- 渲染器不得把 Markdown URL 当作本地文件系统路径。

## comments.json

初始空评论文件：

```json
{
  "schema_version": 1,
  "comments": []
}
```

评论示例：

```json
{
  "id": "55c4e14d-0506-45fd-9e0f-3e8a6d6aa40b",
  "created_at": "2026-06-23T00:20:00+08:00",
  "content": "这里是一条评论。",
  "anchor": null
}
```

引文评论示例：

```json
{
  "id": "55c4e14d-0506-45fd-9e0f-3e8a6d6aa40b",
  "created_at": "2026-06-23T00:20:00+08:00",
  "content": "这里是一条引文评论。",
  "anchor": {
    "type": "quote",
    "selected_text": "被选中的原文",
    "prefix": "前文上下文",
    "suffix": "后文上下文"
  }
}
```

约束：

- 评论只可新增或删除，不可编辑。
- 评论正文是轻量 Markdown，不写入 `content.md`。
- 无文本选区时，`anchor` 为 `null`，表示整篇条目评论。
- 引文锚点记录选中文本及前后上下文。由于正文不可修改，失联评论主要用于导入旧数据
  或未来兼容场景。

## media-manifest.json

初始空媒体文件：

```json
{
  "schema_version": 1,
  "media": []
}
```

媒体项示例：

```json
{
  "id": "8c21d9b4-77c8-4eb2-8ea9-2c72d7c76f13",
  "kind": "image",
  "original": "media/original/8c21d9b4-77c8-4eb2-8ea9-2c72d7c76f13.jpg",
  "preview": "media/preview/8c21d9b4-77c8-4eb2-8ea9-2c72d7c76f13.webp",
  "alt": "雨后的树",
  "created_at": "2026-06-23T00:18:00+08:00"
}
```

约束：

- `schema_version` 必须为 `1`。
- `media` 必须是数组。
- 媒体路径必须是条目目录内的相对路径，不得以 `/` 开头，不得包含 `..`。
- P4 可先实现空 manifest 和结构校验；真实上传、缩略图和媒体读取 API 可留到 P5。

## SQLite 索引

SQLite 索引是可删除、可重建的衍生物，不是事实源。删除索引后，系统必须能从
`entries/` 下的事实文件重建。

索引至少应能支持：

- 按 `created_at` 正序/倒序分页。
- 按日期统计是否有日记。
- 查询标题、内容摘要、评论数、媒体数和删除状态。

索引重建不得修改任何条目事实文件。

## dry-run 迁移

迁移 dry-run 是只读检查：

- 不复制文件。
- 不删除文件。
- 不修改源目录或目标目录。
- 不打印日记正文。

报告应包含：

- 条目数量、评论数量、媒体数量。
- 旧字段、缺失字段、非法目录名和时间不一致问题。
- 可自动迁移与需要人工处理的问题清单。
