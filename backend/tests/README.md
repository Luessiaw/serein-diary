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

These tests do not read or write real diary entries. P4 will add storage and
index tests using temporary directories.
