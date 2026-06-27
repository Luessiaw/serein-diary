"""Tests for the public health endpoint."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from serein.config import (
    Settings,
)
from serein.api.health import build_health_response, router


class HealthEndpointTests(TestCase):
    def test_health_route_is_registered(self) -> None:
        route_paths = {getattr(route, "path", "") for route in router.routes}

        self.assertIn("/health", route_paths)

    def test_health_returns_safe_status(self) -> None:
        with TemporaryDirectory() as data_dir:
            settings = Settings(
                data_dir=Path(data_dir),
                timezone="Asia/Shanghai",
                admin_password="a private lock-screen password",
                session_secret="x" * 32,
            )
            response = build_health_response(settings)

        body = response.model_dump()
        response_text = response.model_dump_json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["config"]["ready"], True)
        self.assertEqual(body["config"]["data_dir"], "configured")
        self.assertEqual(body["config"]["timezone"], "Asia/Shanghai")
        self.assertNotIn(str(settings.data_dir), response_text)
        self.assertNotIn(settings.admin_password, response_text)
        self.assertNotIn(settings.session_secret, response_text)
