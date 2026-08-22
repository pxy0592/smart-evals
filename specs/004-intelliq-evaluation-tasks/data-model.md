# Data Model: 允许向 IntelliQ 系统发起评测任务

**Feature**: 004-intelliq-evaluation-tasks
**Date**: 2026-08-22

## Overview

This feature does not introduce new database entities, API endpoints, or schema changes. The evaluation task pipeline (task creation, execution, scoring, reporting) is already fully provider-agnostic. This document describes the existing entities and their state transitions relevant to the IntelliQ evaluation task flow.

## Entities (existing, referenced)

### EvaluationTask (evaluation_tasks table)

Represents a single evaluation task. Created via `POST /api/v1/evaluation/tasks`, executed asynchronously, and tracked through status transitions.

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `id` | `string (UUID)` | generated | Unique task identifier |
| `name` | `string` | user input | Human-readable task name (e.g., "IntelliQ 回归评测") |
| `chat_id` | `string` | `rag_target.assistant_id` | Agent/Assistant ID (retained for backward compatibility) |
| `dataset_id` | `string` | `rag_target` or user input | Dataset ID to evaluate against |
| `metrics` | `string[]` | user input | Selected metric names (e.g., `["faithfulness", "answer_relevancy"]`) |
| `status` | `enum` | system | `pending` → `running` → `completed` / `failed` / `cancelled` |
| `progress` | `int (0-100)` | system | Percentage complete |
| `total_samples` | `int` | system | Number of samples in dataset |
| `processed_samples` | `int` | system | Samples processed so far |
| `rag_provider` | `string` | `task_source` | Provider type: `"intelliq"` or `"ragflow"` |
| `rag_connection_id` | `string` | `task_source` | Stable connection identifier |
| `rag_connection_revision` | `int` | `task_source` | Connection revision at task creation (for staleness check) |
| `assistant_id` | `string` | `task_source` | Agent ID |
| `assistant_name_snapshot` | `string` | `task_source` | Agent name at creation time |
| `knowledge_base_ids` | `string[]` | `task_source` | Knowledge base IDs (empty for `all`/`none` mode) |
| `knowledge_base_names_snapshot` | `string[]` | `task_source` | Knowledge base names at creation time |
| `knowledge_base_selection_mode_snapshot` | `string` | `task_source` | `"selected"`, `"all"`, or `"none"` |
| `connection_name_snapshot` | `string` | `task_source` | Connection display name at creation time |
| `connection_base_url_snapshot` | `string` | `task_source` | API base URL at creation time |
| `source_legacy` | `boolean` | `task_source` | `true` for legacy RAGFlow (chat_id) tasks, `false` for provider-aware tasks |
| `error_message` | `string?` | system | Error description if status is `failed` |
| `scored_sample_count` | `int?` | system | Number of successfully scored samples |
| `failed_sample_count` | `int?` | system | Number of failed samples |
| `has_warnings` | `boolean` | system | `true` if some samples failed |
| `outcome` | `enum?` | system | `"succeeded"`, `"partially_succeeded"`, `"failed"`, `"cancelled"` |
| `created_at` | `datetime` | system | Task creation timestamp |
| `started_at` | `datetime?` | system | Execution start timestamp |
| `completed_at` | `datetime?` | system | Completion timestamp |

**State transitions**:

```
                    ┌──────────┐
                    │  pending  │
                    └────┬─────┘
                         │ run_evaluation_task()
                    ┌────▼─────┐
              ┌─────│ running  │─────┐
              │     └────┬─────┘     │
              │          │           │
     cancel_task()   all samples  error /
              │      processed    revision mismatch
              │          │           │
         ┌────▼──┐  ┌───▼────┐  ┌───▼───┐
         │cancelled│ │completed│  │ failed │
         └────────┘  └────────┘  └───────┘
```

### EvaluationReport (evaluation_reports table)

Generated after task completion. One report per task.

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `string` | FK to evaluation_tasks.id |
| `overall_scores` | `dict` | Aggregated metric scores (e.g., `{"faithfulness": 0.85, "answer_relevancy": 0.92}`) |
| `detailed_scores` | `list[dict]` | Per-sample score breakdown including `sample_index`, `user_input`, `answer`, `contexts`, `metric_scores`, `completion_status`, `upstream_error` |
| `evaluation_metadata` | `dict` | `{total_count, success_count, failed_count, success_rate, metrics}` |
| `rag_provider` | `string` | `"intelliq"` or `"ragflow"` |
| `source_snapshot` | `dict` | Full task source info (provider, connection, assistant, knowledge bases) |
| `warning` | `dict?` | Present when `failed_count > 0`: `{code, message, failed_samples}` |

### SampleRun (sample_runs table)

Individual sample execution record. Created per sample per attempt.

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `string` | FK to evaluation_tasks.id |
| `sample_index` | `int` | 0-based index in dataset |
| `attempt` | `int` | Attempt number (1-based) |
| `session_id` | `string (UUID)` | Unique SSE session identifier |
| `question` | `string` | The question sent to the RAG system |
| `completion_status` | `string` | `"completed"` or `"failed"` |
| `answer` | `string?` | Full answer from RAG system |
| `partial_answer` | `string?` | Partial answer (when stream failed mid-way) |
| `contexts` | `list[string]?` | Retrieved contexts used for scoring |
| `references` | `list[dict]?` | Raw reference objects from SSE |
| `upstream_error` | `dict?` | Error details: `{category, message, retryable}` |
| `metric_scores` | `dict?` | Per-metric scores for this sample |

### IntelliQ SSE Response (in-memory, not persisted)

The SSE stream from IntelliQ Agent Chat is parsed by `aggregate_intelliq_sse()` into a `RagQueryResult`:

| Field | Type | Description |
|-------|------|-------------|
| `provider` | `string` | `"intelliq"` |
| `session_id` | `string` | SSE session UUID |
| `completed` | `boolean` | `true` if `done: true` received |
| `score_eligible` | `boolean` | `true` if completed with non-empty answer |
| `answer` | `string?` | Aggregated answer from SSE `answer` events |
| `partial_answer` | `string?` | Partial answer (when error occurred before completion) |
| `contexts` | `list[string]` | Content strings from `references` events |
| `references` | `list[dict]` | Raw reference objects |
| `intermediate_event_summary` | `dict` | Count of each `response_type` received |
| `error` | `ProviderError?` | Error details: `{category, message, retryable}` |

## Frontend Data Shapes

### Task List Item (Tasks.tsx)

The frontend already maps API response fields. No new fields needed for IntelliQ support, but the `source_snapshot` from the API provides provider information for display:

```typescript
interface EvaluationTask {
    id: string;
    name: string;
    // ... existing fields ...
    source_snapshot?: {
        provider: 'intelliq' | 'ragflow';
        connection_name: string;
        connection_base_url: string;
        assistant_name: string;
        knowledge_bases: Array<{ id: string; name: string }>;
        legacy: boolean;
    };
}
```

### Task Creation Form (EvaluationTaskForm.tsx)

The form already sends the correct `rag_target` structure. No changes to the data shape:

```typescript
interface CreateTaskPayload {
    name: string;
    dataset_id: string;
    metrics: string[];
    batch_size: number;
    rag_target: {
        provider: string;           // "intelliq" or "ragflow"
        connection_id: string;      // connection UUID
        assistant_id: string;       // agent UUID
        knowledge_base_ids: string[]; // empty for "all"/"none" modes
    };
}
```