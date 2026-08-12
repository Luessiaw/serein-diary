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

from serein.storage.entry import (
    DiaryEntry,
    EntryValidationError,
    parse_media_manifest,
    parse_metadata,
    read_content_file,
    read_entry,
    read_json_file,
)


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


@dataclass(frozen=True)
class EntryHistoryVersion:
    """One immutable predecessor snapshot, without comments or media bytes."""

    revision: int
    entry: DiaryEntry


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


def update_entry(
    data_dir: Path,
    entry_id: UUID,
    *,
    content: str,
    title: str | None,
    created_at: datetime,
    expected_revision: int,
    updated_at: datetime | None = None,
) -> DiaryEntry:
    """Atomically update a v2 entry after snapshotting its current facts."""

    if not content.strip():
        raise EntryValidationError("content.md must not be blank")
    if "\r" in content:
        raise EntryValidationError("content.md must use LF line endings")
    created_at = normalize_created_at(created_at)
    updated_at = normalize_created_at(updated_at)
    entry = find_entry_by_id(data_dir, entry_id)
    if entry.metadata.deleted_at is not None:
        raise EntryValidationError("entry is already deleted")
    current_revision = entry.metadata.revision or 0
    if expected_revision != current_revision:
        raise EntryValidationError("entry revision does not match current revision")

    history_dir = entry.path / "history"
    snapshot_name = (
        f"{current_revision:06d}-initial"
        if current_revision == 0
        else f"{current_revision:06d}-{updated_at.strftime('%Y%m%d%H%M%S')}-{uuid4()}"
    )
    snapshot_dir = history_dir / snapshot_name
    temp_history = Path(tempfile.mkdtemp(prefix=".tmp-history-", dir=entry.path))
    try:
        for name in ("metadata.json", "content.md", "media-manifest.json"):
            shutil.copy2(entry.path / name, temp_history / name)
        history_dir.mkdir(exist_ok=True)
        temp_history.replace(snapshot_dir)
    except Exception:
        shutil.rmtree(temp_history, ignore_errors=True)
        raise

    metadata = entry.metadata.model_dump(mode="json", exclude_none=True)
    metadata.update({
        "schema_version": 2,
        "created_at": created_at.isoformat(),
        "updated_at": updated_at.isoformat(),
        "revision": current_revision + 1,
    })
    normalized_title = (title or "").strip()
    if normalized_title:
        metadata["title"] = normalized_title
    else:
        metadata.pop("title", None)

    temp_dir = Path(tempfile.mkdtemp(prefix=".tmp-update-", dir=entry.path))
    try:
        write_json_file(temp_dir / "metadata.json", metadata)
        (temp_dir / "content.md").write_text(content, encoding="utf-8", newline="\n")
        original_metadata = (entry.path / "metadata.json").read_bytes()
        original_content = (entry.path / "content.md").read_bytes()
        for name in ("metadata.json", "content.md"):
            (temp_dir / name).replace(entry.path / name)
    except Exception:
        if "original_metadata" in locals():
            (entry.path / "metadata.json").write_bytes(original_metadata)
        if "original_content" in locals():
            (entry.path / "content.md").write_bytes(original_content)
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    return read_entry(entry.path)


def list_entry_history(data_dir: Path, entry_id: UUID) -> tuple[EntryHistoryVersion, ...]:
    """Read valid immutable snapshots in ascending revision order."""

    entry = find_entry_by_id(data_dir, entry_id)
    history_dir = entry.path / "history"
    if not history_dir.exists():
        return ()
    if history_dir.is_symlink() or not history_dir.is_dir():
        raise EntryValidationError("history must be a directory inside the entry")

    versions = []
    for snapshot_dir in sorted(history_dir.iterdir(), key=lambda path: path.name):
        if snapshot_dir.is_symlink() or not snapshot_dir.is_dir():
            raise EntryValidationError("history contains an unsafe snapshot")
        versions.append(read_history_snapshot(entry, snapshot_dir))
    return tuple(versions)


def get_entry_history_version(
    data_dir: Path, entry_id: UUID, revision: int
) -> EntryHistoryVersion:
    """Read one predecessor snapshot by the revision it represents."""

    for version in list_entry_history(data_dir, entry_id):
        if version.revision == revision:
            return version
    raise EntryValidationError("history revision not found")


def read_history_snapshot(entry: DiaryEntry, snapshot_dir: Path) -> EntryHistoryVersion:
    """Validate a history snapshot while binding it to the current entry identity."""

    match = re.fullmatch(r"(?P<revision>\d{6})-(?:initial|\d{14}-[0-9a-f-]{36})", snapshot_dir.name)
    if not match:
        raise EntryValidationError("history snapshot name is invalid")
    for name in ("metadata.json", "content.md", "media-manifest.json"):
        if not (snapshot_dir / name).is_file():
            raise EntryValidationError("history snapshot is missing required facts")
    metadata = parse_metadata(read_json_file(snapshot_dir / "metadata.json"))
    if metadata.id != entry.metadata.id:
        raise EntryValidationError("history snapshot entry id does not match")
    content = read_content_file(snapshot_dir / "content.md")
    manifest = parse_media_manifest(read_json_file(snapshot_dir / "media-manifest.json"))
    revision = int(match.group("revision"))
    return EntryHistoryVersion(
        revision=revision,
        entry=DiaryEntry(
            path=snapshot_dir,
            metadata=metadata,
            content=content,
            comments=entry.comments,
            media_manifest=manifest,
        ),
    )


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
    if entries_dir.is_symlink() or not entries_dir.is_dir():
        raise EntryValidationError("entries must be a directory inside DIARY_DATA_DIR")

    matches = []
    for entry_dir in entries_dir.iterdir():
        if entry_dir.is_symlink():
            raise EntryValidationError("entry directories must not be symlinks")
        if entry_dir.is_dir() and entry_dir.name.endswith(f"-{entry_id}"):
            matches.append(entry_dir)

    if not matches:
        raise EntryValidationError("entry not found")
    if len(matches) > 1:
        raise EntryValidationError("multiple entries match the same id")

    return read_entry(matches[0])
