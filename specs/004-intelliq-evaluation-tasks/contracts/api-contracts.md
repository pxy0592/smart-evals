# API Contracts: 允许向 IntelliQ 系统发起评测任务

**Feature**: 004-intelliq-evaluation-tasks
**Date**: 2026-08-22

## Overview

The evaluation task pipeline uses existing API endpoints. No new endpoints are introduced. This document captures the relevant contract surfaces for IntelliQ evaluation tasks.

## Contract 1: Create Evaluation Task

### POST /api/v1/evaluation/tasks

Creates a new evaluation task for any RAG provider (IntelliQ or RAGFlow).

**Request** (provider-aware mode):

```json
{
    "name": "IntelliQ 回归评测",
    "dataset_id": "uuid-of-completed-dataset",
    "metrics": ["faithfulness", "answer_relevancy", "context_precision"],
    "batch_size": 10,
    "rag_target": {
        "provider": "intelliq",
        "connection_id": "uuid-of-intelliq-connection",
        "assistant_id": "uuid-of-intelliq-agent",
        "knowledge_base_ids": ["kb-uuid-1", "kb-uuid-2"]
    }
}
```

**Validation rules**:
- `dataset_id` must reference a dataset with `status: "completed"` and `normalization_status` in `{null, "completed"}`
- `rag_target` and legacy `chat_id` are mutually exclusive (exactly one must be provided)
- `rag_target.connection_id` must reference an enabled connection
- `rag_target.assistant_id` must be selectable and have a known `knowledge_base_selection_mode`
- `knowledge_base_ids` must be non-empty for `selected` mode, empty for `all`/`none` mode
- Each `knowledge_base_id` must belong to the connection and be accessible by the agent

**Response** (201):

```json
{
    "id": "task-uuid",
    "name": "IntelliQ 回归评测",
    "status": "pending",
    "progress": 0,
    "rag_provider": "intelliq",
    "rag_connection_id": "uuid-of-intelliq-connection",
    "assistant_id": "uuid-of-intelliq-agent",
    "assistant_name_snapshot": "My Agent",
    "knowledge_base_ids": ["kb-uuid-1", "kb-uuid-2"],
    "knowledge_base_names_snapshot": ["KB 1", "KB 2"],
    "knowledge_base_selection_mode_snapshot": "selected",
    "connection_name_snapshot": "IntelliQ Prod",
    "connection_base_url_snapshot": "http://192.168.88.104:18080",
    "source_legacy": false,
    "created_at": "2026-08-22T10:00:00Z"
}
```

**Error responses**:

| Status | Category | Message |
|--------|----------|---------|
| 400 | validation | `dataset_id 和 metrics 为必填项` |
| 400 | validation | `rag_target 与 legacy chat_id 必须且只能提供一个` |
| 400 | validation | `数据集不存在或尚未完成归一化` |
| 400 | validation | `RAG connection 不存在或未启用` |
| 400 | validation | `Agent 不可用或知识库模式未知，请刷新资源` |
| 400 | validation | `selected 模式至少需要一个知识库` |
| 400 | validation | `{mode} 模式不能手动提交知识库` |
| 400 | validation | `知识库不属于当前连接或 Agent 无权访问` |

## Contract 2: Get Task Status

### GET /api/v1/evaluation/tasks/{task_id}

Returns task status including provider info and sample runs.

**Response** (200):

```json
{
    "id": "task-uuid",
    "name": "IntelliQ 回归评测",
    "status": "completed",
    "progress": 100,
    "total_samples": 10,
    "processed_samples": 10,
    "scored_sample_count": 9,
    "failed_sample_count": 1,
    "has_warnings": true,
    "outcome": "partially_succeeded",
    "rag_provider": "intelliq",
    "source_snapshot": {
        "provider": "intelliq",
        "connection_id": "uuid",
        "connection_name": "IntelliQ Prod",
        "connection_base_url": "http://192.168.88.104:18080",
        "assistant_id": "uuid",
        "assistant_name": "My Agent",
        "knowledge_base_selection_mode": "selected",
        "knowledge_bases": [
            {"id": "kb-uuid-1", "name": "KB 1"},
            {"id": "kb-uuid-2", "name": "KB 2"}
        ],
        "legacy": false
    },
    "sample_runs": [
        {
            "sample_index": 0,
            "attempt": 1,
            "session_id": "sse-session-uuid",
            "question": "什么是微服务架构？",
            "completion_status": "completed",
            "answer": "微服务架构是一种...",
            "contexts": ["context 1", "context 2"]
        }
    ]
}
```

## Contract 3: IntelliQ SSE Agent Chat (External)

This is the external IntelliQ API contract consumed by the evaluation task.

### POST /api/v1/agent-chat/{session_id}

**Request headers**:
- `Authorization: Bearer {api_key}`
- `Accept: text/event-stream`
- `Content-Type: application/json`

**Request body**:

```json
{
    "query": "什么是微服务架构？",
    "agent_id": "uuid-of-agent",
    "agent_enabled": true,
    "channel": "api",
    "knowledge_base_ids": ["kb-uuid-1", "kb-uuid-2"]
}
```

**Response**: SSE stream (`text/event-stream`)

SSE event types:

| `response_type` | Content | Description |
|-----------------|---------|-------------|
| `answer` | `{"response_type": "answer", "content": "微服务..."}` | Answer chunk — aggregated by client |
| `references` | `{"response_type": "references", "knowledge_references": [{"id": "...", "content": "..."}]}` | Reference sources — extracted as contexts |
| `error` | `{"response_type": "error", "content": "error message"}` | Upstream error — sample marked as failed |
| `done` | `{"response_type": "...", "done": true}` | Stream completion signal |

**Expected behavior**:
- Multiple `answer` events may be sent (streaming) — client concatenates `content` fields
- `references` event may contain `knowledge_references` or `references` field
- `done: true` marks the end of the stream
- On error, the stream may close with `response_type: "error"` or the HTTP response may be non-200

## Contract 4: Cancel Task

### POST /api/v1/evaluation/tasks/{task_id}/cancel

Cancels a running or pending evaluation task.

**Response** (200):

```json
{
    "message": "Task cancelled",
    "task_id": "task-uuid"
}
```

**Error responses**:

| Status | Category | Message |
|--------|----------|---------|
| 404 | not_found | `Task not found` |
| 400 | validation | `Task cannot be cancelled in current status` |

**Behavior**: Sets task status to `cancelled` in the database. The background thread's `cancelled()` callback detects this before each sample and raises `asyncio.CancelledError`, which the `run_evaluation_task()` handler catches to finalize the status.