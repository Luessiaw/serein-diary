"""Filesystem repository helpers for Serein v1 entries."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from serein.storage.entry import DiaryEntry, EntryValidationError, read_entry, read_json_file


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


def create_entry(
    data_dir: Path,
    content: str,
    title: str | None = None,
    created_at: datetime | None = None,
    entry_id: UUID | None = None,
) -> DiaryEntry:
    """Atomically create a new immutable v1 entry and return its parsed facts."""

    created_at = normalize_created_at(created_at)
    entry_id = entry_id or uuid4()
    entry_name = create_entry_directory_name(created_at, entry_id)
    entries_dir = ensure_entries_dir(data_dir)
    final_dir = entries_dir / entry_name

    if final_dir.exists():
        raise EntryValidationError("entry already exists")

    if not content.strip():
        raise EntryValidationError("content.md must not be blank")
    if "\r" in content:
        raise EntryValidationError("content.md must use LF line endings")

    temp_dir = Path(tempfile.mkdtemp(prefix=".tmp-entry-", dir=entries_dir))
    try:
        write_new_entry_files(temp_dir, entry_id, created_at, title, content)
        temp_dir.replace(final_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise

    return read_entry(final_dir)


def mark_entry_deleted(
    data_dir: Path,
    entry_id: UUID,
    deleted_at: datetime | None = None,
) -> DiaryEntry:
    """Soft-delete an entry by adding metadata.deleted_at."""

    deleted_at = normalize_created_at(deleted_at)
    entry = find_entry_by_id(data_dir, entry_id)
    if entry.metadata.deleted_at is not None:
        raise EntryValidationError("entry is already deleted")

    metadata_path = entry.path / "metadata.json"
    metadata = read_json_file(metadata_path)
    if not isinstance(metadata, dict):
        raise EntryValidationError("metadata.json must be an object")

    metadata["deleted_at"] = deleted_at.isoformat()
    write_json_file_atomic(metadata_path, metadata)
    return read_entry(entry.path)


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


def ensure_entries_dir(data_dir: Path) -> Path:
    """Create DIARY_DATA_DIR/entries if needed and reject unsafe variants."""

    entries_dir = Path(data_dir) / "entries"
    if entries_dir.exists() and (entries_dir.is_symlink() or not entries_dir.is_dir()):
        raise EntryValidationError("entries must be a directory inside DIARY_DATA_DIR")

    entries_dir.mkdir(parents=True, exist_ok=True)
    return entries_dir


def create_entry_directory_name(created_at: datetime, entry_id: UUID) -> str:
    """Create the v1 YYYYMMDDHHmm-<uuid> directory name."""

    return f"{created_at.strftime('%Y%m%d%H%M')}-{entry_id}"


def normalize_created_at(value: datetime | None) -> datetime:
    """Return a timezone-aware timestamp suitable for entry facts."""

    timestamp = value or datetime.now(timezone.utc).astimezone()
    if timestamp.utcoffset() is None:
        raise EntryValidationError("timestamp must include a UTC offset")

    return timestamp


def write_new_entry_files(
    entry_dir: Path,
    entry_id: UUID,
    created_at: datetime,
    title: str | None,
    content: str,
) -> None:
    """Write all v1 fact files into a temporary entry directory."""

    metadata: dict[str, object] = {
        "schema_version": 1,
        "id": str(entry_id),
        "created_at": created_at.isoformat(),
    }
    normalized_title = (title or "").strip()
    if normalized_title:
        metadata["title"] = normalized_title

    write_json_file(entry_dir / "metadata.json", metadata)
    (entry_dir / "content.md").write_text(content, encoding="utf-8", newline="\n")
    write_json_file(entry_dir / "comments.json", {"schema_version": 1, "comments": []})
    write_json_file(entry_dir / "media-manifest.json", {"schema_version": 1, "media": []})
    (entry_dir / "media" / "original").mkdir(parents=True)
    (entry_dir / "media" / "preview").mkdir(parents=True)


def write_json_file(path: Path, value: dict) -> None:
    """Write JSON in a stable, human-readable form."""

    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_json_file_atomic(path: Path, value: dict) -> None:
    """Atomically replace a JSON file."""

    temp_path = path.with_name(f".{path.name}.tmp")
    try:
        write_json_file(temp_path, value)
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def find_entry_by_id(data_dir: Path, entry_id: UUID) -> DiaryEntry:
    """Find and parse one entry by UUID."""

    entries_dir = Path(data_dir) / "entries"
    if not entries_dir.exists():
        raise EntryValidationError("entry not found")

    matches = []
    for entry_dir in entries_dir.iterdir():
        if entry_dir.is_dir() and entry_dir.name.endswith(f"-{entry_id}"):
            matches.append(entry_dir)

    if not matches:
        raise EntryValidationError("entry not found")
    if len(matches) > 1:
        raise EntryValidationError("multiple entries match the same id")

    return read_entry(matches[0])
