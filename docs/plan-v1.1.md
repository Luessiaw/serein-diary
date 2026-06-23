# Diary v1.1 Architecture Plan

## Goal

Diary is a standalone, self-hosted personal writing application. It provides a
minimal continuous diary feed for desktop and mobile browsers: read entries as
one long document, create an entry at the end, edit it in place, comment on an
entry or selected quotation, and navigate older entries without tying the
application to an existing portal.

The current Portal implementation is only a migration source. Portal may later
link to Diary, but it is never a runtime dependency.

## Runtime Architecture

```text
browser
  │
  ▼
Caddy web container ── static frontend
  │ /api/v1/*
  ▼
FastAPI API container ── Diary service ── DIARY_DATA_DIR (host volume)
```

Docker Compose is the first supported deployment. `web` serves the built
frontend and reverse-proxies `/api/v1/*` to `api`. `api` is not directly
published. Configuration uses `DIARY_*` variables, notably
`DIARY_DATA_DIR`, `DIARY_TIMEZONE`, `DIARY_ADMIN_PASSWORD`, and
`DIARY_SESSION_SECRET`.

The first public release is single-user: an administrator password initializes
the local account and secure HttpOnly session cookies protect write APIs.
Tailscale or reverse-proxy authentication can add protection but does not
replace application authentication.

## Product and API Model

- The default feed loads the newest entries in cursor pages, then loads older
  entries above the current text. The frontend must not duplicate a cursor
  page.
- Entries have server-created IDs, dates, timestamps, and revisions. Save uses
  optimistic revision checking; a stale save returns a conflict.
- The normal reading UI is intentionally quiet. Entry actions appear only on
  hover/focus; editing activates an inline Tiptap editor with an expandable
  formatting toolbar.
- Comments render below the entry in a distinct, compact style. A selected-text
  comment stores a quotation and context; a no-selection comment belongs to the
  whole entry. A no-longer-matchable quotation is shown as orphaned, never
  silently reattached.
- Public endpoints are namespaced below `/api/v1`: authentication, entry
  paging/create/read/save/delete, comment CRUD, media upload/read, export, and
  health. No Portal-specific API aliases are retained.

## Data Contract

`DIARY_DATA_DIR` remains outside the repository:

```text
entries/<year>/<date>-<uuid>/
├── metadata.json
├── content.md
├── comments.json
├── media-manifest.json
└── media/{original,preview}/
```

- `content.md` is UTF-8 semantic Markdown and the portable body source; it
  contains no CSS, HTML, theme data, or editor session data.
- `metadata.json` contains the stable ID, date, timezone, server timestamps,
  revision, and extensible structured metadata.
- `comments.json` is independent from the body. It contains comment text,
  timestamps, and optional quote anchors.
- `media-manifest.json` maps stable media IDs to entry-local relative files.
  Raw media filenames are not referenced by the body.
- SQLite indexes, previews, rendered HTML, thumbnails, and Tiptap JSON are
  caches/derivatives and must be rebuildable from these files.

## Delivery Sequence

1. Create backend/frontend packages, versioned configuration, authentication,
   and Compose build images.
2. Port and harden filesystem storage; implement the full `/api/v1` contract,
   SQLite rebuildable index, migration dry-run, and API tests.
3. Build the continuous-feed Tiptap UI, comments, mobile interaction, PWA, and
   media workflow.
4. Provide exporter, backup/restore verification, release documentation, and
   a Portal link-only integration option.

## Migration and Non-Goals

The importer must dry-run before copying existing entry files, preserve entry
IDs and media references, and report entry/comment/media counts. It must never
read Portal runtime configuration or copy personal data into the Git checkout.

The first public release excludes multi-user collaboration, public sharing
links, server-side video transcoding, and AI access to diary content. AI may be
added later only with an explicit selected-entry scope and user confirmation.
