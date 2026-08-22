# Tasks: IntelliQ 支持 AI 数据集生成

**Input**: Design documents from `/specs/003-intelliq-ai-dataset-gen/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api-usage.md, quickstart.md

**Tests**: No automated tests requested; manual verification per quickstart.md.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/` for all source changes
- **Frontend**: `frontend/src/` (no changes expected; already sends `connection_id`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify project state and confirm existing patterns

- [ ] T001 Confirm backend is running and current RAGFlow AI generation flow works end-to-end: upload a dataset, open AI generation modal, select RAGFlow connection, generate with small sample count, verify dataset created
- [ ] T002 [P] Review current `backend/services/rag_providers/factory.py` `create_provider()` function signature and confirm it accepts `connection` dict + `api_key` and returns appropriate provider instance
- [ ] T003 [P] Review current `frontend/src/pages/Datasets.tsx` `handleGenerateSubmit()` to confirm `connection_id` is already passed in the request body (line ~447)

---

## Phase 2: Foundational — Capability Declaration & Base Class (US2)

**Purpose**: Fix IntelliQ capability declaration and add `get_chunks()` to the provider base class. These changes are prerequisites for all subsequent phases.

**User Story**: US2 — 连接能力声明与反映 (P1)

**Independent Test**: Call `GET /api/v1/evaluation/rag-connections`, verify IntelliQ connection's `capabilities.generate_dataset_from_knowledge_base` is `true`. Open AI generation modal, verify IntelliQ connection is selectable without capability warning.

### Implementation

- [ ] T004 [US2] Change `IntelliQProvider.capabilities` from `ProviderCapabilities(streaming_chat=True)` to `ProviderCapabilities(generate_dataset_from_knowledge_base=True, streaming_chat=True)` in `backend/services/rag_providers/intelliq.py` line 17
- [ ] T005 [US2] Fix `RagConnectionService._summary()` to derive capabilities from `create_provider()` instead of hardcoded dict: replace the hardcoded capabilities dict (lines 32-39) with `create_provider(row).capabilities.__dict__` in `backend/services/rag_connection_service.py`
- [ ] T006 [US2] Handle `_summary()` edge case: ensure `create_provider()` call doesn't fail when `api_key` is unavailable (decrypt the key or pass empty string for capability-only resolution) in `backend/services/rag_connection_service.py`
- [ ] T007 Add `get_chunks(kb_id: str, limit: int) -> list[dict[str, Any]]` abstract method to `RagProvider` base class in `backend/services/rag_providers/base.py`. Method signature: synchronous, returns list of chunk dicts with `id`, `content`, `doc_name`, `doc_id`, `dataset_id` fields.

**Checkpoint**: IntelliQ connections correctly report `generate_dataset_from_knowledge_base: true` via API. AI generation modal shows IntelliQ as capable. Provider base class has `get_chunks` contract.

---

## Phase 3: User Story 1 — 基于 IntelliQ 知识库生成数据集 (P1) 🎯 MVP

**Goal**: Full end-to-end AI dataset generation from IntelliQ knowledge bases. User selects IntelliQ connection → knowledge base → generates QA pairs from IntelliQ content.

**Independent Test**: Configure an IntelliQ connection with a populated knowledge base, open AI generation modal, select IntelliQ connection and KB, generate 3 samples, verify dataset created with content relevant to the IntelliQ KB.

### Implementation

- [ ] T008 [P] [US1] Implement `RAGFlowProvider.get_chunks()` by extracting chunk retrieval logic from `AIDatasetGenerator._get_chunks_from_dataset()` and `_get_chunks_from_document()` into the provider, using `self.api_base` and `self.api_key` instead of hardcoded instance variables in `backend/services/rag_providers/ragflow.py`
- [ ] T009 [P] [US1] Implement `IntelliQProvider.get_chunks()`: call `GET /api/v1/knowledge-bases/{kb_id}/documents` to list documents, then `GET /api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/chunks` per document. Use `asyncio.run()` to bridge async `_get_json()` to synchronous method. Return chunk dicts with `id`, `content`, `doc_name`, `doc_id`, `dataset_id` fields. Handle empty results and API errors gracefully in `backend/services/rag_providers/intelliq.py`
- [ ] T010 [US1] Refactor `AIDatasetGenerator.__init__()` to accept no RAGFlow-specific config (remove `self.ragflow_base_url`, `self.ragflow_api_key` initialization). The generator no longer reads RAGFlow env vars directly in `backend/services/ai_dataset_generator.py`
- [ ] T011 [US1] Refactor `AIDatasetGenerator.get_knowledge_base_chunks()` to accept a `provider` parameter and delegate to `provider.get_chunks(kb_id, limit)` instead of calling `_get_chunks_from_dataset()` directly in `backend/services/ai_dataset_generator.py`
- [ ] T012 [US1] Refactor `AIDatasetGenerator.generate_dataset_from_kb()` to accept a `provider` parameter and pass it through to `get_knowledge_base_chunks()` in `backend/services/ai_dataset_generator.py`
- [ ] T013 [US1] Remove now-unused `_get_chunks_from_dataset()` and `_get_chunks_from_document()` private methods from `AIDatasetGenerator` (logic moved to `RAGFlowProvider.get_chunks()` in T008) in `backend/services/ai_dataset_generator.py`

**Checkpoint**: `AIDatasetGenerator` is provider-agnostic. Both `RAGFlowProvider` and `IntelliQProvider` implement `get_chunks()`. Generator can produce QA pairs from either provider's chunks.

---

## Phase 4: User Story 3 — 后端路由支持连接参数 (P2)

**Goal**: Backend AI generation endpoint accepts and validates `connection_id`, resolves the connection, creates the correct provider, and passes it to the generator.

**Independent Test**: POST to `/api/v1/evaluation/datasets/generate/ai` with `connection_id` pointing to an IntelliQ connection, verify the route resolves the connection and calls IntelliQ provider.

### Implementation

- [ ] T014 [US3] Update `generate_ai_dataset()` route in `backend/evaluation_db.py` to read `connection_id` from request body and validate it is present; return 400 with `"Connection ID is required"` if missing
- [ ] T015 [US3] Add connection resolution logic in `generate_ai_dataset()`: use `RagConnectionService.get_connection(connection_id, include_secret=True)` to fetch connection details; return 400 with `"Connection not found: {id}"` if None
- [ ] T016 [US3] Add provider capability check: verify `connection["capabilities"]["generate_dataset_from_knowledge_base"]` is `true`; return 400 with `"Connection does not support AI dataset generation"` if false
- [ ] T017 [US3] Create provider instance via `create_provider(connection, api_key)` and pass it to `AIDatasetGenerator.generate_dataset_from_kb()` in the `generate_async()` thread function in `backend/evaluation_db.py`
- [ ] T018 [US3] Update `generate_async()` inner function to capture `connection` dict and `api_key` from the route scope, create provider inside the thread, and pass provider to generator in `backend/evaluation_db.py`

**Checkpoint**: Backend route fully supports `connection_id`. Requests with valid IntelliQ connection ID trigger provider-aware generation. Requests with missing/invalid/incapable connection IDs return appropriate 400 errors.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation, regression testing, and edge case handling.

- [ ] T019 Run all quickstart.md validation scenarios VS-1 through VS-8 and confirm all pass
- [ ] T020 Verify RAGFlow AI generation still works (regression test): select RAGFlow connection, generate dataset, confirm output identical to pre-change behavior
- [ ] T021 Handle edge case: IntelliQ knowledge base has no documents — generator should return empty list, route should set dataset status to "failed" with descriptive error message
- [ ] T022 Handle edge case: IntelliQ API returns 401/403/5xx during chunk retrieval — `get_chunks()` should return empty list (not crash), route should set dataset to "failed"
- [ ] T023 Verify `_get_mock_chunks()` fallback is removed from `AIDatasetGenerator` or refactored as provider-level fallback (mock chunks should not be used for real provider requests)

---

## Dependencies

```
Phase 1 (Setup)
  ↓
Phase 2 (Foundational: US2 + base class)
  ↓
Phase 3 (US1: Provider impls + Generator refactor)
  ↓
Phase 4 (US3: Route changes)
  ↓
Phase 5 (Polish)
```

### Within Phases

**Phase 2**:
- T004, T005, T006: Can run in parallel (different concerns)
- T007: Depends on none, but T008/T009 need it → run T007 first or in parallel with T004-T006

**Phase 3**:
- T008 [P] and T009 [P]: Can run in parallel (different files)
- T010-T013: Sequential (same file, refactoring steps)

**Phase 4**:
- T014-T018: Sequential (same file, building on each other)

## Parallel Execution Examples

### Phase 2
```
Batch 1 (parallel):  T004 (intelliq.py capabilities)
                      T005 + T006 (connection_service.py)
                      T007 (base.py get_chunks)
```

### Phase 3
```
Batch 1 (parallel):  T008 (ragflow.py get_chunks)
                      T009 (intelliq.py get_chunks)

Batch 2 (sequential): T010 → T011 → T012 → T013 (ai_dataset_generator.py)
```

## Implementation Strategy

### MVP (User Story 1 + User Story 2)

**Minimum deliverable**: IntelliQ connections can generate AI datasets.

1. Complete Phase 1: Setup verification
2. Complete Phase 2: Capability declaration + base class method
3. Complete Phase 3: Provider chunk implementations + generator refactor
4. Complete Phase 4: Route changes
5. **STOP and VALIDATE**: Run quickstart.md VS-1 through VS-4

### Full Delivery

After MVP validated:
1. Complete Phase 5: Polish, regression testing, edge cases

---

## Summary

| Phase | Story | Tasks | Description |
|-------|-------|-------|-------------|
| Phase 1 | — | T001-T003 | Setup verification |
| Phase 2 | US2 (P1) | T004-T007 | Capability declaration + base contract |
| Phase 3 | US1 (P1) 🎯 | T008-T013 | Provider chunk impls + generator refactor |
| Phase 4 | US3 (P2) | T014-T018 | Route connection_id support |
| Phase 5 | — | T019-T023 | Polish & validation |
| **Total** | | **23 tasks** | 5 phases |

- **P1 (US1 + US2)**: 13 tasks (T004-T013 + US2 in Phase 2)
- **P2 (US3)**: 5 tasks (T014-T018)
- **Setup/Polish**: 5 tasks (T001-T003, T019-T023)