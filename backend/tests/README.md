# Backend tests

The backend test suite intentionally stays data-free. It verifies the
application shell, configuration checks, public health endpoint, lock-screen
auth helpers, P4 storage contract, rebuildable index, migration dry-run, and
the minimal protected entries API.

Run from the repository root:

```bash
backend/.venv/bin/python -m unittest discover -s backend/tests
```

Current coverage:

- `test_app.py`: FastAPI app assembly and `/api/v1/*` route registration.
- `test_config.py`: required `DIARY_*` variables, safe defaults rejection, and
  redacted sensitive values.
- `test_health.py`: safe health response without leaking paths or secrets.
- `test_auth.py`: login, logout, session cookie, and auth dependency behavior.
- `test_protected.py`: minimal protected route response shape.
- `test_entry_contract.py`: P4 v1 entry directory, metadata, content,
  comments, and media manifest validation.
- `test_storage_scan.py`: P4 flat `entries/` scanning, summary extraction,
  ordering, and path safety checks.
- `test_storage_write.py`: P4 immutable entry creation and soft-delete marker
  behavior.
- `test_entries_api.py`: P5 formal authenticated entries API pagination,
  creation, detail reads, soft deletion, date counts, and stable error
  responses.
- `test_storage_index.py`: P4 rebuildable SQLite index creation, ordering,
  date counts, and deleted-entry filtering.
- `test_migration_dry_run.py`: P4 read-only migration dry-run reports for
  empty sources, v1 entries, blockers, and body-safe output.
- `test_entry_service.py`: P5 entry service pagination cursors, index refresh,
  detail reads, creation, soft deletion, date counts, and stable service errors.

These tests do not read or write real diary entries. Storage tests use temporary
directories and generated fixtures.

For the P4-to-P5 service boundary, see
[`docs/p4-storage-handoff.md`](../../docs/p4-storage-handoff.md).
