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
    sample_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(evaluation_sample_runs)")
    }
    assert {
        "provider_session_id",
        "session_creation_status",
        "session_cleanup_status",
        "session_cleanup_error",
        "session_cleanup_attempts",
        "tool_errors",
    } <= sample_columns
    conn.close()


def test_pending_cleanup_group_and_state_updates(secure_env):
    db = DatabaseManager(str(secure_env / "evaluation.db"))
    db.create_dataset({"id": "d", "name": "D", "status": "completed"})
    db.create_evaluation_task({"id": "t", "chat_id": "a", "dataset_id": "d", "metrics": [], "rag_provider": "intelliq", "rag_connection_id": "conn"})
    run_id = db.create_sample_run({"task_id": "t", "sample_index": 0, "session_id": "local-correlation", "question": "q"})
    db.mark_sample_session_created(run_id, "provider-session")
    assert db.get_pending_session_cleanup_groups() == [{"rag_connection_id": "conn", "session_ids": ["provider-session"]}]
    db.mark_session_cleanup_result(["provider-session"], ["provider-session"], [])
    assert db.get_pending_session_cleanup_groups() == []


def test_sample_run_tool_errors_are_persisted_and_decoded(secure_env):
    db = DatabaseManager(str(secure_env / "evaluation.db"))
    db.create_dataset({"id": "d-tool", "name": "D", "status": "completed"})
    db.create_evaluation_task(
        {"id": "t-tool", "chat_id": "a", "dataset_id": "d-tool", "metrics": []}
    )
    run_id = db.create_sample_run(
        {"task_id": "t-tool", "sample_index": 0, "session_id": "s", "question": "q"}
    )
    db.complete_sample_run(
        run_id,
        {
            "session_id": "provider-s",
            "completed": True,
            "score_eligible": True,
            "answer": "answer",
            "tool_errors": [
                {
                    "tool_call_id": "call-1",
                    "tool_name": "list_knowledge_chunks",
                    "message": "knowledge not found",
                    "recovered": True,
                    "event_count": 1,
                }
            ],
        },
    )

    run = db.get_final_sample_runs("t-tool")[0]
    assert run["tool_errors"][0]["recovered"] is True
