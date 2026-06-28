"""Tests for the formal P5 entries API."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from uuid import UUID

from fastapi import HTTPException, Response

from serein.api.auth import NO_STORE_HEADER
from serein.api.auth import AuthenticatedSession, require_authenticated_session
from serein.api.entries import (
    EntryCreateRequest,
    create_entry_endpoint,
    delete_entry,
    get_entry,
    list_entry_dates,
    list_entries,
)
from serein.config import Settings

from test_entry_contract import create_entry_fixture


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
            empty_page = list_entries(list_response, request, session=session)
            self.assertEqual(empty_page.items, [])
            self.assertEqual(empty_page.page.has_more, False)
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
            self.assertEqual(created.content_excerpt, "这是一条 API 测试日记。")
            self.assertEqual(created.comment_count, 0)
            self.assertEqual(created.media_count, 0)
            self.assertEqual(created.comments, [])
            self.assertEqual(created.media, [])
            self.assertFalse(created.deleted)
            self.assertTrue(created.cursor)

            page = list_entries(Response(), request, session=session)
            self.assertEqual(len(page.items), 1)
            self.assertEqual(page.items[0].id, created.id)
            self.assertEqual(page.items[0].content_excerpt, "这是一条 API 测试日记。")
            self.assertFalse(page.page.has_more)
            self.assertIsNone(page.page.next_before)

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

            visible_page = list_entries(Response(), request, session=session)
            self.assertEqual(visible_page.items, [])
            all_page = list_entries(
                Response(),
                request,
                include_deleted=True,
                session=session,
            )
            self.assertEqual(len(all_page.items), 1)
            self.assertTrue(all_page.items[0].deleted)

    def test_list_entries_uses_formal_cursor_pagination(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            request = self.make_request(root)
            first_id = "11111111-1111-4111-8111-111111111111"
            second_id = "22222222-2222-4222-8222-222222222222"
            third_id = "33333333-3333-4333-8333-333333333333"
            create_entry_fixture(
                root / "entries",
                name=f"202606230910-{first_id}",
                entry_id=first_id,
                created_at="2026-06-23T09:10:00+08:00",
            )
            create_entry_fixture(
                root / "entries",
                name=f"202606230920-{second_id}",
                entry_id=second_id,
                created_at="2026-06-23T09:20:00+08:00",
            )
            create_entry_fixture(
                root / "entries",
                name=f"202606230930-{third_id}",
                entry_id=third_id,
                created_at="2026-06-23T09:30:00+08:00",
            )

            first_page = list_entries(
                Response(),
                request,
                limit=2,
                session=self.make_session(),
            )
            second_page = list_entries(
                Response(),
                request,
                limit=2,
                before=first_page.page.next_before,
                session=self.make_session(),
            )

        self.assertEqual([str(item.id) for item in first_page.items], [second_id, third_id])
        self.assertTrue(first_page.page.has_more)
        self.assertIsNotNone(first_page.page.next_before)
        self.assertEqual([str(item.id) for item in second_page.items], [first_id])
        self.assertFalse(second_page.page.has_more)

    def test_list_entry_dates_returns_calendar_counts(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            request = self.make_request(root)
            first_id = "11111111-1111-4111-8111-111111111111"
            second_id = "22222222-2222-4222-8222-222222222222"
            third_id = "33333333-3333-4333-8333-333333333333"
            create_entry_fixture(
                root / "entries",
                name=f"202606230910-{first_id}",
                entry_id=first_id,
                created_at="2026-06-23T09:10:00+08:00",
            )
            create_entry_fixture(
                root / "entries",
                name=f"202606231010-{second_id}",
                entry_id=second_id,
                created_at="2026-06-23T10:10:00+08:00",
            )
            create_entry_fixture(
                root / "entries",
                name=f"202607010800-{third_id}",
                entry_id=third_id,
                created_at="2026-07-01T08:00:00+08:00",
            )
            delete_entry(UUID(first_id), request, Response(), self.make_session())

            response = Response()
            dates = list_entry_dates(
                response,
                request,
                from_date=date.fromisoformat("2026-06-01"),
                to_date=date.fromisoformat("2026-06-30"),
                session=self.make_session(),
            )
            dates_with_deleted = list_entry_dates(
                Response(),
                request,
                include_deleted=True,
                session=self.make_session(),
            )

        self.assertEqual(response.headers["cache-control"], NO_STORE_HEADER)
        self.assertEqual(
            [(item.date.isoformat(), item.count) for item in dates.dates],
            [("2026-06-23", 1)],
        )
        self.assertEqual(
            [(item.date.isoformat(), item.count) for item in dates_with_deleted.dates],
            [("2026-06-23", 2), ("2026-07-01", 1)],
        )

    def test_list_entry_dates_rejects_inverted_range(self) -> None:
        with TemporaryDirectory() as data_dir:
            request = self.make_request(Path(data_dir))

            with self.assertRaises(HTTPException) as context:
                list_entry_dates(
                    Response(),
                    request,
                    from_date=date.fromisoformat("2026-07-01"),
                    to_date=date.fromisoformat("2026-06-01"),
                    session=self.make_session(),
                )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail["error"]["code"], "invalid_request")

    def test_create_rejects_blank_content_with_stable_error(self) -> None:
        with TemporaryDirectory() as data_dir:
            with self.assertRaises(HTTPException) as context:
                create_entry_endpoint(
                    EntryCreateRequest(title="空", content=" "),
                    self.make_request(Path(data_dir)),
                    Response(),
                    self.make_session(),
                )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail["error"]["code"], "invalid_request")
        self.assertEqual(
            context.exception.detail["error"]["message"],
            "content must not be blank",
        )

    def test_invalid_cursor_returns_stable_error(self) -> None:
        with TemporaryDirectory() as data_dir:
            request = self.make_request(Path(data_dir))

            with self.assertRaises(HTTPException) as context:
                list_entries(
                    Response(),
                    request,
                    before="not-a-cursor",
                    session=self.make_session(),
                )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail["error"]["code"], "invalid_cursor")

    def test_get_missing_entry_returns_stable_404(self) -> None:
        with TemporaryDirectory() as data_dir:
            request = self.make_request(Path(data_dir))

            with self.assertRaises(HTTPException) as context:
                get_entry(
                    UUID("77777777-7777-4777-8777-777777777777"),
                    Response(),
                    request,
                    self.make_session(),
                )

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail["error"]["code"], "entry_not_found")
