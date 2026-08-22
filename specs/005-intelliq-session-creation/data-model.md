# Data Model: IntelliQ 评测前自动创建会话

**Feature**: 005-intelliq-session-creation
**Date**: 2026-08-22

## Overview

This feature introduces no new database entities, tables, or schema changes. It modifies the internal flow of `IntelliQProvider.query_sample()` to add session lifecycle management. The existing evaluation task pipeline (task creation, execution, scoring, reporting) remains unchanged.

## Conceptual Model

### Session Lifecycle

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Evaluation     │     │  IntelliQProvider │     │  IntelliQ API   │
│  Service        │     │                   │     │  Server         │
└────────┬────────┘     └────────┬──────────┘     └────────┬────────┘
         │                       │                         │
         │  query_sample(q,      │                         │
         │    assistant_id,      │                         │
         │    kb_ids, mode)      │                         │
         │──────────────────────>│                         │
         │                       │                         │
         │                       │  POST /api/v1/sessions  │
         │                       │─────────────────────────>
         │                       │                         │
         │                       │  {id: "real-uuid", ...} │
         │                       │<─────────────────────────
         │                       │                         │
         │                       │  POST /agent-chat/{id}  │
         │                       │─────────────────────────>
         │                       │                         │
         │                       │  SSE stream (answer)    │
         │                       │<─────────────────────────
         │                       │                         │
         │  RagQueryResult       │                         │
         │<──────────────────────│                         │
         │                       │                         │
  ... all samples processed ...  │                         │
         │                       │                         │
         │  cleanup_sessions()   │                         │
         │──────────────────────>│                         │
         │                       │  DELETE /sessions/batch │
         │                       │─────────────────────────>
         │                       │                         │
         │                       │  {success: true}        │
         │                       │<─────────────────────────
```

### Key Changes

#### IntelliQProvider (modified)

| Aspect | Before | After |
|--------|--------|-------|
| `query_sample()` signature | `session_id: str` parameter | No `session_id` parameter |
| Session creation | None (uses caller-provided UUID) | Calls `POST /api/v1/sessions` internally |
| `session_id` in result | Echoes caller-provided UUID | Returns IntelliQ-returned session ID |
| Session tracking | None | Accumulates created session IDs internally |
| Cleanup | None | New `cleanup_sessions()` method for batch deletion |

#### evaluation_service.py (modified)

| Aspect | Before | After |
|--------|--------|-------|
| `session_id` generation | `str(uuid.uuid4())` per sample | Removed (provider handles internally) |
| `query_sample()` call | Passes `session_id=` | No longer passes session_id |
| Post-evaluation cleanup | None | Calls `provider.cleanup_sessions()` in finally block |

## Existing Entities (unchanged)

### EvaluationTask (evaluation_tasks table)

No schema changes. Task execution flow unchanged — the provider abstraction insulates the service from session management details.

### RagQueryResult

Existing fields: `provider`, `session_id`, `answer`, `contexts`, `references`, `error`, `partial_answer`, `score_eligible`.

`session_id` field semantics change: was a caller-generated UUID, now reflects the IntelliQ-returned session ID. This is backward-compatible (still a string UUID).

### RagProvider base class

May need a new optional method `cleanup_sessions()` for providers that create server-side resources. RAGFlow provider would have a no-op implementation.

## State Transitions

### Session State (per sample)

```
[Sample Start] → Create Session → [Session Created]
                                      │
                    ┌─────────────────┤
                    ▼                 ▼
            Agent Chat SSE      Session creation failed
                    │                 │
                    ▼                 ▼
            [Answer Received]   [Sample Failed]
                    │
                    ▼
            [Sample Complete]
                    │
                    ▼
            [Session ID collected for cleanup]
```

### Cleanup State (per task)

```
[All samples done] → [Call cleanup_sessions()]
                           │
              ┌─────────────┤
              ▼             ▼
     [DELETE /sessions]  [DELETE failed]
              │             │
              ▼             ▼
     [All sessions     [Log warning,
      deleted]          task still succeeds]
```