# Tasks: 允许向 IntelliQ 系统发起评测任务

**Input**: Design documents from `/specs/004-intelliq-evaluation-tasks/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Not explicitly requested in the feature specification. Test tasks are omitted.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/`, `frontend/src/`
- Backend: `backend/evaluation_db.py`, `backend/services/`, `backend/services/rag_providers/`
- Frontend: `frontend/src/pages/`, `frontend/src/components/`, `frontend/src/services/`

---

## Phase 1: Setup (Verification)

**Purpose**: Verify that all prerequisites are met before any implementation work begins.

- [x] T001 Verify IntelliQ connection is configured and enabled in Docker environment via `docker exec smart-eval python3 -c "import sqlite3, os; conn = sqlite3.connect(os.getenv('DATABASE_PATH', 'data/evaluation.db')); cursor = conn.cursor(); cursor.execute('SELECT id, name, provider, enabled FROM rag_connections WHERE provider=\"intelliq\"'); print(cursor.fetchall()); conn.close()"`
- [x] T002 Verify at least one IntelliQ agent with known knowledge_base_selection_mode exists via `curl -s http://localhost:5003/api/v1/evaluation/rag-connections/<connection_id>/assistants?limit=100`
- [x] T003 Verify at least one completed dataset exists for testing via `curl -s "http://localhost:5003/api/v1/evaluation/datasets?status=completed&limit=100"`

**Checkpoint**: All prerequisites confirmed — ready to proceed with implementation.

---

## Phase 2: Foundational (Verification — No Code Changes)

**Purpose**: Confirm that the existing backend infrastructure is fully provider-agnostic. No code changes are needed in this phase — all tasks are verification-only.

**⚠️ CRITICAL**: Research confirmed that `create_evaluation_task()`, `run_evaluation_task()`, `evaluate_with_provider()`, and `IntelliQProvider.query_sample()` are already fully provider-agnostic. These verification tasks confirm that before any frontend work begins.

- [x] T004 Verify `create_evaluation_task()` in backend/evaluation_db.py accepts `rag_target.connection_id` for any provider by reviewing the route handler at line 688 — confirm it uses `create_provider(connection)` and validates agents/knowledge bases generically
- [x] T005 Verify `run_evaluation_task()` in backend/evaluation_db.py resolves provider via `create_provider()` and passes to `evaluate_with_provider()` at line 778 — confirm revision check and cancellation callbacks are provider-agnostic
- [x] T006 Verify `evaluate_with_provider()` in backend/services/evaluation_service.py iterates samples through `provider.query_sample()` at line 317 — confirm it separates `score_eligible` from failed samples generically
- [x] T007 Verify `IntelliQProvider.query_sample()` in backend/services/rag_providers/intelliq.py handles SSE agent chat with all error cases (timeout, protocol error, upstream error, empty answer) at line 196
- [x] T008 Verify `aggregate_intelliq_sse()` in backend/services/rag_providers/sse.py correctly extracts answer, references, and contexts from SSE events at line 57

**Checkpoint**: Backend infrastructure confirmed ready — no backend changes needed. Proceed to frontend work.

---

## Phase 3: User Story 1 - 创建 IntelliQ 评测任务并获取完整报告 (Priority: P1) 🎯 MVP

**Goal**: Users can create an evaluation task against an IntelliQ connection, monitor its progress, and receive a complete evaluation report with scores and success/failure details.

**Independent Test**: Prepare a verified IntelliQ connection and a completed evaluation dataset, create an evaluation task, wait for completion, and verify the report contains scoring data and success/failure breakdown.

### Implementation for User Story 1

- [x] T009 [P] [US1] Add "RAG 系统" column to task list table in frontend/src/pages/Tasks.tsx — add a new column between "任务名称" and "对话助手" that displays `source_snapshot.connection_name` with a provider-colored Tag (e.g., blue for IntelliQ, green for RAGFlow)
- [x] T010 [P] [US1] Add `source_snapshot` field to the `EvaluationTask` interface in frontend/src/pages/Tasks.tsx — extend the interface to include the optional `source_snapshot` object returned by the API
- [x] T011 [US1] Add provider and connection info to task details drawer in frontend/src/pages/Tasks.tsx — in the drawer content (around line 790), add a section showing RAG provider name, connection name, Agent name, and knowledge base names from `source_snapshot`
- [ ] T012 [US1] End-to-end validation: create IntelliQ evaluation task via frontend — select IntelliQ connection, agent, knowledge bases, dataset, and metrics; submit and verify task appears in list with `pending` status ⚠️ BLOCKED: IntelliQ server returns "Session not found" for all agent-chat calls; task creation succeeds but execution fails
- [ ] T013 [US1] End-to-end validation: monitor task progress to completion — verify status transitions from `pending` → `running` → `completed`, progress bar updates, and processor/sample counts increment
- [ ] T014 [US1] End-to-end validation: verify evaluation report — after task completion, open the report and confirm it contains overall scores, per-sample details, and any failed sample error descriptions

**Checkpoint**: User Story 1 complete — IntelliQ evaluation task creation and reporting works end-to-end.

---

## Phase 4: User Story 2 - 任务状态跟踪与进度反馈 (Priority: P1)

**Goal**: Users can see real-time status changes and progress updates for IntelliQ evaluation tasks in the task list.

**Independent Test**: Create an IntelliQ evaluation task, observe the task list as status changes from pending to running to completed, with progress percentage and sample counts updating.

### Implementation for User Story 2

- [x] T015 [US2] Verify auto-refresh works for IntelliQ tasks in frontend/src/pages/Tasks.tsx — confirm the existing polling interval (around line 250) correctly refreshes task list when IntelliQ tasks are running, displaying updated progress and processed sample counts
- [x] T016 [US2] Add "RAG 系统" filter to task list in frontend/src/pages/Tasks.tsx — add a filter dropdown or column filter for `rag_provider` field to allow filtering tasks by provider type (IntelliQ vs RAGFlow)
- [ ] T017 [US2] End-to-end validation: verify status transitions ⚠️ BLOCKED: depends on T012

**Checkpoint**: User Story 2 complete — task status tracking and progress feedback work for IntelliQ tasks.

---

## Phase 5: User Story 3 - 查看评测报告详情 (Priority: P2)

**Goal**: Users can view detailed evaluation reports for IntelliQ tasks, including per-metric scores, per-sample breakdowns, and failure reasons.

**Independent Test**: After an IntelliQ evaluation task completes, click "查看报告" and verify the report contains all expected metric scores and sample details.

### Implementation for User Story 3

- [x] T018 [US3] Verify report page displays IntelliQ provider info in frontend/src/pages/Reports.tsx — added `source_snapshot.connection_name`, `source_snapshot.assistant_name`, and knowledge base list to the report detail header; report list already has "RAG 系统" column
- [x] T019 [US3] Verify failed sample details are displayed correctly — added `completion_status` column to sample details table showing "失败" Tag with error tooltip; added `upstream_error` Alert and `partial_answer` display in expanded rows for failed samples
- [ ] T020 [US3] End-to-end validation: view full report ⚠️ BLOCKED: depends on T012

**Checkpoint**: User Story 3 complete — report viewing works for IntelliQ tasks.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, edge case handling, and documentation.

- [x] T021 [P] Verify "all" mode agent task creation — confirmed: EvaluationTaskForm.tsx line 142 shows Alert for mode !== 'selected' with appropriate message for "all" and "none" modes
- [x] T022 [P] Verify "none" mode agent task creation — confirmed: same code path as T021 handles both "all" and "none" modes
- [x] T023 Verify revision change rejection — confirmed: run_evaluation_task() at line 798 checks `connection.get("revision") != task.get("rag_connection_revision")` and fails with clear message
- [x] T024 Verify task cancellation — confirmed: run_evaluation_task() passes `cancelled()` callback to `evaluate_with_provider()`, which checks `cancellation_check()` at each sample iteration (line 334)
- [x] T025 Verify SSE error handling — confirmed: `query_sample()` handles timeout (line 211), protocol error (line 208), upstream error (line 213), and HTTP errors (line 205-206); `aggregate_intelliq_sse()` handles JSON decode errors (line 76), error events (line 87-97), and general exceptions (line 98-107)
- [ ] T026 Run quickstart.md validation scenarios ⚠️ BLOCKED: depends on working IntelliQ server

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — verification confirms backend readiness
- **User Story 1 (Phase 3)**: Depends on Foundational phase completion — adds frontend provider display
- **User Story 2 (Phase 4)**: Depends on Foundational phase completion — can run in parallel with US1
- **User Story 3 (Phase 5)**: Depends on Foundational phase completion — can run in parallel with US1/US2
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies on other stories — adds provider column and drawer info
- **User Story 2 (P2)**: No dependencies on other stories — verifies refresh and adds filter
- **User Story 3 (P3)**: No dependencies on other stories — verifies report display

### Within Each User Story

- Frontend interface changes before UI component changes
- UI changes before end-to-end validation
- Each story independently testable after completion

### Parallel Opportunities

- T001, T002, T003 (Setup) can run in parallel
- T004-T008 (Foundational) can run in parallel
- T009, T010 (US1 interface + column) can run in parallel
- US1, US2, US3 phases can all start in parallel after Foundational phase
- T021, T022 (Polish edge cases) can run in parallel
- T023-T026 (Polish validation) are sequential by nature

---

## Parallel Example: User Story 1

```bash
# Launch interface changes together:
Task: "Add 'RAG 系统' column to task list table in frontend/src/pages/Tasks.tsx"
Task: "Add source_snapshot field to the EvaluationTask interface in frontend/src/pages/Tasks.tsx"

# After T009 and T010 complete:
Task: "Add provider and connection info to task details drawer in frontend/src/pages/Tasks.tsx"

# Then end-to-end validation:
Task: "End-to-end validation: create IntelliQ evaluation task via frontend"
Task: "End-to-end validation: monitor task progress to completion"
Task: "End-to-end validation: verify evaluation report"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (verify prerequisites)
2. Complete Phase 2: Foundational (verify backend readiness)
3. Complete Phase 3: User Story 1 (add provider display to frontend)
4. **STOP and VALIDATE**: Create an IntelliQ task end-to-end and verify report
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Backend confirmed ready
2. Add User Story 1 → Provider column + drawer info → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Auto-refresh + filter → Test independently → Deploy/Demo
4. Add User Story 3 → Report display verification → Test independently → Deploy/Demo
5. Polish → Edge case validation → Final release

### Key Insight

The backend evaluation pipeline (`create_evaluation_task` → `run_evaluation_task` → `evaluate_with_provider` → `provider.query_sample`) is already fully provider-agnostic. The IntelliQ SSE agent chat implementation is complete. This feature primarily requires **frontend display enhancements** to surface provider information that the backend already returns, plus **end-to-end validation** to confirm the full flow works correctly.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- No backend code changes are required — the evaluation pipeline is already provider-agnostic
- All frontend changes are in `frontend/src/pages/Tasks.tsx` (task list + drawer) and possibly `frontend/src/pages/Reports.tsx` (report display)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently