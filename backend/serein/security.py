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

# 第二种主体：只用于写入由对话整理生成的条目。它没有任何读取能力，也没有
# 权限改动或删除既有条目——那些接口只认 SESSION_SUBJECT。
AI_WRITER_SUBJECT = "ai-writer"
AI_WRITER_TOKEN_SALT = "serein-ai-writer"
AI_WRITER_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 365

# 允许出现在签名 token 里的主体。read_session_token 只接受这个集合中的值，
# 这样即使将来加了新主体，也不会因为某个调用点忘了检查而互相冒充。
KNOWN_SUBJECTS = frozenset({SESSION_SUBJECT, AI_WRITER_SUBJECT})


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


def create_ai_writer_token(settings: Settings) -> str:
    """Mint a bearer token for the ai-writer agent.

    Uses its own salt, so an AI token can never be replayed as a browser
    session cookie and vice versa, even though both are signed. The password is
    not required to mint one: only an operator with host access can run this.
    """

    serializer = URLSafeTimedSerializer(
        secret_key=settings.session_secret,
        salt=AI_WRITER_TOKEN_SALT,
    )
    return serializer.dumps({"sub": AI_WRITER_SUBJECT, "iat": int(time())})


def read_ai_writer_token(token: str | None, settings: Settings) -> SessionPayload | None:
    """Validate a bearer token and return an ai-writer payload."""

    if not token:
        return None

    # 与浏览器会话使用不同 salt：AI token 无法当作 cookie 使用，反过来也一样。
    serializer = URLSafeTimedSerializer(
        secret_key=settings.session_secret,
        salt=AI_WRITER_TOKEN_SALT,
    )
    try:
        payload = serializer.loads(token, max_age=AI_WRITER_TOKEN_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None

    if not isinstance(payload, dict) or payload.get("sub") != AI_WRITER_SUBJECT:
        return None

    issued_at = payload.get("iat", 0)
    return SessionPayload(
        subject=AI_WRITER_SUBJECT,
        issued_at=issued_at if isinstance(issued_at, int) else 0,
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
    subject = payload.get("sub")
    # 显式 allowlist：本函数只服务于浏览器 cookie 路径，但必须明确拒绝
    # ai-writer，否则把 AI token 塞进 cookie 就能拿到写权限以外的入口。
    if subject not in KNOWN_SUBJECTS:
        return None
    if subject != SESSION_SUBJECT:
        return None

    issued_at = payload.get("iat", 0)
    if not isinstance(issued_at, int):
        issued_at = 0

    return SessionPayload(subject=subject, issued_at=issued_at)


def _create_serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        secret_key=settings.session_secret,
        salt=SESSION_COOKIE_SALT,
    )
