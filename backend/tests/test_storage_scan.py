"""Tests for filesystem entry scanning."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from serein.storage.entry import EntryValidationError
from serein.storage.repository import scan_entry_summaries
from test_entry_contract import create_entry_fixture, write_json


class StorageScanTests(TestCase):
    def test_empty_data_dir_returns_empty_list(self) -> None:
        with TemporaryDirectory() as data_dir:
            summaries = scan_entry_summaries(Path(data_dir))

        self.assertEqual(summaries, [])

    def test_scans_flat_entries_sorted_by_created_at(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            entries = root / "entries"
            first_id = "11111111-1111-4111-8111-111111111111"
            second_id = "22222222-2222-4222-8222-222222222222"
            third_id = "33333333-3333-4333-8333-333333333333"
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
                title=None,
                content="第一篇内容。\n",
            )
            create_entry_fixture(
                entries,
                name=f"202612312359-{third_id}",
                entry_id=third_id,
                created_at="2026-12-31T23:59:00+08:00",
                title="第三篇",
                content="第三篇内容。\n",
            )

            summaries = scan_entry_summaries(root)

        self.assertEqual([str(summary.id) for summary in summaries], [first_id, second_id, third_id])
        self.assertEqual(summaries[0].path, Path("entries") / f"202401010010-{first_id}")
        self.assertEqual(summaries[0].title, None)
        self.assertEqual(summaries[0].content_excerpt, "第一篇内容。")

    def test_summary_counts_comments_and_media(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            entries = root / "entries"
            entry_id = "44444444-4444-4444-8444-444444444444"
            entry_dir = create_entry_fixture(
                entries,
                name=f"202606230014-{entry_id}",
                entry_id=entry_id,
                created_at="2026-06-23T00:14:00+08:00",
            )
            write_json(
                entry_dir / "comments.json",
                {
                    "schema_version": 1,
                    "comments": [
                        {
                            "id": "55c4e14d-0506-45fd-9e0f-3e8a6d6aa40b",
                            "created_at": "2026-06-23T00:20:00+08:00",
                            "content": "comment",
                            "anchor": None,
                        }
                    ],
                },
            )
            write_json(
                entry_dir / "media-manifest.json",
                {
                    "schema_version": 1,
                    "media": [
                        {
                            "id": "8c21d9b4-77c8-4eb2-8ea9-2c72d7c76f13",
                            "kind": "image",
                            "original": "media/original/8c21d9b4-77c8-4eb2-8ea9-2c72d7c76f13.jpg",
                        }
                    ],
                },
            )

            summary = scan_entry_summaries(root)[0]

        self.assertEqual(summary.comment_count, 1)
        self.assertEqual(summary.media_count, 1)
        self.assertFalse(summary.deleted)

    def test_reports_directory_metadata_mismatch(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            entries = root / "entries"
            entry_id = "55555555-5555-4555-8555-555555555555"
            create_entry_fixture(
                entries,
                name=f"202606230015-{entry_id}",
                entry_id=entry_id,
                created_at="2026-06-23T00:14:00+08:00",
            )

            with self.assertRaisesRegex(EntryValidationError, "minute prefix"):
                scan_entry_summaries(root)

    def test_rejects_non_directory_inside_entries(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            entries = root / "entries"
            entries.mkdir()
            (entries / "README.txt").write_text("not an entry", encoding="utf-8")

            with self.assertRaisesRegex(EntryValidationError, "non-directory"):
                scan_entry_summaries(root)

    def test_rejects_symlink_entry_directory(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            entries = root / "entries"
            target = root / "target"
            entries.mkdir()
            target.mkdir()
            (entries / "202606230014-66666666-6666-4666-8666-666666666666").symlink_to(
                target,
                target_is_directory=True,
            )

            with self.assertRaisesRegex(EntryValidationError, "symlinks"):
                scan_entry_summaries(root)

    def test_rejects_entries_symlink(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            target = root / "target"
            target.mkdir()
            (root / "entries").symlink_to(target, target_is_directory=True)

            with self.assertRaisesRegex(EntryValidationError, "entries must be a directory"):
                scan_entry_summaries(root)
