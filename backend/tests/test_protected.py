"""Tests for the minimal protected API skeleton."""

from unittest import TestCase

from serein.api.auth import AuthenticatedSession
from serein.api.protected import get_protected


class ProtectedEndpointTests(TestCase):
    def test_protected_route_returns_minimal_capability_info(self) -> None:
        response = get_protected(AuthenticatedSession(subject="single-admin"))

        self.assertEqual(
            response.model_dump(),
            {
                "authenticated": True,
                "subject": "single-admin",
                "capabilities": ["session:read"],
            },
        )
