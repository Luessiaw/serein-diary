"""Application configuration skeleton.

P3-T03 will implement DIARY_* environment parsing and startup validation here.
"""

from __future__ import annotations

from dataclasses import dataclass


DIARY_DATA_DIR_ENV = "DIARY_DATA_DIR"
DIARY_TIMEZONE_ENV = "DIARY_TIMEZONE"
DIARY_ADMIN_PASSWORD_ENV = "DIARY_ADMIN_PASSWORD"
DIARY_SESSION_SECRET_ENV = "DIARY_SESSION_SECRET"


@dataclass(frozen=True)
class Settings:
    """Runtime settings required by the Serein API.

    The fields are intentionally minimal for P3-T02. Validation and safe error
    reporting are added in P3-T03.
    """

    data_dir: str
    timezone: str
    admin_password: str
    session_secret: str

