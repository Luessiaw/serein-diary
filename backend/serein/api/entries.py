"""Formal authenticated entries API for P5 diary features."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from serein.api.auth import (
    AuthenticatedSession,
    mark_auth_response_uncacheable,
    require_authenticated_session,
)
from serein.config import Settings
from serein.services.entries import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    EntryDetailItem,
    EntryDateCount,
    EntryIndexRefreshResult,
    EntryPage,
    EntryService,
    EntryServiceError,
    EntrySummaryItem,
    EntryWindow,
)
from serein.storage.repository import create_content_excerpt


router = APIRouter(prefix="/entries", tags=["entries"])


class ApiErrorBody(BaseModel):
    """Stable API error body."""

    code: str
    message: str


class ApiErrorResponse(BaseModel):
    """Stable API error wrapper."""

    error: ApiErrorBody


class EntryCreateRequest(BaseModel):
    """Request for creating an immutable diary entry."""

    title: str | None = None
    content: str = Field(min_length=1)


class PageInfoResponse(BaseModel):
    """Pagination metadata for the continuous diary stream."""

    limit: int
    has_older: bool
    has_newer: bool
    older_cursor: str | None
    newer_cursor: str | None


class EntrySummaryResponse(BaseModel):
    """Entry summary returned by the formal entries API."""

    id: UUID
    created_at: datetime
    cursor: str
    title: str | None
    content_excerpt: str
    comment_count: int
    media_count: int
    deleted: bool


class CommentResponse(BaseModel):
    """Comment shape exposed by entry details."""

    id: UUID
    created_at: datetime
    content: str
    anchor: dict | None


class MediaItemResponse(BaseModel):
    """Media item shape exposed by entry details."""

    id: UUID
    kind: str
    url: str
    alt: str | None
    created_at: datetime | None


class EntryDetailResponse(EntrySummaryResponse):
    """Entry detail returned by the formal entries API."""

    content: str
    comments: list[CommentResponse]
    media: list[MediaItemResponse]


class EntryListResponse(BaseModel):
    """Paginated entry list response."""

    items: list[EntrySummaryResponse]
    page: PageInfoResponse


class EntryDateCountResponse(BaseModel):
    """One local date count for the calendar UI."""

    date: date
    count: int


class EntryDatesResponse(BaseModel):
    """Entry date count response."""

    dates: list[EntryDateCountResponse]


class EntryWindowInfoResponse(BaseModel):
    """Date-window metadata for calendar jump navigation."""

    target_date: date
    older_count: int
    newer_count: int
    target_count: int
    has_older: bool
    has_newer: bool
    older_cursor: str | None
    newer_cursor: str | None


class EntryWindowResponse(BaseModel):
    """Entries around one target date."""

    items: list[EntrySummaryResponse]
    window: EntryWindowInfoResponse


class EntryIndexRebuildResponse(BaseModel):
    """Safe response for a derived index rebuild."""

    rebuilt: bool
    total_entries: int
    visible_entries: int
    deleted_entries: int


@router.get("", response_model=EntryListResponse)
def list_entries(
    response: Response,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    older_than: str | None = None,
    newer_than: str | None = None,
    include_deleted: bool = False,
    session: AuthenticatedSession = Depends(require_authenticated_session),
) -> EntryListResponse:
    """Return a formal paginated entry list."""

    _ = session
    mark_auth_response_uncacheable(response)
    try:
        page = get_entry_service(request).list_entries(
            limit=limit,
            older_than=older_than,
            newer_than=newer_than,
            include_deleted=include_deleted,
        )
        return entry_page_to_response(page)
    except EntryServiceError as error:
        raise service_http_error(error) from error


@router.get("/window", response_model=EntryWindowResponse)
def get_entry_window(
    response: Response,
    request: Request,
    target_date: Annotated[date, Query(alias="date")],
    older_count: Annotated[int | None, Query(ge=0, le=MAX_PAGE_LIMIT)] = None,
    newer_count: Annotated[int | None, Query(ge=0, le=MAX_PAGE_LIMIT)] = None,
    include_deleted: bool = False,
    session: AuthenticatedSession = Depends(require_authenticated_session),
) -> EntryWindowResponse:
    """Return a bounded entry window around one local diary date."""

    _ = session
    mark_auth_response_uncacheable(response)
    try:
        return entry_window_to_response(
            get_entry_service(request).get_entry_window(
                target_date=target_date,
                older_count=older_count if older_count is not None else 12,
                newer_count=newer_count if newer_count is not None else 12,
                include_deleted=include_deleted,
            )
        )
    except EntryServiceError as error:
        raise service_http_error(error) from error


@router.get("/dates", response_model=EntryDatesResponse)
def list_entry_dates(
    response: Response,
    request: Request,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    include_deleted: bool = False,
    session: AuthenticatedSession = Depends(require_authenticated_session),
) -> EntryDatesResponse:
    """Return local dates that contain entries for the calendar UI."""

    _ = session
    mark_auth_response_uncacheable(response)
    try:
        return entry_dates_to_response(
            get_entry_service(request).list_entry_dates(
                from_date=from_date,
                to_date=to_date,
                include_deleted=include_deleted,
            )
        )
    except EntryServiceError as error:
        raise service_http_error(error) from error


@router.post("", response_model=EntryDetailResponse, status_code=status.HTTP_201_CREATED)
def create_entry_endpoint(
    payload: EntryCreateRequest,
    request: Request,
    response: Response,
    session: AuthenticatedSession = Depends(require_authenticated_session),
) -> EntryDetailResponse:
    """Create a real immutable v1 entry."""

    _ = session
    mark_auth_response_uncacheable(response)
    content = normalize_create_content(payload.content)
    try:
        detail = get_entry_service(request).create_entry(
            title=payload.title,
            content=content,
            created_at=datetime.now(ZoneInfo(get_settings(request).timezone)),
        )
        return entry_detail_to_response(detail)
    except EntryServiceError as error:
        raise service_http_error(error) from error


@router.post("/rebuild-index", response_model=EntryIndexRebuildResponse)
def rebuild_entry_index(
    response: Response,
    request: Request,
    session: AuthenticatedSession = Depends(require_authenticated_session),
) -> EntryIndexRebuildResponse:
    """Rebuild the derived SQLite index from entry fact files."""

    _ = session
    mark_auth_response_uncacheable(response)
    try:
        return entry_index_rebuild_to_response(get_entry_service(request).rebuild_index_summary())
    except EntryServiceError as error:
        raise service_http_error(error) from error


@router.get("/{entry_id}", response_model=EntryDetailResponse)
def get_entry(
    entry_id: UUID,
    response: Response,
    request: Request,
    session: AuthenticatedSession = Depends(require_authenticated_session),
) -> EntryDetailResponse:
    """Read one entry's content and summaries from fact files."""

    _ = session
    mark_auth_response_uncacheable(response)
    try:
        return entry_detail_to_response(get_entry_service(request).get_entry(entry_id))
    except EntryServiceError as error:
        raise service_http_error(error) from error


@router.delete("/{entry_id}", response_model=EntryDetailResponse)
def delete_entry(
    entry_id: UUID,
    request: Request,
    response: Response,
    session: AuthenticatedSession = Depends(require_authenticated_session),
) -> EntryDetailResponse:
    """Soft-delete one entry by writing metadata.deleted_at."""

    _ = session
    mark_auth_response_uncacheable(response)
    try:
        deleted = get_entry_service(request).delete_entry(
            entry_id,
            deleted_at=datetime.now(ZoneInfo(get_settings(request).timezone)),
        )
        response.status_code = status.HTTP_200_OK
        return entry_detail_to_response(deleted)
    except EntryServiceError as error:
        raise service_http_error(error) from error


def entry_page_to_response(page: EntryPage) -> EntryListResponse:
    return EntryListResponse(
        items=[entry_summary_to_response(item) for item in page.items],
        page=PageInfoResponse(
            limit=page.limit,
            has_older=page.has_older,
            has_newer=page.has_newer,
            older_cursor=page.older_cursor,
            newer_cursor=page.newer_cursor,
        ),
    )


def entry_dates_to_response(dates: tuple[EntryDateCount, ...]) -> EntryDatesResponse:
    return EntryDatesResponse(
        dates=[
            EntryDateCountResponse(date=date.fromisoformat(item.date), count=item.count)
            for item in dates
        ]
    )


def entry_window_to_response(window: EntryWindow) -> EntryWindowResponse:
    return EntryWindowResponse(
        items=[entry_summary_to_response(item) for item in window.items],
        window=EntryWindowInfoResponse(
            target_date=window.target_date,
            older_count=window.older_count,
            newer_count=window.newer_count,
            target_count=window.target_count,
            has_older=window.has_older,
            has_newer=window.has_newer,
            older_cursor=window.older_cursor,
            newer_cursor=window.newer_cursor,
        ),
    )


def entry_index_rebuild_to_response(result: EntryIndexRefreshResult) -> EntryIndexRebuildResponse:
    return EntryIndexRebuildResponse(
        rebuilt=result.rebuilt,
        total_entries=result.total_entries,
        visible_entries=result.visible_entries,
        deleted_entries=result.deleted_entries,
    )


def entry_summary_to_response(item: EntrySummaryItem) -> EntrySummaryResponse:
    return EntrySummaryResponse(
        id=item.id,
        created_at=item.created_at,
        cursor=item.cursor,
        title=item.title,
        content_excerpt=item.content_excerpt,
        comment_count=item.comment_count,
        media_count=item.media_count,
        deleted=item.deleted,
    )


def entry_detail_to_response(detail: EntryDetailItem) -> EntryDetailResponse:
    entry = detail.entry
    return EntryDetailResponse(
        id=entry.metadata.id,
        created_at=entry.metadata.created_at,
        cursor=detail.cursor,
        title=entry.metadata.title,
        content_excerpt=create_content_excerpt(entry.content),
        comment_count=len(entry.comments.comments),
        media_count=len(entry.media_manifest.media),
        deleted=entry.metadata.deleted_at is not None,
        content=entry.content,
        comments=[
            CommentResponse(
                id=comment.id,
                created_at=comment.created_at,
                content=comment.content,
                anchor=comment.anchor.model_dump(mode="json") if comment.anchor else None,
            )
            for comment in entry.comments.comments
        ],
        media=[
            MediaItemResponse(
                id=item.id,
                kind=item.kind,
                url=f"/api/v1/entries/{entry.metadata.id}/media/{item.id}",
                alt=item.alt,
                created_at=item.created_at,
            )
            for item in entry.media_manifest.media
        ],
    )


def normalize_create_content(content: str) -> str:
    """Reject blank submitted content before reaching storage."""

    if not content.strip():
        raise service_http_error(
            EntryServiceError("invalid_request", "content must not be blank")
        )
    return content


def get_entry_service(request: Request) -> EntryService:
    return EntryService(get_settings(request).data_dir)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def service_http_error(error: EntryServiceError) -> HTTPException:
    status_code_by_error = {
        "invalid_request": status.HTTP_400_BAD_REQUEST,
        "invalid_cursor": status.HTTP_400_BAD_REQUEST,
        "storage_contract_error": status.HTTP_400_BAD_REQUEST,
        "entry_not_found": status.HTTP_404_NOT_FOUND,
        "entry_deleted": status.HTTP_409_CONFLICT,
    }
    return HTTPException(
        status_code=status_code_by_error.get(error.code, status.HTTP_500_INTERNAL_SERVER_ERROR),
        detail=ApiErrorResponse(
            error=ApiErrorBody(code=error.code, message=error.message)
        ).model_dump(),
    )
