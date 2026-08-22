"""Initialize and migrate the SQLite tables used by evaluation reports."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def get_column_type(column_name: str) -> str:
    """Return the SQLite type/default used for a known column."""
    if column_name in {"progress", "file_size", "num_samples"}:
        return "INTEGER DEFAULT 0"
    if column_name in {"has_reference", "has_contexts"}:
        return "INTEGER DEFAULT 0"
    if column_name in {"created_at", "completed_at", "started_at"}:
        return "TIMESTAMP"
    return "TEXT"


def _ensure_columns(
    cursor: sqlite3.Cursor,
    table_name: str,
    required_columns: list[str],
) -> None:
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing = {row[1] for row in cursor.fetchall()}
    for column_name in required_columns:
        if column_name not in existing:
            cursor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN "
                f"{column_name} {get_column_type(column_name)}"
            )


def init_database(db_path: str | os.PathLike[str] | None = None) -> None:
    """Create the report table and add missing columns to existing tables."""
    path = Path(db_path) if db_path else Path(__file__).with_name("evaluation.db")
    connection = sqlite3.connect(path)
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_reports (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                dataset_id TEXT NOT NULL,
                report_data TEXT,
                overall_scores TEXT,
                detailed_scores TEXT,
                evaluation_metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES evaluation_tasks (id)
            )
            """)
        _ensure_columns(
            cursor,
            "evaluation_tasks",
            [
                "id",
                "name",
                "status",
                "progress",
                "chat_id",
                "dataset_id",
                "metrics",
                "created_at",
                "completed_at",
                "started_at",
                "error_message",
            ],
        )
        _ensure_columns(
            cursor,
            "datasets",
            [
                "id",
                "name",
                "file_type",
                "file_size",
                "num_samples",
                "has_reference",
                "has_contexts",
                "created_at",
            ],
        )
        connection.commit()
        print("✅ 数据库表结构初始化成功")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    init_database()
