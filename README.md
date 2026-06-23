# Diary

Self-hosted personal diary application. This repository is independent from the
parent server-operations repository.

## Boundaries

- Application code, Compose deployment files, migrations, and public docs live
  here.
- Personal diary data is external: set `DIARY_DATA_DIR` to its host directory.
- The application must not depend on Portal routes, `PORTAL_*` variables, or
  files from the parent repository.

## Status

Scaffold only. The existing Portal Diary implementation is a migration source,
not a runtime dependency.
