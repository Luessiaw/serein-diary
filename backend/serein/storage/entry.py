"""P4 v1 entry data models and validation helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


ENTRY_DIR_NAME_PATTERN = re.compile(
    r"^(?P<minute>\d{12})-(?P<id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$"
)
REQUIRED_ENTRY_FILES = (
    "metadata.json",
    "content.md",
    "comments.json",
    "media-manifest.json",
)


class EntryValidationError(ValueError):
    """Raised when an entry directory does not match the v1 data contract."""


@dataclass(frozen=True)
class EntryDirectoryIdentity:
    """Parsed identity from an entry directory name."""

    minute_prefix: str
    entry_id: UUID


class Metadata(BaseModel):
    """metadata.json v1 model."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    id: UUID
    created_at: datetime
    title: str | None = None
    location: dict | None = None
    fields: dict | None = None
    deleted_at: datetime | None = None

    @field_validator("created_at", "deleted_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("must include a UTC offset")
        return value

    @field_validator("title")
    @classmethod
    def normalize_blank_title(cls, value: str | None) -> str | None:
        if value is None:
            return None

        stripped = value.strip()
        return stripped or None


class QuoteAnchor(BaseModel):
    """Selected-text comment anchor."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["quote"]
    selected_text: str
    prefix: str
    suffix: str


class Comment(BaseModel):
    """comments.json comment item."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    created_at: datetime
    content: str
    anchor: QuoteAnchor | None = None

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("must include a UTC offset")
        return value

    @field_validator("content")
    @classmethod
    def require_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class CommentsFile(BaseModel):
    """comments.json v1 model."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    comments: list[Comment]


class MediaItem(BaseModel):
    """media-manifest.json media item."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    kind: Literal["image", "video", "audio", "file"]
    original: str
    preview: str | None = None
    alt: str | None = None
    created_at: datetime | None = None

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("must include a UTC offset")
        return value

    @field_validator("original", "preview")
    @classmethod
    def require_safe_relative_media_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        validate_safe_relative_path(value)
        return value


class MediaManifest(BaseModel):
    """media-manifest.json v1 model."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    media: list[MediaItem]


@dataclass(frozen=True)
class DiaryEntry:
    """Fully parsed v1 entry facts."""

    path: Path
    metadata: Metadata
    content: str
    comments: CommentsFile
    media_manifest: MediaManifest


def read_entry(entry_dir: Path) -> DiaryEntry:
    """Read and validate a v1 entry directory."""

    entry_dir = Path(entry_dir)
    reject_legacy_year_parent(entry_dir)
    identity = parse_entry_directory_name(entry_dir.name)
    ensure_required_files(entry_dir)

    metadata = parse_metadata(read_json_file(entry_dir / "metadata.json"))
    validate_directory_identity(identity, metadata)

    content = read_content_file(entry_dir / "content.md")
    comments = parse_comments(read_json_file(entry_dir / "comments.json"))
    media_manifest = parse_media_manifest(read_json_file(entry_dir / "media-manifest.json"))

    return DiaryEntry(
        path=entry_dir,
        metadata=metadata,
        content=content,
        comments=comments,
        media_manifest=media_manifest,
    )


def reject_legacy_year_parent(entry_dir: Path) -> None:
    """Reject legacy entries/<year>/<date>-<uuid> style directories."""

    if re.fullmatch(r"\d{4}", entry_dir.parent.name):
        raise EntryValidationError(
            "entry directory name must match YYYYMMDDHHmm-<uuid>; "
            "legacy year subdirectories are not supported"
        )


def parse_entry_directory_name(name: str) -> EntryDirectoryIdentity:
    """Parse and validate an entry directory basename."""

    match = ENTRY_DIR_NAME_PATTERN.fullmatch(name)
    if not match:
        raise EntryValidationError(
            "entry directory name must match YYYYMMDDHHmm-<uuid>"
        )

    return EntryDirectoryIdentity(
        minute_prefix=match.group("minute"),
        entry_id=UUID(match.group("id")),
    )


def ensure_required_files(entry_dir: Path) -> None:
    """Ensure an entry directory contains all v1 fact files."""

    missing = [name for name in REQUIRED_ENTRY_FILES if not (entry_dir / name).is_file()]
    if missing:
        raise EntryValidationError(
            "entry is missing required file(s): " + ", ".join(sorted(missing))
        )


def read_json_file(path: Path) -> object:
    """Read a JSON file and convert parser errors to safe validation errors."""

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as error:
        raise EntryValidationError(f"{path.name} must be UTF-8") from error
    except json.JSONDecodeError as error:
        raise EntryValidationError(f"{path.name} must contain valid JSON") from error


def read_content_file(path: Path) -> str:
    """Read and validate content.md without exposing its body in errors."""

    try:
        raw_content = path.read_bytes()
        content = raw_content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise EntryValidationError("content.md must be UTF-8") from error

    if "\r" in content:
        raise EntryValidationError("content.md must use LF line endings")
    if not content.strip():
        raise EntryValidationError("content.md must not be blank")

    return content


def parse_metadata(value: object) -> Metadata:
    try:
        return Metadata.model_validate(value)
    except ValidationError as error:
        raise EntryValidationError(
            "metadata.json does not match the v1 contract: "
            + summarize_validation_error(error)
        ) from error


def parse_comments(value: object) -> CommentsFile:
    try:
        return CommentsFile.model_validate(value)
    except ValidationError as error:
        raise EntryValidationError(
            "comments.json does not match the v1 contract: "
            + summarize_validation_error(error)
        ) from error


def parse_media_manifest(value: object) -> MediaManifest:
    try:
        return MediaManifest.model_validate(value)
    except ValidationError as error:
        raise EntryValidationError(
            "media-manifest.json does not match the v1 contract: "
            + summarize_validation_error(error)
        ) from error


def validate_directory_identity(
    identity: EntryDirectoryIdentity,
    metadata: Metadata,
) -> None:
    """Validate directory UUID and minute prefix against metadata."""

    if identity.entry_id != metadata.id:
        raise EntryValidationError("entry directory UUID does not match metadata.id")

    created_minute = metadata.created_at.strftime("%Y%m%d%H%M")
    if identity.minute_prefix != created_minute:
        raise EntryValidationError(
            "entry directory minute prefix does not match metadata.created_at"
        )


def validate_safe_relative_path(value: str) -> None:
    """Validate a media path is relative and stays inside the entry directory."""

    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("must be a safe relative path")


def summarize_validation_error(error: ValidationError) -> str:
    """Return a compact validation summary without including diary bodies."""

    first = error.errors(include_input=False)[0]
    location = ".".join(str(part) for part in first.get("loc", ())) or "<root>"
    message = first.get("msg", "invalid value")
    return f"{location}: {message}"
