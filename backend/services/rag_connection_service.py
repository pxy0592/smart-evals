"""Connection management and provider resolution."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from db import get_db_manager
from services.credential_cipher import CredentialCipher
from services.rag_providers.factory import create_provider
from services.rag_providers.ragflow import RAGFlowProvider
from services.rag_providers.url_policy import validate_provider_url


class RagConnectionService:
    def __init__(self, db=None):
        self.db = db or get_db_manager()

    @staticmethod
    def _allowed_hosts():
        return {x.strip() for x in os.getenv("RAG_PROVIDER_ALLOWED_HOSTS", "").split(",") if x.strip()}

    def _ragflow_summary(self):
        provider = RAGFlowProvider()
        return {"id": "ragflow-default", "provider": "ragflow", "name": "RAGFlow", "api_url": provider.service_root, "api_key_configured": bool(provider.api_key), "editable": False, "enabled": bool(provider.api_key), "status": "untested", "revision": 1, "capabilities": provider.capabilities.__dict__, "last_tested_at": None, "error": None}

    @staticmethod
    def _summary(row):
        error = None
        if row.get("last_error_message"):
            error = {"category": row.get("last_error_category") or "upstream", "message": row["last_error_message"], "retryable": False}
        connection = {"id": row["id"], "provider": row["provider"], "name": row["name"], "base_url": row["base_url"], "api_url": row["base_url"]}
        try:
            cipher = CredentialCipher()
            api_key = cipher.decrypt(row["api_key_ciphertext"]) if row.get("api_key_ciphertext") else ""
            provider = create_provider(connection, api_key)
            capabilities = provider.capabilities.__dict__
        except Exception:
            capabilities = {"list_knowledge_bases": True, "list_assistants": True, "select_multiple_knowledge_bases": True, "generate_dataset_from_knowledge_base": False, "streaming_chat": True}
        return {"id": row["id"], "provider": row["provider"], "name": row["name"], "api_url": row["base_url"], "api_key_configured": bool(row.get("api_key_ciphertext")), "editable": True, "enabled": bool(row["enabled"]), "status": row["validation_status"], "revision": row["revision"], "capabilities": capabilities, "last_tested_at": row.get("last_validated_at"), "error": error}

    def list_connections(self):
        return [self._ragflow_summary(), *[self._summary(row) for row in self.db.list_rag_connections()]]

    def get_connection(self, connection_id: str, include_secret: bool = False):
        if connection_id == "ragflow-default":
            summary = self._ragflow_summary()
            if include_secret:
                summary["api_key"] = os.getenv("RAGFLOW_API_KEY", "")
                summary["base_url"] = summary["api_url"]
            return summary
        row = self.db.get_rag_connection(connection_id)
        if not row:
            return None
        result = self._summary(row)
        result["base_url"] = row["base_url"]
        if include_secret:
            result["api_key"] = CredentialCipher().decrypt(row["api_key_ciphertext"])
        return result

    def create(self, data: dict, actor: str = "deployment-admin"):
        if self.db.list_rag_connections(provider="intelliq"):
            raise ValueError("第一阶段仅支持一个 IntelliQ 连接")
        normalized = validate_provider_url(data.get("api_url", ""), self._allowed_hosts(), allow_http=os.getenv("FLASK_ENV") in {"development", "testing"})
        key = data.get("api_key", "")
        cipher = CredentialCipher()
        connection_id = str(uuid.uuid4())
        row = {"id": connection_id, "name": str(data.get("name") or "IntelliQ").strip(), "provider": "intelliq", "base_url": normalized.service_root, "api_key_ciphertext": cipher.encrypt(key), "api_key_fingerprint": cipher.fingerprint(key), "enabled": bool(data.get("enabled", True)), "revision": 1, "validation_status": "untested", "created_by": actor}
        self.db.create_rag_connection(row)
        self.db.add_rag_connection_audit(connection_id, 1, "created", ["name", "base_url", "api_key", "enabled"], actor, "success")
        return self._summary(self.db.get_rag_connection(connection_id))

    def update(self, connection_id: str, data: dict, actor: str = "deployment-admin"):
        current = self.db.get_rag_connection(connection_id)
        if not current:
            return None
        updates = {}
        changed = []
        if "name" in data:
            updates["name"] = str(data["name"]).strip(); changed.append("name")
        if "api_url" in data:
            normalized = validate_provider_url(data["api_url"], self._allowed_hosts(), allow_http=os.getenv("FLASK_ENV") in {"development", "testing"})
            updates["base_url"] = normalized.service_root; changed.append("base_url")
        if "enabled" in data:
            updates["enabled"] = bool(data["enabled"]); changed.append("enabled")
        if "api_key" in data:
            cipher = CredentialCipher(); key = data["api_key"]
            updates["api_key_ciphertext"] = cipher.encrypt(key); updates["api_key_fingerprint"] = cipher.fingerprint(key); changed.append("api_key")
        if not changed:
            raise ValueError("没有可更新字段")
        updates["revision"] = int(current["revision"]) + 1
        updates["validation_status"] = "untested"
        self.db.update_rag_connection(connection_id, updates)
        self.db.add_rag_connection_audit(connection_id, updates["revision"], "updated", changed, actor, "success")
        return self._summary(self.db.get_rag_connection(connection_id))

    async def validate(self, connection_id: str):
        connection = self.get_connection(connection_id, include_secret=True)
        if not connection:
            return None
        provider = create_provider(connection, connection.get("api_key"))
        try:
            result = await provider.validate_connection()
            self.db.update_rag_connection_validation(connection_id, "available", None, None)
            return {"status": "available", **result, "tested_at": datetime.now(timezone.utc).isoformat()}
        except Exception as exc:
            message = str(exc)[:500]
            category = message.split(":", 1)[0] if ":" in message else "upstream"
            self.db.update_rag_connection_validation(connection_id, "unavailable", category, message)
            raise
        finally:
            await provider.close()
