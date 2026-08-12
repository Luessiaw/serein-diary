"""Tests for immutable entry creation and soft deletion."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from uuid import UUID

from serein.storage.entry import EntryValidationError
from serein.storage.repository import (
    create_entry,
    get_entry_history_version,
    list_entry_history,
    mark_entry_deleted,
    scan_entry_summaries,
    update_entry,
)


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

    def test_update_entry_upgrades_v1_snapshots_and_changes_display_date(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            original = create_entry(
                root, title="Before", content="before\n", created_at=CREATED_AT, entry_id=ENTRY_ID
            )
            changed_at = datetime.fromisoformat("2026-06-24T09:30:00+08:00")

            updated = update_entry(
                root,
                ENTRY_ID,
                title="After",
                content="after\n",
                created_at=changed_at,
                expected_revision=0,
                updated_at=changed_at,
            )

            snapshot = original.path / "history" / "000000-initial"
            self.assertEqual(updated.metadata.schema_version, 2)
            self.assertEqual(updated.metadata.revision, 1)
            self.assertEqual(updated.metadata.created_at, changed_at)
            self.assertEqual(updated.content, "after\n")
            self.assertEqual((snapshot / "content.md").read_text(encoding="utf-8"), "before\n")
            self.assertEqual(read_json(snapshot / "metadata.json")["schema_version"], 1)
            self.assertEqual(scan_entry_summaries(root)[0].created_at, changed_at)

    def test_update_entry_rejects_stale_revision_without_overwriting_facts(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            create_entry(root, content="before\n", created_at=CREATED_AT, entry_id=ENTRY_ID)
            update_entry(
                root, ENTRY_ID, content="after\n", title=None,
                created_at=CREATED_AT, expected_revision=0, updated_at=CREATED_AT,
            )

            with self.assertRaisesRegex(EntryValidationError, "revision"):
                update_entry(
                    root, ENTRY_ID, content="stale\n", title=None,
                    created_at=CREATED_AT, expected_revision=0, updated_at=CREATED_AT,
                )

            self.assertEqual((root / "entries" / f"202606230014-{ENTRY_ID}" / "content.md").read_text(encoding="utf-8"), "after\n")

    def test_history_versions_are_read_only_predecessor_snapshots(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            create_entry(root, content="before\n", created_at=CREATED_AT, entry_id=ENTRY_ID)
            update_entry(root, ENTRY_ID, content="after\n", title=None, created_at=CREATED_AT, expected_revision=0, updated_at=CREATED_AT)
            update_entry(root, ENTRY_ID, content="latest\n", title="Latest", created_at=CREATED_AT, expected_revision=1, updated_at=CREATED_AT)

            versions = list_entry_history(root, ENTRY_ID)

            self.assertEqual([item.revision for item in versions], [0, 1])
            self.assertEqual([item.entry.content for item in versions], ["before\n", "after\n"])
            self.assertEqual(get_entry_history_version(root, ENTRY_ID, 1).entry.metadata.revision, 1)
            with self.assertRaisesRegex(EntryValidationError, "history revision not found"):
                get_entry_history_version(root, ENTRY_ID, 2)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
