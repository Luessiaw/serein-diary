"""Tests for DIARY_* configuration loading."""

from __future__ import annotations

from tempfile import TemporaryDirectory
from unittest import TestCase

from serein.config import (
    DIARY_ADMIN_PASSWORD_ENV,
    DIARY_DATA_DIR_ENV,
    DIARY_SESSION_SECRET_ENV,
    DIARY_TIMEZONE_ENV,
    ConfigError,
    load_settings,
)


class LoadSettingsTests(TestCase):
    def make_env(self, data_dir: str) -> dict[str, str]:
        return {
            DIARY_DATA_DIR_ENV: data_dir,
            DIARY_TIMEZONE_ENV: "Asia/Shanghai",
            DIARY_ADMIN_PASSWORD_ENV: "a private lock-screen password",
            DIARY_SESSION_SECRET_ENV: "x" * 32,
        }

    def test_loads_valid_settings(self) -> None:
        with TemporaryDirectory() as data_dir:
            settings = load_settings(self.make_env(data_dir))

        self.assertEqual(settings.timezone, "Asia/Shanghai")
        self.assertEqual(settings.admin_password, "a private lock-screen password")
        self.assertEqual(settings.session_secret, "x" * 32)

    def test_requires_data_dir(self) -> None:
        env = self.make_env("/tmp")
        env.pop(DIARY_DATA_DIR_ENV)

        with self.assertRaisesRegex(ConfigError, DIARY_DATA_DIR_ENV):
            load_settings(env)

    def test_rejects_relative_data_dir(self) -> None:
        env = self.make_env("relative/path")

        with self.assertRaisesRegex(ConfigError, "absolute path"):
            load_settings(env)

    def test_rejects_missing_data_dir(self) -> None:
        env = self.make_env("/definitely/missing/serein-data")

        with self.assertRaisesRegex(ConfigError, "existing directory"):
            load_settings(env)

    def test_rejects_invalid_timezone(self) -> None:
        with TemporaryDirectory() as data_dir:
            env = self.make_env(data_dir)
            env[DIARY_TIMEZONE_ENV] = "Not/AZone"

            with self.assertRaisesRegex(ConfigError, DIARY_TIMEZONE_ENV):
                load_settings(env)

    def test_rejects_default_admin_password(self) -> None:
        with TemporaryDirectory() as data_dir:
            env = self.make_env(data_dir)
            env[DIARY_ADMIN_PASSWORD_ENV] = "change-this-before-first-start"

            with self.assertRaisesRegex(ConfigError, DIARY_ADMIN_PASSWORD_ENV):
                load_settings(env)

    def test_rejects_short_session_secret(self) -> None:
        with TemporaryDirectory() as data_dir:
            env = self.make_env(data_dir)
            env[DIARY_SESSION_SECRET_ENV] = "short"

            with self.assertRaisesRegex(ConfigError, "at least 32"):
                load_settings(env)

    def test_repr_redacts_sensitive_values(self) -> None:
        with TemporaryDirectory() as data_dir:
            settings = load_settings(self.make_env(data_dir))

        settings_repr = repr(settings)
        self.assertIn("admin_password=<redacted>", settings_repr)
        self.assertIn("session_secret=<redacted>", settings_repr)
        self.assertNotIn("a private lock-screen password", settings_repr)
        self.assertNotIn("x" * 32, settings_repr)
