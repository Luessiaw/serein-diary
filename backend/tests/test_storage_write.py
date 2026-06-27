"""Tests for immutable entry creation and soft deletion."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from uuid import UUID

from serein.storage.entry import EntryValidationError
from serein.storage.repository import create_entry, mark_entry_deleted, scan_entry_summaries


ENTRY_ID = UUID("77777777-7777-4777-8777-777777777777")
CREATED_AT = datetime.fromisoformat("2026-06-23T00:14:23+08:00")


class StorageWriteTests(TestCase):
    def test_create_entry_writes_v1_fact_files_atomically(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)

            entry = create_entry(
                root,
                title="  夜雨  ",
                content="今天下了一场雨。\n",
                created_at=CREATED_AT,
                entry_id=ENTRY_ID,
            )

            entry_dir = root / "entries" / f"202606230014-{ENTRY_ID}"
            self.assertEqual(entry.path, entry_dir)
            self.assertTrue((entry_dir / "metadata.json").is_file())
            self.assertTrue((entry_dir / "content.md").is_file())
            self.assertTrue((entry_dir / "comments.json").is_file())
            self.assertTrue((entry_dir / "media-manifest.json").is_file())
            self.assertTrue((entry_dir / "media" / "original").is_dir())
            self.assertTrue((entry_dir / "media" / "preview").is_dir())
            self.assertEqual(entry.metadata.title, "夜雨")
            self.assertEqual(entry.content, "今天下了一场雨。\n")

    def test_create_entry_omits_blank_title(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)

            entry = create_entry(
                root,
                title=" ",
                content="没有标题。\n",
                created_at=CREATED_AT,
                entry_id=ENTRY_ID,
            )

            metadata = read_json(entry.path / "metadata.json")
            self.assertNotIn("title", metadata)
            self.assertIsNone(entry.metadata.title)

    def test_create_entry_rejects_blank_content(self) -> None:
        with TemporaryDirectory() as data_dir:
            with self.assertRaisesRegex(EntryValidationError, "content.md must not be blank"):
                create_entry(Path(data_dir), content="  \n", created_at=CREATED_AT)

    def test_create_entry_rejects_naive_created_at(self) -> None:
        with TemporaryDirectory() as data_dir:
            with self.assertRaisesRegex(EntryValidationError, "UTC offset"):
                create_entry(
                    Path(data_dir),
                    content="content\n",
                    created_at=datetime(2026, 6, 23, 0, 14, 23),
                )

    def test_create_entry_does_not_overwrite_existing_id(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            create_entry(root, content="first\n", created_at=CREATED_AT, entry_id=ENTRY_ID)

            with self.assertRaisesRegex(EntryValidationError, "already exists"):
                create_entry(root, content="second\n", created_at=CREATED_AT, entry_id=ENTRY_ID)

            self.assertEqual(scan_entry_summaries(root)[0].content_excerpt, "first")

    def test_mark_entry_deleted_sets_deleted_at_without_changing_content(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            entry = create_entry(root, content="content\n", created_at=CREATED_AT, entry_id=ENTRY_ID)
            deleted_at = datetime.fromisoformat("2026-06-24T09:30:00+08:00")

            deleted = mark_entry_deleted(root, ENTRY_ID, deleted_at=deleted_at)

            self.assertEqual(deleted.metadata.deleted_at, deleted_at)
            self.assertEqual(deleted.content, "content\n")
            self.assertEqual((entry.path / "content.md").read_text(encoding="utf-8"), "content\n")
            self.assertTrue(scan_entry_summaries(root)[0].deleted)

    def test_mark_entry_deleted_rejects_missing_entry(self) -> None:
        with TemporaryDirectory() as data_dir:
            with self.assertRaisesRegex(EntryValidationError, "entry not found"):
                mark_entry_deleted(Path(data_dir), ENTRY_ID)

    def test_mark_entry_deleted_rejects_already_deleted_entry(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            create_entry(root, content="content\n", created_at=CREATED_AT, entry_id=ENTRY_ID)
            mark_entry_deleted(root, ENTRY_ID, deleted_at=CREATED_AT)

            with self.assertRaisesRegex(EntryValidationError, "already deleted"):
                mark_entry_deleted(root, ENTRY_ID, deleted_at=datetime.now(timezone.utc))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
