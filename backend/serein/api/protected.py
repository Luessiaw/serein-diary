"""Minimal protected API route used to verify auth boundaries."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from serein.api.auth import (
    AuthenticatedSession,
    mark_auth_response_uncacheable,
    require_authenticated_session,
)


router = APIRouter(tags=["protected"])


class ProtectedResponse(BaseModel):
    """Minimal authenticated capability response."""

    authenticated: bool
    subject: str
    capabilities: list[str]


@router.get("/protected", response_model=ProtectedResponse)
def get_protected(
    response: Response,
    session: AuthenticatedSession = Depends(require_authenticated_session),
) -> ProtectedResponse:
    """Return a minimal response only after lock-screen authentication."""

    mark_auth_response_uncacheable(response)
    return ProtectedResponse(
        authenticated=True,
        subject=session.subject,
        capabilities=["session:read"],
    )
