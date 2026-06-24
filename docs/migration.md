# Migrating the Portal Diary Prototype to Serein

The Portal Diary code is a source reference only. Do not copy Portal settings,
deployment scripts, Caddy root directories, or `/api/diary` routes into this
repository.

When an importer is implemented, it must accept the existing entry directory
format (`metadata.json`, `content.md`, `comments.json`, and media files), run a
dry-run first, and preserve IDs and source files.
