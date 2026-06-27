"""Tests for the rebuildable SQLite entry index."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from serein.storage.index import (
    DateCount,
    count_entries_by_date,
    get_index_path,
    get_index_schema_version,
    list_indexed_entries,
    rebuild_index,
)
from serein.storage.repository import mark_entry_deleted
from test_entry_contract import create_entry_fixture


class StorageIndexTests(TestCase):
    def test_rebuilds_empty_index(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)

            index_path = rebuild_index(root)

            self.assertEqual(index_path, get_index_path(root))
            self.assertTrue(index_path.is_file())
            self.assertEqual(get_index_schema_version(index_path), 1)
            self.assertEqual(list_indexed_entries(index_path), [])

    def test_rebuilds_index_from_multiple_years_sorted_by_created_at(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            entries = root / "entries"
            first_id = "11111111-1111-4111-8111-111111111111"
            second_id = "22222222-2222-4222-8222-222222222222"
            create_entry_fixture(
                entries,
                name=f"202606230930-{second_id}",
                entry_id=second_id,
                created_at="2026-06-23T09:30:00+08:00",
                title="第二篇",
                content="第二篇内容。\n",
            )
            create_entry_fixture(
                entries,
                name=f"202401010010-{first_id}",
                entry_id=first_id,
                created_at="2024-01-01T00:10:00+08:00",
                title="第一篇",
                content="第一篇内容。\n",
            )

            index_path = rebuild_index(root)
            indexed = list_indexed_entries(index_path)

        self.assertEqual([str(summary.id) for summary in indexed], [first_id, second_id])
        self.assertEqual(indexed[0].path, Path("entries") / f"202401010010-{first_id}")
        self.assertEqual(indexed[0].title, "第一篇")
        self.assertEqual(indexed[0].content_excerpt, "第一篇内容。")

    def test_rebuild_overwrites_stale_index(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            entries = root / "entries"
            first_id = "11111111-1111-4111-8111-111111111111"
            create_entry_fixture(
                entries,
                name=f"202401010010-{first_id}",
                entry_id=first_id,
                created_at="2024-01-01T00:10:00+08:00",
            )
            index_path = rebuild_index(root)
            self.assertEqual(len(list_indexed_entries(index_path)), 1)

            second_id = "22222222-2222-4222-8222-222222222222"
            create_entry_fixture(
                entries,
                name=f"202606230930-{second_id}",
                entry_id=second_id,
                created_at="2026-06-23T09:30:00+08:00",
            )
            index_path.unlink()

            rebuild_index(root)
            indexed = list_indexed_entries(index_path)

        self.assertEqual(len(indexed), 2)

    def test_index_counts_by_date_excludes_deleted_by_default(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            entries = root / "entries"
            first_id = "11111111-1111-4111-8111-111111111111"
            second_id = "22222222-2222-4222-8222-222222222222"
            create_entry_fixture(
                entries,
                name=f"202606230930-{first_id}",
                entry_id=first_id,
                created_at="2026-06-23T09:30:00+08:00",
            )
            create_entry_fixture(
                entries,
                name=f"202606231010-{second_id}",
                entry_id=second_id,
                created_at="2026-06-23T10:10:00+08:00",
            )
            mark_entry_deleted(root, first_id)

            index_path = rebuild_index(root)

            self.assertEqual(count_entries_by_date(index_path), [DateCount("2026-06-23", 1)])
            self.assertEqual(
                count_entries_by_date(index_path, include_deleted=True),
                [DateCount("2026-06-23", 2)],
            )
            self.assertEqual(len(list_indexed_entries(index_path, include_deleted=False)), 1)
