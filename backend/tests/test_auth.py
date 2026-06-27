"""Tests for minimal lock-screen access protection."""

from __future__ import annotations

from http.cookies import SimpleCookie
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase

from fastapi import HTTPException, Response

from serein.api.auth import (
    LoginRequest,
    NO_STORE_HEADER,
    get_session,
    login,
    logout,
    require_authenticated_session,
)
from serein.config import Settings
from serein.security import SESSION_COOKIE_NAME


class AuthEndpointTests(TestCase):
    def make_settings(self) -> Settings:
        return Settings(
            data_dir=Path("/tmp"),
            timezone="Asia/Shanghai",
            admin_password="a private lock-screen password",
            session_secret="x" * 32,
        )

    def make_request(self, cookies: dict[str, str] | None = None) -> SimpleNamespace:
        return SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(settings=self.make_settings())),
            cookies=cookies or {},
        )

    def test_session_is_false_without_cookie(self) -> None:
        raw_response = Response()

        response = get_session(self.make_request(), raw_response)

        self.assertEqual(response.model_dump(), {"authenticated": False, "subject": None})
        self.assertEqual(raw_response.headers["cache-control"], NO_STORE_HEADER)

    def test_login_rejects_wrong_password(self) -> None:
        with self.assertRaises(HTTPException) as context:
            login(LoginRequest(password="wrong"), self.make_request(), Response())

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(context.exception.detail, "Invalid password.")

    def test_login_sets_httponly_cookie_and_session_is_valid(self) -> None:
        raw_response = Response()

        response = login(
            LoginRequest(password="a private lock-screen password"),
            self.make_request(),
            raw_response,
        )

        self.assertEqual(
            response.model_dump(),
            {"authenticated": True, "subject": "single-admin"},
        )
        cookie_header = raw_response.headers["set-cookie"]
        self.assertIn(SESSION_COOKIE_NAME, cookie_header)
        self.assertIn("HttpOnly", cookie_header)
        self.assertIn("SameSite=lax", cookie_header)

        cookie = SimpleCookie()
        cookie.load(cookie_header)
        session_raw_response = Response()
        session_response = get_session(
            self.make_request({SESSION_COOKIE_NAME: cookie[SESSION_COOKIE_NAME].value}),
            session_raw_response,
        )
        self.assertEqual(
            session_response.model_dump(),
            {"authenticated": True, "subject": "single-admin"},
        )
        self.assertEqual(session_raw_response.headers["cache-control"], NO_STORE_HEADER)

    def test_logout_clears_cookie(self) -> None:
        raw_response = Response()

        response = logout(raw_response)

        self.assertEqual(response.model_dump(), {"authenticated": False, "subject": None})
        self.assertIn(SESSION_COOKIE_NAME, raw_response.headers["set-cookie"])
        self.assertIn("Max-Age=0", raw_response.headers["set-cookie"])
        self.assertEqual(raw_response.headers["cache-control"], NO_STORE_HEADER)

    def test_protected_dependency_rejects_missing_cookie(self) -> None:
        with self.assertRaises(HTTPException) as context:
            require_authenticated_session(self.make_request())

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(context.exception.detail, "Authentication required.")

    def test_protected_dependency_accepts_valid_cookie(self) -> None:
        raw_response = Response()
        login(
            LoginRequest(password="a private lock-screen password"),
            self.make_request(),
            raw_response,
        )
        cookie = SimpleCookie()
        cookie.load(raw_response.headers["set-cookie"])

        session = require_authenticated_session(
            self.make_request({SESSION_COOKIE_NAME: cookie[SESSION_COOKIE_NAME].value})
        )

        self.assertEqual(session.model_dump(), {"subject": "single-admin"})
