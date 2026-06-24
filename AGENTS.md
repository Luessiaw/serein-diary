# Diary Project Guide

`diary/` is an independent, self-hosted application repository. It is ignored
by the parent `srv` repository and must never depend on Portal source code,
routes, configuration names, or deployment scripts.

The current development approach is deliberately incremental: first establish
the static frontend scroll area and entry modes, then connect data, API,
authentication, and deployment. Do not implement a later stage merely because
its architecture is documented.

## Read First

| Task | Read first |
|---|---|
| Overall architecture, stages, or scope | `docs/plan-v1.1.md` |
| Entry, media, or comment persistence | `docs/plan-v1.1.md` |
| Importing the Portal prototype | `docs/migration.md` |
| Docker/Caddy deployment | `compose.yaml`, `deploy/Caddyfile` |

## Boundaries

- Application source belongs in `backend/` and `frontend/`; deployment assets
  belong in `deploy/`.
- Keep frontend modules independent from persistence: the frontend receives
  entry-shaped data through a small API adapter and never assumes local paths.
- Personal data is external. Use `DIARY_DATA_DIR`; never put real entries,
  media, `.env`, or secrets under Git.
- Public API is versioned under `/api/v1/*`; do not add `/api/diary` or
  `PORTAL_*` compatibility paths.
- Docker Compose is the supported first-release deployment. The web container
  serves the frontend and proxies only `/api/*` to the API container.
- Preserve `metadata.json`, `content.md`, `comments.json`, and
  `media-manifest.json` as the data facts. HTML, editor state, indexes, and
  previews are rebuildable derivatives; their v1 outline lives in the plan.
- `content.md` is semantic Markdown, not HTML. CSS, layout options, temporary
  editor state, and rendered previews must not become canonical diary data.

## Safety and Handoff

- Validate paths, IDs, file types, sizes, and revisions server-side. Do not
  expose arbitrary file access or log diary bodies.
- Authentication is local single-admin password plus secure session cookies;
  reverse-proxy protection is additive, not a replacement.
- Do not run privileged deployment commands. Document the exact Docker command
  for the operator instead.
