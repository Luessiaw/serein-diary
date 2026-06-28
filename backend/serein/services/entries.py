"""Entry service layer for formal P5 diary APIs."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from serein.storage.entry import DiaryEntry, EntryValidationError
from serein.storage.index import (
    get_index_path,
    list_indexed_entries,
    rebuild_index,
)
from serein.storage.repository import (
    EntrySummary,
    create_entry,
    find_entry_by_id,
    mark_entry_deleted,
)


DEFAULT_PAGE_LIMIT = 30
MAX_PAGE_LIMIT = 100
CURSOR_SEPARATOR = "|"


@dataclass(frozen=True)
class EntryServiceError(ValueError):
    """Stable service error intended for API-layer translation."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class EntrySummaryItem:
    """Entry summary plus its opaque pagination cursor."""

    id: UUID
    created_at: datetime
    path: Path
    title: str | None
    content_excerpt: str
    comment_count: int
    media_count: int
    deleted: bool
    cursor: str


@dataclass(frozen=True)
class EntryDetailItem:
    """Full entry facts plus the entry cursor."""

    entry: DiaryEntry
    cursor: str


@dataclass(frozen=True)
class EntryPage:
    """One page of entry summaries for the continuous diary stream."""

    items: tuple[EntrySummaryItem, ...]
    limit: int
    has_more: bool
    next_before: str | None


@dataclass(frozen=True)
class EntryCursor:
    """Decoded cursor facts."""

    created_at: datetime
    entry_id: UUID


class EntryService:
    """Coordinate entry storage, index reads, and write-after-index refresh."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)

    def list_entries(
        self,
        *,
        limit: int = DEFAULT_PAGE_LIMIT,
        before: str | None = None,
        include_deleted: bool = False,
    ) -> EntryPage:
        """Return a created_at-ascending page for the diary stream."""

        normalized_limit = normalize_limit(limit)
        try:
            summaries = self._read_indexed_entries(include_deleted=include_deleted)
        except EntryValidationError as error:
            raise map_storage_error(error) from error
        if before is None:
            page_source = summaries
        else:
            cursor = decode_entry_cursor(before)
            page_source = [
                summary
                for summary in summaries
                if entry_sort_key(summary) < (cursor.created_at, cursor.entry_id)
            ]

        selected = page_source[-normalized_limit:]
        has_more = len(page_source) > normalized_limit
        items = tuple(summary_to_item(summary) for summary in selected)
        next_before = items[0].cursor if has_more and items else None

        return EntryPage(
            items=items,
            limit=normalized_limit,
            has_more=has_more,
            next_before=next_before,
        )

    def get_entry(self, entry_id: UUID) -> EntryDetailItem:
        """Read one entry detail from fact files."""

        try:
            entry = find_entry_by_id(self.data_dir, entry_id)
        except EntryValidationError as error:
            raise map_storage_error(error) from error

        return EntryDetailItem(
            entry=entry,
            cursor=encode_entry_cursor(entry.metadata.created_at, entry.metadata.id),
        )

    def create_entry(
        self,
        *,
        content: str,
        title: str | None = None,
        created_at: datetime | None = None,
        entry_id: UUID | None = None,
    ) -> EntryDetailItem:
        """Create an immutable entry and refresh the rebuildable index."""

        try:
            entry = create_entry(
                self.data_dir,
                content=content,
                title=title,
                created_at=created_at,
                entry_id=entry_id,
            )
            self.refresh_index()
        except EntryValidationError as error:
            raise map_storage_error(error) from error

        return EntryDetailItem(
            entry=entry,
            cursor=encode_entry_cursor(entry.metadata.created_at, entry.metadata.id),
        )

    def delete_entry(
        self,
        entry_id: UUID,
        *,
        deleted_at: datetime | None = None,
    ) -> EntryDetailItem:
        """Soft-delete one entry and refresh the rebuildable index."""

        try:
            entry = mark_entry_deleted(
                self.data_dir,
                entry_id,
                deleted_at=deleted_at,
            )
            self.refresh_index()
        except EntryValidationError as error:
            raise map_storage_error(error) from error

        return EntryDetailItem(
            entry=entry,
            cursor=encode_entry_cursor(entry.metadata.created_at, entry.metadata.id),
        )

    def refresh_index(self) -> Path:
        """Rebuild the derived SQLite index from fact files."""

        return rebuild_index(self.data_dir)

    def _read_indexed_entries(self, *, include_deleted: bool) -> list[EntrySummary]:
        index_path = get_index_path(self.data_dir)
        if not index_path.exists():
            self.refresh_index()
        try:
            return list_indexed_entries(index_path, include_deleted=include_deleted)
        except Exception:
            self.refresh_index()
            return list_indexed_entries(index_path, include_deleted=include_deleted)


def normalize_limit(limit: int) -> int:
    """Validate and clamp the page limit."""

    if limit < 1:
        raise EntryServiceError("invalid_request", "limit must be at least 1")
    return min(limit, MAX_PAGE_LIMIT)


def summary_to_item(summary: EntrySummary) -> EntrySummaryItem:
    """Attach an opaque cursor to an indexed summary."""

    return EntrySummaryItem(
        id=summary.id,
        created_at=summary.created_at,
        path=summary.path,
        title=summary.title,
        content_excerpt=summary.content_excerpt,
        comment_count=summary.comment_count,
        media_count=summary.media_count,
        deleted=summary.deleted,
        cursor=encode_entry_cursor(summary.created_at, summary.id),
    )


def encode_entry_cursor(created_at: datetime, entry_id: UUID) -> str:
    """Encode the service cursor as an opaque base64url string."""

    payload = f"{created_at.isoformat()}{CURSOR_SEPARATOR}{entry_id}"
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def decode_entry_cursor(value: str) -> EntryCursor:
    """Decode and validate one opaque entry cursor."""

    try:
        padded = value + "=" * (-len(value) % 4)
        payload = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        raw_created_at, raw_entry_id = payload.split(CURSOR_SEPARATOR, maxsplit=1)
        created_at = datetime.fromisoformat(raw_created_at)
        entry_id = UUID(raw_entry_id)
    except (ValueError, UnicodeDecodeError, binascii.Error) as error:
        raise EntryServiceError("invalid_cursor", "Invalid pagination cursor") from error

    if created_at.utcoffset() is None:
        raise EntryServiceError("invalid_cursor", "Invalid pagination cursor")

    return EntryCursor(created_at=created_at, entry_id=entry_id)


def entry_sort_key(summary: EntrySummary) -> tuple[datetime, UUID]:
    """Return the stable order key used by cursors."""

    return summary.created_at, summary.id


def map_storage_error(error: EntryValidationError) -> EntryServiceError:
    """Map storage validation errors to stable service error codes."""

    message = str(error)
    if "not found" in message:
        return EntryServiceError("entry_not_found", "Entry not found")
    if "already deleted" in message:
        return EntryServiceError("entry_deleted", "Entry is already deleted")
    return EntryServiceError("storage_contract_error", message)
