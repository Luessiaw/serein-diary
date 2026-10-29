"""Tests for FastAPI app assembly."""

import ast
import importlib
from os import environ
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from serein.config import (
    DIARY_ADMIN_PASSWORD_ENV,
    DIARY_DATA_DIR_ENV,
    DIARY_SESSION_SECRET_ENV,
    DIARY_TIMEZONE_ENV,
    Settings,
)


class AppAssemblyTests(TestCase):
    def make_settings(self) -> Settings:
        return Settings(
            data_dir=Path("/tmp"),
            timezone="Asia/Shanghai",
            admin_password="a private lock-screen password",
            session_secret="x" * 32,
        )

    def test_create_app_mounts_versioned_p3_routes(self) -> None:
        settings = self.make_settings()

        create_app = self.import_create_app()
        app = create_app(settings)

        route_paths = {getattr(route, "path", "") for route in app.routes}
        self.assertIs(app.state.settings, settings)
        self.assertIn("/api/v1/health", route_paths)
        self.assertIn("/api/v1/auth/login", route_paths)
        self.assertIn("/api/v1/auth/logout", route_paths)
        self.assertIn("/api/v1/auth/session", route_paths)
        self.assertIn("/api/v1/protected", route_paths)
        self.assertIn("/api/v1/entries", route_paths)
        self.assertIn("/api/v1/entries/{entry_id}", route_paths)
        self.assertIn("/api/v1/entries/{entry_id}/media/{media_id}", route_paths)

    def test_api_submodules_do_not_import_the_api_package_itself(self) -> None:
        """Nothing under `serein/api/` may do `from serein.api import X` (except __init__).

        While `serein.api` is initialising, a submodule asking the *package* for
        an attribute that is not set yet re-enters the same namespace. Python
        3.13+ recovers via `sys.modules`; Python 3.12, which the container image
        runs, raises
        `ImportError: cannot import name 'auth' from partially initialized
        module 'serein.api' (most likely due to a circular import)`.

        This regressed once by adding `from serein.storage.entry import ...`
        plus a sibling import to `api/entries.py`: the virtualenv is 3.14 and
        tolerated it, the image failed. Sibling-package imports such as
        `serein.storage.repository` are NOT the problem — `serein.api.__init__`
        imports five submodules that all pull in `serein.config` — so the guard
        is deliberately narrow.
        """

        offenders = []
        api_dir = Path(__file__).resolve().parents[1] / "serein" / "api"
        for path in sorted(api_dir.glob("*.py")):
            if path.name == "__init__.py":
                # __init__ is the one place allowed to name the package.
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module == "serein.api":
                    offenders.append(f"{path.name}: from serein.api import ...")

        self.assertEqual(
            offenders,
            [],
            "these modules import the serein.api package while it is still "
            "initialising, which fails on Python 3.12:\n" + "\n".join(offenders),
        )

    def import_create_app(self):
        with TemporaryDirectory() as data_dir:
            with patch.dict(
                environ,
                {
                    DIARY_DATA_DIR_ENV: data_dir,
                    DIARY_TIMEZONE_ENV: "Asia/Shanghai",
                    DIARY_ADMIN_PASSWORD_ENV: "a private lock-screen password",
                    DIARY_SESSION_SECRET_ENV: "x" * 32,
                },
            ):
                return importlib.import_module("serein.main").create_app
