# Contract: Dataset Page API Usage

**Feature**: 002-dataset-provider-flow  
**Date**: 2026-08-22

This document defines which existing API endpoints the Datasets page must call — and must NOT call — under various user actions.

## API Surface Used

All endpoints are existing; no new endpoints are created by this feature.

### 1. GET `/evaluation/datasets`

**When**: Page load, polling refresh  
**Purpose**: Load dataset list (FR-001)  
**Replaces**: N/A (always called)  
**Must NOT trigger**: Any RAG connection or resource request

### 2. POST `/evaluation/datasets`

**When**: User uploads a dataset file  
**Purpose**: Upload dataset to Smart Eval only (FR-004)  
**Must NOT trigger**: RAG connection list, knowledge base, or assistant requests

### 3. GET `/evaluation/rag-connections`

**When**: User opens task creation modal OR AI generation modal  
**Purpose**: Load available connections on-demand (FR-008, FR-016)  
**Response shape**: `{ connections: RagConnectionSummary[] }`  
**Must NOT be called**: On page load, on dataset poll, on upload

### 4. GET `/evaluation/rag-connections/{id}/assistants`

**When**: User selects a connection in task creation modal  
**Purpose**: Load assistants for the selected connection (FR-010)  
**Response shape**: `{ provider, connection_id, items: AssistantRef[], total }`  
**Must NOT be called**: Before user selects a connection, or for non-selected connections

### 5. GET `/evaluation/rag-connections/{id}/knowledge-bases`

**When**: 
- User selects an assistant with `knowledge_base_selection_mode === 'selected'` (FR-011)
- User selects a connection in AI generation modal (FR-017)  
**Purpose**: Load knowledge bases for the selected connection  
**Response shape**: `{ provider, connection_id, items: RagResourceRef[], total }`  
**Must NOT be called**: Before user selects a connection, or when mode is 'all'/'none' in task form

### 6. POST `/evaluation/tasks`

**When**: User submits task creation form  
**Purpose**: Create evaluation task with `rag_target` (FR-013)  
**Request body**: Must include `rag_target: { provider, connection_id, assistant_id, knowledge_base_ids }`  
**Must NOT**: Use legacy `chat_id` field instead of `rag_target`

### 7. POST `/evaluation/datasets/generate/ai`

**When**: User submits AI dataset generation form  
**Purpose**: Generate dataset from selected connection + KB (FR-020)  
**Request body**: Must include `connection_id` and `kb_id` from the selected connection  
**Must NOT**: Use default RAGFlow connection or omit connection identity

## API Surface NOT Used (removed from Datasets page)

These endpoints are currently called on page load but MUST be removed:

| Endpoint | Current Behavior | Required Change |
|----------|-----------------|-----------------|
| `GET /evaluation/knowledgebases` | Called in `useEffect` on mount | Remove call; KBs loaded per-connection on-demand |
| Legacy `chatApi.list()` | Called in `handleCreateTask` | Remove; use `ragResourceApi.listAssistants(connectionId)` instead |
| Legacy `metricApi.list()` in `handleCreateTask` | Called eagerly | Keep in task creation modal; move to modal-open handler |

## Request Sequencing Contract

```
DATASET PAGE LOAD:
  GET /evaluation/datasets  ← ONLY this

USER CLICKS "创建评测":
  GET /evaluation/rag-connections
  GET /evaluation/datasets?limit=100
  GET /evaluation/metrics

USER SELECTS CONNECTION (task):
  GET /evaluation/rag-connections/{id}/assistants
  (Abort any previous assistants request)

USER SELECTS ASSISTANT (mode='selected'):
  GET /evaluation/rag-connections/{id}/knowledge-bases?assistant_id=X
  (Abort any previous KB request)

USER SUBMITS TASK:
  POST /evaluation/tasks  (with rag_target)

USER CLICKS "AI 智能生成":
  GET /evaluation/rag-connections

USER SELECTS CONNECTION (AI gen, capable):
  GET /evaluation/rag-connections/{id}/knowledge-bases
  (Abort any previous KB request)

USER SUBMITS AI GENERATION:
  POST /evaluation/datasets/generate/ai  (with connection_id + kb_id)
```

## Stale Response Prevention

Every resource fetch (assistants, KBs) must pass an `AbortController.signal` to Axios. The controller is aborted when:
- User switches to a different connection
- User switches to a different assistant
- Modal is closed
- Component unmounts