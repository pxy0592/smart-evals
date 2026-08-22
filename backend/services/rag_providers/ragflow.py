"""RAGFlow adapter preserving the legacy Smart Eval behavior."""
from __future__ import annotations

import logging
import os
import re
from typing import Any

import aiohttp
import requests

from .base import AssistantRef, KnowledgeBaseRef, ProviderCapabilities, ProviderError, RagProvider, RagQueryResult
from .url_policy import normalize_service_url

logger = logging.getLogger(__name__)


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

    def get_chunks(self, kb_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve knowledge base content chunks for AI dataset generation.

        Uses RAGFlow sync REST API to list documents and fetch chunks per document.
        """
        try:
            chunks: list[dict[str, Any]] = []
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            docs_resp = requests.get(
                f"{self.api_base}/datasets/{kb_id}/documents",
                headers=headers,
                params={"page": 1, "page_size": 50},
                timeout=30,
            )
            if docs_resp.status_code != 200:
                return []
            docs_data = docs_resp.json()
            if docs_data.get("code") != 0:
                return []
            documents = docs_data.get("data", {}).get("docs", [])
            if not documents:
                return []
            chunks_per_doc = max(1, limit // len(documents))
            for doc in documents[:10]:
                doc_id = doc.get("id")
                doc_name = doc.get("name", "未知文档")
                if not doc_id:
                    continue
                chunks_resp = requests.get(
                    f"{self.api_base}/datasets/{kb_id}/documents/{doc_id}/chunks",
                    headers=headers,
                    params={"page": 1, "page_size": chunks_per_doc},
                    timeout=30,
                )
                if chunks_resp.status_code != 200:
                    continue
                chunks_data = chunks_resp.json()
                if chunks_data.get("code") != 0:
                    continue
                raw_chunks = chunks_data.get("data", {}).get("chunks", [])
                for chunk in raw_chunks:
                    content = str(chunk.get("content", "")).strip()
                    if not content:
                        continue
                    chunks.append({
                        "id": str(chunk.get("id", "")),
                        "content": content,
                        "doc_name": doc_name,
                        "doc_id": str(doc_id),
                        "dataset_id": kb_id,
                        "page_number": chunk.get("page_number", 0),
                        "positions": chunk.get("positions", []),
                    })
                if len(chunks) >= limit:
                    break
            return chunks[:limit]
        except Exception:
            logger.exception("Error getting chunks from RAGFlow dataset %s", kb_id)
            return []

    async def query_sample(self, *, question: str, assistant_id: str, knowledge_base_ids: list[str], knowledge_base_selection_mode: str):
        import uuid
        fallback_id = str(uuid.uuid4())
        session = await self._client()
        try:
            async with session.post(f"{self.api_base}/chats/{assistant_id}/sessions", json={}, headers=self._headers()) as create_response:
                created = await create_response.json(content_type=None)
                upstream_session = ((created.get("data") or {}).get("id") if created.get("code") == 0 else None) or fallback_id
            async with session.post(f"{self.api_base}/chats/{assistant_id}/completions", json={"question": question, "stream": False, "session_id": upstream_session}, headers=self._headers()) as response:
                data = await response.json(content_type=None)
                if response.status != 200 or data.get("code") != 0 or not data.get("data"):
                    return RagQueryResult(provider="ragflow", session_id=upstream_session, error=ProviderError("upstream", data.get("message") or f"RAGFlow HTTP {response.status}"))
                result = data["data"]
                refs = (result.get("reference") or {}).get("chunks") or []
                answer = re.sub(r"\[ID:\d+\]\s*", "", str(result.get("answer") or "")).strip()
                return RagQueryResult(provider="ragflow", session_id=str(result.get("session_id") or upstream_session), completed=bool(answer), score_eligible=bool(answer), answer=answer, contexts=[str(x.get("content")) for x in refs if x.get("content")], references=refs, error=None if answer else ProviderError("protocol", "RAGFlow 返回空答案"))
        except Exception as exc:
            return RagQueryResult(provider="ragflow", session_id=fallback_id, error=ProviderError("upstream", str(exc), True))
