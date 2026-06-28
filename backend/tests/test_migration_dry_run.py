"""Tests for P4 migration dry-run checks."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from serein.storage.migration import dry_run_migration

from test_entry_contract import CREATED_AT, ENTRY_ID, create_entry_fixture, write_json


class MigrationDryRunTests(TestCase):
    def test_empty_source_reports_zero_entries_without_writing_target(self) -> None:
        with TemporaryDirectory() as source_dir, TemporaryDirectory() as target_dir:
            target_entries = Path(target_dir) / "entries"

            report = dry_run_migration(Path(source_dir), Path(target_dir))

        self.assertEqual(report.entry_count, 0)
        self.assertEqual(report.migratable_count, 0)
        self.assertEqual(report.blocked_count, 0)
        self.assertFalse(target_entries.exists())

    def test_valid_v1_source_reports_migratable_entry(self) -> None:
        with TemporaryDirectory() as source_dir:
            entries_dir = Path(source_dir) / "entries"
            entry_dir = create_entry_fixture(entries_dir)

            report = dry_run_migration(Path(source_dir))

        self.assertEqual(report.entry_count, 1)
        self.assertEqual(report.migratable_count, 1)
        self.assertEqual(report.blocked_count, 0)
        self.assertEqual(report.comment_count, 0)
        self.assertEqual(report.media_count, 0)
        self.assertEqual(report.entries[0].detected_format, "v1")
        self.assertEqual(report.entries[0].entry_id, ENTRY_ID)
        self.assertEqual(report.entries[0].created_at, CREATED_AT)
        self.assertEqual(report.entries[0].target_name, entry_dir.name)
        self.assertGreater(report.entries[0].content_bytes, 0)

    def test_single_entry_directory_can_be_checked_directly(self) -> None:
        with TemporaryDirectory() as source_dir:
            entry_dir = create_entry_fixture(Path(source_dir))

            report = dry_run_migration(entry_dir)

        self.assertEqual(report.entry_count, 1)
        self.assertEqual(report.migratable_count, 1)
        self.assertEqual(report.entries[0].source_path, str(entry_dir))

    def test_legacy_source_reports_old_fields_and_target_name(self) -> None:
        with TemporaryDirectory() as source_dir:
            entry_dir = create_legacy_entry_fixture(Path(source_dir))

            report = dry_run_migration(Path(source_dir))

        self.assertEqual(report.entry_count, 1)
        self.assertEqual(report.migratable_count, 1)
        self.assertEqual(report.blocked_count, 0)
        entry = report.entries[0]
        self.assertEqual(entry.detected_format, "legacy")
        self.assertEqual(entry.entry_id, ENTRY_ID)
        self.assertEqual(entry.created_at, CREATED_AT)
        self.assertEqual(entry.target_name, f"202606230014-{ENTRY_ID}")
        self.assertEqual(entry.comment_count, 1)
        self.assertEqual(entry.media_count, 1)
        self.assertEqual(entry.source_path, str(entry_dir))
        self.assertEqual(
            entry.old_metadata_fields,
            ("date", "revision", "tags", "updated_at"),
        )
        self.assertTrue(
            any(issue.code == "old_metadata_fields" for issue in entry.issues)
        )

    def test_invalid_legacy_entry_is_blocked(self) -> None:
        with TemporaryDirectory() as source_dir:
            entry_dir = create_legacy_entry_fixture(Path(source_dir))
            (entry_dir / "content.md").unlink()

            report = dry_run_migration(Path(source_dir))

        self.assertEqual(report.entry_count, 1)
        self.assertEqual(report.migratable_count, 0)
        self.assertEqual(report.blocked_count, 1)
        self.assertTrue(
            any(
                issue.code == "missing_required_files"
                for issue in report.entries[0].issues
            )
        )

    def test_report_text_does_not_include_diary_body(self) -> None:
        secret_body = "这是一段不应该出现在报告里的正文。\n"
        with TemporaryDirectory() as source_dir:
            entries_dir = Path(source_dir) / "entries"
            create_entry_fixture(entries_dir, content=secret_body)

            report = dry_run_migration(Path(source_dir))

        report_text = report.to_text()
        self.assertNotIn(secret_body.strip(), report_text)
        self.assertIn("content_bytes=", report_text)

    def test_unknown_directory_is_reported_as_blocked(self) -> None:
        with TemporaryDirectory() as source_dir:
            bad_dir = Path(source_dir) / "entries" / "not-an-entry"
            bad_dir.mkdir(parents=True)

            report = dry_run_migration(Path(source_dir))

        self.assertEqual(report.entry_count, 1)
        self.assertEqual(report.blocked_count, 1)
        self.assertEqual(report.entries[0].detected_format, "unknown")
        self.assertTrue(
            any(
                issue.code == "unknown_directory_format"
                for issue in report.entries[0].issues
            )
        )


def create_legacy_entry_fixture(root: Path) -> Path:
    entry_dir = root / "entries" / "2026" / f"2026-06-23-{ENTRY_ID}"
    entry_dir.mkdir(parents=True)
    write_json(
        entry_dir / "metadata.json",
        {
            "schema_version": 1,
            "id": ENTRY_ID,
            "created_at": CREATED_AT,
            "date": "2026-06-23",
            "title": "早期条目",
            "updated_at": CREATED_AT,
            "revision": 3,
            "tags": ["旧字段"],
        },
    )
    (entry_dir / "content.md").write_text("旧日记正文。\n", encoding="utf-8")
    write_json(
        entry_dir / "comments.json",
        {
            "schema_version": 1,
            "comments": [
                {
                    "id": "55c4e14d-0506-45fd-9e0f-3e8a6d6aa40b",
                    "created_at": "2026-06-23T00:20:00+08:00",
                    "content": "一条旧评论。",
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
                    "original": "media/original/tree.jpg",
                }
            ],
        },
    )
    return entry_dir
