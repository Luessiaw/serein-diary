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

    def test_api_package_lists_submodules_with_relative_imports(self) -> None:
        """`serein/api/__init__.py` must name its submodules relatively.

        The package is still initialising when `serein.main` imports it. Both
        `from serein.api import a, b` and `import serein.api.a as a` resolve
        absolute names against a partially initialised package; on Python 3.12
        (the image runtime) that raised `ModuleNotFoundError: No module named
        'serein.api.auth'` and, before that, `ImportError: cannot import name
        'auth' from partially initialized module`. The dev virtualenv runs
        3.14, which recovers, so importing here proves nothing. `from . import
        a, b` resolves through the package's own `__path__` and is the only
        form that behaves identically on all supported versions.
        """

        path = Path(__file__).resolve().parents[1] / "serein" / "api" / "__init__.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders = []
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                if node.module == "serein" or node.module.startswith("serein.api"):
                    offenders.append(f"from {node.module} import ...")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "serein" or alias.name.startswith("serein.api"):
                        offenders.append(f"import {alias.name}")

        self.assertEqual(
            offenders,
            [],
            "serein/api/__init__.py names its submodules absolutely while the "
            "package is still initialising (fails on Python 3.12); use "
            "`from . import a, b`:\n" + "\n".join(offenders),
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
