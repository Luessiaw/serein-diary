"""Tests for the P5 entry service layer."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from uuid import UUID

from serein.services.entries import (
    EntryService,
    EntryServiceError,
    decode_entry_cursor,
    encode_entry_cursor,
)
from serein.storage.index import get_index_path, list_indexed_entries, rebuild_index

from test_entry_contract import create_entry_fixture


class EntryServiceTests(TestCase):
    def test_lists_empty_directory_and_creates_missing_index(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            service = EntryService(root)

            page = service.list_entries(limit=30)

            self.assertEqual(page.items, ())
            self.assertEqual(page.limit, 30)
            self.assertFalse(page.has_more)
            self.assertIsNone(page.next_before)
            self.assertTrue(get_index_path(root).is_file())

    def test_lists_recent_entries_ascending_with_before_cursor(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            created_ids = create_ordered_entries(root, count=5)
            service = EntryService(root)

            first_page = service.list_entries(limit=2)
            second_page = service.list_entries(limit=2, before=first_page.next_before)

        self.assertEqual([str(item.id) for item in first_page.items], created_ids[3:5])
        self.assertTrue(first_page.has_more)
        self.assertIsNotNone(first_page.next_before)
        self.assertEqual([str(item.id) for item in second_page.items], created_ids[1:3])
        self.assertTrue(second_page.has_more)

    def test_final_page_has_no_next_before(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            created_ids = create_ordered_entries(root, count=3)
            service = EntryService(root)

            first_page = service.list_entries(limit=2)
            final_page = service.list_entries(limit=2, before=first_page.next_before)

        self.assertEqual([str(item.id) for item in final_page.items], created_ids[:1])
        self.assertFalse(final_page.has_more)
        self.assertIsNone(final_page.next_before)

    def test_lists_later_entries_with_after_cursor(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            created_ids = create_ordered_entries(root, count=5)
            service = EntryService(root)

            early_page = service.list_entries(limit=2, before=service.list_entries(limit=2).next_before)
            later_page = service.list_entries(limit=2, after=early_page.items[-1].cursor)

        self.assertEqual([str(item.id) for item in early_page.items], created_ids[1:3])
        self.assertEqual([str(item.id) for item in later_page.items], created_ids[3:5])
        self.assertFalse(later_page.has_more)
        self.assertIsNone(later_page.next_after)

    def test_invalid_cursor_and_limit_raise_stable_errors(self) -> None:
        with TemporaryDirectory() as data_dir:
            service = EntryService(Path(data_dir))

            with self.assertRaises(EntryServiceError) as cursor_error:
                service.list_entries(before="not-a-cursor")
            with self.assertRaises(EntryServiceError) as limit_error:
                service.list_entries(limit=0)
            with self.assertRaises(EntryServiceError) as direction_error:
                service.list_entries(before="abc", after="def")

        self.assertEqual(cursor_error.exception.code, "invalid_cursor")
        self.assertEqual(limit_error.exception.code, "invalid_request")
        self.assertEqual(direction_error.exception.code, "invalid_request")

    def test_get_entry_returns_detail_and_cursor(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            entry_id = "11111111-1111-4111-8111-111111111111"
            create_entry_fixture(
                root / "entries",
                name=f"202606230930-{entry_id}",
                entry_id=entry_id,
                created_at="2026-06-23T09:30:00+08:00",
            )
            service = EntryService(root)

            detail = service.get_entry(UUID(entry_id))

        self.assertEqual(str(detail.entry.metadata.id), entry_id)
        self.assertEqual(decode_entry_cursor(detail.cursor).entry_id, UUID(entry_id))

    def test_create_entry_refreshes_index(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            service = EntryService(root)
            rebuild_index(root)
            self.assertEqual(list_indexed_entries(get_index_path(root)), [])

            created = service.create_entry(
                title="服务层创建",
                content="服务层写入正文。\n",
            )
            indexed = list_indexed_entries(get_index_path(root))

        self.assertEqual(len(indexed), 1)
        self.assertEqual(indexed[0].id, created.entry.metadata.id)
        self.assertEqual(indexed[0].title, "服务层创建")

    def test_delete_entry_refreshes_index_and_filters_deleted_by_default(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            entry_id = "11111111-1111-4111-8111-111111111111"
            create_entry_fixture(
                root / "entries",
                name=f"202606230930-{entry_id}",
                entry_id=entry_id,
                created_at="2026-06-23T09:30:00+08:00",
            )
            service = EntryService(root)
            rebuild_index(root)

            deleted = service.delete_entry(UUID(entry_id))
            visible_page = service.list_entries()
            all_page = service.list_entries(include_deleted=True)

        self.assertIsNotNone(deleted.entry.metadata.deleted_at)
        self.assertEqual(visible_page.items, ())
        self.assertEqual(len(all_page.items), 1)
        self.assertTrue(all_page.items[0].deleted)

    def test_list_entry_dates_counts_visible_entries_and_filters_range(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            first_id = "11111111-1111-4111-8111-111111111111"
            second_id = "22222222-2222-4222-8222-222222222222"
            third_id = "33333333-3333-4333-8333-333333333333"
            create_entry_fixture(
                root / "entries",
                name=f"202606230930-{first_id}",
                entry_id=first_id,
                created_at="2026-06-23T09:30:00+08:00",
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
            service = EntryService(root)
            service.delete_entry(UUID(first_id))

            visible_dates = service.list_entry_dates()
            all_dates = service.list_entry_dates(include_deleted=True)
            july_dates = service.list_entry_dates(
                from_date=date.fromisoformat("2026-07-01"),
                to_date=date.fromisoformat("2026-07-31"),
            )

        self.assertEqual(
            [(item.date, item.count) for item in visible_dates],
            [("2026-06-23", 1), ("2026-07-01", 1)],
        )
        self.assertEqual(
            [(item.date, item.count) for item in all_dates],
            [("2026-06-23", 2), ("2026-07-01", 1)],
        )
        self.assertEqual(
            [(item.date, item.count) for item in july_dates],
            [("2026-07-01", 1)],
        )

    def test_list_entry_dates_rejects_inverted_range(self) -> None:
        with TemporaryDirectory() as data_dir:
            service = EntryService(Path(data_dir))

            with self.assertRaises(EntryServiceError) as error:
                service.list_entry_dates(
                    from_date=date.fromisoformat("2026-07-01"),
                    to_date=date.fromisoformat("2026-06-01"),
                )

        self.assertEqual(error.exception.code, "invalid_request")

    def test_get_entry_window_returns_target_day_and_surrounding_entries(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            created_ids = create_ordered_entries(root, count=6)
            service = EntryService(root)

            window = service.get_entry_window(
                target_date=date.fromisoformat("2026-06-23"),
                before_count=2,
                after_count=1,
            )

        self.assertEqual([str(item.id) for item in window.items], created_ids)
        self.assertEqual(window.target_count, 6)
        self.assertFalse(window.has_earlier)
        self.assertFalse(window.has_later)
        self.assertIsNone(window.earlier_before)
        self.assertIsNone(window.later_after)

    def test_get_entry_window_bounds_context_around_middle_date(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            ids = []
            for index, day in enumerate(range(1, 8), start=1):
                entry_id = f"{index:08d}-{index:04d}-4{index:03d}-8{index:03d}-{index:012d}"
                ids.append(entry_id)
                create_entry_fixture(
                    root / "entries",
                    name=f"202606{day:02d}0900-{entry_id}",
                    entry_id=entry_id,
                    created_at=f"2026-06-{day:02d}T09:00:00+08:00",
                )
            service = EntryService(root)

            window = service.get_entry_window(
                target_date=date.fromisoformat("2026-06-04"),
                before_count=2,
                after_count=1,
            )

        self.assertEqual([str(item.id) for item in window.items], ids[1:5])
        self.assertEqual(window.target_count, 1)
        self.assertTrue(window.has_earlier)
        self.assertTrue(window.has_later)
        self.assertEqual(decode_entry_cursor(window.earlier_before).entry_id, UUID(ids[1]))
        self.assertEqual(decode_entry_cursor(window.later_after).entry_id, UUID(ids[4]))

    def test_get_entry_window_returns_empty_for_date_without_entries(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            create_ordered_entries(root, count=2)
            service = EntryService(root)

            window = service.get_entry_window(
                target_date=date.fromisoformat("2026-07-01"),
                before_count=2,
                after_count=2,
            )

        self.assertEqual(window.items, ())
        self.assertEqual(window.target_count, 0)
        self.assertFalse(window.has_earlier)
        self.assertFalse(window.has_later)

    def test_get_entry_window_rejects_negative_counts(self) -> None:
        with TemporaryDirectory() as data_dir:
            service = EntryService(Path(data_dir))

            with self.assertRaises(EntryServiceError) as error:
                service.get_entry_window(
                    target_date=date.fromisoformat("2026-06-23"),
                    before_count=-1,
                    after_count=0,
                )

        self.assertEqual(error.exception.code, "invalid_request")

    def test_missing_entry_raises_service_error(self) -> None:
        with TemporaryDirectory() as data_dir:
            service = EntryService(Path(data_dir))

            with self.assertRaises(EntryServiceError) as error:
                service.get_entry(UUID("11111111-1111-4111-8111-111111111111"))

        self.assertEqual(error.exception.code, "entry_not_found")

    def test_cursor_round_trip(self) -> None:
        entry_id = UUID("11111111-1111-4111-8111-111111111111")
        created_at = create_aware_datetime()

        cursor = encode_entry_cursor(created_at, entry_id)
        decoded = decode_entry_cursor(cursor)

        self.assertEqual(decoded.created_at, created_at)
        self.assertEqual(decoded.entry_id, entry_id)


def create_ordered_entries(root: Path, count: int) -> list[str]:
    ids = []
    entries = root / "entries"
    for index in range(count):
        item_number = index + 1
        entry_id = f"{item_number:08d}-{item_number:04d}-4{item_number:03d}-8{item_number:03d}-{item_number:012d}"
        ids.append(entry_id)
        minute = 10 + index
        create_entry_fixture(
            entries,
            name=f"2026062309{minute:02d}-{entry_id}",
            entry_id=entry_id,
            created_at=f"2026-06-23T09:{minute:02d}:00+08:00",
            title=f"第 {item_number} 篇",
            content=f"第 {item_number} 篇内容。\n",
        )
    return ids


def create_aware_datetime():
    return datetime.fromisoformat("2026-06-23T09:30:00+08:00")
