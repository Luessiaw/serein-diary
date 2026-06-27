"""Tests for the minimal entries API used to verify P4 storage."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

from fastapi import HTTPException
from fastapi import Response

from serein.api.auth import NO_STORE_HEADER
from serein.api.auth import AuthenticatedSession, require_authenticated_session
from serein.api.entries import (
    EntryCreateRequest,
    create_entry_endpoint,
    delete_entry,
    get_entry,
    list_entries,
)
from serein.config import Settings


class EntriesApiTests(TestCase):
    def make_request(self, data_dir: Path) -> SimpleNamespace:
        return SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    settings=Settings(
                        data_dir=data_dir,
                        timezone="Asia/Shanghai",
                        admin_password="a private lock-screen password",
                        session_secret="x" * 32,
                    )
                )
            ),
            cookies={},
        )

    def make_session(self) -> AuthenticatedSession:
        return AuthenticatedSession(subject="single-admin")

    def test_entries_dependency_rejects_unauthenticated_request(self) -> None:
        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(settings=None)),
            cookies={},
        )

        with self.assertRaises(HTTPException) as context:
            require_authenticated_session(request)

        self.assertEqual(context.exception.status_code, 401)

    def test_list_create_get_delete_entries_round_trip(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            request = self.make_request(root)
            session = self.make_session()

            list_response = Response()
            self.assertEqual(list_entries(list_response, request, session), [])
            self.assertEqual(list_response.headers["cache-control"], NO_STORE_HEADER)

            create_response = Response()
            created = create_entry_endpoint(
                EntryCreateRequest(title="测试", content="这是一条 API 测试日记。\n"),
                request,
                create_response,
                session,
            )
            self.assertEqual(create_response.headers["cache-control"], NO_STORE_HEADER)
            self.assertEqual(created.title, "测试")
            self.assertEqual(created.content, "这是一条 API 测试日记。\n")
            self.assertEqual(created.comment_count, 0)
            self.assertEqual(created.media_count, 0)
            self.assertFalse(created.deleted)
            self.assertTrue((root / created.path).is_dir())

            summaries = list_entries(Response(), request, session)
            self.assertEqual(len(summaries), 1)
            self.assertEqual(summaries[0].id, created.id)
            self.assertEqual(summaries[0].content_excerpt, "这是一条 API 测试日记。")

            get_response = Response()
            detail = get_entry(created.id, get_response, request, session)
            self.assertEqual(get_response.headers["cache-control"], NO_STORE_HEADER)
            self.assertEqual(detail.id, created.id)
            self.assertEqual(detail.content, created.content)

            delete_response = Response()
            deleted = delete_entry(created.id, request, delete_response, session)
            self.assertEqual(delete_response.headers["cache-control"], NO_STORE_HEADER)
            self.assertTrue(deleted.deleted)
            self.assertEqual(deleted.content, created.content)
            self.assertTrue(get_entry(created.id, Response(), request, session).deleted)

    def test_create_rejects_blank_content(self) -> None:
        with TemporaryDirectory() as data_dir:
            with self.assertRaises(HTTPException) as context:
                create_entry_endpoint(
                    EntryCreateRequest(title="空", content=" "),
                    self.make_request(Path(data_dir)),
                    Response(),
                    self.make_session(),
                )

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("content.md must not be blank", context.exception.detail)

    def test_get_missing_entry_returns_404(self) -> None:
        with TemporaryDirectory() as data_dir:
            request = self.make_request(Path(data_dir))

            with self.assertRaises(HTTPException) as context:
                get_entry(
                    "77777777-7777-4777-8777-777777777777",
                    Response(),
                    request,
                    self.make_session(),
                )

        self.assertEqual(context.exception.status_code, 404)
