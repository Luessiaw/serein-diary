"""Tests for FastAPI app assembly."""

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
