"""Tests for the minimal protected API skeleton."""

from unittest import TestCase

from fastapi import Response

from serein.api.auth import NO_STORE_HEADER
from serein.api.auth import AuthenticatedSession
from serein.api.protected import get_protected


class ProtectedEndpointTests(TestCase):
    def test_protected_route_returns_minimal_capability_info(self) -> None:
        raw_response = Response()

        response = get_protected(raw_response, AuthenticatedSession(subject="single-admin"))

        self.assertEqual(
            response.model_dump(),
            {
                "authenticated": True,
                "subject": "single-admin",
                "capabilities": ["session:read"],
            },
        )
        self.assertEqual(raw_response.headers["cache-control"], NO_STORE_HEADER)
