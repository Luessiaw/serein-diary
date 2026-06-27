# Backend tests

The backend test suite intentionally stays small and data-free during P3. It
verifies the application shell, configuration checks, public health endpoint,
lock-screen auth helpers, and the minimal protected API skeleton.

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

These tests do not read or write real diary entries. Storage tests use temporary
directories and generated fixtures.
