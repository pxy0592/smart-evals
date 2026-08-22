# Tasks: 数据集页面按需访问 RAG 系统

**Input**: Design documents from `/specs/002-dataset-provider-flow/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: No automated tests requested; manual verification per quickstart.md.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `frontend/src/` for all source changes
- No backend changes needed (all APIs already exist)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify project state and prepare for changes

- [X] T001 Confirm backend APIs are running and return expected shapes by running `quickstart.md` prerequisites: `GET /evaluation/rag-connections`, `GET /evaluation/rag-connections/{id}/assistants`, `GET /evaluation/rag-connections/{id}/knowledge-bases`
- [X] T002 [P] Review current `frontend/src/pages/Datasets.tsx` eager-loading code paths to confirm all RAG calls to remove: `fetchKnowledgeBases()` on mount, `fetchChatAssistants()` in `handleCreateTask`, `fetchMetrics()` in `handleCreateTask`
- [X] T003 [P] Review current `frontend/src/components/EvaluationTaskForm.tsx` to confirm it already uses `ragConnectionApi`/`ragResourceApi` correctly and can be wired into Datasets.tsx modal

---

## Phase 2: User Story 1 - 独立浏览数据集 (Priority: P1) 🎯 MVP

**Goal**: Dataset page loads without any RAG system calls. Only Smart Eval dataset list is fetched.

**Independent Test**: Open DevTools Network tab, navigate to Datasets page, verify only `GET /evaluation/datasets` appears. No RAG connection, knowledge base, or assistant requests.

### Implementation for User Story 1

- [X] T004 [US1] Remove `fetchKnowledgeBases()` call from `useEffect` on mount in `frontend/src/pages/Datasets.tsx` (the `useEffect` at ~line 102 that calls `fetchKnowledgeBases()`)
- [X] T005 [US1] Remove `loadingKnowledgeBases` state variable and `setLoadingKnowledgeBases` calls from `frontend/src/pages/Datasets.tsx` (variable declaration and all setter usages)
- [X] T006 [US1] Remove `knowledgeBases` state variable and `setKnowledgeBases` calls from `frontend/src/pages/Datasets.tsx` (variable declaration and all setter usages)
- [X] T007 [US1] Verify dataset polling in `useEffect` only calls `datasetApi.list()` and does not trigger any RAG requests in `frontend/src/pages/Datasets.tsx`
- [X] T008 [US1] Verify dataset search, preview, and delete operations remain functional without `knowledgeBases` state in `frontend/src/pages/Datasets.tsx`

**Checkpoint**: Dataset page loads independently. No RAG calls on page load or poll refresh.

---

## Phase 3: User Story 2 - 独立上传评测数据集 (Priority: P1)

**Goal**: Dataset upload works without any RAG system calls. Upload, validation, and normalization happen entirely within Smart Eval.

**Independent Test**: Stop all RAG services, upload a valid CSV/JSON dataset, verify upload succeeds and no RAG errors appear.

### Implementation for User Story 2

- [X] T009 [US2] Verify `handleUpload` in `frontend/src/pages/Datasets.tsx` does not call any RAG-related APIs (it already only calls `datasetApi.upload()` — confirm no regressions after US1 changes)
- [X] T010 [US2] Remove any remaining `knowledgeBases` references from upload modal JSX in `frontend/src/pages/Datasets.tsx` (if the upload modal references `knowledgeBases` state removed in T006)

**Checkpoint**: Upload works independently of all RAG systems.

---

## Phase 4: User Story 3 - 按所选连接创建评测任务 (Priority: P1)

**Goal**: Clicking "创建评测" opens a modal with connection selection. Only the selected connection's assistants and knowledge bases are loaded. Task submission uses `rag_target`.

**Independent Test**: Configure two RAG connections, create a task selecting one, verify only that connection receives requests.

### Implementation for User Story 3

- [X] T011 [US3] Add task creation session state to `frontend/src/pages/Datasets.tsx`: `taskConnections` (RagConnectionSummary[]), `taskConnectionLoading`, `taskAssistants` (AssistantRef[]), `taskAssistantLoading`, `taskKbs` (RagResourceRef[]), `taskKbLoading`, `taskAbortController` (AbortController)
- [X] T012 [US3] Replace `handleCreateTask` body: remove eager `fetchChatAssistants()` and `fetchMetrics()` calls; instead set `createTaskVisible` and trigger connection list load in `frontend/src/pages/Datasets.tsx`
- [X] T013 [US3] Add `useEffect` hook to load connections when `createTaskVisible` becomes true: call `ragConnectionApi.list()`, filter enabled connections, set skeleton → populated state within 2s in `frontend/src/pages/Datasets.tsx`
- [X] T014 [US3] Add connection selection handler: call `ragResourceApi.listAssistants(connectionId)` with AbortController signal, populate `taskAssistants` in `frontend/src/pages/Datasets.tsx`
- [X] T015 [US3] Add assistant selection handler: read `knowledge_base_selection_mode`, if `'selected'` call `ragResourceApi.listKnowledgeBases(connectionId, {assistant_id})`; if `'all'` or `'none'` show info alert per `EvaluationTaskForm.tsx` pattern in `frontend/src/pages/Datasets.tsx`
- [X] T016 [US3] Add connection/assistant switch handler: abort previous AbortController, create new one, clear dependent state (assistants reset on connection switch, KBs reset on assistant switch) in `frontend/src/pages/Datasets.tsx`
- [X] T017 [US3] Replace the legacy task creation modal body with `EvaluationTaskForm` component (or inline form using the same service calls) that receives session state and uses `rag_target` for submission in `frontend/src/pages/Datasets.tsx`
- [X] T018 [US3] Update `handleCreateTaskSubmit` to construct `TaskCreateParams` with `rag_target` field instead of legacy `chat_id` field in `frontend/src/pages/Datasets.tsx`
- [X] T019 [US3] Add modal close handler: abort `taskAbortController`, reset all task session state to initial values in `frontend/src/pages/Datasets.tsx`
- [X] T020 [US3] Add error state with retry button for connection list load failure inside the modal (not a toast, not automatic close) in `frontend/src/pages/Datasets.tsx`
- [X] T021 [US3] Add skeleton loading placeholders (Ant Design `Skeleton`) for connection dropdown during initial load in `frontend/src/pages/Datasets.tsx`
- [X] T022 [US3] Remove unused `chatAssistants`, `loadingChats`, `fetchChatAssistants`, `metrics`, `loadingMetrics`, `fetchMetrics` state and functions from `frontend/src/pages/Datasets.tsx` (they are replaced by on-demand session state)

**Checkpoint**: Task creation modal works with connection-scoped resource loading.

---

## Phase 5: User Story 4 - 按所选连接生成 AI 数据集 (Priority: P2)

**Goal**: Clicking "AI 智能生成数据集" opens a modal with connection selection. Connections show capability badges. Only the selected connection's knowledge bases are loaded. Generation request includes connection identity.

**Independent Test**: Configure one capable and one incapable connection, verify incapable is disabled, capable loads KBs and submits with connection_id.

### Implementation for User Story 4

- [X] T023 [US4] Add AI generation session state to `frontend/src/pages/Datasets.tsx`: `genConnections` (RagConnectionSummary[]), `genConnectionLoading`, `genSelectedConnectionId`, `genKbs` (RagResourceRef[]), `genKbLoading`, `genAbortController`
- [X] T024 [US4] Replace `handleGenerate` button handler: remove eager `knowledgeBases` dependency; set `generateVisible` and trigger connection list load in `frontend/src/pages/Datasets.tsx`
- [X] T025 [US4] Add `useEffect` hook to load connections when `generateVisible` becomes true: call `ragConnectionApi.list()`, set skeleton state, display each connection with capability badge (`generate_dataset_from_knowledge_base`) in `frontend/src/pages/Datasets.tsx`
- [X] T026 [US4] Add connection selection handler for AI generation: if `capabilities.generate_dataset_from_knowledge_base` is true, call `ragResourceApi.listKnowledgeBases(connectionId)` with AbortController signal; if false, disable KB selector and submit button, show reason text in `frontend/src/pages/Datasets.tsx`
- [X] T027 [US4] Add connection switch handler for AI generation: abort previous AbortController, clear KB list and selection, reload KBs for new connection in `frontend/src/pages/Datasets.tsx`
- [X] T028 [US4] Update `handleGenerate` submit to call `datasetApi.generateAIDataset()` with `connection_id` and `kb_id` from the selected connection (update the API call signature if needed) in `frontend/src/pages/Datasets.tsx`
- [X] T029 [US4] Add modal close handler: abort `genAbortController`, reset all gen session state to initial values in `frontend/src/pages/Datasets.tsx`
- [X] T030 [US4] Add error state with retry button for connection list load failure in AI generation modal in `frontend/src/pages/Datasets.tsx`
- [X] T031 [US4] Add skeleton loading placeholders for connection dropdown in AI generation modal in `frontend/src/pages/Datasets.tsx`
- [X] T032 [US4] Update `datasetApi.generateAIDataset` signature in `frontend/src/services/evaluation.ts` to accept `connection_id` and `kb_id` params (replace legacy `kb_id`-only signature) if the backend expects `connection_id`

**Checkpoint**: AI generation modal works with connection-scoped resource loading and capability gating.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Cleanup, edge case hardening, and final verification

- [X] T033 [P] Remove unused imports from `frontend/src/pages/Datasets.tsx`: `chatApi`, `metricApi`, `knowledgeBaseApi` (if no longer used after all changes)
- [X] T034 [P] Remove unused `knowledgeBases` and `loadingKnowledgeBases` from AI generation modal JSX: replace with `genKbs` and `genKbLoading` in `frontend/src/pages/Datasets.tsx`
- [ ] T035 Verify all 8 quickstart validation scenarios from `quickstart.md` pass manually
- [ ] T036 Verify edge cases from spec.md: stale response prevention (rapid connection switching), modal close/reopen state isolation, disabled connection re-validation on submit

---

## Dependencies

```
Phase 1 (Setup)
    │
    ▼
Phase 2 (US1: Dataset browsing) ────────┐
    │                                     │
    ▼                                     │
Phase 3 (US2: Upload) ──────────────────┤
    │                                     │
    ▼                                     ▼
Phase 4 (US3: Task creation)    Phase 5 (US4: AI generation)
    │                                     │
    └──────────────┬──────────────────────┘
                   ▼
            Phase 6 (Polish)
```

- **US1 must be first**: Removes eager loading that interferes with US3/US4
- **US2 can follow US1**: Requires `knowledgeBases` state removal from US1
- **US3 and US4 can run in parallel** after US1/US2 are complete: they use different modal state and different API call patterns
- **Phase 6 depends on all user stories**

## Parallel Execution Examples

### Within US3 (Task Creation)
- T011 (state declaration) and T021 (skeleton) can be done in any order after T012 (wire modal open)
- T014 (connection handler) and T015 (assistant handler) are sequential (assistant depends on connection)

### Within US4 (AI Generation)
- T023 (state) and T031 (skeleton) can be done in any order after T024 (wire modal open)
- T026 (connection handler) and T027 (switch handler) are sequential

### Across User Stories
- US3 (T011-T022) and US4 (T023-T032) can be implemented in parallel by different developers after US1/US2 are complete

## Implementation Strategy

### MVP (User Stories 1 + 2 only)
1. Complete Phase 1 (Setup): T001-T003
2. Complete Phase 2 (US1): T004-T008 → Dataset page loads without RAG
3. Complete Phase 3 (US2): T009-T010 → Upload works independently
4. **STOP and VALIDATE**: Run quickstart VS-1, VS-2
5. Deploy/demo if ready

### Full Feature
1. MVP above
2. Add Phase 4 (US3): T011-T022 → Task creation with connection selection
3. Add Phase 5 (US4): T023-T032 → AI generation with connection selection
4. Phase 6 (Polish): T033-T036 → Cleanup and final verification
5. Run all quickstart scenarios VS-1 through VS-8