# Tasks: IntelliQ 评测前自动创建会话

**Feature**: 005-intelliq-session-creation
**Generated**: 2026-08-22
**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)

## Task Format

`[ID] [P?] [US?] Description` — `[P]` = parallelizable, `[US#]` = user story scope

---

## Phase 1: Setup

> ⚠️ Project already initialized; no new dependencies or files needed.

- [x] **T001** Verify IntelliQ session API endpoints are accessible from the container: `curl -f http://192.168.88.104:18080/api/v1/sessions` with X-API-Key header

---

## Phase 2: Foundational — ABC & Provider Contract Changes

> ⚠️ These changes affect ALL providers. Must be completed before any user story work.

- [x] **T002** [P] Verify `RagQueryResult.session_id` field semantics: field stays but value now comes from provider API response, not caller-supplied UUID. No code change needed to the dataclass itself.
- [x] **T003** Remove `session_id` parameter from `RagProvider.query_sample()` abstract method signature in `backend/services/rag_providers/base.py` (line ~116)
- [x] **T004** [P] Add optional `cleanup_sessions()` method to `RagProvider` ABC in `backend/services/rag_providers/base.py` with a default no-op implementation (returns `None`)
- [x] **T005** [P] Update `RAGFlowProvider.query_sample()` in `backend/services/rag_providers/ragflow.py` — remove `session_id` parameter from signature, keep internal `upstream_session` logic unchanged
- [x] **T006** [P] Update `RagQueryResult` constructor calls in `backend/services/rag_providers/ragflow.py` — replace `session_id` references with `upstream_session` (the provider-created session ID)

---

## Phase 3: User Story 1 — 评测任务自动创建会话并成功执行 (P1) 🎯 MVP

> **Goal**: IntelliQProvider creates a real session via `POST /api/v1/sessions` before calling agent-chat, so evaluation tasks no longer fail with "Session not found".

### IntelliQ Provider Changes

- [x] **T007** [US1] Add `_session_ids: list[str]` instance attribute to `IntelliQProvider.__init__()` in `backend/services/rag_providers/intelliq.py` — tracks created session IDs for later cleanup
- [x] **T008** [US1] Add `_create_session()` async helper method to `IntelliQProvider` in `backend/services/rag_providers/intelliq.py`:
  - `POST {api_base}/sessions` with `{"title": "SmartQ Eval - {timestamp}", "description": "Auto-created session for evaluation"}` and `_headers()`
  - On success (HTTP 200 + `data.id`), return `data.id` as string
  - On failure, return `None` and log the error
  - Use existing `_client()` for aiohttp session; use `await response.json(content_type=None)`
- [x] **T009** [US1] Rewrite `IntelliQProvider.query_sample()` in `backend/services/rag_providers/intelliq.py`:
  - Remove `session_id` parameter from signature
  - Call `self._create_session()` before the agent-chat call
  - If session creation fails, return `RagQueryResult(provider="intelliq", error=...)` with a descriptive `ProviderError("upstream", "Session creation failed: ...")`
  - On success, append the session ID to `self._session_ids`
  - Use the IntelliQ-returned session ID (not a caller-supplied UUID) in the agent-chat URL path and in `RagQueryResult.session_id`
  - Keep the existing SSE processing, error handling, and `aggregate_intelliq_sse()` call unchanged
- [x] **T010** [US1] Add `cleanup_sessions()` method to `IntelliQProvider` in `backend/services/rag_providers/intelliq.py`:
  - If `self._session_ids` is empty, return immediately (no-op)
  - `DELETE {api_base}/sessions/batch` with `{"ids": self._session_ids}` and `_headers()`
  - On success, clear `self._session_ids` and log info
  - On failure, log warning (do not raise, do not affect task status — per FR-005)
  - Clear `self._session_ids` even on failure (best-effort, don't retry forever)

### Evaluation Service Changes

- [x] **T011** [US1] Remove `session_id = str(uuid.uuid4())` generation from `evaluate_with_provider()` loop in `backend/services/evaluation_service.py` (line ~342)
- [x] **T012** [US1] Remove `session_id=session_id` from `provider.query_sample()` call in `evaluate_with_provider()` in `backend/services/evaluation_service.py` (line ~350)
- [x] **T013** [US1] Wrap the sample processing loop in `evaluate_with_provider()` with a `try/finally` block that calls `await provider.cleanup_sessions()` in the `finally` clause — ensures cleanup on cancellation (FR-006), error, or success
  - Use `if hasattr(provider, 'cleanup_sessions'):` guard for provider-agnostic safety

### Test Updates

- [x] **T014** [US1] Update `test_scoring_eligibility.py` mock `Provider.query_sample()` signature — remove `session_id` from `**kwargs` usage; update `RagQueryResult` constructor calls to use a fixed session_id string like `"mock-session"` (providers now set it internally, but the field still exists on the dataclass)

---

## Phase 4: User Story 2 — 会话资源清理 (P2)

> **Goal**: After evaluation completes (or is cancelled), all IntelliQ sessions created during the task are batch-deleted.

- [x] **T015** [US2] Verify `cleanup_sessions()` is called in the `finally` block of `evaluate_with_provider()` — already implemented in T013; this task is to verify end-to-end with a real IntelliQ instance
- [x] **T016** [US2] Verify that `cleanup_sessions()` is a no-op for RAGFlowProvider (which has no session tracking) — ensure the `hasattr` guard in T013 works correctly
- [ ] **T017** [US2] Manual E2E test: run a small evaluation (2-3 samples) against IntelliQ, then check the IntelliQ server that no sessions remain via `GET /api/v1/sessions` or IntelliQ UI

---

## Phase 5: Polish & Cross-Cutting

- [x] **T018** Run existing unit tests: `cd backend && python -m pytest tests/unit/test_scoring_eligibility.py -v` — confirm all pass after signature changes
- [x] **T019** Run syntax checks: `bash -n *.sh && docker-compose config` per AGENTS.md
- [ ] **T020** Run full validation: `./start.sh`, confirm `curl -f http://localhost:5003/health`, test an IntelliQ evaluation task, then `./stop.sh`
- [ ] **T021** [P] Update `specs/005-intelliq-session-creation/quickstart.md` with any corrections discovered during implementation

---

## Task Summary

| Phase | Tasks | Parallel |
|-------|-------|----------|
| Phase 1: Setup | T001 | — |
| Phase 2: Foundational | T002–T006 | T002, T004, T005, T006 |
| Phase 3: US1 (P1) MVP | T007–T014 | T007 (independent of T008–T009) |
| Phase 4: US2 (P2) | T015–T017 | — |
| Phase 5: Polish | T018–T021 | T021 |

**Total**: 21 tasks

## Dependencies

```
T001 (verify API)
  │
  ▼
T002 ── T003 ── T004 (ABC changes, sequential)
  │       │
  ▼       ▼
T005, T006 (RAGFlow update)
  │
  ▼
T007 ── T008 ── T009 ── T010 (IntelliQ provider, sequential)
  │
  ▼
T011, T012, T013 (eval service, sequential)
  │
  ▼
T014 (test update)
  │
  ▼
T015 ── T016 ── T017 (cleanup verification)
  │
  ▼
T018 ── T019 ── T020 (validation)
  │
  ▼
T021 (doc update)
```

## Unblocks 004 Tasks

Completing US1 (T007–T014) unblocks the following tasks from `specs/004-intelliq-evaluation-tasks/tasks.md`:
- T012: E2E evaluation with knowledge base selection
- T013: Progress tracking during evaluation
- T014: E2E evaluation with all metrics
- T017: E2E evaluation with scoring configuration
- T020: E2E test with multiple datasets
- T026: Full regression validation