# IntelliQ Session API Contract

**Feature**: `005-intelliq-session-creation`

**Date**: 2026-08-23

All paths are relative to the configured IntelliQ API base. Every request uses the same connection credential and MUST NOT follow redirects.

## POST /sessions - Create Session

### Request

```http
POST /api/v1/sessions
Content-Type: application/json
Accept: application/json
X-API-Key: <IntelliQ API Key>
```

```json
{
  "title": "SmartQ Eval - <task-id> - <sample-index> - <attempt>",
  "description": "Auto-created session for evaluation"
}
```

### Success Contract

A creation is successful only when all conditions hold:

1. HTTP status is in the 2xx range.
2. Response body is valid JSON.
3. `success` is `true`.
4. `data.id` is a non-empty string.

The returned `data.id` is the only valid value for the following Agent Chat URL. Its format is opaque and must not be assumed to be a UUID.

### Failure Contract

The following are session creation failures:

- Any non-2xx HTTP response.
- A 2xx response with `success=false`.
- A non-JSON response.
- Missing or empty `data.id`.
- Network error or timeout.

Smart Eval records a structured, redacted error with HTTP status, upstream code if present, a bounded message/details summary, and retryability. It MUST NOT send Agent Chat when creation fails.

`POST /sessions` is treated as non-idempotent. Smart Eval does not blindly retry it until IntelliQ documents a safe idempotency or recovery contract.

## POST /agent-chat/{session_id} - Agent Chat

### Preconditions

- `{session_id}` comes from a successful `POST /sessions` under the same IntelliQ connection credential.
- `selected` knowledge-base mode sends the selected `knowledge_base_ids`.
- `all` and `none` modes omit explicit knowledge-base IDs.

### Request

```http
POST /api/v1/agent-chat/{session_id}
Content-Type: application/json
Accept: text/event-stream
X-API-Key: <IntelliQ API Key>
```

### Completion Contract

- SSE output must include a complete final answer and the defined completion signal before the sample is scoreable.
- Session creation failure, non-SSE response, stream interruption, error events, or missing completion signal produce an unscoreable sample result.
- A Session created before a failed Agent Chat still enters task-level cleanup.

## DELETE /sessions/batch - Batch Delete Sessions

### Request

```http
DELETE /api/v1/sessions/batch
Content-Type: application/json
Accept: application/json
X-API-Key: <IntelliQ API Key>
```

```json
{
  "ids": ["<provider-session-id-1>", "<provider-session-id-2>"]
}
```

### Preconditions

- The list contains only real IntelliQ Session IDs successfully created by the current evaluation task.
- IDs are de-duplicated locally.
- An empty list does not call IntelliQ.

### Success Contract

Cleanup is successful only when HTTP status is 2xx and the JSON response declares `success=true`.

### Failure Contract

- Cleanup failure is recorded as a safe task-level warning and per-session cleanup failure state.
- Cleanup failure MUST NOT alter a completed, partially succeeded, failed, or cancelled evaluation outcome.
- Failed IDs remain eligible for a later compensation attempt.
- Batch size, unknown-ID, partial-success, rate-limit, and retry behavior require controlled real-environment verification before enabling automatic retry.

## External Verification Boundary

The following behavior must be validated in a disposable IntelliQ tenant or approved test environment:

- Exact 2xx statuses returned by create and delete.
- Whether additional tenant headers are required.
- Maximum `ids` per batch delete.
- Duplicate, missing, or already-deleted ID semantics.
- Partial deletion response shape.
- 429 / 5xx and `Retry-After` behavior.
- Whether IntelliQ exposes a safe Agent Chat cancellation endpoint.
