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

    def test_api_package_imports_submodules_without_package_attributes(self) -> None:
        """`serein/api/__init__.py` must not rely on package attributes mid-init.

        `from serein.api import a, b` requires `serein.api` to already carry
        those attributes; if any submodule (or a package it pulls in) reaches
        `serein.api` during initialisation, Python 3.12 raises
        `ImportError: cannot import name 'auth' from partially initialized
        module 'serein.api'` while 3.13+ recovers from sys.modules. The image
        runs 3.12 and the virtualenv here runs 3.14, so a plain import test
        cannot catch it. `import serein.api.X as X` has neither requirement.
        """

        path = Path(__file__).resolve().parents[1] / "serein" / "api" / "__init__.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders = []
        for node in tree.body:
            if not isinstance(node, ast.ImportFrom):
                continue
            # `from serein.api import X` — the fragile form.
            if node.module == "serein.api":
                offenders.append("from serein.api import " + ", ".join(a.name for a in node.names))
            # `from serein import api` would bind the package, same fragility.
            if node.module == "serein" and any(a.name == "api" for a in node.names):
                offenders.append("from serein import api")

        self.assertEqual(
            offenders,
            [],
            "serein/api/__init__.py uses a form that fails on Python 3.12 when a "
            "submodule re-enters the package; use `import serein.api.X as X`:\n"
            + "\n".join(offenders),
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
