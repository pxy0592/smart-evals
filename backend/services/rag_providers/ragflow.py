"""RAGFlow adapter preserving the legacy Smart Eval behavior."""
from __future__ import annotations

import os
import re
from typing import Any

import aiohttp

from .base import AssistantRef, KnowledgeBaseRef, ProviderCapabilities, ProviderError, RagProvider, RagQueryResult
from .url_policy import normalize_service_url


class RAGFlowProvider(RagProvider):
    provider_name = "ragflow"
    capabilities = ProviderCapabilities(generate_dataset_from_knowledge_base=True, streaming_chat=False)

    def __init__(self, base_url: str | None = None, api_key: str | None = None, connection_id: str = "ragflow-default"):
        self.connection_id = connection_id
        self.service_root = normalize_service_url(base_url or os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380")).service_root
        self.api_base = f"{self.service_root}/api/v1"
        self.api_key = api_key if api_key is not None else os.getenv("RAGFLOW_API_KEY", "")
        self._session: aiohttp.ClientSession | None = None

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _client(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60, connect=10, sock_read=50))
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def validate_connection(self):
        knowledge = await self.list_knowledge_bases(limit=1)
        assistants = await self.list_assistants(limit=1)
        return {"knowledge_base_count": len(knowledge), "assistant_count": len(assistants)}

    async def list_knowledge_bases(self, **params):
        session = await self._client()
        payload = {"page": 1, "page_size": params.get("limit", 100)}
        if params.get("search"):
            payload["name"] = params["search"]
        async with session.get(f"{self.api_base}/datasets", params=payload, headers=self._headers()) as response:
            data = await response.json(content_type=None)
            if response.status != 200 or data.get("code") != 0:
                raise RuntimeError(data.get("message") or f"RAGFlow HTTP {response.status}")
            rows = (data.get("data") or {}).get("datasets") or []
            return [KnowledgeBaseRef(id=str(row["id"]), provider="ragflow", connection_id=self.connection_id, name=str(row.get("name") or row["id"]), description=str(row.get("description") or ""), document_count=row.get("document_count"), chunk_count=row.get("chunk_count")) for row in rows]

    async def list_assistants(self, **params):
        session = await self._client()
        payload = {"page": 1, "page_size": params.get("limit", 100)}
        if params.get("search"):
            payload["name"] = params["search"]
        async with session.get(f"{self.api_base}/chats", params=payload, headers=self._headers()) as response:
            data = await response.json(content_type=None)
            if response.status != 200 or data.get("code") != 0:
                raise RuntimeError(data.get("message") or f"RAGFlow HTTP {response.status}")
            rows = data.get("data") or []
            return [AssistantRef(id=str(row["id"]), provider="ragflow", connection_id=self.connection_id, name=str(row.get("name") or row["id"]), description=str(row.get("description") or ""), selectable=True, knowledge_base_selection_mode="selected", allowed_knowledge_base_ids=tuple(str(x) for x in row.get("datasets") or [])) for row in rows]

    async def query_sample(self, *, question: str, assistant_id: str, knowledge_base_ids: list[str], knowledge_base_selection_mode: str, session_id: str):
        session = await self._client()
        try:
            async with session.post(f"{self.api_base}/chats/{assistant_id}/sessions", json={}, headers=self._headers()) as create_response:
                created = await create_response.json(content_type=None)
                upstream_session = ((created.get("data") or {}).get("id") if created.get("code") == 0 else None) or session_id
            async with session.post(f"{self.api_base}/chats/{assistant_id}/completions", json={"question": question, "stream": False, "session_id": upstream_session}, headers=self._headers()) as response:
                data = await response.json(content_type=None)
                if response.status != 200 or data.get("code") != 0 or not data.get("data"):
                    return RagQueryResult(provider="ragflow", session_id=upstream_session, error=ProviderError("upstream", data.get("message") or f"RAGFlow HTTP {response.status}"))
                result = data["data"]
                refs = (result.get("reference") or {}).get("chunks") or []
                answer = re.sub(r"\[ID:\d+\]\s*", "", str(result.get("answer") or "")).strip()
                return RagQueryResult(provider="ragflow", session_id=str(result.get("session_id") or upstream_session), completed=bool(answer), score_eligible=bool(answer), answer=answer, contexts=[str(x.get("content")) for x in refs if x.get("content")], references=refs, error=None if answer else ProviderError("protocol", "RAGFlow 返回空答案"))
        except Exception as exc:
            return RagQueryResult(provider="ragflow", session_id=session_id, error=ProviderError("upstream", str(exc), True))
