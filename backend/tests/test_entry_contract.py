"""Tests for P4 v1 entry data contract validation."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from serein.storage.entry import EntryValidationError, read_entry


ENTRY_ID = "0b6d2ebd-74f8-4a5c-9515-aaf4076b6189"
CREATED_AT = "2026-06-23T00:14:23+08:00"
ENTRY_DIR_NAME = f"202606230014-{ENTRY_ID}"


class EntryContractTests(TestCase):
    def test_reads_valid_v1_entry(self) -> None:
        with TemporaryDirectory() as data_dir:
            entry_dir = create_entry_fixture(Path(data_dir))

            entry = read_entry(entry_dir)

        self.assertEqual(str(entry.metadata.id), ENTRY_ID)
        self.assertEqual(entry.metadata.created_at.isoformat(), CREATED_AT)
        self.assertEqual(entry.content, "今天下了一场很轻的雨。\n")
        self.assertEqual(entry.comments.comments, [])
        self.assertEqual(entry.media_manifest.media, [])

    def test_rejects_missing_required_file(self) -> None:
        with TemporaryDirectory() as data_dir:
            entry_dir = create_entry_fixture(Path(data_dir))
            (entry_dir / "content.md").unlink()

            with self.assertRaisesRegex(EntryValidationError, "content.md"):
                read_entry(entry_dir)

    def test_rejects_bad_json(self) -> None:
        with TemporaryDirectory() as data_dir:
            entry_dir = create_entry_fixture(Path(data_dir))
            (entry_dir / "metadata.json").write_text("{", encoding="utf-8")

            with self.assertRaisesRegex(EntryValidationError, "valid JSON"):
                read_entry(entry_dir)

    def test_rejects_unknown_metadata_field_and_old_date_field(self) -> None:
        with TemporaryDirectory() as data_dir:
            entry_dir = create_entry_fixture(Path(data_dir))
            metadata = read_json(entry_dir / "metadata.json")
            metadata["date"] = "2026-06-23"
            write_json(entry_dir / "metadata.json", metadata)

            with self.assertRaisesRegex(EntryValidationError, "date"):
                read_entry(entry_dir)

    def test_rejects_updated_at_and_revision(self) -> None:
        with TemporaryDirectory() as data_dir:
            entry_dir = create_entry_fixture(Path(data_dir))
            metadata = read_json(entry_dir / "metadata.json")
            metadata["updated_at"] = CREATED_AT
            metadata["revision"] = 1
            write_json(entry_dir / "metadata.json", metadata)

            with self.assertRaisesRegex(EntryValidationError, "updated_at"):
                read_entry(entry_dir)

    def test_rejects_invalid_entry_directory_name(self) -> None:
        with TemporaryDirectory() as data_dir:
            entry_dir = create_entry_fixture(Path(data_dir), name=f"2026/{ENTRY_DIR_NAME}")

            with self.assertRaisesRegex(EntryValidationError, "YYYYMMDDHHmm"):
                read_entry(entry_dir)

    def test_rejects_directory_uuid_mismatch(self) -> None:
        with TemporaryDirectory() as data_dir:
            entry_dir = create_entry_fixture(
                Path(data_dir),
                name="202606230014-1c4cbc1c-e81f-42be-932e-0bd135290af3",
            )

            with self.assertRaisesRegex(EntryValidationError, "UUID"):
                read_entry(entry_dir)

    def test_rejects_directory_time_mismatch(self) -> None:
        with TemporaryDirectory() as data_dir:
            entry_dir = create_entry_fixture(
                Path(data_dir),
                name=f"202606230015-{ENTRY_ID}",
            )

            with self.assertRaisesRegex(EntryValidationError, "minute prefix"):
                read_entry(entry_dir)

    def test_rejects_created_at_without_offset(self) -> None:
        with TemporaryDirectory() as data_dir:
            entry_dir = create_entry_fixture(Path(data_dir))
            metadata = read_json(entry_dir / "metadata.json")
            metadata["created_at"] = "2026-06-23T00:14:23"
            write_json(entry_dir / "metadata.json", metadata)

            with self.assertRaisesRegex(EntryValidationError, "UTC offset"):
                read_entry(entry_dir)

    def test_rejects_blank_content_without_leaking_body(self) -> None:
        with TemporaryDirectory() as data_dir:
            entry_dir = create_entry_fixture(Path(data_dir))
            (entry_dir / "content.md").write_text("   \n", encoding="utf-8")

            with self.assertRaisesRegex(EntryValidationError, "content.md must not be blank"):
                read_entry(entry_dir)

    def test_rejects_crlf_content(self) -> None:
        with TemporaryDirectory() as data_dir:
            entry_dir = create_entry_fixture(Path(data_dir))
            (entry_dir / "content.md").write_text("line 1\r\nline 2\r\n", encoding="utf-8")

            with self.assertRaisesRegex(EntryValidationError, "LF line endings"):
                read_entry(entry_dir)

    def test_rejects_comment_without_timezone(self) -> None:
        with TemporaryDirectory() as data_dir:
            entry_dir = create_entry_fixture(Path(data_dir))
            write_json(
                entry_dir / "comments.json",
                {
                    "schema_version": 1,
                    "comments": [
                        {
                            "id": "55c4e14d-0506-45fd-9e0f-3e8a6d6aa40b",
                            "created_at": "2026-06-23T00:20:00",
                            "content": "comment",
                            "anchor": None,
                        }
                    ],
                },
            )

            with self.assertRaisesRegex(EntryValidationError, "UTC offset"):
                read_entry(entry_dir)

    def test_accepts_quote_comment_anchor(self) -> None:
        with TemporaryDirectory() as data_dir:
            entry_dir = create_entry_fixture(Path(data_dir))
            write_json(
                entry_dir / "comments.json",
                {
                    "schema_version": 1,
                    "comments": [
                        {
                            "id": "55c4e14d-0506-45fd-9e0f-3e8a6d6aa40b",
                            "created_at": "2026-06-23T00:20:00+08:00",
                            "content": "comment",
                            "anchor": {
                                "type": "quote",
                                "selected_text": "雨",
                                "prefix": "轻的",
                                "suffix": "。",
                            },
                        }
                    ],
                },
            )

            entry = read_entry(entry_dir)

        self.assertEqual(entry.comments.comments[0].anchor.selected_text, "雨")

    def test_rejects_media_path_escape(self) -> None:
        with TemporaryDirectory() as data_dir:
            entry_dir = create_entry_fixture(Path(data_dir))
            write_json(
                entry_dir / "media-manifest.json",
                {
                    "schema_version": 1,
                    "media": [
                        {
                            "id": "8c21d9b4-77c8-4eb2-8ea9-2c72d7c76f13",
                            "kind": "image",
                            "original": "../secret.jpg",
                        }
                    ],
                },
            )

            with self.assertRaisesRegex(EntryValidationError, "safe relative path"):
                read_entry(entry_dir)


def create_entry_fixture(
    root: Path,
    name: str = ENTRY_DIR_NAME,
    entry_id: str = ENTRY_ID,
    created_at: str = CREATED_AT,
    title: str | None = "雨",
    content: str = "今天下了一场很轻的雨。\n",
) -> Path:
    entry_dir = root / name
    entry_dir.mkdir(parents=True)
    metadata = {
        "schema_version": 1,
        "id": entry_id,
        "created_at": created_at,
    }
    if title is not None:
        metadata["title"] = title

    write_json(entry_dir / "metadata.json", metadata)
    (entry_dir / "content.md").write_text(content, encoding="utf-8")
    write_json(entry_dir / "comments.json", {"schema_version": 1, "comments": []})
    write_json(entry_dir / "media-manifest.json", {"schema_version": 1, "media": []})
    return entry_dir


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
