# Serein Project Guide

`/home/luessiaw/storage/srv/projects/serein-diary` is the independent,
self-hosted Serein Diary application repository. It is ignored by the parent
`srv` repository and must never depend on Portal source code, routes,
configuration names, or deployment scripts.

## Start Here

1. Read `/home/luessiaw/storage/srv/AGENTS.md` for server-wide rules.
2. Read `README.md` and the focused document for the task below.
3. Read `tasks.csv` and `docs/01_migration-inventory.md` for the completed
   directory-migration record. The prior product plan is preserved in local
   `docs/tasks.csv` and must be reviewed before reuse.
4. Check this repository, the parent operations repository, and Portal for
   unrelated changes before editing.

## Repository Boundary

- This is an independent Git repository. The parent intentionally ignores
  `projects/`; do not force-add this project there or alter that rule to track
  it.
- Application source belongs in `backend/` and `frontend/`; deployment assets
  belong in `deploy/`.
- Parent-owned Portal publishing scripts, Caddy integration, server migration
  scripts, and cross-project documentation stay in
  `/home/luessiaw/storage/srv`.
- On luessiaw-server, the parent may publish `frontend/` at `/diary/`. Treat
  this as deployment glue, not a Serein runtime dependency.
- Personal data is external. Use `DIARY_DATA_DIR`; never put real entries,
  media, `.env`, secrets, or runtime databases under Git.

## Read First

| Task | Read first |
|---|---|
| Directory migration | `docs/01_migration-inventory.md`, then `tasks.csv` |
| Runtime migration acceptance | `docs/02_runtime-acceptance.md` |
| Overall architecture, stages, or scope | `docs/plan-v1.1.md` |
| Backend scope, API skeleton, or auth | `docs/backend-boundary.md`, then `docs/plan-v1.1.md` |
| Data contract, storage, index, or migration | `docs/data-contract-v1.md`, then `docs/p4-storage-handoff.md` |
| Formal API, frontend adapter, comments, or media | `docs/p5-api-frontend-contract.md`, then `docs/p4-storage-handoff.md` |
| Frontend layout, alignment, or visual spacing | `docs/layout.md`, then `frontend/styles/tokens.css` |
| Visual/interaction redesign research (external references, screenshots) | `docs/visual-references.md`, then `docs/reference-gallery.html` |
| Tiptap/editor experiments | `docs/tiptap-experiment.md` |
| Self-hosted "local Notion" alternatives (AFFiNE, AppFlowy, SiYuan, Docmost, Outline) | `docs/notion-alternatives-research.md` |
| Importing the historical Portal prototype | `docs/migration.md` |
| Docker/Caddy or static deployment | `docs/deployment.md`, then `compose.yaml`, `deploy/Caddyfile` |
| Historical product task state | `docs/tasks.csv`, then `docs/dev-handoff.md` |

## Application and Data Boundaries

- Keep frontend modules independent from persistence. The frontend receives
  entry-shaped data through the API adapter and never assumes host paths.
- Public API is versioned under `/api/v1/*`; do not add `/api/diary` or
  `PORTAL_*` compatibility paths.
- Docker Compose and Caddy are optional deployment examples. The frontend must
  remain usable through other static servers.
- Preserve `metadata.json`, `content.md`, `comments.json`, and
  `media-manifest.json` as data facts. HTML, editor state, indexes, and previews
  are rebuildable derivatives.
- `content.md` is semantic Markdown, not HTML. CSS, layout, editor state, and
  rendered previews must not become canonical diary data.
- Validate paths, IDs, file types, sizes, and revisions server-side. Never
  expose arbitrary file access or log diary bodies.
- Authentication is a local single-admin password plus secure session cookies;
  reverse-proxy protection is additive, not a replacement.

## Migration Protection

- `frontend/styles/tokens.css` is the controlled source for visual parameters.
  It may be changed for approved UI work; add semantic tokens rather than
  hard-coding component values, and do not reformat or overwrite unrelated
  user customizations.
- Preserve the `dev` branch, existing history and GitHub `origin`.
- The existing `.env` and `backend/.venv/` moved with the repository and remain
  ignored. Never print `.env` values. Its permissions must be tightened to
  `600` before runtime recreation.
- Existing Compose containers were created from the old working directory.
  Do not assume they adopted the new path; follow the P4 recreation and label
  validation steps in the migration plan.
- Do not create a compatibility symlink at the former root-level path.

## Development and Validation

- During frontend/backend integration, small namespaced browser debug logs are
  acceptable. Keep them easy to disable and never print secrets, sessions,
  diary bodies, or private media paths.
- Run backend tests from `backend/` with
  `.venv/bin/python -m unittest discover -s tests`; this avoids depending on an
  editable-install path tied to the repository's former location. Syntax-check
  frontend JavaScript with Node.js.
- Validate Compose without printing resolved secrets. Prefer
  `docker compose config --quiet`; do not paste full resolved configuration.
- Do not run privileged deployment commands. Give the operator exact commands.
- After frontend changes, remind the user to publish through the parent Portal
  deployment flow before browser testing; do not run it automatically.
- When a missing tool blocks validation, recommend the smallest mainstream
  installation and a version check. Do not install tools automatically.
- Preserve unrelated changes and use `apply_patch` for manual edits.

## Project Maintenance and Handoff

- Keep `tasks.csv` as the completed directory-migration record. Review local
  `docs/tasks.csv` before establishing the next current product plan.
- Update `README.md` when architecture, canonical paths, or deployment changes.
- Update this guide when structure, routing, data boundaries, or cross-repo
  ownership changes; keep it a concise index.
- Report parent, Portal, and Serein repository changes separately.
- Commit your own verified changes automatically; do not wait to be asked:

  ```bash
  git add . && git commit -m "<Category>: <中文摘要>"
  ```

- Do not push automatically. Push only when the user explicitly asks in that
  turn. See the parent `AGENTS.md` "Git Handoff" section for the full policy.

- Use `Add`, `Fix`, `Refine`, `Document`, `Scaffold`, or `Configure`.
- `AGENTS.md` and root `tasks.csv` are local collaboration files and do not
  need to be tracked unless the user explicitly changes that policy.
