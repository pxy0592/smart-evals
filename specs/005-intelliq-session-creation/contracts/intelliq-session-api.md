# IntelliQ Session API Contract

**Feature**: 005-intelliq-session-creation
**Date**: 2026-08-22

These are the external IntelliQ API contracts used by the provider. All endpoints are relative to the IntelliQ base URL (e.g., `http://192.168.88.104:18080/api/v1`).

## POST /sessions — Create Session

Creates a new conversation session for agent-chat.

### Request

```
POST /api/v1/sessions
Content-Type: application/json
X-API-Key: <api_key>
```

```json
{
    "title": "SmartQ Eval - 2026-08-22T21:17:59",
    "description": "Auto-created session for evaluation"
}
```

### Response (200 OK)

```json
{
    "success": true,
    "data": {
        "id": "b6660558-3493-4cbd-ab46-f4579b63e77c",
        "title": "SmartQ Eval - 2026-08-22T21:17:59",
        "description": "Auto-created session for evaluation",
        "tenant_id": 10001,
        "user_id": "df6269ab-42f6-4523-b412-676adedc34d9",
        "is_pinned": false,
        "created_at": "2026-08-22T21:17:59.145803518+08:00",
        "updated_at": "2026-08-22T21:17:59.145803612+08:00",
        "deleted_at": null
    }
}
```

### Error Response

```json
{
    "success": false,
    "error": {
        "code": "<error_code>",
        "message": "<error_message>",
        "details": "<error_details>"
    }
}
```

## DELETE /sessions/batch — Batch Delete Sessions

Deletes multiple sessions by ID.

### Request

```
DELETE /api/v1/sessions/batch
Content-Type: application/json
X-API-Key: <api_key>
```

```json
{
    "ids": [
        "b6660558-3493-4cbd-ab46-f4579b63e77c",
        "ceb9babb-1e30-41d7-817d-fd584954304b"
    ]
}
```

### Response (200 OK)

```json
{
    "success": true,
    "message": "Sessions deleted successfully"
}
```

## POST /agent-chat/:session_id — Agent Chat (existing, unchanged)

### Request

```
POST /api/v1/agent-chat/{session_id}
Content-Type: application/json
X-API-Key: <api_key>
Accept: text/event-stream
```

```json
{
    "query": "用户问题",
    "agent_id": "<agent-uuid>",
    "agent_enabled": true,
    "knowledge_base_ids": ["<kb-uuid>"],
    "channel": "api"
}
```

### Response (200 OK, SSE stream)

```
Content-Type: text/event-stream

event: message
data: {"id":"...","response_type":"references","content":"","done":false,"knowledge_references":[...]}

event: message
data: {"id":"...","response_type":"answer","content":"回答内容...","done":false,"knowledge_references":null}

event: message
data: {"id":"...","response_type":"answer","content":"","done":true,"knowledge_references":null}
```

### Error (non-SSE)

```json
{
    "success": false,
    "error": {
        "code": 1003,
        "message": "Session not found"
    }
}
```