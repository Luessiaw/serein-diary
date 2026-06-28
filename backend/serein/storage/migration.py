"""Read-only migration dry-run helpers for Serein v1 entry data."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from serein.storage.entry import (
    ENTRY_DIR_NAME_PATTERN,
    EntryValidationError,
    read_entry,
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
    """Dry-run result for one candidate v1 entry directory."""

    source_path: str
    detected_format: Literal["v1", "unknown"]
    can_migrate: bool
    entry_id: str | None = None
    created_at: str | None = None
    target_name: str | None = None
    title_present: bool = False
    content_bytes: int = 0
    comment_count: int = 0
    media_count: int = 0
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
            for issue in entry.issues:
                lines.append(
                    f"  [{issue.severity}] {issue.code} {issue.path}: {issue.message}"
                )

        return "\n".join(lines)


@dataclass
class _EntryReportBuilder:
    """Mutable helper used internally while inspecting one entry."""

    source_path: str
    detected_format: Literal["v1", "unknown"]
    entry_id: str | None = None
    created_at: str | None = None
    target_name: str | None = None
    title_present: bool = False
    content_bytes: int = 0
    comment_count: int = 0
    media_count: int = 0
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
            issues=tuple(self.issues),
        )


def dry_run_migration(
    source_dir: Path,
    target_dir: Path | None = None,
) -> MigrationDryRunReport:
    """Inspect v1 source entries without modifying source or target directories."""

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
    """Find likely v1 entry directories under a data root or entries directory."""

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

        candidates.append(child)

    return candidates, issues


def looks_like_entry_dir(path: Path) -> bool:
    """Return whether a directory itself appears to be one entry."""

    return (
        ENTRY_DIR_NAME_PATTERN.fullmatch(path.name) is not None
        or any((path / name).exists() for name in REQUIRED_FACT_FILES)
    )


def inspect_candidate_entry(entry_dir: Path) -> MigrationEntryReport:
    """Inspect one candidate entry without mutating it."""

    if ENTRY_DIR_NAME_PATTERN.fullmatch(entry_dir.name):
        return inspect_v1_entry(entry_dir)
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


def inspect_unknown_entry(entry_dir: Path) -> MigrationEntryReport:
    """Report an unrecognized directory as blocked."""

    builder = _EntryReportBuilder(
        source_path=str(entry_dir),
        detected_format="unknown",
    )
    builder.issue(
        "error",
        "unknown_directory_format",
        "entry directory must match v1 YYYYMMDDHHmm-<uuid>",
    )
    return builder.build()
