"""Provider factory."""
from __future__ import annotations

from .intelliq import IntelliQProvider
from .ragflow import RAGFlowProvider


def create_provider(connection: dict, api_key: str | None = None):
    provider = connection.get("provider")
    if provider == "ragflow":
        return RAGFlowProvider(base_url=connection.get("base_url") or connection.get("api_url"), api_key=api_key, connection_id=connection.get("id", "ragflow-default"))
    if provider == "intelliq":
        if not api_key:
            raise ValueError("IntelliQ API Key 未配置")
        return IntelliQProvider(base_url=connection.get("base_url") or connection.get("api_url"), api_key=api_key, connection_id=connection["id"])
    raise ValueError(f"Unsupported RAG provider: {provider}")
