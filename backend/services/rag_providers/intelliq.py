"""IntelliQ adapter for resource discovery and SSE Agent chat."""
from __future__ import annotations

import asyncio
import logging
from email.utils import parsedate_to_datetime
from typing import Any

import aiohttp

from datetime import datetime, timezone

from .base import AssistantRef, KnowledgeBaseRef, ProviderCapabilities, ProviderError, RagProvider, RagQueryResult
from .sse import aggregate_intelliq_sse
from .url_policy import normalize_service_url

logger = logging.getLogger(__name__)


class IntelliQProvider(RagProvider):
    provider_name = "intelliq"
    capabilities = ProviderCapabilities(generate_dataset_from_knowledge_base=True, streaming_chat=True)

    def __init__(self, *, base_url: str, api_key: str, connection_id: str, max_retries: int = 1):
        normalized = normalize_service_url(base_url)
        self.service_root = normalized.service_root
        self.api_base = normalized.api_base
        self.api_key = api_key
        self.connection_id = connection_id
        self.max_retries = max(0, max_retries)
        self._session_ids: list[str] = []
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
                    if response.status != 200:
                        error = self._error(response.status, f"HTTP {response.status}")
                        if not error.retryable or attempt >= self.max_retries:
                            raise RuntimeError(f"{error.category}:{error.message}")
                        await asyncio.sleep(0.2 * (2**attempt))
                        continue
                    try:
                        payload = await response.json(content_type=None)
                    except (ValueError, aiohttp.ContentTypeError) as exc:
                        raise RuntimeError(f"protocol:non-json response ({exc})") from exc
                    return payload
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

    def get_chunks(self, kb_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve knowledge base content chunks for AI dataset generation.

        Uses IntelliQ REST API (4-step flow):
        1. GET /knowledge-bases/{kb_id}/knowledge to list knowledge items
        2. GET /chunks/{knowledge_id} to get chunk IDs per knowledge item
        3. GET /chunks/by-id/{chunk_id} to get chunk data for each chunk ID

        Bridges async HTTP via asyncio.run() since the generator runs in a sync thread.
        """
        async def _fetch():
            chunks: list[dict[str, Any]] = []
            try:
                # Step 1: list knowledge items (documents) in the KB
                knowledge_path = f"/knowledge-bases/{kb_id}/knowledge"
                knowledge_payload = await self._get_json(knowledge_path, {"page": 1, "page_size": 50})
                knowledge_items = knowledge_payload.get("data") or []
                if not knowledge_items:
                    logger.info("IntelliQ KB %s has no knowledge items", kb_id)
                    return chunks
                logger.info("IntelliQ KB %s: found %d knowledge items", kb_id, len(knowledge_items))
                chunks_per_item = max(1, limit // len(knowledge_items))
                for item in knowledge_items[:10]:
                    knowledge_id = str(item.get("id"))
                    knowledge_name = str(item.get("title") or item.get("file_name") or item.get("name") or knowledge_id)
                    kb_name = str(item.get("knowledge_base_name") or "")
                    if not knowledge_id:
                        continue
                    # Step 2: get chunk IDs for this knowledge item
                    try:
                        chunks_payload = await self._get_json(
                            f"/chunks/{knowledge_id}",
                            {"page": 1, "page_size": chunks_per_item},
                        )
                    except RuntimeError:
                        logger.warning("Failed to get chunk IDs for knowledge %s in KB %s", knowledge_id, kb_id)
                        continue
                    chunk_ids = [
                        str(c.get("id")) for c in (chunks_payload.get("data") or [])
                        if c.get("id")
                    ]
                    if not chunk_ids:
                        continue
                    # Step 3: fetch chunk data by ID
                    for chunk_id in chunk_ids:
                        try:
                            chunk_data = await self._get_json(f"/chunks/by-id/{chunk_id}")
                        except RuntimeError:
                            logger.warning("Failed to get chunk data for chunk %s", chunk_id)
                            continue
                        content = str((chunk_data.get("data") or {}).get("content") or "").strip()
                        if not content:
                            continue
                        chunks.append({
                            "id": chunk_id,
                            "content": content,
                            "doc_name": knowledge_name,
                            "doc_id": knowledge_id,
                            "dataset_id": kb_id,
                            "knowledge_base_name": kb_name,
                        })
                        if len(chunks) >= limit:
                            break
                    if len(chunks) >= limit:
                        break
                return chunks[:limit]
            except RuntimeError:
                logger.exception("IntelliQ API error getting chunks from KB %s", kb_id)
                return chunks
            except Exception:
                logger.exception("Error getting chunks from IntelliQ KB %s", kb_id)
                return chunks
            finally:
                await self.close()

        try:
            return asyncio.run(_fetch())
        except RuntimeError:
            logger.exception("Error getting chunks from IntelliQ KB %s", kb_id)
            return []

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

    async def _create_session(self) -> str | None:
        """Create an IntelliQ session for agent-chat. Returns session ID or None on failure."""
        try:
            session = await self._client()
            timestamp = datetime.now(timezone.utc).isoformat()
            async with session.post(
                f"{self.api_base}/sessions",
                json={"title": f"SmartQ Eval - {timestamp}", "description": "Auto-created session for evaluation"},
                headers=self._headers(),
            ) as response:
                if not 200 <= response.status < 300:
                    text = await response.text()
                    logger.error("IntelliQ session creation failed: HTTP %s - %s", response.status, text[:500])
                    return None
                data = await response.json(content_type=None)
                sid = (data.get("data") or {}).get("id")
                if not sid:
                    logger.error("IntelliQ session creation response missing data.id: %s", data)
                    return None
                return str(sid)
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.error("IntelliQ session creation network error: %s", exc)
            return None

    async def cleanup_sessions(self) -> None:
        """Batch-delete all sessions created during this evaluation run."""
        if not self._session_ids:
            return
        ids_to_delete = list(self._session_ids)
        self._session_ids.clear()
        try:
            session = await self._client()
            async with session.delete(
                f"{self.api_base}/sessions/batch",
                json={"ids": ids_to_delete},
                headers=self._headers(),
            ) as response:
                if response.status == 200:
                    logger.info("Deleted %d IntelliQ session(s)", len(ids_to_delete))
                else:
                    text = await response.text()
                    logger.warning("IntelliQ session cleanup failed: HTTP %s - %s", response.status, text[:500])
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.warning("IntelliQ session cleanup network error: %s", exc)

    async def query_sample(self, *, question: str, assistant_id: str, knowledge_base_ids: list[str], knowledge_base_selection_mode: str):
        payload: dict[str, Any] = {"query": question, "agent_id": assistant_id, "agent_enabled": True, "channel": "api"}
        if knowledge_base_selection_mode == "selected":
            payload["knowledge_base_ids"] = knowledge_base_ids

        # Create a real session before calling agent-chat (FR-001)
        real_session_id = await self._create_session()
        if not real_session_id:
            return RagQueryResult(
                provider="intelliq",
                session_id="",
                error=ProviderError("upstream", "Session creation failed: IntelliQ returned no session ID"),
            )
        self._session_ids.append(real_session_id)

        session = await self._client()
        try:
            async with session.post(
                f"{self.api_base}/agent-chat/{real_session_id}",
                json=payload,
                headers=self._headers("text/event-stream"),
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    error = self._error(response.status, text[:500] or f"HTTP {response.status}")
                    return RagQueryResult(provider="intelliq", session_id=real_session_id, error=error)
                if "text/event-stream" not in response.headers.get("Content-Type", ""):
                    return RagQueryResult(
                        provider="intelliq",
                        session_id=real_session_id,
                        error=ProviderError("protocol", "IntelliQ 未返回 text/event-stream"),
                    )
                return await aggregate_intelliq_sse(response.content.iter_any(), real_session_id)
        except asyncio.TimeoutError:
            return RagQueryResult(
                provider="intelliq",
                session_id=real_session_id,
                error=ProviderError("timeout", "IntelliQ 回答超时", True),
            )
        except aiohttp.ClientError as exc:
            return RagQueryResult(
                provider="intelliq",
                session_id=real_session_id,
                error=ProviderError("upstream", str(exc), True),
            )
