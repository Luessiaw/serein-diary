"""Filesystem repository helpers for Serein v1 entries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from serein.storage.entry import DiaryEntry, EntryValidationError, read_entry


CONTENT_EXCERPT_MAX_CHARS = 120


@dataclass(frozen=True)
class EntrySummary:
    """Lightweight entry facts for listing, indexing, and pagination."""

    id: UUID
    created_at: datetime
    path: Path
    title: str | None
    content_excerpt: str
    comment_count: int
    media_count: int
    deleted: bool


def scan_entry_summaries(data_dir: Path) -> list[EntrySummary]:
    """Scan DIARY_DATA_DIR/entries and return entry summaries sorted by time."""

    entries_dir = Path(data_dir) / "entries"
    if not entries_dir.exists():
        return []
    if entries_dir.is_symlink() or not entries_dir.is_dir():
        raise EntryValidationError("entries must be a directory inside DIARY_DATA_DIR")

    summaries = []
    for entry_dir in sorted(entries_dir.iterdir(), key=lambda path: path.name):
        if entry_dir.is_symlink():
            raise EntryValidationError("entry directories must not be symlinks")
        if not entry_dir.is_dir():
            raise EntryValidationError(
                f"entries contains a non-directory item: {entry_dir.name}"
            )

        summaries.append(create_entry_summary(read_entry(entry_dir), data_dir))

    return sorted(summaries, key=lambda summary: summary.created_at)


def create_entry_summary(entry: DiaryEntry, data_dir: Path) -> EntrySummary:
    """Create a safe lightweight summary from a fully parsed entry."""

    return EntrySummary(
        id=entry.metadata.id,
        created_at=entry.metadata.created_at,
        path=entry.path.relative_to(data_dir),
        title=entry.metadata.title,
        content_excerpt=create_content_excerpt(entry.content),
        comment_count=len(entry.comments.comments),
        media_count=len(entry.media_manifest.media),
        deleted=entry.metadata.deleted_at is not None,
    )


def create_content_excerpt(content: str) -> str:
    """Create a compact, single-line content excerpt."""

    excerpt = re.sub(r"\s+", " ", content).strip()
    if len(excerpt) <= CONTENT_EXCERPT_MAX_CHARS:
        return excerpt

    return excerpt[: CONTENT_EXCERPT_MAX_CHARS - 1].rstrip() + "…"
