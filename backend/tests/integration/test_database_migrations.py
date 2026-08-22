import sqlite3

from models.database import DatabaseManager


def test_database_path_wal_and_idempotent_schema(secure_env):
    path = secure_env / "evaluation.db"
    db = DatabaseManager(str(path))
    db.init_database()
    conn = db.get_connection()
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"rag_connections", "rag_connection_audit", "evaluation_sample_runs"} <= tables
    columns = {row[1] for row in conn.execute("PRAGMA table_info(evaluation_tasks)")}
    assert {"rag_provider", "assistant_id", "knowledge_base_selection_mode_snapshot", "outcome"} <= columns
    conn.close()
