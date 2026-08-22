global db_manager

"""
RAG 评估系统数据库模型
使用 SQLite 作为轻量级数据库
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            backend_dir = os.path.dirname(base_dir)
            db_path = os.path.join(backend_dir, "evaluation.db")
        else:
            if not os.path.isabs(db_path):
                base_dir = os.path.dirname(os.path.abspath(__file__))
                backend_dir = os.path.dirname(base_dir)
                db_path = os.path.join(backend_dir, db_path)
        self.db_path = db_path
        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        """初始化数据库表"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "\n            CREATE TABLE IF NOT EXISTS api_configs (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                name VARCHAR(100) NOT NULL UNIQUE,\n                provider VARCHAR(50) NOT NULL,\n                api_key VARCHAR(500) NOT NULL,\n                endpoint VARCHAR(500),\n                model VARCHAR(100),\n                embedding_model VARCHAR(100),\n                temperature REAL DEFAULT 0.7,\n                max_tokens INTEGER DEFAULT 4000,\n                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                is_default BOOLEAN DEFAULT 0\n            )\n        "
        )
        cursor.execute(
            "\n            CREATE TABLE IF NOT EXISTS system_settings (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                key VARCHAR(100) NOT NULL UNIQUE,\n                value TEXT,\n                description TEXT,\n                category VARCHAR(50) DEFAULT 'general',\n                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n            )\n        "
        )
        cursor.execute(
            "\n            CREATE TABLE IF NOT EXISTS datasets (\n                id VARCHAR(50) PRIMARY KEY,\n                name VARCHAR(200) NOT NULL,\n                description TEXT,\n                file_name VARCHAR(200),\n                file_type VARCHAR(10),\n                file_size INTEGER,\n                storage_path VARCHAR(500),\n                num_samples INTEGER DEFAULT 0,\n                has_reference BOOLEAN DEFAULT 0,\n                has_contexts BOOLEAN DEFAULT 0,\n                sample_fields TEXT,  -- JSON 格式存储字段信息\n                status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, completed, failed\n                progress INTEGER DEFAULT 0,\n                error_message TEXT,\n                created_by VARCHAR(100),\n                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n            )\n        "
        )
        cursor.execute(
            "\n            CREATE TABLE IF NOT EXISTS evaluation_tasks (\n                id VARCHAR(50) PRIMARY KEY,\n                name VARCHAR(200),\n                chat_id VARCHAR(50) NOT NULL,\n                dataset_id VARCHAR(50) NOT NULL,\n                llm_model VARCHAR(100),\n                embedding_model VARCHAR(100),\n                metrics TEXT,  -- JSON 格式存储指标列表\n                status VARCHAR(20) DEFAULT 'pending',\n                progress INTEGER DEFAULT 0,\n                total_samples INTEGER DEFAULT 0,\n                processed_samples INTEGER DEFAULT 0,\n                batch_size INTEGER DEFAULT 10,\n                error_message TEXT,\n                created_by VARCHAR(100),\n                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                started_at TIMESTAMP,\n                completed_at TIMESTAMP,\n                FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE\n            )\n        "
        )
        cursor.execute(
            "\n            CREATE TABLE IF NOT EXISTS evaluation_reports (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                task_id VARCHAR(50) NOT NULL UNIQUE,\n                chat_id VARCHAR(50) NOT NULL,\n                dataset_id VARCHAR(50) NOT NULL,\n                overall_scores TEXT,  -- JSON 格式存储总体分数\n                detailed_scores TEXT,  -- JSON 格式存储详细分数\n                evaluation_metadata TEXT,  -- JSON 格式存储元数据\n                report_file_path VARCHAR(500),\n                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                FOREIGN KEY (task_id) REFERENCES evaluation_tasks(id) ON DELETE CASCADE,\n                FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE\n            )\n        "
        )
        cursor.execute(
            "\n            CREATE TABLE IF NOT EXISTS evaluation_logs (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                task_id VARCHAR(50),\n                level VARCHAR(10),  -- INFO, ERROR, DEBUG\n                message TEXT,\n                details TEXT,  -- JSON 格式存储详细信息\n                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                FOREIGN KEY (task_id) REFERENCES evaluation_tasks(id) ON DELETE CASCADE\n            )\n        "
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_datasets_name ON datasets(name)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_status ON evaluation_tasks(status)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON evaluation_tasks(created_at)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_reports_task_id ON evaluation_reports(task_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_settings_category ON system_settings(category)"
        )
        self.insert_default_settings(cursor)
        self.insert_default_api_config(cursor)
        conn.commit()
        conn.close()

    def insert_default_settings(self, cursor):
        """插入默认系统设置"""
        default_settings = [
            (
                "ragflow_base_url",
                "http://localhost:9380",
                "RAGFlow 服务地址",
                "ragflow",
            ),
            ("default_llm_provider", "siliconflow", "默认 LLM 提供商", "llm"),
            ("default_llm_model", "Qwen/Qwen2.5-32B-Instruct", "默认 LLM 模型", "llm"),
            ("default_embedding_model", "BAAI/bge-m3", "默认 Embedding 模型", "llm"),
            ("evaluation_timeout", "300", "评测超时时间(秒)", "evaluation"),
            ("evaluation_max_workers", "2", "评测最大并发数", "evaluation"),
            ("evaluation_max_retries", "2", "评测最大重试次数", "evaluation"),
            ("max_upload_size", "104857600", "最大上传文件大小(字节)", "system"),
        ]
        for key, value, description, category in default_settings:
            cursor.execute(
                "\n                INSERT OR IGNORE INTO system_settings (key, value, description, category)\n                VALUES (?, ?, ?, ?)\n            ",
                (key, value, description, category),
            )

    def insert_default_api_config(self, cursor):
        """插入默认API配置（如果不存在）"""
        cursor.execute("SELECT COUNT(*) as count FROM api_configs")
        count = cursor.fetchone()["count"]
        if count == 0:
            api_key = os.getenv("SILICONFLOW_API_KEY", "sk-your-api-key-here")
            endpoint = os.getenv(
                "SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"
            )
            provider = os.getenv("DEFAULT_LLM_PROVIDER", "siliconflow")
            model = os.getenv("DEFAULT_LLM_MODEL", "Qwen/Qwen2.5-32B-Instruct")
            embedding_model = os.getenv("DEFAULT_EMBEDDING_MODEL", "BAAI/bge-m3")
            cursor.execute(
                "\n                INSERT INTO api_configs (\n                    name, provider, api_key, endpoint, model, embedding_model,\n                    temperature, max_tokens, is_default\n                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)\n            ",
                (
                    "Default API Config",
                    provider,
                    api_key,
                    endpoint,
                    model,
                    embedding_model,
                    0.7,
                    4000,
                    True,
                ),
            )

    def create_api_config(self, config_data: Dict[str, Any]) -> str:
        """创建 API 配置"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "\n            INSERT INTO api_configs (name, provider, api_key, endpoint, model, embedding_model, temperature, max_tokens, is_default)\n            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)\n        ",
            (
                config_data["name"],
                config_data["provider"],
                config_data["api_key"],
                config_data.get("endpoint"),
                config_data.get("model"),
                config_data.get("embedding_model"),
                config_data.get("temperature", 0.7),
                config_data.get("max_tokens", 4000),
                config_data.get("is_default", False),
            ),
        )
        config_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return str(config_id)

    def get_api_configs(self) -> List[Dict[str, Any]]:
        """获取所有 API 配置"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM api_configs ORDER BY is_default DESC, created_at DESC"
        )
        configs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return configs

    def get_default_api_config(self) -> Optional[Dict[str, Any]]:
        """获取默认 API 配置"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM api_configs WHERE is_default = 1 LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)

    def update_api_config(self, config_id: int, config_data: Dict[str, Any]) -> bool:
        """更新 API 配置"""
        conn = self.get_connection()
        cursor = conn.cursor()
        update_fields = []
        update_values = []
        field_mapping = {
            "name": "name",
            "provider": "provider",
            "api_key": "api_key",
            "endpoint": "endpoint",
            "model": "model",
            "embedding_model": "embedding_model",
            "temperature": "temperature",
            "max_tokens": "max_tokens",
        }
        for key, db_field in field_mapping.items():
            if key in config_data:
                update_fields.append(f"{db_field} = ?")
                update_values.append(config_data[key])
        if not update_fields:
            conn.close()
            return False
        else:
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            update_values.append(config_id)
            sql = f"UPDATE api_configs SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(sql, tuple(update_values))
            if config_data.get("is_default", False):
                cursor.execute(
                    "UPDATE api_configs SET is_default = 0 WHERE id != ?", (config_id,)
                )
                cursor.execute(
                    "UPDATE api_configs SET is_default = 1 WHERE id = ?", (config_id,)
                )
            success = cursor.rowcount > 0
            conn.commit()
            conn.close()
            return success

    def delete_api_config(self, config_id: int) -> bool:
        """删除 API 配置"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM api_configs WHERE id = ?", (config_id,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def get_setting(self, key: str, default: Any = None) -> Any:
        """获取系统设置"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return row["value"]
        else:
            return default

    def update_setting(
        self, key: str, value: str, description: str = None, category: str = "general"
    ):
        """更新系统设置"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "\n            INSERT OR REPLACE INTO system_settings (key, value, description, category, updated_at)\n            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)\n        ",
            (key, value, description, category),
        )
        conn.commit()
        conn.close()

    def create_dataset(self, dataset_data: Dict[str, Any]) -> str:
        """创建数据集"""
        
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "\n            INSERT INTO datasets (\n                id, name, description, file_name, file_type, file_size,\n                storage_path, num_samples, has_reference, has_contexts,\n                sample_fields, status, progress, created_by\n            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n        ",
            (
                dataset_data["id"],
                dataset_data["name"],
                dataset_data.get("description"),
                dataset_data.get("file_name"),
                dataset_data.get("file_type"),
                dataset_data.get("file_size"),
                dataset_data.get("storage_path"),
                dataset_data.get("num_samples", False),
                dataset_data.get("has_reference", False),
                dataset_data.get("has_contexts", False),
                dataset_data.get("status", "pending"),
                dataset_data.get("progress", 0),
                dataset_data.get("created_by", "system"),
            ),
        )
        conn.commit()
        conn.close()
        return dataset_data["id"]

    def update_dataset_status(
        self,
        dataset_id: str,
        status: str,
        progress: int = None,
        error_message: str = None,
        num_samples: int = None,
        has_reference: bool = None,
        has_contexts: bool = None,
    ):
        """更新数据集状态"""
        conn = self.get_connection()
        cursor = conn.cursor()
        update_fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
        update_values = [status]
        if progress is not None:
            update_fields.append("progress = ?")
            update_values.append(progress)
        if error_message is not None:
            update_fields.append("error_message = ?")
            update_values.append(error_message)
        if num_samples is not None:
            update_fields.append("num_samples = ?")
            update_values.append(num_samples)
        if has_reference is not None:
            update_fields.append("has_reference = ?")
            update_values.append(has_reference)
        if has_contexts is not None:
            update_fields.append("has_contexts = ?")
            update_values.append(has_contexts)
        update_values.append(dataset_id)
        cursor.execute(
            f"\n            UPDATE datasets\n            SET {', '.join(update_fields)}\n            WHERE id = ?\n        ",
            update_values,
        )
        conn.commit()
        conn.close()

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """获取单个数据集"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,))
        row = cursor.fetchone()
        if row:
            dataset = dict(row)
            if dataset["sample_fields"]:
                dataset["sample_fields"] = json.loads(dataset["sample_fields"])
            conn.close()
            return dataset
        else:
            conn.close()

    def get_datasets(self, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """获取数据集列表"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM datasets")
        total = cursor.fetchone()["total"]
        cursor.execute(
            "\n            SELECT * FROM datasets\n            ORDER BY created_at DESC\n            LIMIT ? OFFSET ?\n        ",
            (limit, offset),
        )
        datasets = []
        for row in cursor.fetchall():
            dataset = dict(row)
            if dataset["sample_fields"]:
                dataset["sample_fields"] = json.loads(dataset["sample_fields"])
            datasets.append(dataset)
        conn.close()
        return {"datasets": datasets, "total": total, "limit": limit, "offset": offset}

    def create_evaluation_task(self, task_data: Dict[str, Any]) -> str:
        """创建评测任务"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "\n            INSERT INTO evaluation_tasks (\n                id, name, chat_id, dataset_id, llm_model, embedding_model,\n                metrics, batch_size, created_by\n            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)\n        ",
            (
                task_data["id"],
                task_data.get("name"),
                task_data["chat_id"],
                task_data["dataset_id"],
                task_data.get("llm_model"),
                task_data.get("embedding_model"),
                json.dumps(task_data.get("metrics", [])),
                task_data.get("batch_size", 10),
                task_data.get("created_by", "anonymous"),
            ),
        )
        conn.commit()
        conn.close()
        return task_data["id"]

    def update_task_status(
        self,
        task_id: str,
        status: str,
        progress: int = None,
        error_message: str = None,
        processed_samples: int = None,
        total_samples: int = None,
    ):
        """更新任务状态"""
        conn = self.get_connection()
        cursor = conn.cursor()
        update_fields = ["status = ?"]
        update_values = [status]
        if progress is not None:
            update_fields.append("progress = ?")
            update_values.append(progress)
        if error_message is not None:
            update_fields.append("error_message = ?")
            update_values.append(error_message)
        if processed_samples is not None:
            update_fields.append("processed_samples = ?")
            update_values.append(processed_samples)
        if total_samples is not None:
            update_fields.append("total_samples = ?")
            update_values.append(total_samples)
        if status == "running" and progress == 0:
            update_fields.append("started_at = CURRENT_TIMESTAMP")
        else:
            if status in ["completed", "failed"]:
                update_fields.append("completed_at = CURRENT_TIMESTAMP")
        update_values.append(task_id)
        cursor.execute(
            f"\n            UPDATE evaluation_tasks\n            SET {', '.join(update_fields)}\n            WHERE id = ?\n        ",
            update_values,
        )
        conn.commit()
        conn.close()

    def save_evaluation_report(self, report_data: Dict[str, Any]) -> str:
        """保存评测报告"""
        conn = self.get_connection()
        cursor = conn.cursor()
        report_file_path = self._generate_report_file(report_data)
        cursor.execute(
            "\n            INSERT OR REPLACE INTO evaluation_reports (\n                task_id, chat_id, dataset_id, overall_scores, detailed_scores,\n                evaluation_metadata, report_file_path\n            ) VALUES (?, ?, ?, ?, ?, ?, ?)\n        ",
            (
                report_data["task_id"],
                report_data["chat_id"],
                report_data["dataset_id"],
                json.dumps(report_data.get("overall_scores", {})),
                json.dumps(report_data.get("detailed_scores", [])),
                json.dumps(report_data.get("evaluation_metadata", {})),
                report_file_path,
            ),
        )
        report_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return str(report_id)

    def get_evaluation_report(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取评测报告"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "\n            SELECT * FROM evaluation_reports\n            WHERE task_id = ?\n        ",
            (task_id,),
        )
        row = cursor.fetchone()
        if row:
            report = dict(row)
            for field in ["overall_scores", "detailed_scores", "evaluation_metadata"]:
                if report[field]:
                    report[field] = json.loads(report[field])
            conn.close()
            return report
        else:
            conn.close()

    def _generate_report_file(self, report_data: Dict[str, Any]) -> str:
        """生成评测报告文件"""
        
        reports_dir = Path("tmp/evaluation/reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        task_id = report_data.get("task_id", "unknown")[:8]
        filename = f"evaluation_report_{task_id}_{timestamp}.json"
        file_path = reports_dir / filename
        report_content = {
            "task_info": {
                "task_id": report_data.get("task_id"),
                "chat_id": report_data.get("chat_id"),
                "dataset_id": report_data.get("dataset_id"),
                "created_at": datetime.now().isoformat(),
                "status": "completed",
            },
            "overall_scores": report_data.get("overall_scores", {}),
            "detailed_scores": report_data.get("detailed_scores", []),
            "evaluation_metadata": report_data.get("evaluation_metadata", {}),
            "summary": {
                "total_questions": len(report_data.get("overall_scores", {})),
                "success_rate": report_data.get("success_rate", 0),
                "average_score": report_data.get("overall_scores", {}).get(
                    "average_score", 0
                ),
            },
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(report_content, f, ensure_ascii=False, indent=2)
        return str(file_path)
        return str(file_path)


db_manager = None


def get_db_manager() -> DatabaseManager:
    """获取数据库管理器实例"""
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager
