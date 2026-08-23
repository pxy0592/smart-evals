---

description: "Implementation tasks for durable IntelliQ evaluation session lifecycle"
---

# Tasks: IntelliQ 评测前自动创建会话

**Input**: Design documents from `/specs/005-intelliq-session-creation/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/intelliq-session-api.md`, `quickstart.md`

**Tests**: Tests are required. The feature changes external resource lifecycle behavior and must be verified using a stateful IntelliQ mock before any live smoke test.

**Organization**: Tasks are grouped by user story. Shared persistence and provider contracts are completed before session lifecycle stories.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare stateful IntelliQ Session test fixtures and configuration needed by all lifecycle work.

- [X] T001 [P] Add Session lifecycle configuration defaults and documentation for cleanup batch size and compensation behavior in `backend/config.py` and `.env.example`
- [X] T002 [P] Extend the stateful IntelliQ mock server skeleton with in-memory Session, deletion-batch, and request-audit stores in `backend/tests/mock_intelliq_server.py`
- [X] T003 [P] Create reusable Session lifecycle test helpers and isolated task/database fixtures in `backend/tests/conftest.py` and `backend/tests/fixtures/sessions/README.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add durable sample-run Session lifecycle fields and provider-neutral cleanup contracts before implementing either user story.

**CRITICAL**: Complete this phase before User Story 1 or User Story 2 work.

### Foundational Tests

- [X] T004 [P] Add failing migration tests for provider Session IDs, creation status, cleanup status, cleanup errors, cleanup attempts, and startup pending-cleanup lookup in `backend/tests/integration/test_database_migrations.py`
- [X] T005 [P] Add failing provider-base tests for Session cleanup result objects and no-op behavior for non-IntelliQ providers in `backend/tests/unit/test_rag_provider_base.py`
- [X] T006 [P] Add failing persistence tests for writing the real provider Session ID after creation and querying current-task pending cleanup IDs in `backend/tests/integration/test_intelliq_session_lifecycle.py`

### Foundational Implementation

- [X] T007 Add additive `evaluation_sample_runs` Session lifecycle migration columns, pending-cleanup index, and idempotent defaults in `backend/models/database.py`
- [X] T008 Implement sample-run updates for provider Session creation, structured creation failures, cleanup state transitions, and pending cleanup queries in `backend/models/database.py` and `backend/db.py`
- [X] T009 Define provider-neutral `SessionCreationResult` and `SessionCleanupResult` contracts plus no-op defaults in `backend/services/rag_providers/base.py`
- [X] T010 Add startup recovery that discovers pending IntelliQ cleanup records without changing completed task outcomes in `backend/evaluation_db.py`
- [X] T011 Run foundational migration, base-contract, and persistence tests in `backend/tests/integration/test_database_migrations.py`, `backend/tests/unit/test_rag_provider_base.py`, and `backend/tests/integration/test_intelliq_session_lifecycle.py`

**Checkpoint**: The application can persist real provider Session IDs and unresolved cleanup work before any IntelliQ network behavior is changed.

---

## Phase 3: User Story 1 - IntelliQ 评测任务自动创建会话并成功执行 (Priority: P1) MVP

**Goal**: Each IntelliQ sample creates a real Session, records the upstream Session ID, uses that ID for Agent Chat, and returns structured diagnostics when creation fails.

**Independent Test**: A stateful mock rejects Agent Chat for unknown Session IDs, while a two-sample evaluation creates two distinct Sessions, sends each real ID to Chat, and records those IDs in `evaluation_sample_runs`.

### Tests for User Story 1

- [X] T012 [P] [US1] Add unit tests for `POST /sessions` request path, headers, title/description, HTTP 200/201 success, `success=false`, missing `data.id`, non-JSON, 401/403/429/5xx, and timeout mapping in `backend/tests/unit/test_intelliq_resources.py`
- [X] T013 [P] [US1] Add stateful mock tests that reject unknown Agent Chat Session IDs with code 1003 and accept only Session IDs returned by `POST /sessions` in `backend/tests/mock_intelliq_server.py` and `backend/tests/integration/test_intelliq_session_lifecycle.py`
- [X] T014 [P] [US1] Add integration tests for two distinct provider Session IDs, selected/all/none Agent modes, creation failure with zero Chat requests, and Session ID persistence in `backend/tests/integration/test_intelliq_session_lifecycle.py`

### Implementation for User Story 1

- [X] T015 [US1] Refactor `_create_session()` to return a structured success or redacted `ProviderError` with HTTP status and upstream error details in `backend/services/rag_providers/intelliq.py`
- [X] T016 [US1] Update `IntelliQProvider.query_sample()` to record successful real Session IDs, invoke a provider-session-created callback before Agent Chat, refuse Chat after creation failure, and pass the real ID to SSE aggregation in `backend/services/rag_providers/intelliq.py`
- [X] T017 [US1] Extend the provider `query_sample()` contract and `EvaluationService.evaluate_with_provider()` callbacks so local correlation IDs and real provider Session IDs are persisted separately in `backend/services/rag_providers/base.py` and `backend/services/evaluation_service.py`
- [X] T018 [US1] Write the real Session creation status, provider Session ID, Agent Chat failure diagnostics, and score eligibility to the sample-run record in `backend/evaluation_db.py` and `backend/db.py`
- [X] T019 [US1] Verify P1 behavior with the stateful mock and update expected sample-session fields in `backend/tests/unit/test_scoring_eligibility.py` and `backend/tests/integration/test_intelliq_task_flow.py`

**Checkpoint**: IntelliQ samples no longer send caller-generated UUIDs to Agent Chat, and creation failures are visible, safe, and unscoreable.

---

## Phase 4: User Story 2 - 会话资源清理 (Priority: P2)

**Goal**: Smart Eval reliably cleans Sessions created by a task, retains unresolved cleanup work, and never changes a completed evaluation outcome solely because cleanup failed.

**Independent Test**: A task with successful, failed, and cancelled samples sends one deduplicated batch delete containing only successfully created real Session IDs; cleanup failure is persisted as a warning and can be recovered later.

### Tests for User Story 2

- [X] T020 [P] [US2] Add provider tests for empty cleanup no-op, stable de-duplication, batch splitting, no redirects, HTTP 2xx plus `success=true` success, and `success=false` failure in `backend/tests/unit/test_intelliq_resources.py`
- [X] T021 [P] [US2] Add integration tests for Chat SSE failure cleanup, partial-success cleanup failure, all-failed cleanup, and cancellation between samples in `backend/tests/integration/test_intelliq_session_lifecycle.py`
- [X] T022 [P] [US2] Add startup compensation tests for pending/failed cleanup records and verify RAGFlow never participates in IntelliQ cleanup in `backend/tests/integration/test_intelliq_session_lifecycle.py` and `backend/tests/integration/test_ragflow_legacy_flow.py`

### Implementation for User Story 2

- [X] T023 [US2] Refactor `cleanup_sessions()` to collect only current task real Session IDs, defer in-memory removal until business-success confirmation, disable redirects, split batches by configured size, and return structured cleanup results in `backend/services/rag_providers/intelliq.py`
- [X] T024 [US2] Update `EvaluationService.evaluate_with_provider()` to call cleanup in all terminal paths, apply cleanup result updates to sample records, and keep completed/partially-succeeded/failed/cancelled outcomes unchanged in `backend/services/evaluation_service.py`
- [X] T025 [US2] Implement task-end and startup compensation cleanup orchestration, safe warning logging, and report/task warning projection in `backend/evaluation_db.py` and `backend/db.py`
- [X] T026 [US2] Extend the stateful mock's batch-delete behavior for duplicate IDs, unknown IDs, business failure, HTTP failure, and request auditing in `backend/tests/mock_intelliq_server.py`
- [X] T027 [US2] Verify cleanup behavior against all automated lifecycle tests and confirm quickstart cancellation/failure expectations in `specs/005-intelliq-session-creation/quickstart.md`

**Checkpoint**: Session cleanup is observable, compensable, and non-destructive to evaluation outcomes.

---

## Phase 5: Polish & Cross-Cutting Validation

**Purpose**: Complete operator evidence, controlled real-environment validation, and documentation without leaking IntelliQ credentials.

- [X] T028 [P] Add secret-redaction regression cases for Session creation and cleanup error payloads in `backend/tests/unit/test_secret_redaction.py`
- [X] T029 [P] Update test-only IntelliQ mock usage and Session lifecycle troubleshooting guidance in `README.md` and `QUICKSTART.md`
- [X] T030 Run the complete automated Session lifecycle suite, backend compilation, and RAGFlow regression; record commands and results in `specs/005-intelliq-session-creation/validation-results.md`
- [X] T031 Perform the controlled IntelliQ smoke test from `specs/005-intelliq-session-creation/quickstart.md` with a disposable tenant, record only non-secret evidence in `specs/005-intelliq-session-creation/validation-results.md`, and explicitly note skipped external checks if credentials are unavailable

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001-T003 can start immediately.
- **Foundational (Phase 2)**: T004-T011 block all user stories because provider Session IDs and cleanup states must be durable first.
- **User Story 1 (Phase 3)**: Depends on T011; delivers the Session creation MVP.
- **User Story 2 (Phase 4)**: Depends on US1 because cleanup only applies to successfully created provider Sessions.
- **Polish (Phase 5)**: Depends on both user stories.

### User Story Dependencies

```text
Foundation
  -> US1: create and persist real IntelliQ Sessions
      -> US2: clean up and compensate Session lifecycle work
          -> Polish: validate and document
```

### Parallel Opportunities

- T001-T003 can run in parallel.
- T004-T006 can run in parallel before foundational implementation.
- T012-T014 can run in parallel before User Story 1 implementation.
- T020-T022 can run in parallel before User Story 2 implementation.
- T028-T029 can run in parallel after lifecycle behavior is stable.

## Parallel Example: User Story 1

```text
Task T012: Add Session creation response tests in backend/tests/unit/test_intelliq_resources.py
Task T013: Add stateful Session/Chat mock tests in backend/tests/mock_intelliq_server.py and backend/tests/integration/test_intelliq_session_lifecycle.py
Task T014: Add evaluation lifecycle persistence tests in backend/tests/integration/test_intelliq_session_lifecycle.py
```

## Parallel Example: User Story 2

```text
Task T020: Add batch cleanup contract tests in backend/tests/unit/test_intelliq_resources.py
Task T021: Add failure and cancellation cleanup tests in backend/tests/integration/test_intelliq_session_lifecycle.py
Task T022: Add startup compensation and RAGFlow regression tests in backend/tests/integration/test_intelliq_session_lifecycle.py and backend/tests/integration/test_ragflow_legacy_flow.py
```

## Implementation Strategy

### MVP First: User Story 1

1. Complete T001-T011.
2. Complete T012-T019.
3. Stop and verify stateful mock coverage: create real Session, use returned ID for Chat, persist returned ID, and reject creation failures before Chat.

### Incremental Delivery

1. Durable Session persistence and structured creation errors.
2. Real Session creation and Agent Chat validation.
3. Cleanup business-success handling and compensation recovery.
4. Controlled IntelliQ smoke test and documentation.

## Notes

- All Session IDs in cleanup requests must be real IntelliQ provider IDs, not local correlation IDs.
- `POST /sessions` remains non-idempotent until IntelliQ documents safe retry semantics.
- Cleanup failure is a resource-governance warning, not a scoring failure.
- Do not commit real API Keys, Session IDs, tenant identifiers, or raw upstream error bodies.
