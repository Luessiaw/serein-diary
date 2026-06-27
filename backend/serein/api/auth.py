"""Lock-screen access protection routes."""

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from serein.config import Settings
from serein.security import (
    SESSION_COOKIE_MAX_AGE_SECONDS,
    SESSION_COOKIE_NAME,
    create_session_token,
    read_session_token,
    verify_lock_password,
)


router = APIRouter(prefix="/auth", tags=["auth"])
NO_STORE_HEADER = "no-store"


class LoginRequest(BaseModel):
    """Lock-screen login request."""

    password: str = Field(min_length=1)


class SessionResponse(BaseModel):
    """Minimal session state."""

    authenticated: bool
    subject: str | None = None


class AuthenticatedSession(BaseModel):
    """Current authenticated single-admin session."""

    subject: str


@router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> SessionResponse:
    """Validate the lock-screen password and set a signed session cookie."""

    mark_auth_response_uncacheable(response)
    settings = _get_settings(request)
    if not verify_lock_password(payload.password, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password.",
        )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_token(settings),
        max_age=SESSION_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )
    return SessionResponse(authenticated=True, subject="single-admin")


@router.post("/logout", response_model=SessionResponse)
def logout(response: Response) -> SessionResponse:
    """Clear the signed session cookie."""

    mark_auth_response_uncacheable(response)
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        samesite="lax",
    )
    return SessionResponse(authenticated=False)


@router.get("/session", response_model=SessionResponse)
def get_session(request: Request, response: Response) -> SessionResponse:
    """Return whether the current request has a valid lock-screen session."""

    mark_auth_response_uncacheable(response)
    session = read_current_session(request)
    if session is None:
        return SessionResponse(authenticated=False)

    return SessionResponse(authenticated=True, subject=session.subject)


def require_authenticated_session(request: Request) -> AuthenticatedSession:
    """Require a valid lock-screen session for protected API routes."""

    session = read_current_session(request)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    return AuthenticatedSession(subject=session.subject)


def read_current_session(request: Request) -> AuthenticatedSession | None:
    """Read the current request cookie and return a minimal authenticated session."""

    settings = _get_settings(request)
    session = read_session_token(request.cookies.get(SESSION_COOKIE_NAME), settings)
    if session is None:
        return None

    return AuthenticatedSession(subject=session.subject)


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings


def mark_auth_response_uncacheable(response: Response) -> None:
    """Prevent browsers or proxies from reusing stale authentication state."""

    response.headers["Cache-Control"] = NO_STORE_HEADER
