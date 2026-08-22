"""IntelliQ adapter for resource discovery and SSE Agent chat."""
from __future__ import annotations

import asyncio
from email.utils import parsedate_to_datetime
from typing import Any

import aiohttp

from .base import AssistantRef, KnowledgeBaseRef, ProviderCapabilities, ProviderError, RagProvider, RagQueryResult
from .sse import aggregate_intelliq_sse
from .url_policy import normalize_service_url


class IntelliQProvider(RagProvider):
    provider_name = "intelliq"
    capabilities = ProviderCapabilities(streaming_chat=True)

    def __init__(self, *, base_url: str, api_key: str, connection_id: str, max_retries: int = 1):
        normalized = normalize_service_url(base_url)
        self.service_root = normalized.service_root
        self.api_base = normalized.api_base
        self.api_key = api_key
        self.connection_id = connection_id
        self.max_retries = max(0, max_retries)
        self._session: aiohttp.ClientSession | None = None

    async def _client(self):
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=300, connect=10, sock_read=120)
            self._session = aiohttp.ClientSession(timeout=timeout, raise_for_status=False)
        return self._session

    def _headers(self, accept: str = "application/json"):
        return {"X-API-Key": self.api_key, "Content-Type": "application/json", "Accept": accept}

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    @staticmethod
    def _error(status: int, message: str) -> ProviderError:
        category = "authentication" if status == 401 else "permission" if status == 403 else "rate_limit" if status == 429 else "validation" if 400 <= status < 500 else "upstream"
        return ProviderError(category, message, status in {429, 502, 503, 504}, status)

    async def _get_json(self, path: str, params: dict[str, Any] | None = None):
        session = await self._client()
        for attempt in range(self.max_retries + 1):
            try:
                async with session.get(f"{self.api_base}{path}", params=params, headers=self._headers(), allow_redirects=False) as response:
                    payload = await response.json(content_type=None)
                    if response.status == 200:
                        return payload
                    error = self._error(response.status, str(payload.get("message") or payload.get("error") or f"HTTP {response.status}"))
                    if not error.retryable or attempt >= self.max_retries:
                        raise RuntimeError(f"{error.category}:{error.message}")
                    await asyncio.sleep(0.2 * (2**attempt))
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt >= self.max_retries:
                    raise RuntimeError(f"timeout:{exc}") from exc
                await asyncio.sleep(0.2 * (2**attempt))
        raise RuntimeError("IntelliQ request failed")

    async def validate_connection(self):
        knowledge, assistants = await asyncio.gather(self.list_knowledge_bases(limit=100), self.list_assistants(limit=100))
        return {"knowledge_base_count": len(knowledge), "assistant_count": len(assistants)}

    async def list_knowledge_bases(self, **params):
        query = {k: v for k, v in {"agent_id": params.get("assistant_id")}.items() if v}
        payload = await self._get_json("/knowledge-bases", query)
        rows = payload.get("data") or []
        search = str(params.get("search") or "").lower()
        result = []
        for row in rows:
            name = str(row.get("name") or row.get("id") or "")
            if search and search not in name.lower():
                continue
            result.append(KnowledgeBaseRef(id=str(row.get("id")), provider="intelliq", connection_id=self.connection_id, name=name, description=str(row.get("description") or ""), selectable=True, document_count=row.get("knowledge_count"), chunk_count=row.get("chunk_count")))
        offset, limit = int(params.get("offset", 0)), int(params.get("limit", 100))
        return result[offset : offset + limit]

    @staticmethod
    def _normalize_mode(config: dict[str, Any]) -> str | None:
        raw = str(config.get("kb_selection_mode") or "").lower()
        mapping = {"all": "all", "selected": "selected", "specified": "selected", "none": "none"}
        return mapping.get(raw)

    async def list_assistants(self, **params):
        payload = await self._get_json("/agents")
        rows = payload.get("data") or []
        disabled = {str(x) for x in payload.get("disabled_own_agent_ids") or []}
        search = str(params.get("search") or "").lower()
        result = []
        for row in rows:
            aid = str(row.get("id"))
            name = str(row.get("name") or aid)
            if search and search not in name.lower():
                continue
            config = row.get("config") or {}
            mode = self._normalize_mode(config)
            selectable = aid not in disabled and mode is not None
            reason = "当前租户已禁用该 Agent" if aid in disabled else "Agent 知识库模式未知，请刷新配置" if mode is None else None
            allowed = tuple(str(x) for x in config.get("knowledge_bases") or config.get("knowledge_base_ids") or [])
            result.append(AssistantRef(id=aid, provider="intelliq", connection_id=self.connection_id, name=name, description=str(row.get("description") or ""), built_in=bool(row.get("is_builtin")), selectable=selectable, disabled_reason=reason, knowledge_base_selection_mode=mode, allowed_knowledge_base_ids=allowed))
        offset, limit = int(params.get("offset", 0)), int(params.get("limit", 100))
        return result[offset : offset + limit]

    async def query_sample(self, *, question: str, assistant_id: str, knowledge_base_ids: list[str], knowledge_base_selection_mode: str, session_id: str):
        payload: dict[str, Any] = {"query": question, "agent_id": assistant_id, "agent_enabled": True, "channel": "api"}
        if knowledge_base_selection_mode == "selected":
            payload["knowledge_base_ids"] = knowledge_base_ids
        session = await self._client()
        try:
            async with session.post(f"{self.api_base}/agent-chat/{session_id}", json=payload, headers=self._headers("text/event-stream"), allow_redirects=False) as response:
                if response.status != 200:
                    text = await response.text()
                    error = self._error(response.status, text[:500] or f"HTTP {response.status}")
                    return RagQueryResult(provider="intelliq", session_id=session_id, error=error)
                if "text/event-stream" not in response.headers.get("Content-Type", ""):
                    return RagQueryResult(provider="intelliq", session_id=session_id, error=ProviderError("protocol", "IntelliQ 未返回 text/event-stream"))
                return await aggregate_intelliq_sse(response.content.iter_any(), session_id)
        except asyncio.TimeoutError:
            return RagQueryResult(provider="intelliq", session_id=session_id, error=ProviderError("timeout", "IntelliQ 回答超时", True))
        except aiohttp.ClientError as exc:
            return RagQueryResult(provider="intelliq", session_id=session_id, error=ProviderError("upstream", str(exc), True))
