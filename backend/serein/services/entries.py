"""Entry service layer for formal P5 diary APIs."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

from serein.storage.entry import DiaryEntry, EntryValidationError
from serein.storage.index import (
    DateCount,
    count_entries_by_date,
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
    has_older: bool
    has_newer: bool
    older_cursor: str | None
    newer_cursor: str | None


@dataclass(frozen=True)
class EntryWindow:
    """A bounded entry slice around one local diary date."""

    target_date: date
    items: tuple[EntrySummaryItem, ...]
    older_count: int
    newer_count: int
    target_count: int
    has_older: bool
    has_newer: bool
    older_cursor: str | None
    newer_cursor: str | None


@dataclass(frozen=True)
class EntryDateCount:
    """Number of visible entries on one local diary date."""

    date: str
    count: int


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
        older_than: str | None = None,
        newer_than: str | None = None,
        include_deleted: bool = False,
    ) -> EntryPage:
        """Return a created_at-ascending page for the diary stream."""

        normalized_limit = normalize_limit(limit)
        if older_than is not None and newer_than is not None:
            raise EntryServiceError(
                "invalid_request",
                "older_than and newer_than cannot be used together",
            )
        try:
            summaries = self._read_indexed_entries(include_deleted=include_deleted)
        except EntryValidationError as error:
            raise map_storage_error(error) from error
        if newer_than is not None:
            cursor = decode_entry_cursor(newer_than)
            page_source = [
                summary
                for summary in summaries
                if entry_sort_key(summary) > (cursor.created_at, cursor.entry_id)
            ]
            selected = page_source[:normalized_limit]
            has_newer = len(page_source) > normalized_limit
            items = tuple(summary_to_item(summary) for summary in selected)
            return EntryPage(
                items=items,
                limit=normalized_limit,
                has_older=bool(items),
                has_newer=has_newer,
                older_cursor=items[0].cursor if items else None,
                newer_cursor=items[-1].cursor if has_newer and items else None,
            )

        if older_than is None:
            page_source = summaries
        else:
            cursor = decode_entry_cursor(older_than)
            page_source = [
                summary
                for summary in summaries
                if entry_sort_key(summary) < (cursor.created_at, cursor.entry_id)
            ]

        selected = page_source[-normalized_limit:]
        has_older = len(page_source) > normalized_limit
        items = tuple(summary_to_item(summary) for summary in selected)

        return EntryPage(
            items=items,
            limit=normalized_limit,
            has_older=has_older,
            has_newer=older_than is not None,
            older_cursor=items[0].cursor if has_older and items else None,
            newer_cursor=items[-1].cursor if older_than is not None and items else None,
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

    def list_entry_dates(
        self,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        include_deleted: bool = False,
    ) -> tuple[EntryDateCount, ...]:
        """Return local diary dates that contain entries."""

        if from_date is not None and to_date is not None and from_date > to_date:
            raise EntryServiceError(
                "invalid_request",
                "from_date must be earlier than or equal to to_date",
            )

        try:
            date_counts = self._read_date_counts(include_deleted=include_deleted)
        except EntryValidationError as error:
            raise map_storage_error(error) from error

        return tuple(
            EntryDateCount(date=item.date, count=item.count)
            for item in date_counts
            if is_date_in_range(item.date, from_date=from_date, to_date=to_date)
        )

    def get_entry_window(
        self,
        *,
        target_date: date,
        older_count: int,
        newer_count: int,
        include_deleted: bool = False,
    ) -> EntryWindow:
        """Return entries on a date plus bounded context before and after it."""

        normalized_older_count = normalize_window_count(older_count, "older_count")
        normalized_newer_count = normalize_window_count(newer_count, "newer_count")
        try:
            summaries = self._read_indexed_entries(include_deleted=include_deleted)
        except EntryValidationError as error:
            raise map_storage_error(error) from error

        target_indices = [
            index
            for index, summary in enumerate(summaries)
            if summary.created_at.date() == target_date
        ]
        if not target_indices:
            return EntryWindow(
                target_date=target_date,
                items=(),
                older_count=normalized_older_count,
                newer_count=normalized_newer_count,
                target_count=0,
                has_older=False,
                has_newer=False,
                older_cursor=None,
                newer_cursor=None,
            )

        first_target_index = target_indices[0]
        last_target_index = target_indices[-1]
        start_index = max(0, first_target_index - normalized_older_count)
        end_index = min(len(summaries), last_target_index + normalized_newer_count + 1)
        selected = summaries[start_index:end_index]
        items = tuple(summary_to_item(summary) for summary in selected)
        has_older = start_index > 0
        has_newer = end_index < len(summaries)

        return EntryWindow(
            target_date=target_date,
            items=items,
            older_count=normalized_older_count,
            newer_count=normalized_newer_count,
            target_count=len(target_indices),
            has_older=has_older,
            has_newer=has_newer,
            older_cursor=items[0].cursor if has_older and items else None,
            newer_cursor=items[-1].cursor if has_newer and items else None,
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

    def _read_date_counts(self, *, include_deleted: bool) -> list[DateCount]:
        index_path = get_index_path(self.data_dir)
        if not index_path.exists():
            self.refresh_index()
        try:
            return count_entries_by_date(index_path, include_deleted=include_deleted)
        except Exception:
            self.refresh_index()
            return count_entries_by_date(index_path, include_deleted=include_deleted)


def normalize_limit(limit: int) -> int:
    """Validate and clamp the page limit."""

    if limit < 1:
        raise EntryServiceError("invalid_request", "limit must be at least 1")
    return min(limit, MAX_PAGE_LIMIT)


def normalize_window_count(value: int, field_name: str) -> int:
    """Validate and clamp one date-window side count."""

    if value < 0:
        raise EntryServiceError("invalid_request", f"{field_name} must be at least 0")
    return min(value, MAX_PAGE_LIMIT)


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


def is_date_in_range(
    value: str,
    *,
    from_date: date | None,
    to_date: date | None,
) -> bool:
    """Return whether an ISO date string is within the optional range."""

    entry_date = date.fromisoformat(value)
    if from_date is not None and entry_date < from_date:
        return False
    if to_date is not None and entry_date > to_date:
        return False
    return True


def map_storage_error(error: EntryValidationError) -> EntryServiceError:
    """Map storage validation errors to stable service error codes."""

    message = str(error)
    if "not found" in message:
        return EntryServiceError("entry_not_found", "Entry not found")
    if "already deleted" in message:
        return EntryServiceError("entry_deleted", "Entry is already deleted")
    return EntryServiceError("storage_contract_error", message)
