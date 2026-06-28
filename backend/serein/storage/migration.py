"""Read-only migration dry-run helpers for Serein entry data."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import ValidationError

from serein.storage.entry import (
    ENTRY_DIR_NAME_PATTERN,
    EntryValidationError,
    MediaManifest,
    parse_comments,
    parse_media_manifest,
    parse_metadata,
    read_entry,
)
from serein.storage.repository import create_entry_directory_name


LEGACY_ENTRY_DIR_NAME_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$"
)
OLD_METADATA_FIELDS = frozenset(
    {
        "date",
        "updated_at",
        "revision",
        "tags",
        "mood",
        "weather",
        "time_range",
        "is_favorite",
    }
)
REQUIRED_FACT_FILES = (
    "metadata.json",
    "content.md",
    "comments.json",
    "media-manifest.json",
)


IssueSeverity = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class MigrationIssue:
    """One safe dry-run issue item."""

    severity: IssueSeverity
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class MigrationEntryReport:
    """Dry-run result for one candidate entry directory."""

    source_path: str
    detected_format: Literal["v1", "legacy", "unknown"]
    can_migrate: bool
    entry_id: str | None = None
    created_at: str | None = None
    target_name: str | None = None
    title_present: bool = False
    content_bytes: int = 0
    comment_count: int = 0
    media_count: int = 0
    old_metadata_fields: tuple[str, ...] = ()
    issues: tuple[MigrationIssue, ...] = ()


@dataclass(frozen=True)
class MigrationDryRunReport:
    """Read-only migration inspection result."""

    source_dir: str
    target_dir: str | None
    entry_count: int
    migratable_count: int
    blocked_count: int
    comment_count: int
    media_count: int
    entries: tuple[MigrationEntryReport, ...] = ()
    issues: tuple[MigrationIssue, ...] = ()

    def to_text(self) -> str:
        """Render a compact human-readable report without diary bodies."""

        lines = [
            "Serein migration dry-run",
            f"source: {self.source_dir}",
            f"target: {self.target_dir or '<not provided>'}",
            (
                "entries: "
                f"{self.entry_count}, migratable: {self.migratable_count}, "
                f"blocked: {self.blocked_count}"
            ),
            f"comments: {self.comment_count}, media: {self.media_count}",
        ]
        for issue in self.issues:
            lines.append(f"[{issue.severity}] {issue.code} {issue.path}: {issue.message}")
        for entry in self.entries:
            status = "ok" if entry.can_migrate else "blocked"
            lines.append(
                (
                    f"- {status} {entry.detected_format} {entry.source_path} "
                    f"-> {entry.target_name or '<no target>'} "
                    f"content_bytes={entry.content_bytes} "
                    f"comments={entry.comment_count} media={entry.media_count}"
                )
            )
            if entry.old_metadata_fields:
                lines.append(
                    "  old_metadata_fields="
                    + ",".join(entry.old_metadata_fields)
                )
            for issue in entry.issues:
                lines.append(
                    f"  [{issue.severity}] {issue.code} {issue.path}: {issue.message}"
                )

        return "\n".join(lines)


@dataclass
class _EntryReportBuilder:
    """Mutable helper used internally while inspecting one entry."""

    source_path: str
    detected_format: Literal["v1", "legacy", "unknown"]
    entry_id: str | None = None
    created_at: str | None = None
    target_name: str | None = None
    title_present: bool = False
    content_bytes: int = 0
    comment_count: int = 0
    media_count: int = 0
    old_metadata_fields: tuple[str, ...] = ()
    issues: list[MigrationIssue] = field(default_factory=list)

    def issue(self, severity: IssueSeverity, code: str, message: str) -> None:
        self.issues.append(
            MigrationIssue(
                severity=severity,
                code=code,
                path=self.source_path,
                message=message,
            )
        )

    def build(self) -> MigrationEntryReport:
        can_migrate = not any(issue.severity == "error" for issue in self.issues)
        return MigrationEntryReport(
            source_path=self.source_path,
            detected_format=self.detected_format,
            can_migrate=can_migrate,
            entry_id=self.entry_id,
            created_at=self.created_at,
            target_name=self.target_name,
            title_present=self.title_present,
            content_bytes=self.content_bytes,
            comment_count=self.comment_count,
            media_count=self.media_count,
            old_metadata_fields=self.old_metadata_fields,
            issues=tuple(self.issues),
        )


def dry_run_migration(
    source_dir: Path,
    target_dir: Path | None = None,
) -> MigrationDryRunReport:
    """Inspect source entries without modifying source or target directories."""

    source_dir = Path(source_dir)
    target_dir = Path(target_dir) if target_dir is not None else None
    top_level_issues: list[MigrationIssue] = []

    candidates, discovery_issues = discover_candidate_entry_dirs(source_dir)
    top_level_issues.extend(discovery_issues)
    entries = tuple(inspect_candidate_entry(path) for path in candidates)

    return MigrationDryRunReport(
        source_dir=str(source_dir),
        target_dir=str(target_dir) if target_dir is not None else None,
        entry_count=len(entries),
        migratable_count=sum(1 for entry in entries if entry.can_migrate),
        blocked_count=sum(1 for entry in entries if not entry.can_migrate),
        comment_count=sum(entry.comment_count for entry in entries),
        media_count=sum(entry.media_count for entry in entries),
        entries=entries,
        issues=tuple(top_level_issues),
    )


def discover_candidate_entry_dirs(
    source_dir: Path,
) -> tuple[list[Path], list[MigrationIssue]]:
    """Find likely entry directories under a data root or entries directory."""

    issues: list[MigrationIssue] = []
    if not source_dir.exists():
        issues.append(
            MigrationIssue(
                severity="error",
                code="source_missing",
                path=str(source_dir),
                message="source directory does not exist",
            )
        )
        return [], issues
    if source_dir.is_symlink() or not source_dir.is_dir():
        issues.append(
            MigrationIssue(
                severity="error",
                code="source_not_directory",
                path=str(source_dir),
                message="source must be a real directory",
            )
        )
        return [], issues

    if looks_like_entry_dir(source_dir):
        return [source_dir], issues

    root = source_dir / "entries" if (source_dir / "entries").exists() else source_dir
    if root.is_symlink() or not root.is_dir():
        issues.append(
            MigrationIssue(
                severity="error",
                code="entries_not_directory",
                path=str(root),
                message="entries must be a real directory",
            )
        )
        return [], issues

    candidates: list[Path] = []
    for child in sorted(root.iterdir(), key=lambda path: path.name):
        if child.is_symlink():
            issues.append(
                MigrationIssue(
                    severity="error",
                    code="symlink_rejected",
                    path=str(child),
                    message="symlink entries are not inspected",
                )
            )
            continue
        if not child.is_dir():
            issues.append(
                MigrationIssue(
                    severity="warning",
                    code="non_directory_ignored",
                    path=str(child),
                    message="non-directory item ignored",
                )
            )
            continue

        if child.name.isdigit() and len(child.name) == 4:
            candidates.extend(discover_legacy_year_entries(child, issues))
        else:
            candidates.append(child)

    return candidates, issues


def looks_like_entry_dir(path: Path) -> bool:
    """Return whether a directory itself appears to be one entry."""

    return (
        ENTRY_DIR_NAME_PATTERN.fullmatch(path.name) is not None
        or LEGACY_ENTRY_DIR_NAME_PATTERN.fullmatch(path.name) is not None
        or any((path / name).exists() for name in REQUIRED_FACT_FILES)
    )


def discover_legacy_year_entries(
    year_dir: Path,
    issues: list[MigrationIssue],
) -> list[Path]:
    """Find legacy entries inside one entries/<year>/ directory."""

    candidates: list[Path] = []
    for child in sorted(year_dir.iterdir(), key=lambda path: path.name):
        if child.is_symlink():
            issues.append(
                MigrationIssue(
                    severity="error",
                    code="symlink_rejected",
                    path=str(child),
                    message="symlink entries are not inspected",
                )
            )
            continue
        if child.is_dir():
            candidates.append(child)
        else:
            issues.append(
                MigrationIssue(
                    severity="warning",
                    code="non_directory_ignored",
                    path=str(child),
                    message="non-directory item ignored",
                )
            )
    return candidates


def inspect_candidate_entry(entry_dir: Path) -> MigrationEntryReport:
    """Inspect one candidate entry without mutating it."""

    if ENTRY_DIR_NAME_PATTERN.fullmatch(entry_dir.name):
        return inspect_v1_entry(entry_dir)
    if LEGACY_ENTRY_DIR_NAME_PATTERN.fullmatch(entry_dir.name):
        return inspect_legacy_entry(entry_dir)
    return inspect_unknown_entry(entry_dir)


def inspect_v1_entry(entry_dir: Path) -> MigrationEntryReport:
    """Validate one current-format entry."""

    builder = _EntryReportBuilder(
        source_path=str(entry_dir),
        detected_format="v1",
    )
    try:
        entry = read_entry(entry_dir)
    except EntryValidationError as error:
        builder.issue("error", "v1_invalid", str(error))
        return builder.build()

    builder.entry_id = str(entry.metadata.id)
    builder.created_at = entry.metadata.created_at.isoformat()
    builder.target_name = entry_dir.name
    builder.title_present = entry.metadata.title is not None
    builder.content_bytes = (entry_dir / "content.md").stat().st_size
    builder.comment_count = len(entry.comments.comments)
    builder.media_count = len(entry.media_manifest.media)
    return builder.build()


def inspect_legacy_entry(entry_dir: Path) -> MigrationEntryReport:
    """Inspect an early entries/<year>/YYYY-MM-DD-<uuid> entry."""

    builder = _EntryReportBuilder(
        source_path=str(entry_dir),
        detected_format="legacy",
    )
    missing = [name for name in REQUIRED_FACT_FILES if not (entry_dir / name).is_file()]
    if missing:
        builder.issue(
            "error",
            "missing_required_files",
            "missing required file(s): " + ", ".join(sorted(missing)),
        )

    directory_identity = parse_legacy_directory_identity(entry_dir)
    if directory_identity is None:
        builder.issue(
            "error",
            "legacy_directory_invalid",
            "legacy directory name must match YYYY-MM-DD-<uuid>",
        )
    else:
        directory_date, directory_uuid = directory_identity
        builder.entry_id = str(directory_uuid)
        if entry_dir.parent.name.isdigit() and entry_dir.parent.name != directory_date[:4]:
            builder.issue(
                "warning",
                "legacy_year_mismatch",
                "year parent does not match legacy directory date",
            )

    metadata = read_json_object_for_report(entry_dir / "metadata.json", builder)
    created_at = parse_legacy_created_at(metadata, builder) if metadata is not None else None
    if metadata is not None:
        builder.title_present = bool(str(metadata.get("title", "")).strip())
        builder.old_metadata_fields = tuple(sorted(OLD_METADATA_FIELDS.intersection(metadata)))
        if builder.old_metadata_fields:
            builder.issue(
                "warning",
                "old_metadata_fields",
                "old metadata fields found: " + ", ".join(builder.old_metadata_fields),
            )
        validate_legacy_metadata_shape(metadata, builder)
        validate_legacy_identity(metadata, directory_identity, builder)

    if created_at is not None:
        builder.created_at = created_at.isoformat()
        if builder.entry_id is not None:
            builder.target_name = create_entry_directory_name(created_at, UUID(builder.entry_id))

    builder.content_bytes = inspect_content_file(entry_dir / "content.md", builder)
    builder.comment_count = inspect_comments_file(entry_dir / "comments.json", builder)
    builder.media_count = inspect_media_manifest_file(
        entry_dir / "media-manifest.json",
        builder,
    )
    return builder.build()


def inspect_unknown_entry(entry_dir: Path) -> MigrationEntryReport:
    """Report an unrecognized directory as blocked but still count safe facts."""

    builder = _EntryReportBuilder(
        source_path=str(entry_dir),
        detected_format="unknown",
    )
    builder.issue(
        "error",
        "unknown_directory_format",
        "entry directory must be v1 YYYYMMDDHHmm-<uuid> or legacy YYYY-MM-DD-<uuid>",
    )
    builder.content_bytes = inspect_content_file(entry_dir / "content.md", builder)
    builder.comment_count = inspect_comments_file(entry_dir / "comments.json", builder)
    builder.media_count = inspect_media_manifest_file(
        entry_dir / "media-manifest.json",
        builder,
    )
    return builder.build()


def parse_legacy_directory_identity(entry_dir: Path) -> tuple[str, UUID] | None:
    """Return legacy date and UUID from a YYYY-MM-DD-<uuid> directory name."""

    match = LEGACY_ENTRY_DIR_NAME_PATTERN.fullmatch(entry_dir.name)
    if not match:
        return None
    return match.group("date"), UUID(match.group("id"))


def read_json_object_for_report(
    path: Path,
    builder: _EntryReportBuilder,
) -> dict[str, object] | None:
    """Read one JSON object for dry-run reporting."""

    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        builder.issue("error", f"{path.name}_not_utf8", f"{path.name} must be UTF-8")
        return None
    except json.JSONDecodeError:
        builder.issue(
            "error",
            f"{path.name}_invalid_json",
            f"{path.name} must contain valid JSON",
        )
        return None

    if not isinstance(value, dict):
        builder.issue("error", f"{path.name}_not_object", f"{path.name} must be an object")
        return None
    return value


def parse_legacy_created_at(
    metadata: dict[str, object],
    builder: _EntryReportBuilder,
) -> datetime | None:
    """Parse timezone-aware metadata.created_at from a legacy metadata object."""

    raw_created_at = metadata.get("created_at")
    if not isinstance(raw_created_at, str):
        builder.issue("error", "created_at_missing", "metadata.created_at is required")
        return None
    try:
        created_at = datetime.fromisoformat(raw_created_at)
    except ValueError:
        builder.issue("error", "created_at_invalid", "metadata.created_at is invalid")
        return None
    if created_at.utcoffset() is None:
        builder.issue(
            "error",
            "created_at_without_timezone",
            "metadata.created_at must include a UTC offset",
        )
        return None
    return created_at


def validate_legacy_metadata_shape(
    metadata: dict[str, object],
    builder: _EntryReportBuilder,
) -> None:
    """Classify whether legacy metadata already satisfies v1 after field cleanup."""

    v1_candidate = {
        key: value
        for key, value in metadata.items()
        if key not in OLD_METADATA_FIELDS
    }
    try:
        parse_metadata(v1_candidate)
    except EntryValidationError as error:
        builder.issue(
            "error",
            "metadata_requires_manual_fix",
            str(error),
        )


def validate_legacy_identity(
    metadata: dict[str, object],
    directory_identity: tuple[str, UUID] | None,
    builder: _EntryReportBuilder,
) -> None:
    """Check legacy metadata ID and directory identity."""

    raw_id = metadata.get("id")
    try:
        metadata_id = UUID(str(raw_id))
    except (TypeError, ValueError):
        builder.issue("error", "metadata_id_invalid", "metadata.id must be a UUID")
        return

    if directory_identity is not None and metadata_id != directory_identity[1]:
        builder.issue(
            "error",
            "directory_uuid_mismatch",
            "legacy directory UUID does not match metadata.id",
        )


def inspect_content_file(path: Path, builder: _EntryReportBuilder) -> int:
    """Inspect content.md without returning or rendering its body."""

    if not path.exists():
        return 0
    try:
        raw_content = path.read_bytes()
        content = raw_content.decode("utf-8")
    except UnicodeDecodeError:
        builder.issue("error", "content_not_utf8", "content.md must be UTF-8")
        return 0
    if "\r" in content:
        builder.issue("error", "content_crlf", "content.md must use LF line endings")
    if not content.strip():
        builder.issue("error", "content_blank", "content.md must not be blank")
    return len(raw_content)


def inspect_comments_file(path: Path, builder: _EntryReportBuilder) -> int:
    """Inspect comments.json and return a safe comment count."""

    value = read_json_object_for_report(path, builder)
    if value is None:
        return 0
    try:
        comments_file = parse_comments(value)
    except EntryValidationError as error:
        builder.issue("error", "comments_invalid", str(error))
        raw_comments = value.get("comments")
        return len(raw_comments) if isinstance(raw_comments, list) else 0
    return len(comments_file.comments)


def inspect_media_manifest_file(path: Path, builder: _EntryReportBuilder) -> int:
    """Inspect media-manifest.json and return a safe media count."""

    value = read_json_object_for_report(path, builder)
    if value is None:
        return 0
    try:
        media_manifest = parse_media_manifest(value)
    except EntryValidationError as error:
        builder.issue("error", "media_manifest_invalid", str(error))
        return count_raw_media_items(value)
    except ValidationError as error:
        builder.issue("error", "media_manifest_invalid", str(error))
        return count_raw_media_items(value)
    return len(media_manifest.media)


def count_raw_media_items(value: object) -> int:
    """Return raw media count for malformed manifests when possible."""

    try:
        media = MediaManifest.model_validate(value).media
    except ValidationError:
        if isinstance(value, dict) and isinstance(value.get("media"), list):
            return len(value["media"])
        return 0
    return len(media)
