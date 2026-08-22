# Data Model: 数据集页面按需访问 RAG 系统

**Feature**: 002-dataset-provider-flow  
**Date**: 2026-08-22

## Overview

This feature is a frontend-only change. No new database entities, API endpoints, or backend data structures are introduced. All entities described below are existing types from `frontend/src/services/evaluation.ts`, used here for reference.

## Entities (existing, unchanged)

### RagConnectionSummary

Represents a configured RAG system connection. Already returned by `GET /api/v1/evaluation/rag-connections`.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `string` | Stable connection identifier |
| `provider` | `'ragflow' \| 'intelliq'` | RAG system type |
| `name` | `string` | Human-readable connection name |
| `enabled` | `boolean` | Whether the connection is active |
| `status` | `'untested' \| 'available' \| 'unavailable'` | Connection health |
| `capabilities` | `object` (see below) | Feature flags for this connection |

**Capabilities sub-object**:

| Field | Type | Description |
|-------|------|-------------|
| `list_knowledge_bases` | `boolean` | Can list knowledge bases |
| `list_assistants` | `boolean` | Can list assistants |
| `select_multiple_knowledge_bases` | `boolean` | Supports multi-KB selection |
| `generate_dataset_from_knowledge_base` | `boolean` | Supports AI dataset generation |
| `streaming_chat` | `boolean` | Supports streaming chat |

**Relevance**: Used in both task creation and AI generation modals. The `generate_dataset_from_knowledge_base` capability gates the AI generation flow (FR-016/FR-018).

### AssistantRef

Represents a chat assistant / agent belonging to a specific connection.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `string` | Assistant identifier (connection-scoped) |
| `provider` | `RagProvider` | Owning provider |
| `connection_id` | `string` | Owning connection ID |
| `name` | `string` | Display name |
| `selectable` | `boolean` | Whether the assistant can be selected |
| `knowledge_base_selection_mode` | `'all' \| 'selected' \| 'none' \| null` | KB selection requirement |
| `allowed_knowledge_base_ids` | `string[]` | KBs this assistant can access |

**Relevance**: Loaded after user selects a connection in the task creation modal (FR-010). The `knowledge_base_selection_mode` drives conditional KB loading (FR-011).

### RagResourceRef

Represents a knowledge base belonging to a specific connection.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `string` | KB identifier (connection-scoped) |
| `provider` | `RagProvider` | Owning provider |
| `connection_id` | `string` | Owning connection ID |
| `name` | `string` | Display name |
| `selectable` | `boolean` | Whether the KB can be selected |

**Relevance**: Loaded in task creation when the assistant's mode is `'selected'` (FR-011). Loaded in AI generation when the user selects a capable connection (FR-017).

### TaskCreateParams (rag_target)

The `rag_target` field on task creation binds the task to a specific connection:

| Field | Type | Description |
|-------|------|-------------|
| `provider` | `RagProvider` | Provider type |
| `connection_id` | `string` | Selected connection ID |
| `assistant_id` | `string` | Selected assistant ID |
| `knowledge_base_ids` | `string[]` | Selected KB IDs (empty if mode is 'all' or 'none') |

**Relevance**: Already exists in `EvaluationTaskForm.tsx`. The Datasets page must pass this instead of the legacy `chat_id` field (FR-013/FR-020).

## Session State (frontend-only, ephemeral)

### Task Creation Session

Lives in `Datasets.tsx` local state, destroyed on modal close (FR-022).

| State | Type | Purpose |
|-------|------|---------|
| `connections` | `RagConnectionSummary[]` | Available connections, loaded on modal open |
| `selectedConnectionId` | `string \| null` | User's current connection choice |
| `assistants` | `AssistantRef[]` | Assistants for selected connection |
| `selectedAssistantId` | `string \| null` | User's current assistant choice |
| `knowledgeBases` | `RagResourceRef[]` | KBs for selected connection (if mode requires) |
| `selectedKbIds` | `string[]` | User's KB selections |
| `connectionLoading` | `boolean` | Skeleton vs. form state |
| `assistantLoading` | `boolean` | Loading indicator for assistant dropdown |
| `kbLoading` | `boolean` | Loading indicator for KB selector |
| `abortController` | `AbortController` | Cancels in-flight requests on switch/close |

### AI Generation Session

Lives in `Datasets.tsx` local state, destroyed on modal close (FR-022).

| State | Type | Purpose |
|-------|------|---------|
| `genConnections` | `RagConnectionSummary[]` | Connections, filtered by capability |
| `selectedGenConnectionId` | `string \| null` | User's connection choice |
| `genKnowledgeBases` | `RagResourceRef[]` | KBs for selected connection |
| `selectedGenKbId` | `string \| null` | User's KB selection |
| `genConnectionLoading` | `boolean` | Skeleton vs. form state |
| `genKbLoading` | `boolean` | Loading indicator |
| `genAbortController` | `AbortController` | Cancels in-flight requests |

## State Transitions

### Task Creation Modal

```
CLOSED → [user clicks "创建评测"] → LOADING_CONNECTIONS
  → (success) → READY (connections shown, skeleton removed)
  → (error) → ERROR (retry button shown)

READY → [user selects connection] → LOADING_ASSISTANTS
  → (success) → ASSISTANTS_LOADED
  → (error) → ASSISTANT_ERROR

ASSISTANTS_LOADED → [user selects assistant] →
  → (mode='selected') → LOADING_KBS → KBS_LOADED
  → (mode='all'|'none') → READY_TO_SUBMIT

READY_TO_SUBMIT → [user submits] → SUBMITTING → (success) → CLOSED
```

### AI Generation Modal

```
CLOSED → [user clicks "AI 智能生成"] → LOADING_CONNECTIONS
  → (success) → READY (connections shown with capability badges)
  → (error) → ERROR (retry button shown)

READY → [user selects capable connection] → LOADING_KBS → KBS_LOADED
READY → [user selects incapable connection] → DISABLED (reason shown)

KBS_LOADED → [user selects KB, fills params, submits] → GENERATING → (success) → CLOSED
```