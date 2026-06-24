# Serein

Serein is a self-hosted personal diary application. Its name evokes the quiet,
clear air after rain. This repository is independent from the parent
server-operations repository.

## Visual Principles

- **Minimal:** keep persistent UI out of the way so writing remains central.
- **Fluid:** loading and saving should not interrupt thought or visual flow.
- **Modular:** diary data, layout, frontend modules, and backend services stay
  separable so the data remains portable and the interface remains adjustable.

## Boundaries

- Application code, Compose deployment files, migrations, and public docs live
  here.
- Personal diary data is external: set `DIARY_DATA_DIR` to its host directory.
- The application must not depend on Portal routes, `PORTAL_*` variables, or
  files from the parent repository.

## Status

Scaffold only. The existing Portal Diary implementation is a migration source,
not a runtime dependency.
