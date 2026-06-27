"""Security helpers for the minimal lock-screen model."""

from __future__ import annotations

from dataclasses import dataclass
from hmac import compare_digest
from time import time

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from serein.config import Settings

SESSION_COOKIE_NAME = "serein_session"
SESSION_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30
SESSION_COOKIE_SALT = "serein-lock-screen"
SESSION_SUBJECT = "single-admin"


@dataclass(frozen=True)
class SessionPayload:
    """Minimal authenticated session payload."""

    subject: str
    issued_at: int


def verify_lock_password(candidate: str, settings: Settings) -> bool:
    """Return whether a submitted lock-screen password is valid."""

    return compare_digest(candidate, settings.admin_password)


def create_session_token(settings: Settings) -> str:
    """Create a signed single-admin session token."""

    serializer = _create_serializer(settings)
    return serializer.dumps(
        {
            "sub": SESSION_SUBJECT,
            "iat": int(time()),
        }
    )


def read_session_token(token: str | None, settings: Settings) -> SessionPayload | None:
    """Read and validate a signed session token."""

    if not token:
        return None

    serializer = _create_serializer(settings)
    try:
        payload = serializer.loads(token, max_age=SESSION_COOKIE_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None

    if not isinstance(payload, dict):
        return None
    if payload.get("sub") != SESSION_SUBJECT:
        return None

    issued_at = payload.get("iat", 0)
    if not isinstance(issued_at, int):
        issued_at = 0

    return SessionPayload(subject=SESSION_SUBJECT, issued_at=issued_at)


def _create_serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        secret_key=settings.session_secret,
        salt=SESSION_COOKIE_SALT,
    )
