"""Authenticated integration APIs exposed to the Serein frontend."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import Response as BinaryResponse
from pydantic import BaseModel, Field

from serein.api.auth import (
    AuthenticatedSession,
    mark_auth_response_uncacheable,
    require_authenticated_session,
)
from serein.services.immich import ImmichError, get_immich_client


router = APIRouter(prefix="/integrations/immich", tags=["integrations"])


class ImmichSearchRequest(BaseModel):
    query: str | None = Field(default=None, max_length=200)
    taken_after: date | None = None
    taken_before: date | None = None
    album_id: UUID | None = None
    cursor: str | None = Field(default=None, max_length=100)
    limit: int = Field(default=60, ge=1, le=100)


@router.get("/status")
async def get_immich_status(
    request: Request,
    response: Response,
    session: AuthenticatedSession = Depends(require_authenticated_session),
) -> dict:
    _ = session
    mark_auth_response_uncacheable(response)
    return await get_immich_client(request).status()


@router.get("/albums")
async def get_immich_albums(
    request: Request,
    response: Response,
    session: AuthenticatedSession = Depends(require_authenticated_session),
) -> dict:
    _ = session
    mark_auth_response_uncacheable(response)
    try:
        return {"albums": await get_immich_client(request).albums()}
    except ImmichError as error:
        raise _http_error(error) from error


@router.post("/search")
async def search_immich_assets(
    payload: ImmichSearchRequest,
    request: Request,
    response: Response,
    session: AuthenticatedSession = Depends(require_authenticated_session),
) -> dict:
    _ = session
    mark_auth_response_uncacheable(response)
    if payload.taken_after and payload.taken_before and payload.taken_after > payload.taken_before:
        raise _http_error(ImmichError("invalid_request", "Invalid date range", 400))
    try:
        return await get_immich_client(request).search(
            query=payload.query,
            taken_after=payload.taken_after,
            taken_before=payload.taken_before,
            album_id=payload.album_id,
            cursor=payload.cursor,
            limit=payload.limit,
        )
    except ImmichError as error:
        raise _http_error(error) from error


@router.get("/assets/{asset_id}/thumbnail")
async def get_immich_thumbnail(
    asset_id: UUID,
    request: Request,
    session: AuthenticatedSession = Depends(require_authenticated_session),
) -> BinaryResponse:
    _ = session
    try:
        content, media_type = await get_immich_client(request).thumbnail(asset_id)
    except ImmichError as error:
        raise _http_error(error) from error
    response = BinaryResponse(content=content, media_type=media_type)
    response.headers["Cache-Control"] = "private, max-age=300"
    return response


def _http_error(error: ImmichError):
    from fastapi import HTTPException

    return HTTPException(
        status_code=error.status_code,
        detail={"error": {"code": error.code, "message": str(error)}},
    )
