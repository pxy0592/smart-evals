# Research: IntelliQ 评测前自动创建会话

**Feature**: 005-intelliq-session-creation
**Date**: 2026-08-22

## Research Questions

### RQ1: How does IntelliQ session creation work?

**Decision**: Use `POST /api/v1/sessions` with `X-API-Key` header, passing optional `title` and `description`.

**Rationale**: Verified via curl against the live IntelliQ server at `192.168.88.104:18080`. The endpoint returns `{"success": true, "data": {"id": "uuid", ...}}`. Both `title` and `description` are optional, but providing them aids identification in the IntelliQ UI.

**Alternatives considered**:
- Using a different endpoint (e.g., `POST /api/v1/agent-chat` without session_id) — not supported by the API
- Reusing a single session across all samples — rejected because samples should be independent, and session history would pollute subsequent answers

### RQ2: How does IntelliQ session deletion work?

**Decision**: Use `DELETE /api/v1/sessions/batch` with `{"ids": [...]}`.

**Rationale**: Verified via curl. The batch endpoint accepts an array of session IDs and deletes them all at once. The response is `{"success": true, "message": "Sessions deleted successfully"}`.

**Alternatives considered**:
- Individual `DELETE /api/v1/sessions/:id` per session — works but would require N API calls for N samples, less efficient
- Not deleting sessions — would accumulate garbage sessions in IntelliQ, unacceptable for production use

### RQ3: Where should session lifecycle management live?

**Decision**: Session creation in `IntelliQProvider.query_sample()`, session cleanup in `evaluation_service.py` via a new `cleanup()` method on the provider.

**Rationale**: Session creation is a provider-specific concern — only IntelliQ needs it. `query_sample()` already manages the SSE call lifecycle, so adding session creation is natural. Cleanup needs to happen after all samples are processed, which requires coordination at the evaluation service level. A `collect_session_ids()` / `cleanup_sessions()` pattern on the provider keeps the service provider-agnostic.

**Alternatives considered**:
- Session creation in `evaluation_service.py` — would break provider agnosticism
- Session cleanup in `query_sample()` — cannot clean up after all samples, only one at a time
- No cleanup at all — violates spec requirement FR-004

### RQ4: What error handling is needed for session operations?

**Decision**: Session creation failure → return error through existing `RagQueryResult.error` path. Session deletion failure → log warning, do not affect task status.

**Rationale**: If session creation fails, the sample cannot be evaluated — this is a hard error. Session deletion is best-effort cleanup; the evaluation result is already complete so deletion failure should not invalidate it.

### RQ5: Does the existing `session_id` parameter in `query_sample()` need to change?

**Decision**: The `session_id` parameter should be removed from `query_sample()` signature. Instead, `query_sample()` generates its own session internally.

**Rationale**: The `session_id` passed from `evaluation_service.py` is currently a random UUID that serves no purpose (it's not a real IntelliQ session). With the fix, the real session ID comes from the IntelliQ API response. The evaluation service should not need to know about session IDs at all.

**Impact**: Changes the `query_sample()` signature — removes `session_id` parameter. The `RagQueryResult.session_id` field will contain the IntelliQ-returned session ID. The evaluation service passes `session_id` from `str(uuid.uuid4())` — this can be removed since the provider handles it internally.