"""Rebuildable SQLite index for Serein entries."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

from serein.storage.repository import EntrySummary, scan_entry_summaries


INDEX_RELATIVE_PATH = Path(".serein") / "index.sqlite3"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DateCount:
    """Number of entries on a local diary date."""

    date: str
    count: int


def get_index_path(data_dir: Path) -> Path:
    """Return the conventional rebuildable index path inside DIARY_DATA_DIR."""

    return Path(data_dir) / INDEX_RELATIVE_PATH


def rebuild_index(data_dir: Path, index_path: Path | None = None) -> Path:
    """Rebuild the SQLite index from fact files and return the index path."""

    data_dir = Path(data_dir)
    index_path = Path(index_path) if index_path is not None else get_index_path(data_dir)
    summaries = scan_entry_summaries(data_dir)

    index_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(index_path)) as connection:
        with connection:
            create_schema(connection)
            replace_entries(connection, summaries)

    return index_path


def create_schema(connection: sqlite3.Connection) -> None:
    """Create the current index schema."""

    connection.executescript(
        """
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS entries (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            local_date TEXT NOT NULL,
            entry_path TEXT NOT NULL,
            title TEXT,
            content_excerpt TEXT NOT NULL,
            comment_count INTEGER NOT NULL,
            media_count INTEGER NOT NULL,
            deleted INTEGER NOT NULL CHECK (deleted IN (0, 1))
        );

        CREATE INDEX IF NOT EXISTS idx_entries_created_at ON entries(created_at);
        CREATE INDEX IF NOT EXISTS idx_entries_local_date ON entries(local_date);
        CREATE INDEX IF NOT EXISTS idx_entries_deleted ON entries(deleted);
        """
    )
    connection.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )


def replace_entries(connection: sqlite3.Connection, summaries: list[EntrySummary]) -> None:
    """Replace all indexed entries with the provided summaries."""

    connection.execute("DELETE FROM entries")
    connection.executemany(
        """
        INSERT INTO entries (
            id,
            created_at,
            local_date,
            entry_path,
            title,
            content_excerpt,
            comment_count,
            media_count,
            deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                str(summary.id),
                summary.created_at.isoformat(),
                summary.created_at.date().isoformat(),
                summary.path.as_posix(),
                summary.title,
                summary.content_excerpt,
                summary.comment_count,
                summary.media_count,
                int(summary.deleted),
            )
            for summary in summaries
        ],
    )


def list_indexed_entries(
    index_path: Path,
    *,
    descending: bool = False,
    include_deleted: bool = True,
) -> list[EntrySummary]:
    """List entries from an existing SQLite index."""

    direction = "DESC" if descending else "ASC"
    where = "" if include_deleted else "WHERE deleted = 0"
    with closing(sqlite3.connect(index_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"SELECT * FROM entries {where} ORDER BY created_at {direction}, id {direction}"
        ).fetchall()

    return [row_to_summary(row) for row in rows]


def count_entries_by_date(
    index_path: Path,
    *,
    include_deleted: bool = False,
) -> list[DateCount]:
    """Return local-date entry counts from an existing SQLite index."""

    where = "" if include_deleted else "WHERE deleted = 0"
    with closing(sqlite3.connect(index_path)) as connection:
        rows = connection.execute(
            f"""
            SELECT local_date, COUNT(*) AS count
            FROM entries
            {where}
            GROUP BY local_date
            ORDER BY local_date ASC
            """
        ).fetchall()

    return [DateCount(date=row[0], count=row[1]) for row in rows]


def get_index_schema_version(index_path: Path) -> int | None:
    """Read the schema version from an existing index."""

    with closing(sqlite3.connect(index_path)) as connection:
        row = connection.execute(
            "SELECT value FROM meta WHERE key = ?",
            ("schema_version",),
        ).fetchone()

    return int(row[0]) if row else None


def row_to_summary(row: sqlite3.Row) -> EntrySummary:
    """Convert an indexed row back to an EntrySummary-like object."""

    return EntrySummary(
        id=UUID(row["id"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        path=Path(row["entry_path"]),
        title=row["title"],
        content_excerpt=row["content_excerpt"],
        comment_count=row["comment_count"],
        media_count=row["media_count"],
        deleted=bool(row["deleted"]),
    )
