from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class ActivityRow:
    timestamp_local: str
    date_local: str
    status: str
    source_type: str
    window_title: str
    process_name: str
    url: str
    domain: str
    interval_minutes: int


class ActivityStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_local TEXT NOT NULL,
                    date_local TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source_type TEXT NOT NULL DEFAULT 'application',
                    window_title TEXT,
                    process_name TEXT,
                    url TEXT,
                    domain TEXT,
                    interval_minutes INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_activity_date_local
                ON activity_log(date_local)
                """
            )
            self._ensure_source_type_column(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_assignments (
                    process_name TEXT NOT NULL,
                    window_title TEXT NOT NULL,
                    task_name TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (process_name, window_title)
                )
                """
            )

    def _ensure_source_type_column(self, conn: sqlite3.Connection) -> None:
        columns = conn.execute("PRAGMA table_info(activity_log)").fetchall()
        column_names = {col[1] for col in columns}
        if "source_type" not in column_names:
            conn.execute(
                """
                ALTER TABLE activity_log
                ADD COLUMN source_type TEXT NOT NULL DEFAULT 'application'
                """
            )

    def insert_activity(self, row: ActivityRow) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO activity_log (
                    timestamp_local,
                    date_local,
                    status,
                    source_type,
                    window_title,
                    process_name,
                    url,
                    domain,
                    interval_minutes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.timestamp_local,
                    row.date_local,
                    row.status,
                    row.source_type,
                    row.window_title,
                    row.process_name,
                    row.url,
                    row.domain,
                    row.interval_minutes,
                ),
            )

    def cleanup_older_than_days(self, retention_days: int) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM activity_log
                WHERE date(date_local) < date('now', 'localtime', ?)
                """,
                (f"-{retention_days} days",),
            )
            return cursor.rowcount

    def get_entries_for_date(self, date_value: str) -> list[ActivityRow]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    timestamp_local,
                    date_local,
                    status,
                    source_type,
                    window_title,
                    process_name,
                    url,
                    domain,
                    interval_minutes
                FROM activity_log
                WHERE date_local = ?
                ORDER BY timestamp_local ASC
                """,
                (date_value,),
            ).fetchall()
        return [ActivityRow(*row) for row in rows]

    def get_available_dates(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT date_local
                FROM activity_log
                ORDER BY date_local DESC
                """
            ).fetchall()
        return [row[0] for row in rows]

    def get_task_assignments(self) -> dict[str, str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT process_name, window_title, task_name
                FROM task_assignments
                """
            ).fetchall()
        return {_assignment_key(process_name, window_title): task_name for process_name, window_title, task_name in rows}

    def upsert_task_assignment(self, process_name: str, window_title: str, task_name: str) -> None:
        normalized_task = (task_name or "").strip()
        with self._connect() as conn:
            if not normalized_task or normalized_task.lower() == "unassigned":
                conn.execute(
                    """
                    DELETE FROM task_assignments
                    WHERE process_name = ? AND window_title = ?
                    """,
                    (process_name, window_title),
                )
                return

            conn.execute(
                """
                INSERT INTO task_assignments (
                    process_name,
                    window_title,
                    task_name,
                    updated_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(process_name, window_title) DO UPDATE SET
                    task_name = excluded.task_name,
                    updated_at = excluded.updated_at
                """,
                (
                    process_name,
                    window_title,
                    normalized_task,
                    now_local().isoformat(),
                ),
            )


def _assignment_key(process_name: str, window_title: str) -> str:
    return f"{process_name}\t{window_title}"


def now_local() -> datetime:
    return datetime.now().astimezone()
