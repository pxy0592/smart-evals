"""Provider-neutral contracts for evaluated RAG systems."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderCapabilities:
    list_knowledge_bases: bool = True
    list_assistants: bool = True
    select_multiple_knowledge_bases: bool = True
    generate_dataset_from_knowledge_base: bool = False
    streaming_chat: bool = False


@dataclass(frozen=True)
class KnowledgeBaseRef:
    id: str
    provider: str
    connection_id: str
    name: str
    description: str = ""
    selectable: bool = True
    disabled_reason: str | None = None
    document_count: int | None = None
    chunk_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AssistantRef:
    id: str
    provider: str
    connection_id: str
    name: str
    description: str = ""
    built_in: bool | None = None
    selectable: bool = True
    disabled_reason: str | None = None
    knowledge_base_selection_mode: str | None = None
    allowed_knowledge_base_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["allowed_knowledge_base_ids"] = list(self.allowed_knowledge_base_ids)
        return data


@dataclass(frozen=True)
class ProviderError:
    category: str
    message: str
    retryable: bool = False
    http_status: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RagQueryResult:
    provider: str
    session_id: str
    completed: bool = False
    score_eligible: bool = False
    answer: str = ""
    partial_answer: str = ""
    contexts: list[str] = field(default_factory=list)
    references: list[dict[str, Any]] = field(default_factory=list)
    intermediate_event_summary: dict[str, int] = field(default_factory=dict)
    error: ProviderError | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "session_id": self.session_id,
            "completed": self.completed,
            "score_eligible": self.score_eligible,
            "answer": self.answer,
            "partial_answer": self.partial_answer,
            "contexts": self.contexts,
            "references": self.references,
            "intermediate_event_summary": self.intermediate_event_summary,
            "error": self.error.to_dict() if self.error else None,
        }


class RagProvider(ABC):
    provider_name: str
    connection_id: str
    capabilities: ProviderCapabilities

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def close(self) -> None:
        return None

    async def cleanup_sessions(self) -> None:
        """Optional: clean up provider-side resources created during evaluation.

        Default is a no-op. Providers that create server-side sessions
        (e.g. IntelliQ) should override this to batch-delete them.
        """
        return None

    @abstractmethod
    async def validate_connection(self) -> dict[str, Any]: ...

    @abstractmethod
    async def list_knowledge_bases(self, **params) -> list[KnowledgeBaseRef]: ...

    @abstractmethod
    async def list_assistants(self, **params) -> list[AssistantRef]: ...

    @abstractmethod
    async def query_sample(
        self,
        *,
        question: str,
        assistant_id: str,
        knowledge_base_ids: list[str],
        knowledge_base_selection_mode: str,
    ) -> RagQueryResult: ...

    @abstractmethod
    def get_chunks(self, kb_id: str, limit: int) -> list[dict[str, Any]]:
        """Retrieve knowledge base content chunks for AI dataset generation.

        Args:
            kb_id: Knowledge base identifier (provider-scoped).
            limit: Maximum number of chunks to return.

        Returns:
            List of chunk dicts, each with id, content, doc_name, doc_id, dataset_id.
        """
        ...
