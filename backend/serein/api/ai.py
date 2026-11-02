"""Write-only API for entries generated from a conversation.

This router is the only surface an AI agent can reach, and it can do exactly
one thing: create a new entry. There is no list, read, update, or delete here,
so the agent can neither see the user's handwritten diary nor modify anything
that already exists — including entries it wrote itself earlier.

The token is checked against a sha256 digest in settings; the plaintext token
never reaches the server.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator

# 相对导入：本模块位于 serein.api 内，包初始化期间用绝对名导入包成员会在
# Python 3.12 上失败（见 api/__init__.py 顶部说明）。
from .auth import mark_auth_response_uncacheable
from .entries import get_entry_service, get_settings, service_http_error
from serein.config import Settings
from serein.services.entries import EntryServiceError
from serein.storage.entry import SOURCE_KIND_AI_DIALOGUE


router = APIRouter(prefix="/ai", tags=["ai"])

MAX_CONTENT_CHARS = 20_000
MAX_TITLE_CHARS = 120


class AiEntryRequest(BaseModel):
    """One entry an agent wants recorded."""

    content: str = Field(min_length=1, max_length=MAX_CONTENT_CHARS)
    title: str | None = Field(default=None, max_length=MAX_TITLE_CHARS)
    # 只记时间范围或等价引用，不记对话原文：素材留在会话日志里。
    source_material: str | None = Field(default=None, max_length=200)
    source_session_ids: list[str] = Field(default_factory=list, max_length=20)
    source_review: str = Field(default="unreviewed", max_length=32)

    @field_validator("content")
    @classmethod
    def require_real_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("source_review")
    @classmethod
    def limit_review_values(cls, value: str) -> str:
        allowed = {"unreviewed", "confirmed", "rejected"}
        if value not in allowed:
            raise ValueError("must be one of: " + ", ".join(sorted(allowed)))
        return value


class AiEntryCreatedResponse(BaseModel):
    """Minimal acknowledgement: an id and the facts the agent just supplied.

    Deliberately not the full entry detail. Echoing the stored body back would
    make this endpoint a read surface as well, and the agent already knows what
    it wrote.
    """

    id: str
    created_at: datetime
    source_kind: str


class AiHealthResponse(BaseModel):
    """Lets a scheduled agent check whether it may write, without leaking data."""

    status: str
    write_enabled: bool


def require_ai_writer(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Accept only a valid ai-writer bearer token."""

    settings = get_settings(request)
    if not settings.ai_writer_enabled or not settings.ai_token_sha256:
        # 未启用时与"token 错误"返回同样的状态码，避免暴露功能开关状态。
        raise _unauthorized()

    token = _extract_bearer(authorization)
    if not token:
        raise _unauthorized()

    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(digest, settings.ai_token_sha256):
        raise _unauthorized()


def _extract_bearer(header: str | None) -> str | None:
    if not header:
        return None
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.get("/health", response_model=AiHealthResponse)
def ai_health(request: Request, response: Response) -> AiHealthResponse:
    """Report readiness without requiring the token.

    A scheduled agent uses this to distinguish "the feature is off" from
    "my token is wrong"; it exposes no diary content either way.
    """

    _ = response
    settings: Settings = get_settings(request)
    return AiHealthResponse(
        status="ok",
        write_enabled=bool(settings.ai_writer_enabled and settings.ai_token_sha256),
    )


@router.post(
    "/entries",
    response_model=AiEntryCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_ai_writer)],
)
def create_ai_entry(
    payload: AiEntryRequest,
    request: Request,
    response: Response,
) -> AiEntryCreatedResponse:
    """Create one ai-dialogue entry. Never touches existing entries."""

    mark_auth_response_uncacheable(response)
    settings = get_settings(request)

    source: dict[str, object] = {
        "source_kind": SOURCE_KIND_AI_DIALOGUE,
        "source_review": payload.source_review,
    }
    if payload.source_material:
        source["source_material"] = payload.source_material
    if payload.source_session_ids:
        source["source_session_ids"] = list(payload.source_session_ids)

    try:
        detail = get_entry_service(request).create_entry(
            title=payload.title,
            content=payload.content,
            created_at=datetime.now(ZoneInfo(settings.timezone)),
            source=source,
        )
    except EntryServiceError as error:
        raise service_http_error(error) from error

    entry = detail.entry
    return AiEntryCreatedResponse(
        id=str(entry.metadata.id),
        created_at=entry.metadata.created_at,
        source_kind=entry.metadata.source_kind(),
    )
