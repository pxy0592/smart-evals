"""SQLite persistence for Smart Eval."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class DatabaseManager:
    def __init__(self, db_path: str | None = None):
        configured = db_path or os.getenv("DATABASE_PATH", "data/evaluation.db")
        if not os.path.isabs(configured):
            repo_root = Path(__file__).resolve().parents[2]
            configured = str(repo_root / configured)
        self.db_path = os.path.abspath(configured)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        legacy = Path(__file__).resolve().parents[1] / "evaluation.db"
        if not os.path.exists(self.db_path) and legacy.exists() and str(legacy) != self.db_path:
            shutil.copy2(legacy, self.db_path)
        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @staticmethod
    def _ensure_columns(cursor: sqlite3.Cursor, table: str, columns: Dict[str, str]) -> None:
        existing = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()}
        for name, declaration in columns.items():
            if name not in existing:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")

    def init_database(self) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS api_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                provider TEXT NOT NULL,
                api_key TEXT NOT NULL,
                endpoint TEXT,
                model TEXT,
                embedding_model TEXT,
                temperature REAL DEFAULT 0.7,
                max_tokens INTEGER DEFAULT 4000,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_default BOOLEAN DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS system_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT,
                description TEXT,
                category TEXT DEFAULT 'general',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS datasets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                file_name TEXT,
                file_type TEXT,
                file_size INTEGER,
                storage_path TEXT,
                num_samples INTEGER DEFAULT 0,
                has_reference BOOLEAN DEFAULT 0,
                has_contexts BOOLEAN DEFAULT 0,
                sample_fields TEXT,
                status TEXT DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                error_message TEXT,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS evaluation_tasks (
                id TEXT PRIMARY KEY,
                name TEXT,
                chat_id TEXT NOT NULL,
                dataset_id TEXT NOT NULL,
                llm_model TEXT,
                embedding_model TEXT,
                metrics TEXT,
                status TEXT DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                total_samples INTEGER DEFAULT 0,
                processed_samples INTEGER DEFAULT 0,
                batch_size INTEGER DEFAULT 10,
                error_message TEXT,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY(dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS evaluation_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL UNIQUE,
                chat_id TEXT NOT NULL,
                dataset_id TEXT NOT NULL,
                overall_scores TEXT,
                detailed_scores TEXT,
                evaluation_metadata TEXT,
                report_file_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS evaluation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                level TEXT,
                message TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS rag_connections (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                provider TEXT NOT NULL,
                base_url TEXT NOT NULL,
                api_key_ciphertext TEXT NOT NULL,
                api_key_fingerprint TEXT NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT 1,
                revision INTEGER NOT NULL DEFAULT 1,
                validation_status TEXT NOT NULL DEFAULT 'untested',
                last_validated_at TIMESTAMP,
                last_error_category TEXT,
                last_error_message TEXT,
                created_by TEXT NOT NULL DEFAULT 'deployment-admin',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS rag_connection_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                connection_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                action TEXT NOT NULL,
                changed_fields TEXT NOT NULL,
                actor TEXT NOT NULL DEFAULT 'deployment-admin',
                caller_label TEXT,
                result TEXT NOT NULL,
                error_category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS evaluation_sample_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                sample_index INTEGER NOT NULL,
                attempt INTEGER NOT NULL DEFAULT 1,
                session_id TEXT NOT NULL,
                provider_session_id TEXT,
                session_creation_status TEXT NOT NULL DEFAULT 'pending',
                session_cleanup_status TEXT NOT NULL DEFAULT 'not_required',
                session_cleanup_error TEXT,
                session_cleanup_attempts INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                question TEXT NOT NULL,
                answer TEXT,
                partial_answer TEXT,
                contexts TEXT NOT NULL DEFAULT '[]',
                references_json TEXT NOT NULL DEFAULT '[]',
                intermediate_event_summary TEXT NOT NULL DEFAULT '{}',
                completed_signal_received BOOLEAN NOT NULL DEFAULT 0,
                score_eligible BOOLEAN NOT NULL DEFAULT 0,
                error_category TEXT,
                error_message TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                UNIQUE(task_id, sample_index, attempt)
            );
            """
        )
        self._ensure_columns(cursor, "datasets", {
            "normalized_storage_path": "TEXT",
            "normalization_status": "TEXT DEFAULT 'pending'",
        })
        self._ensure_columns(cursor, "evaluation_tasks", {
            "rag_provider": "TEXT NOT NULL DEFAULT 'ragflow'",
            "rag_connection_id": "TEXT",
            "rag_connection_revision": "INTEGER",
            "assistant_id": "TEXT",
            "assistant_name_snapshot": "TEXT",
            "knowledge_base_ids": "TEXT NOT NULL DEFAULT '[]'",
            "knowledge_base_names_snapshot": "TEXT NOT NULL DEFAULT '[]'",
            "knowledge_base_selection_mode_snapshot": "TEXT",
            "connection_name_snapshot": "TEXT",
            "connection_base_url_snapshot": "TEXT",
            "source_legacy": "BOOLEAN NOT NULL DEFAULT 1",
            "interrupted_at": "TIMESTAMP",
            "has_warnings": "BOOLEAN NOT NULL DEFAULT 0",
            "outcome": "TEXT",
            "scored_sample_count": "INTEGER NOT NULL DEFAULT 0",
            "failed_sample_count": "INTEGER NOT NULL DEFAULT 0",
        })
        self._ensure_columns(cursor, "evaluation_reports", {
            "rag_provider": "TEXT NOT NULL DEFAULT 'ragflow'",
            "rag_connection_id": "TEXT",
            "assistant_id": "TEXT",
            "knowledge_base_ids": "TEXT NOT NULL DEFAULT '[]'",
            "source_snapshot": "TEXT NOT NULL DEFAULT '{}'",
            "scored_sample_count": "INTEGER NOT NULL DEFAULT 0",
            "failed_sample_count": "INTEGER NOT NULL DEFAULT 0",
            "total_sample_count": "INTEGER NOT NULL DEFAULT 0",
            "success_rate": "REAL NOT NULL DEFAULT 0",
            "warning": "TEXT",
        })
        self._ensure_columns(cursor, "evaluation_sample_runs", {
            "provider_session_id": "TEXT",
            "session_creation_status": "TEXT NOT NULL DEFAULT 'pending'",
            "session_cleanup_status": "TEXT NOT NULL DEFAULT 'not_required'",
            "session_cleanup_error": "TEXT",
            "session_cleanup_attempts": "INTEGER NOT NULL DEFAULT 0",
        })
        cursor.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_rag_connections_provider ON rag_connections(provider, enabled);
            CREATE INDEX IF NOT EXISTS idx_tasks_provider_status ON evaluation_tasks(rag_provider, status);
            CREATE INDEX IF NOT EXISTS idx_sample_runs_task ON evaluation_sample_runs(task_id, sample_index, attempt);
            CREATE INDEX IF NOT EXISTS idx_sample_runs_pending_cleanup ON evaluation_sample_runs(session_cleanup_status, provider_session_id);
            INSERT OR IGNORE INTO schema_migrations(version, name) VALUES (1, 'rag_provider_foundation');
            """
        )
        self.insert_default_settings(cursor)
        self.insert_default_api_config(cursor)
        conn.commit()
        conn.close()

    def insert_default_settings(self, cursor: sqlite3.Cursor) -> None:
        settings = {
            "system_name": ("Smart Evaluation", "系统名称", "general"),
            "language": ("zh-CN", "系统语言", "general"),
            "timezone": ("Asia/Shanghai", "时区", "general"),
            "max_upload_size": ("10", "最大上传大小(MB)", "general"),
        }
        for key, (value, description, category) in settings.items():
            cursor.execute("INSERT OR IGNORE INTO system_settings(key,value,description,category) VALUES (?,?,?,?)", (key, value, description, category))

    def insert_default_api_config(self, cursor: sqlite3.Cursor) -> None:
        if cursor.execute("SELECT COUNT(*) FROM api_configs").fetchone()[0] == 0:
            cursor.execute(
                """INSERT INTO api_configs(name,provider,api_key,endpoint,model,embedding_model,temperature,max_tokens,is_default)
                VALUES (?,?,?,?,?,?,?,?,1)""",
                (
                    "Default API Config",
                    os.getenv("DEFAULT_LLM_PROVIDER", "siliconflow"),
                    os.getenv("SILICONFLOW_API_KEY", ""),
                    os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
                    os.getenv("DEFAULT_LLM_MODEL", "Qwen/Qwen2.5-32B-Instruct"),
                    os.getenv("DEFAULT_EMBEDDING_MODEL", "BAAI/bge-m3"),
                    0.7,
                    4000,
                ),
            )

    # API/LLM configuration
    def create_api_config(self, data: Dict[str, Any]) -> str:
        conn = self.get_connection()
        cursor = conn.execute(
            """INSERT INTO api_configs(name,provider,api_key,endpoint,model,embedding_model,temperature,max_tokens,is_default)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (data["name"], data["provider"], data["api_key"], data.get("endpoint"), data.get("model"), data.get("embedding_model"), data.get("temperature", .7), data.get("max_tokens", 4000), bool(data.get("is_default"))),
        )
        conn.commit(); value = str(cursor.lastrowid); conn.close(); return value

    def get_api_configs(self) -> List[Dict[str, Any]]:
        conn = self.get_connection(); rows = [dict(r) for r in conn.execute("SELECT * FROM api_configs ORDER BY is_default DESC, created_at DESC")]; conn.close(); return rows

    def get_default_api_config(self) -> Optional[Dict[str, Any]]:
        conn = self.get_connection(); row = conn.execute("SELECT * FROM api_configs ORDER BY is_default DESC, id LIMIT 1").fetchone(); conn.close(); return dict(row) if row else None

    def update_api_config(self, config_id: int, data: Dict[str, Any]) -> bool:
        mapping = {"name", "provider", "api_key", "endpoint", "model", "embedding_model", "temperature", "max_tokens", "is_default"}
        values = [(k, v) for k, v in data.items() if k in mapping]
        if not values: return False
        conn = self.get_connection()
        if data.get("is_default"):
            conn.execute("UPDATE api_configs SET is_default=0")
        sql = ",".join(f"{k}=?" for k, _ in values) + ",updated_at=CURRENT_TIMESTAMP"
        cursor = conn.execute(f"UPDATE api_configs SET {sql} WHERE id=?", [v for _, v in values] + [config_id])
        conn.commit(); changed = cursor.rowcount > 0; conn.close(); return changed

    def delete_api_config(self, config_id: int) -> bool:
        conn = self.get_connection(); cursor = conn.execute("DELETE FROM api_configs WHERE id=?", (config_id,)); conn.commit(); changed = cursor.rowcount > 0; conn.close(); return changed

    def get_setting(self, key: str, default: Any = None) -> Any:
        conn = self.get_connection(); row = conn.execute("SELECT value FROM system_settings WHERE key=?", (key,)).fetchone(); conn.close(); return row["value"] if row else default

    def update_setting(self, key: str, value: str, description: str | None = None, category: str = "general") -> None:
        conn = self.get_connection(); conn.execute("""INSERT INTO system_settings(key,value,description,category) VALUES (?,?,?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, description=COALESCE(excluded.description,system_settings.description), category=excluded.category, updated_at=CURRENT_TIMESTAMP""", (key, value, description, category)); conn.commit(); conn.close()

    # Datasets
    def create_dataset(self, data: Dict[str, Any]) -> str:
        conn = self.get_connection()
        conn.execute("""INSERT INTO datasets(id,name,description,file_name,file_type,file_size,storage_path,num_samples,has_reference,has_contexts,sample_fields,status,progress,error_message,created_by,normalized_storage_path,normalization_status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            data["id"], data["name"], data.get("description"), data.get("file_name"), data.get("file_type"), data.get("file_size"), data.get("storage_path"), data.get("num_samples", 0), bool(data.get("has_reference")), bool(data.get("has_contexts")), json.dumps(data.get("sample_fields", [])), data.get("status", "pending"), data.get("progress", 0), data.get("error_message"), data.get("created_by", "system"), data.get("normalized_storage_path"), data.get("normalization_status", "pending")))
        conn.commit(); conn.close(); return data["id"]

    def update_dataset_status(self, dataset_id: str, status: str, **values) -> None:
        allowed = {"progress", "error_message", "num_samples", "has_reference", "has_contexts", "normalized_storage_path", "normalization_status", "sample_fields"}
        updates = [("status", status)] + [(k, json.dumps(v) if k == "sample_fields" else v) for k, v in values.items() if k in allowed and v is not None]
        conn = self.get_connection(); sql = ",".join(f"{k}=?" for k, _ in updates) + ",updated_at=CURRENT_TIMESTAMP"; conn.execute(f"UPDATE datasets SET {sql} WHERE id=?", [v for _, v in updates] + [dataset_id]); conn.commit(); conn.close()

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection(); row = conn.execute("SELECT * FROM datasets WHERE id=?", (dataset_id,)).fetchone(); conn.close()
        if not row: return None
        result = dict(row); result["sample_fields"] = json.loads(result.get("sample_fields") or "[]"); return result

    def get_datasets(self, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        conn = self.get_connection(); total = conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]; rows = [dict(r) for r in conn.execute("SELECT * FROM datasets ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))]; conn.close()
        for row in rows: row["sample_fields"] = json.loads(row.get("sample_fields") or "[]")
        return {"datasets": rows, "total": total, "limit": limit, "offset": offset}

    # Tasks
    def create_evaluation_task(self, data: Dict[str, Any]) -> str:
        conn = self.get_connection()
        conn.execute("""INSERT INTO evaluation_tasks(id,name,chat_id,dataset_id,llm_model,embedding_model,metrics,batch_size,created_by,rag_provider,rag_connection_id,rag_connection_revision,assistant_id,assistant_name_snapshot,knowledge_base_ids,knowledge_base_names_snapshot,knowledge_base_selection_mode_snapshot,connection_name_snapshot,connection_base_url_snapshot,source_legacy)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            data["id"], data.get("name"), data.get("chat_id") or data.get("assistant_id"), data["dataset_id"], data.get("llm_model"), data.get("embedding_model"), json.dumps(data.get("metrics", [])), data.get("batch_size", 10), data.get("created_by", "anonymous"), data.get("rag_provider", "ragflow"), data.get("rag_connection_id"), data.get("rag_connection_revision"), data.get("assistant_id") or data.get("chat_id"), data.get("assistant_name_snapshot"), json.dumps(data.get("knowledge_base_ids", [])), json.dumps(data.get("knowledge_base_names_snapshot", [])), data.get("knowledge_base_selection_mode_snapshot"), data.get("connection_name_snapshot"), data.get("connection_base_url_snapshot"), bool(data.get("source_legacy", False))))
        conn.commit(); conn.close(); return data["id"]

    def update_task_status(self, task_id: str, status: str, **values) -> None:
        allowed = {"progress", "error_message", "processed_samples", "total_samples", "has_warnings", "outcome", "scored_sample_count", "failed_sample_count", "interrupted_at"}
        updates = [("status", status)] + [(k, v) for k, v in values.items() if k in allowed and v is not None]
        extras = []
        if status == "running" and values.get("progress", 0) == 0: extras.append("started_at=CURRENT_TIMESTAMP")
        if status in {"completed", "failed", "cancelled"}: extras.append("completed_at=CURRENT_TIMESTAMP")
        sql = ",".join(f"{k}=?" for k, _ in updates)
        if extras: sql += "," + ",".join(extras)
        conn = self.get_connection(); conn.execute(f"UPDATE evaluation_tasks SET {sql} WHERE id=?", [v for _, v in updates] + [task_id]); conn.commit(); conn.close()

    # Reports
    def save_evaluation_report(self, data: Dict[str, Any]) -> str:
        report_path = self._generate_report_file(data)
        conn = self.get_connection(); cursor = conn.execute("""INSERT OR REPLACE INTO evaluation_reports(task_id,chat_id,dataset_id,overall_scores,detailed_scores,evaluation_metadata,report_file_path,rag_provider,rag_connection_id,assistant_id,knowledge_base_ids,source_snapshot,scored_sample_count,failed_sample_count,total_sample_count,success_rate,warning)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            data["task_id"], data.get("chat_id") or data.get("assistant_id"), data["dataset_id"], json.dumps(data.get("overall_scores", {})), json.dumps(data.get("detailed_scores", [])), json.dumps(data.get("evaluation_metadata", {})), report_path, data.get("rag_provider", "ragflow"), data.get("rag_connection_id"), data.get("assistant_id") or data.get("chat_id"), json.dumps(data.get("knowledge_base_ids", [])), json.dumps(data.get("source_snapshot", {})), data.get("scored_sample_count", 0), data.get("failed_sample_count", 0), data.get("total_sample_count", 0), data.get("success_rate", 0), json.dumps(data.get("warning")) if data.get("warning") else None))
        conn.commit(); value = str(cursor.lastrowid); conn.close(); return value

    def get_evaluation_report(self, task_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection(); row = conn.execute("SELECT * FROM evaluation_reports WHERE task_id=?", (task_id,)).fetchone(); conn.close()
        if not row: return None
        result = dict(row)
        for field, default in (("overall_scores", "{}"), ("detailed_scores", "[]"), ("evaluation_metadata", "{}"), ("knowledge_base_ids", "[]"), ("source_snapshot", "{}"), ("warning", "null")):
            result[field] = json.loads(result.get(field) or default)
        return result

    # RAG connections and audit
    def list_rag_connections(self, provider: str | None = None) -> List[Dict[str, Any]]:
        conn = self.get_connection(); sql = "SELECT * FROM rag_connections"; params: list[Any] = []
        if provider: sql += " WHERE provider=?"; params.append(provider)
        rows = [dict(r) for r in conn.execute(sql + " ORDER BY created_at", params)]; conn.close(); return rows

    def get_rag_connection(self, connection_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection(); row = conn.execute("SELECT * FROM rag_connections WHERE id=?", (connection_id,)).fetchone(); conn.close(); return dict(row) if row else None

    def create_rag_connection(self, data: Dict[str, Any]) -> str:
        conn = self.get_connection(); conn.execute("""INSERT INTO rag_connections(id,name,provider,base_url,api_key_ciphertext,api_key_fingerprint,enabled,revision,validation_status,created_by) VALUES (?,?,?,?,?,?,?,?,?,?)""", (data["id"], data["name"], data["provider"], data["base_url"], data["api_key_ciphertext"], data["api_key_fingerprint"], bool(data.get("enabled", True)), data.get("revision", 1), data.get("validation_status", "untested"), data.get("created_by", "deployment-admin"))); conn.commit(); conn.close(); return data["id"]

    def update_rag_connection(self, connection_id: str, updates: Dict[str, Any]) -> bool:
        allowed = {"name", "base_url", "api_key_ciphertext", "api_key_fingerprint", "enabled", "revision", "validation_status"}; values = [(k, v) for k, v in updates.items() if k in allowed]
        if not values: return False
        conn = self.get_connection(); sql = ",".join(f"{k}=?" for k, _ in values) + ",updated_at=CURRENT_TIMESTAMP"; cursor = conn.execute(f"UPDATE rag_connections SET {sql} WHERE id=?", [v for _, v in values] + [connection_id]); conn.commit(); changed = cursor.rowcount > 0; conn.close(); return changed

    def update_rag_connection_validation(self, connection_id: str, status: str, category: str | None, message: str | None) -> None:
        conn = self.get_connection(); conn.execute("UPDATE rag_connections SET validation_status=?,last_validated_at=CURRENT_TIMESTAMP,last_error_category=?,last_error_message=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, category, message, connection_id)); conn.commit(); conn.close()

    def add_rag_connection_audit(self, connection_id: str, revision: int, action: str, changed_fields: List[str], actor: str, result: str, error_category: str | None = None, caller_label: str | None = None) -> None:
        conn = self.get_connection(); conn.execute("INSERT INTO rag_connection_audit(connection_id,revision,action,changed_fields,actor,caller_label,result,error_category) VALUES (?,?,?,?,?,?,?,?)", (connection_id, revision, action, json.dumps(changed_fields), actor, caller_label, result, error_category)); conn.commit(); conn.close()

    # Sample execution
    def create_sample_run(self, data: Dict[str, Any]) -> int:
        conn = self.get_connection()
        cursor = conn.execute(
            """INSERT INTO evaluation_sample_runs
            (task_id,sample_index,attempt,session_id,status,question,session_creation_status,session_cleanup_status,started_at)
            VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
            (
                data["task_id"], data["sample_index"], data.get("attempt", 1),
                data["session_id"], data.get("status", "running"),
                data.get("question", ""), "pending", "not_required",
            ),
        )
        conn.commit(); run_id = cursor.lastrowid; conn.close(); return run_id

    def mark_sample_session_created(self, run_id: int, provider_session_id: str) -> None:
        conn = self.get_connection()
        conn.execute(
            """UPDATE evaluation_sample_runs
            SET provider_session_id=?, session_creation_status='created', session_cleanup_status='pending'
            WHERE id=?""",
            (provider_session_id, run_id),
        )
        conn.commit(); conn.close()

    def mark_sample_session_creation_failed(self, run_id: int, error: Dict[str, Any]) -> None:
        conn = self.get_connection()
        conn.execute(
            """UPDATE evaluation_sample_runs
            SET session_creation_status='failed', session_cleanup_status='not_required',
                error_category=?, error_message=? WHERE id=?""",
            (error.get("category"), error.get("message"), run_id),
        )
        conn.commit(); conn.close()

    def complete_sample_run(self, run_id: int, result: Dict[str, Any]) -> None:
        error = result.get("error") or {}
        provider_session_id = result.get("session_id") or None
        creation_status = result.get("session_creation_status") or ("created" if provider_session_id else "failed")
        cleanup_status = "pending" if creation_status == "created" else "not_required"
        conn = self.get_connection()
        conn.execute(
            """UPDATE evaluation_sample_runs SET
            status=?, provider_session_id=COALESCE(?, provider_session_id),
            session_creation_status=?, session_cleanup_status=CASE
                WHEN session_cleanup_status='cleaned' THEN 'cleaned' ELSE ? END,
            answer=?, partial_answer=?, contexts=?, references_json=?, intermediate_event_summary=?,
            completed_signal_received=?, score_eligible=?, error_category=?, error_message=?, completed_at=CURRENT_TIMESTAMP
            WHERE id=?""",
            (
                "completed" if result.get("score_eligible") else "failed",
                provider_session_id, creation_status, cleanup_status,
                result.get("answer"), result.get("partial_answer"),
                json.dumps(result.get("contexts", [])), json.dumps(result.get("references", [])),
                json.dumps(result.get("intermediate_event_summary", {})), bool(result.get("completed")),
                bool(result.get("score_eligible")), error.get("category"), error.get("message"), run_id,
            ),
        )
        conn.commit(); conn.close()

    def get_final_sample_runs(self, task_id: str) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        rows = conn.execute(
            """SELECT r.* FROM evaluation_sample_runs r JOIN (
                SELECT sample_index,MAX(attempt) attempt
                FROM evaluation_sample_runs WHERE task_id=? GROUP BY sample_index
            ) x ON x.sample_index=r.sample_index AND x.attempt=r.attempt
            WHERE r.task_id=? ORDER BY r.sample_index""",
            (task_id, task_id),
        ).fetchall()
        conn.close()
        return [self._decode_sample_run(dict(row)) for row in rows]

    @staticmethod
    def _decode_sample_run(item: Dict[str, Any]) -> Dict[str, Any]:
        item["contexts"] = json.loads(item.get("contexts") or "[]")
        item["references"] = json.loads(item.pop("references_json") or "[]")
        item["intermediate_event_summary"] = json.loads(item.get("intermediate_event_summary") or "{}")
        return item

    def get_pending_session_cleanup_groups(self) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        rows = conn.execute(
            """SELECT t.rag_connection_id, GROUP_CONCAT(DISTINCT r.provider_session_id) AS session_ids
            FROM evaluation_sample_runs r
            JOIN evaluation_tasks t ON t.id=r.task_id
            WHERE t.rag_provider='intelliq'
              AND r.session_creation_status='created'
              AND r.session_cleanup_status IN ('pending','failed')
              AND r.provider_session_id IS NOT NULL
            GROUP BY t.rag_connection_id"""
        ).fetchall()
        conn.close()
        return [
            {"rag_connection_id": row["rag_connection_id"], "session_ids": row["session_ids"].split(",")}
            for row in rows if row["rag_connection_id"] and row["session_ids"]
        ]

    def mark_session_cleanup_result(self, session_ids: List[str], cleaned_ids: List[str], failed_ids: List[str], error: Dict[str, Any] | None = None) -> None:
        if not session_ids:
            return
        conn = self.get_connection()
        for session_id in cleaned_ids:
            conn.execute(
                """UPDATE evaluation_sample_runs SET session_cleanup_status='cleaned',
                session_cleanup_error=NULL, session_cleanup_attempts=session_cleanup_attempts+1
                WHERE provider_session_id=?""", (session_id,)
            )
        failure_set = set(failed_ids) or (set(session_ids) - set(cleaned_ids))
        for session_id in failure_set:
            conn.execute(
                """UPDATE evaluation_sample_runs SET session_cleanup_status='failed',
                session_cleanup_error=?, session_cleanup_attempts=session_cleanup_attempts+1
                WHERE provider_session_id=?""",
                ((error or {}).get("message", "Session cleanup failed"), session_id),
            )
        conn.commit(); conn.close()

    def _generate_report_file(self, data: Dict[str, Any]) -> str:
        reports_dir = Path(os.getenv("REPORTS_DIR", "tmp/evaluation/reports")); reports_dir.mkdir(parents=True, exist_ok=True)
        filename = f"evaluation_report_{data.get('task_id','unknown')[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"; path = reports_dir / filename
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"); return str(path)


db_manager: DatabaseManager | None = None


def get_db_manager() -> DatabaseManager:
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager
