# Data Model: IntelliQ 支持 AI 数据集生成

**Feature**: 003-intelliq-ai-dataset-gen  
**Date**: 2026-08-22

## Overview

This feature does not introduce new database entities or API response shapes. All changes are to existing entities: the `RagProvider` base class gains a `get_chunks` method, the `IntelliQProvider` gains `generate_dataset_from_knowledge_base` capability and chunk retrieval, and `RagConnectionService` derives capabilities from provider instances rather than hardcoding them.

## Entities (existing, modified)

### RagConnection (RagConnectionService._summary output)

The connection summary returned by `GET /api/v1/evaluation/rag-connections`. **Change**: `capabilities` fields are now sourced from the actual provider instance via `create_provider()`, not hardcoded.

| Field | Type | Change | Description |
|-------|------|--------|-------------|
| `id` | `string` | unchanged | Stable connection identifier |
| `provider` | `'ragflow' \| 'intelliq'` | unchanged | RAG system type |
| `name` | `string` | unchanged | Human-readable name |
| `enabled` | `boolean` | unchanged | Connection active flag |
| `capabilities` | `ProviderCapabilities` | **modified** | Now sourced from `create_provider(connection).capabilities.__dict__` |

**Capabilities sub-object** (for IntelliQ connections, after change):

| Field | Before | After | Description |
|-------|--------|-------|-------------|
| `list_knowledge_bases` | `true` | `true` | unchanged |
| `list_assistants` | `true` | `true` | unchanged |
| `select_multiple_knowledge_bases` | `true` | `true` | unchanged |
| `generate_dataset_from_knowledge_base` | **`false`** | **`true`** | **Changed** |
| `streaming_chat` | `true` | `true` | unchanged |

### ProviderCapabilities (IntelliQProvider)

**Change**: `IntelliQProvider.capabilities` changes from `ProviderCapabilities(streaming_chat=True)` to `ProviderCapabilities(generate_dataset_from_knowledge_base=True, streaming_chat=True)`.

No new fields added to the `ProviderCapabilities` dataclass. The existing `generate_dataset_from_knowledge_base: bool = False` field is simply set to `True` for IntelliQ.

### RagProvider (abstract base)

**New method**: `get_chunks(kb_id: str, limit: int) -> list[dict[str, Any]]`

| Parameter | Type | Description |
|-----------|------|-------------|
| `kb_id` | `str` | Knowledge base ID (provider-scoped) |
| `limit` | `int` | Maximum number of chunks to return |

| Return field | Type | Description |
|-------------|------|-------------|
| `[].id` | `str` | Chunk identifier |
| `[].content` | `str` | Chunk text content (required for LLM generation) |
| `[].doc_name` | `str` | Source document name |
| `[].doc_id` | `str` | Source document ID |

**Implementations**:
- `RAGFlowProvider.get_chunks()` — wraps existing `AIDatasetGenerator._get_chunks_from_dataset()` logic, using the provider's own `api_base` and `api_key`
- `IntelliQProvider.get_chunks()` — calls `GET /api/v1/knowledge-bases/{kb_id}/documents` then `GET /api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/chunks` via `asyncio.run()`

### AIDatasetGenerator (refactored)

**Change**: Constructor and `__init__` no longer read `RAGFLOW_BASE_URL` / `RAGFLOW_API_KEY` directly. Instead, `generate_dataset_from_kb()` accepts a `provider` parameter.

| Before | After |
|--------|-------|
| `__init__(self)` reads env vars | `__init__(self)` takes no config |
| `generate_dataset_from_kb(self, kb_id, sample_count, question_types)` | `generate_dataset_from_kb(self, kb_id, sample_count, question_types, provider=None)` |
| `get_knowledge_base_chunks()` calls RAGFlow HTTP | `get_knowledge_base_chunks()` delegates to `provider.get_chunks()` |

### AI Generation API Request (POST /api/v1/evaluation/datasets/generate/ai)

**Change**: Route handler reads `connection_id` from request body, resolves the connection, and passes the provider to `AIDatasetGenerator`.

| Request field | Type | Required | Change |
|--------------|------|----------|--------|
| `kb_id` | `string` | yes | unchanged |
| `sample_count` | `int` | yes | unchanged |
| `question_types` | `string[]` | yes | unchanged |
| `connection_id` | `string` | **yes (new)** | **Newly required** |

## State Transitions

No new state machines. The existing AI generation task lifecycle is unchanged:

```
[POST /datasets/generate/ai]
  → dataset.status = "processing"
  → background thread starts
    → chunk retrieval (now provider-aware)
    → LLM generation (unchanged)
    → dataset.status = "completed" | "failed"
```

The only change: chunk retrieval now resolves the provider from `connection_id` instead of always using RAGFlow.