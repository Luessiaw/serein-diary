"""Minimal authenticated entries API for P4 storage verification."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from serein.api.auth import (
    AuthenticatedSession,
    mark_auth_response_uncacheable,
    require_authenticated_session,
)
from serein.config import Settings
from serein.storage.entry import DiaryEntry, EntryValidationError
from serein.storage.repository import (
    EntrySummary,
    create_entry,
    create_content_excerpt,
    find_entry_by_id,
    mark_entry_deleted,
    scan_entry_summaries,
)


router = APIRouter(prefix="/entries", tags=["entries"])


class EntryCreateRequest(BaseModel):
    """Minimal request for creating an immutable diary entry."""

    title: str | None = None
    content: str = Field(min_length=1)


class EntrySummaryResponse(BaseModel):
    """Entry summary returned by the minimal verification API."""

    id: UUID
    created_at: datetime
    path: str
    title: str | None
    content_excerpt: str
    comment_count: int
    media_count: int
    deleted: bool


class EntryDetailResponse(EntrySummaryResponse):
    """Entry detail returned by the minimal verification API."""

    content: str
    comments: dict
    media_manifest: dict


@router.get("", response_model=list[EntrySummaryResponse])
def list_entries(
    response: Response,
    request: Request,
    session: AuthenticatedSession = Depends(require_authenticated_session),
) -> list[EntrySummaryResponse]:
    """Return filesystem-backed entry summaries."""

    _ = session
    mark_auth_response_uncacheable(response)
    settings = get_settings(request)
    try:
        return [entry_summary_to_response(summary) for summary in scan_entry_summaries(settings.data_dir)]
    except EntryValidationError as error:
        raise storage_http_error(error) from error


@router.post("", response_model=EntryDetailResponse, status_code=status.HTTP_201_CREATED)
def create_entry_endpoint(
    payload: EntryCreateRequest,
    request: Request,
    response: Response,
    session: AuthenticatedSession = Depends(require_authenticated_session),
) -> EntryDetailResponse:
    """Create a real immutable v1 entry using the filesystem storage layer."""

    _ = session
    mark_auth_response_uncacheable(response)
    settings = get_settings(request)
    try:
        entry = create_entry(
            settings.data_dir,
            title=payload.title,
            content=payload.content,
            created_at=datetime.now(ZoneInfo(settings.timezone)),
        )
        return entry_detail_to_response(entry, settings.data_dir)
    except EntryValidationError as error:
        raise storage_http_error(error) from error


@router.get("/{entry_id}", response_model=EntryDetailResponse)
def get_entry(
    entry_id: UUID,
    response: Response,
    request: Request,
    session: AuthenticatedSession = Depends(require_authenticated_session),
) -> EntryDetailResponse:
    """Read one entry's content and fact-file summaries."""

    _ = session
    mark_auth_response_uncacheable(response)
    settings = get_settings(request)
    try:
        return entry_detail_to_response(
            find_entry_by_id(settings.data_dir, entry_id),
            settings.data_dir,
        )
    except EntryValidationError as error:
        raise storage_http_error(error) from error


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
    settings = get_settings(request)
    try:
        deleted = mark_entry_deleted(
            settings.data_dir,
            entry_id,
            deleted_at=datetime.now(ZoneInfo(settings.timezone)),
        )
        response.status_code = status.HTTP_200_OK
        return entry_detail_to_response(deleted, settings.data_dir)
    except EntryValidationError as error:
        raise storage_http_error(error) from error


def entry_summary_to_response(summary: EntrySummary) -> EntrySummaryResponse:
    return EntrySummaryResponse(
        id=summary.id,
        created_at=summary.created_at,
        path=summary.path.as_posix(),
        title=summary.title,
        content_excerpt=summary.content_excerpt,
        comment_count=summary.comment_count,
        media_count=summary.media_count,
        deleted=summary.deleted,
    )


def entry_detail_to_response(entry: DiaryEntry, data_dir: Path) -> EntryDetailResponse:
    summary = entry_summary_to_response(EntrySummary(
        id=entry.metadata.id,
        created_at=entry.metadata.created_at,
        path=entry.path.relative_to(data_dir),
        title=entry.metadata.title,
        content_excerpt=create_content_excerpt(entry.content),
        comment_count=len(entry.comments.comments),
        media_count=len(entry.media_manifest.media),
        deleted=entry.metadata.deleted_at is not None,
    ))
    return EntryDetailResponse(
        **summary.model_dump(),
        content=entry.content,
        comments=entry.comments.model_dump(mode="json"),
        media_manifest=entry.media_manifest.model_dump(mode="json"),
    )


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def storage_http_error(error: EntryValidationError) -> HTTPException:
    detail = str(error)
    status_code = status.HTTP_404_NOT_FOUND if "not found" in detail else status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=status_code, detail=detail)
