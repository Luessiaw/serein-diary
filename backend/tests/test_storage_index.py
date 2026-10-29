"""Tests for the rebuildable SQLite entry index."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from serein.storage.index import (
    SCHEMA_VERSION,
    DateCount,
    count_entries_by_date,
    get_index_path,
    get_index_schema_version,
    list_indexed_entries,
    rebuild_index,
)
from serein.storage.repository import mark_entry_deleted
from test_entry_contract import create_entry_fixture, read_json, write_json


class StorageIndexTests(TestCase):
    def test_rebuilds_empty_index(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)

            index_path = rebuild_index(root)

            self.assertEqual(index_path, get_index_path(root))
            self.assertTrue(index_path.is_file())
            self.assertEqual(get_index_schema_version(index_path), SCHEMA_VERSION)
            self.assertEqual(list_indexed_entries(index_path), [])

    def test_rebuilds_a_v1_index_that_lacks_source_kind(self) -> None:
        """An index written before schema 2 must upgrade in place, not crash."""

        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            entries = root / "entries"
            entry_id = "11111111-1111-4111-8111-111111111111"
            create_entry_fixture(
                entries,
                name=f"202606230930-{entry_id}",
                entry_id=entry_id,
                created_at="2026-06-23T09:30:00+08:00",
            )
            index_path = get_index_path(root)
            index_path.parent.mkdir(parents=True)
            with sqlite3.connect(index_path) as connection:
                connection.executescript(
                    """
                    CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    INSERT INTO meta(key, value) VALUES ('schema_version', '1');
                    CREATE TABLE entries (
                        id TEXT PRIMARY KEY,
                        created_at TEXT NOT NULL,
                        local_date TEXT NOT NULL,
                        entry_path TEXT NOT NULL,
                        title TEXT,
                        content_excerpt TEXT NOT NULL,
                        comment_count INTEGER NOT NULL,
                        media_count INTEGER NOT NULL,
                        deleted INTEGER NOT NULL CHECK (deleted IN (0, 1))
                    );
                    """
                )

            rebuilt = rebuild_index(root, index_path)

            self.assertEqual(get_index_schema_version(rebuilt), SCHEMA_VERSION)
            listed = list_indexed_entries(rebuilt)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].source_kind, "human")

    def test_index_keeps_source_kind_per_entry(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            entries = root / "entries"
            human_id = "11111111-1111-4111-8111-111111111111"
            ai_id = "22222222-2222-4222-8222-222222222222"
            create_entry_fixture(
                entries,
                name=f"202606230930-{human_id}",
                entry_id=human_id,
                created_at="2026-06-23T09:30:00+08:00",
            )
            ai_dir = create_entry_fixture(
                entries,
                name=f"202606231030-{ai_id}",
                entry_id=ai_id,
                created_at="2026-06-23T10:30:00+08:00",
            )
            metadata = read_json(ai_dir / "metadata.json")
            metadata["source_kind"] = "ai-dialogue"
            write_json(ai_dir / "metadata.json", metadata)

            index_path = rebuild_index(root)
            listed = list_indexed_entries(index_path)

        self.assertEqual(
            [(str(summary.id), summary.source_kind) for summary in listed],
            [(human_id, "human"), (ai_id, "ai-dialogue")],
        )

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
