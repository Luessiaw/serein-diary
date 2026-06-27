"""Application configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from os import access, environ
from os import R_OK, W_OK, X_OK
from pathlib import Path
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DIARY_DATA_DIR_ENV = "DIARY_DATA_DIR"
DIARY_TIMEZONE_ENV = "DIARY_TIMEZONE"
DIARY_ADMIN_PASSWORD_ENV = "DIARY_ADMIN_PASSWORD"
DIARY_SESSION_SECRET_ENV = "DIARY_SESSION_SECRET"
DEFAULT_TIMEZONE = "UTC"
MIN_SESSION_SECRET_LENGTH = 32
UNSAFE_ADMIN_PASSWORDS = {
    "",
    "admin",
    "password",
    "change-this-before-first-start",
}
UNSAFE_SESSION_SECRETS = {
    "",
    "replace-with-a-long-random-secret",
    "replace-with-a-real-random-secret-at-least-32-chars",
}


class ConfigError(RuntimeError):
    """Raised when runtime configuration is missing or unsafe."""


@dataclass(frozen=True, repr=False)
class Settings:
    """Runtime settings required by the Serein API.

    Sensitive values are intentionally omitted from ``repr(settings)``.
    """

    data_dir: Path
    timezone: str
    admin_password: str
    session_secret: str

    def __repr__(self) -> str:
        return (
            "Settings("
            f"data_dir={self.data_dir!s}, "
            f"timezone={self.timezone!r}, "
            "admin_password=<redacted>, "
            "session_secret=<redacted>"
            ")"
        )


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Load and validate DIARY_* settings from an environment mapping."""

    source = environ if env is None else env
    data_dir = _read_required(source, DIARY_DATA_DIR_ENV)
    timezone = _read_optional(source, DIARY_TIMEZONE_ENV, DEFAULT_TIMEZONE)
    admin_password = _read_required(source, DIARY_ADMIN_PASSWORD_ENV)
    session_secret = _read_required(source, DIARY_SESSION_SECRET_ENV)

    return Settings(
        data_dir=_validate_data_dir(data_dir),
        timezone=_validate_timezone(timezone),
        admin_password=_validate_admin_password(admin_password),
        session_secret=_validate_session_secret(session_secret),
    )


def _read_required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is required.")
    return value


def _read_optional(env: Mapping[str, str], name: str, default: str) -> str:
    return env.get(name, default).strip() or default


def _validate_data_dir(value: str) -> Path:
    path = Path(value).expanduser()

    if not path.is_absolute():
        raise ConfigError(f"{DIARY_DATA_DIR_ENV} must be an absolute path.")
    if not path.exists():
        raise ConfigError(f"{DIARY_DATA_DIR_ENV} must point to an existing directory.")
    if not path.is_dir():
        raise ConfigError(f"{DIARY_DATA_DIR_ENV} must point to a directory.")
    if not access(path, R_OK | W_OK | X_OK):
        raise ConfigError(f"{DIARY_DATA_DIR_ENV} must be readable, writable, and searchable.")

    return path


def _validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ConfigError(f"{DIARY_TIMEZONE_ENV} must be a valid IANA timezone.") from exc
    return value


def _validate_admin_password(value: str) -> str:
    if value.strip().lower() in UNSAFE_ADMIN_PASSWORDS:
        raise ConfigError(f"{DIARY_ADMIN_PASSWORD_ENV} must be changed from the default.")
    return value


def _validate_session_secret(value: str) -> str:
    if value.strip().lower() in UNSAFE_SESSION_SECRETS:
        raise ConfigError(f"{DIARY_SESSION_SECRET_ENV} must be changed from the default.")
    if len(value) < MIN_SESSION_SECRET_LENGTH:
        raise ConfigError(
            f"{DIARY_SESSION_SECRET_ENV} must be at least "
            f"{MIN_SESSION_SECRET_LENGTH} characters."
        )
    return value
