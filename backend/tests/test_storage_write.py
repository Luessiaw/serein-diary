"""Tests for immutable entry creation and soft deletion."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from uuid import UUID

from PIL import Image

from serein.storage.entry import EntryValidationError
from serein.storage.repository import (
    ImageAttachment,
    attach_image,
    attach_images,
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

    def test_attach_image_writes_original_webp_preview_and_manifest(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            entry = create_entry(root, content="entry\n", created_at=CREATED_AT, entry_id=ENTRY_ID)
            image_bytes = create_png_bytes()

            attached = attach_image(root, ENTRY_ID, content=image_bytes, alt="  evening  ", expected_revision=0, created_at=CREATED_AT)

            item = attached.media_manifest.media[0]
            self.assertEqual(item.kind, "image")
            self.assertEqual(item.alt, "evening")
            self.assertTrue((entry.path / item.original).is_file())
            self.assertEqual((entry.path / item.original).read_bytes(), image_bytes)
            self.assertTrue((entry.path / item.preview).is_file())
            self.assertEqual(attached.metadata.revision, 1)
            self.assertEqual((entry.path / "history" / "000000-initial" / "media-manifest.json").is_file(), True)
            with Image.open(entry.path / item.preview) as preview:
                self.assertEqual(preview.format, "WEBP")

    def test_attach_image_rejects_non_image_before_writing_facts(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            entry = create_entry(root, content="entry\n", created_at=CREATED_AT, entry_id=ENTRY_ID)

            with self.assertRaisesRegex(EntryValidationError, "not a valid image"):
                attach_image(root, ENTRY_ID, content=b"not an image", alt=None, expected_revision=0, created_at=CREATED_AT)

            self.assertEqual(read_json(entry.path / "media-manifest.json")["media"], [])

    def test_attach_image_rejects_stale_revision_without_creating_media(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            entry = create_entry(root, content="entry\n", created_at=CREATED_AT, entry_id=ENTRY_ID)
            attach_image(root, ENTRY_ID, content=create_png_bytes(), alt=None, expected_revision=0, created_at=CREATED_AT)

            with self.assertRaisesRegex(EntryValidationError, "revision"):
                attach_image(root, ENTRY_ID, content=create_png_bytes(), alt=None, expected_revision=0, created_at=CREATED_AT)

            self.assertEqual(len(read_json(entry.path / "media-manifest.json")["media"]), 1)

    def test_attach_images_commits_ordered_batch_with_one_revision(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            entry = create_entry(root, content="entry\n", created_at=CREATED_AT, entry_id=ENTRY_ID)

            attached = attach_images(
                root,
                ENTRY_ID,
                attachments=(
                    ImageAttachment(create_png_bytes(), "first"),
                    ImageAttachment(create_png_bytes(), "second"),
                ),
                expected_revision=0,
                created_at=CREATED_AT,
            )

            self.assertEqual(attached.metadata.revision, 1)
            self.assertEqual([item.alt for item in attached.media_manifest.media], ["first", "second"])
            self.assertTrue(all((entry.path / item.original).is_file() for item in attached.media_manifest.media))

    def test_attach_images_rolls_back_entire_invalid_batch(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            entry = create_entry(root, content="entry\n", created_at=CREATED_AT, entry_id=ENTRY_ID)

            with self.assertRaisesRegex(EntryValidationError, "not a valid image"):
                attach_images(
                    root,
                    ENTRY_ID,
                    attachments=(
                        ImageAttachment(create_png_bytes(), "valid"),
                        ImageAttachment(b"not-image", "invalid"),
                    ),
                    expected_revision=0,
                    created_at=CREATED_AT,
                )

            self.assertEqual(read_json(entry.path / "media-manifest.json")["media"], [])
            self.assertEqual(list((entry.path / "media" / "original").iterdir()), [])


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def create_png_bytes() -> bytes:
    stream = __import__("io").BytesIO()
    Image.new("RGB", (6, 4), "#789abc").save(stream, format="PNG")
    return stream.getvalue()
