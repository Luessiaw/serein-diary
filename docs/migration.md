# 从 Portal Diary 原型迁移到 Serein

Portal Diary 的代码仅供参考。不得将 Portal 配置、部署脚本、Caddy 根目录或
`/api/diary` 路由复制到本仓库。

迁移器实现后，必须接受现有的条目目录格式（`metadata.json`、`content.md`、
`comments.json` 与媒体文件），先执行 dry-run，并保留原始 ID 和源文件。
