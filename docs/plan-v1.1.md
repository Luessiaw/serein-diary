# Diary v1.1 Architecture Plan

## Goal

Diary is a standalone, self-hosted personal writing application. It provides a
minimal continuous diary feed for desktop and mobile browsers: read entries as
one long document, create an entry at the end, edit it in place, comment on an
entry or selected quotation, and navigate older entries without tying the
application to an existing portal.

The current Portal implementation is only a migration source. Portal may later
link to Diary, but it is never a runtime dependency.

## Development Method and Frontend Stages

Development is intentionally small-step. The current first milestone is a
frontend-only static prototype; it does not need Docker, API, authentication,
or real diary files.

1. **Step 0 — style contract:** minimal, fluent, modular. The page has one
   full-width, indefinitely scrollable diary area and avoids permanent panels,
   metadata controls, Markdown previews, or noisy loading UI.
2. **Step 1 — scroll area:** create a full-page scroll region filled with
   bordered placeholder entry cards containing mock text. Entries form a
   vertical list; no backend or storage is involved.
3. **Step 2 — entry modes:** use a static list of sample entries to develop
   three switchable modes: saved reading, inline editing, and an unsaved “new
   entry” item at the end of the list. New mode differs only by its label and
   lack of a persisted ID.
4. **Later frontend stages:** replace mock data with the API adapter, introduce
   Tiptap for active inline editing, then add comments, media, timeline/search,
   PWA, and configuration-driven visual tuning.

Each frontend module should have a narrow role: feed/loading, entry rendering,
entry editing, comments, and visual tokens. Styling knobs such as font, size,
spacing, and colors live in a frontend configuration/token module rather than
being duplicated through components.

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
- The normal reading UI is intentionally quiet. Entries are shown continuously
  like one long document; a new-entry affordance remains at the end. Entry
  actions appear only on hover/focus; editing activates an inline Tiptap editor
  with an expandable formatting toolbar.
- Date labels are server-created. The UI may show Today/Yesterday for recent
  entries, and includes time when several entries share a day. Loading older
  cursor pages inserts them above current text without duplication.
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

### Metadata v1

`metadata.json` has `schema_version`, UUID `id`, `date`, `timezone`, server
`created_at`/`updated_at`, `revision`, optional title, tags, mood, weather,
location, time range, favorite state, and typed custom fields. Dates use
`YYYY-MM-DD`; timestamps use RFC 3339 with offset. Unknown top-level write
fields are rejected; custom fields are governed by a root-level
`field-definitions.json` so label changes do not rewrite historical entries.

### Content and media v1

`content.md` uses UTF-8/LF semantic Markdown. Images use
`![alt](media:<uuid>)`. Video and audio use a versioned `diary-media` fenced
block with `id`, `kind`, and optional caption. The renderer resolves a media ID
through `media-manifest.json`; it never treats a Markdown URL as a local
filesystem path. Text-only export degrades media to a readable ID reference.

### Comments v1

`comments.json` contains a schema version and an array of comments. A comment
has UUID, Markdown body, timestamps, and either no anchor (entry comment) or a
quote anchor. A quote anchor records selected text and context. If later body
edits prevent a safe match, its state becomes `orphaned`; it must never attach
to similar but different text. Comments render under their entry, in a compact
style distinct from diary prose.

## Delivery Sequence

1. Complete static Step 0--2 frontend prototypes and browser checks.
2. Create backend/frontend packages, versioned configuration, authentication,
   and Compose build images.
3. Port and harden filesystem storage; implement the full `/api/v1` contract,
   SQLite rebuildable index, migration dry-run, and API tests.
4. Connect the continuous-feed Tiptap UI, comments, mobile interaction, PWA,
   and media workflow.
5. Provide exporter, backup/restore verification, release documentation, and
   a Portal link-only integration option.

## Migration and Non-Goals

The importer must dry-run before copying existing entry files, preserve entry
IDs and media references, and report entry/comment/media counts. It must never
read Portal runtime configuration or copy personal data into the Git checkout.

The first public release excludes multi-user collaboration, public sharing
links, server-side video transcoding, and AI access to diary content. AI may be
added later only with an explicit selected-entry scope and user confirmation.
