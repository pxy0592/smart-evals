---

description: "Implementation tasks for IntelliQ RAG system integration"
---

# Tasks: 新 RAG 系统接入

**Input**: Design documents from `/specs/001-rag-system-integration/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Backend unit, migration, contract, and integration tests are included because the plan requires deterministic validation of SSE completion, credential protection, SQLite migration, provider isolation, and legacy compatibility. Story tests must fail before their implementation tasks begin.

**Organization**: Tasks are grouped by user story so each increment can be implemented and validated with explicit dependencies.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it writes different files and has no dependency on an incomplete task in the same phase
- **[Story]**: Maps implementation tasks to User Story 1, 2, or 3
- Every task includes an exact file path

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the dependency, test, configuration, and module skeleton needed by all implementation phases.

- [X] T001 Add `cryptography` to production dependencies and create pytest/pytest-asyncio/jsonschema development dependencies in `backend/requirements.txt` and `backend/requirements-dev.txt`
- [X] T002 [P] Create the provider package skeleton and exports in `backend/services/rag_providers/__init__.py`, `backend/services/rag_providers/base.py`, `backend/services/rag_providers/factory.py`, `backend/services/rag_providers/ragflow.py`, `backend/services/rag_providers/intelliq.py`, `backend/services/rag_providers/sse.py`, and `backend/services/rag_providers/url_policy.py`
- [X] T003 [P] Add documented placeholders for `DATABASE_PATH`, `RAG_CREDENTIAL_ENCRYPTION_KEY`, `SMART_EVAL_ADMIN_TOKEN`, `RAG_PROVIDER_ALLOWED_HOSTS`, `EVALUATION_MAX_WORKERS`, and `EVALUATION_MAX_RETRIES` in `.env.example`
- [X] T004 [P] Create isolated temporary-database, temporary-directory, mock-upstream, and dataset-fixture helpers in `backend/tests/conftest.py` and `backend/tests/fixtures/datasets/README.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish persistence, credential, authorization, URL-security, provider, and compatibility foundations required by every user story.

**CRITICAL**: No user story implementation begins until this phase passes its focused tests.

### Foundational Tests

- [X] T005 [P] Add failing tests for configured database paths, legacy `/app/evaluation.db` detection, idempotent migrations, WAL mode, busy timeout, and rollback behavior in `backend/tests/integration/test_database_migrations.py`
- [X] T006 [P] Add failing encryption, missing-key fail-closed, decrypt-failure, fingerprint, and secret-redaction tests in `backend/tests/unit/test_credential_cipher.py`
- [X] T007 [P] Add failing URL normalization and SSRF tests for root URLs, `/api/v1`, docs/Swagger paths, duplicate versions, userinfo, query, fragment, redirect, loopback, link-local, and allowlisted private hosts in `backend/tests/unit/test_url_policy.py`
- [X] T008 [P] Add failing administrator-token tests for missing, empty, wrong, and valid Bearer values without logging the token in `backend/tests/unit/test_admin_auth.py`
- [X] T009 [P] Add failing normalized provider-model and RAGFlow legacy-mapping tests in `backend/tests/unit/test_rag_provider_base.py` and `backend/tests/integration/test_ragflow_legacy_flow.py`

### Foundational Implementation

- [X] T010 Implement authoritative `DATABASE_PATH`, encryption/admin-token/allowlist settings, aligned worker/retry environment names, and fail-closed production validation in `backend/config.py`
- [X] T011 Implement schema versioning, legacy database-path migration, WAL, busy timeout, bounded lock retry, and short transaction helpers in `backend/models/database.py`
- [X] T012 Extend SQLite migrations with `rag_connections`, `rag_connection_audit`, `evaluation_sample_runs`, provider/source columns, report aggregation columns, indexes, and legacy RAGFlow backfills in `backend/models/database.py`
- [X] T013 Implement connection, audit, provider-aware task, sample-run, and report persistence methods with final-attempt aggregation in `backend/db.py`
- [X] T014 [P] Implement Fernet-based API-key encryption, fingerprints, safe update semantics, and redaction helpers in `backend/services/credential_cipher.py`
- [X] T015 [P] Implement canonical service-root normalization, `/api/v1` construction, semantic docs/Swagger rejection, DNS/IP validation, redirect checks, and exact-host allowlisting in `backend/services/rag_providers/url_policy.py`
- [X] T016 [P] Implement deployment administrator Bearer validation and a reusable connection-write guard in `backend/utils/admin_auth.py`
- [X] T017 [P] Implement `RagProvider`, `KnowledgeBaseRef`, `AssistantRef`, `RagQueryResult`, `ProviderError`, capabilities, and source-snapshot types in `backend/services/rag_providers/base.py`
- [X] T018 Implement provider construction from synthetic `ragflow-default` or stored IntelliQ connection revisions in `backend/services/rag_providers/factory.py`
- [X] T019 Implement `RAGFlowProvider` resource normalization and isolated per-sample session/completion behavior while retaining Bearer authentication in `backend/services/rag_providers/ragflow.py`
- [X] T020 Implement provider-safe error categories, response envelopes, and structured redacted logging fields in `backend/utils/shared_utils.py`
- [X] T021 Integrate migration startup, stale-running-task interruption recovery, SQLite/data-directory readiness, and single-process task ownership checks in `backend/app.py` and `backend/evaluation_db.py`
- [X] T022 Run the blocking foundation suite in `backend/tests/unit/` and `backend/tests/integration/test_database_migrations.py` and resolve all failures before starting User Story phases

**Checkpoint**: Database persistence, secure configuration, provider abstraction, and RAGFlow compatibility foundations are ready.

---

## Phase 3: User Story 1 - 配置并发现 RAG 资源 (Priority: P1) MVP

**Goal**: An administrator can securely configure/test one IntelliQ connection and users can discover normalized knowledge bases and Assistants with authoritative all/selected/none modes.

**Independent Test**: With a mock IntelliQ server and a valid deployment admin token, create and test the connection, fetch knowledge bases and Assistants, verify disabled/unknown-mode Assistants are not selectable, and confirm no credential appears in responses, logs, audits, or database projections.

### Tests for User Story 1

- [X] T023 [P] [US1] Add failing OpenAPI contract tests for connection list/create/get/update/enable/disable/test, 401 handling, API-key omission, and single-IntelliQ conflict behavior in `backend/tests/contract/test_rag_connections_api.py`
- [X] T024 [P] [US1] Add failing contract tests for normalized knowledge-base and Assistant lists, pagination/search, disabled Agent IDs, unknown modes, and connection scoping in `backend/tests/contract/test_resources_api.py`
- [X] T025 [P] [US1] Add failing IntelliQ client tests for `X-API-Key`, `GET /api/v1/knowledge-bases`, `GET /api/v1/agents`, service-root equivalence, and sanitized error mapping in `backend/tests/unit/test_intelliq_resources.py`
- [X] T026 [P] [US1] Add failing integration tests for admin-token-before-upstream ordering, connection revision/audit updates, and zero mock calls on unauthorized requests in `backend/tests/integration/test_intelliq_connection_flow.py`

### Implementation for User Story 1

- [X] T027 [US1] Implement stored IntelliQ plus synthetic RAGFlow connection CRUD, revisioning, encrypted-key preservation, audit records, and capabilities in `backend/services/rag_connection_service.py`
- [X] T028 [US1] Implement IntelliQ connection validation, knowledge-base normalization, Agent normalization, disabled IDs, allowed knowledge bases, and all/selected/none mode mapping in `backend/services/rag_providers/intelliq.py`
- [X] T029 [US1] Add administrator-protected connection list/create/get/update/enable/disable/test routes matching the OpenAPI contract in `backend/evaluation_db.py`
- [X] T030 [US1] Add provider-neutral knowledge-base and Assistant discovery routes with search, limits, sanitized stale/error states, and no generic upstream proxy exposure in `backend/evaluation_db.py`
- [X] T031 [US1] Add `RagConnectionSummary`, capabilities, `KnowledgeBaseRef`, `AssistantRef`, connection API, and resource-discovery API types in `frontend/src/services/evaluation.ts`
- [X] T032 [US1] Implement the API-key-safe IntelliQ connection editor, admin-token submission, validation status, loading, empty, and inline error states in `frontend/src/components/RagConnectionForm.tsx`
- [X] T033 [US1] Add a separate “RAG 系统” settings tab without changing evaluator-LLM configuration behavior in `frontend/src/pages/Settings.tsx`
- [X] T034 [US1] Execute `backend/tests/contract/test_rag_connections_api.py`, `backend/tests/contract/test_resources_api.py`, and `backend/tests/integration/test_intelliq_connection_flow.py`, then verify the Settings flow with the mock upstream using `specs/001-rag-system-integration/quickstart.md`

**Checkpoint**: User Story 1 is independently deployable as the secure connection and resource-discovery MVP.

---

## Phase 4: User Story 2 - 使用新系统创建评测任务 (Priority: P1)

**Goal**: Users can upload any supported evaluation dataset, create an IntelliQ task that obeys the selected Agent mode, execute isolated SSE sample calls, and observe accurate progress and partial-failure warnings.

**Independent Test**: Upload each of the five supported formats, create selected/all/none tasks against a mock IntelliQ server, verify per-attempt session isolation and SSE completion, and confirm partial failures score only completed samples while all-failed tasks produce no final report.

### Tests for User Story 2

- [X] T035 [P] [US2] Add failing normalization tests for JSON, JSONL, CSV, XLSX, XLS, exactly 10,485,760 bytes, oversized files, TXT rejection, malformed rows, and temporary-file cleanup in `backend/tests/unit/test_dataset_normalization.py`
- [X] T036 [P] [US2] Add failing SSE parser tests for split UTF-8/JSON chunks, multiple events per chunk, comments, heartbeats, references, delta answers, diagnostics, unknown events, error events, missing `done`, empty completed answers, and stream cancellation in `backend/tests/unit/test_intelliq_sse.py`
- [X] T037 [P] [US2] Add failing retry/session/scoring tests for unique session IDs, no retry after business events, 401/403 no-retry, 429/5xx pre-event retry, partial-answer isolation, and `score_eligible` gates in `backend/tests/unit/test_scoring_eligibility.py`
- [X] T038 [P] [US2] Add failing task API contract tests for legacy `chat_id`, provider-aware `rag_target`, selected/all/none rules, unknown/changed modes, cross-connection resources, and incomplete datasets in `backend/tests/contract/test_tasks_api.py`
- [X] T039 [P] [US2] Add failing end-to-end mock IntelliQ tests for upload, task execution, sample-run persistence, cancellation, partial failure, all failure, and RAGFlow non-regression in `backend/tests/integration/test_intelliq_task_flow.py`

### Implementation for User Story 2

- [X] T040 [US2] Implement five-format parsing, 10 MiB pre-parse enforcement, canonical sample-field mapping, normalized JSON output, invalid-sample reporting, and cleanup in `backend/services/dataset_manager.py`
- [X] T041 [US2] Update dataset upload to use the normalization service, return 413/415/422 correctly, and mark completed only after normalized output is readable in `backend/evaluation_db.py`
- [X] T042 [P] [US2] Implement incremental SSE line parsing, reference deduplication, answer-only aggregation, diagnostic event counts, explicit completion, and protocol failures in `backend/services/rag_providers/sse.py`
- [X] T043 [US2] Implement task-scoped IntelliQ `query_sample()` with `X-API-Key`, unique session per attempt, all/selected/none payloads, bounded timeouts, safe retry, cancellation, and normalized results in `backend/services/rag_providers/intelliq.py`
- [X] T044 [US2] Implement sample-run create/update/final-attempt query, throttled progress, success/failure counts, and cancellation checks in `backend/db.py`
- [X] T045 [US2] Refactor RAG response preparation to use a task-scoped provider and include only `score_eligible=true` samples in RAGAS input in `backend/services/evaluation_service.py`
- [X] T046 [US2] Extend task creation and execution with server-authoritative Agent mode validation, resource snapshots, connection revision checks, legacy payload mapping, partial-success outcome, warning projection, and all-failed finalization in `backend/evaluation_db.py`
- [X] T047 [US2] Return provider, connection, Agent, knowledge-base mode, explicit resources, dataset name, outcome, warnings, and sample diagnostics from task list/detail managers in `backend/db.py`
- [X] T048 [US2] Add provider-aware task, `RagTarget`, outcome, warning, dataset normalization, and task-filter types and calls in `frontend/src/services/evaluation.ts`
- [X] T049 [US2] Implement a reusable provider-aware task form that clears stale selections and renders a knowledge-base multi-select only for selected mode in `frontend/src/components/EvaluationTaskForm.tsx`
- [X] T050 [US2] Replace the Tasks page’s direct RAGFlow calls and duplicate form with `EvaluationTaskForm`, show provider/source/outcome/warnings, and remove `// @ts-nocheck` in `frontend/src/pages/Tasks.tsx`
- [X] T051 [US2] Integrate normalized uploads and `EvaluationTaskForm` into Datasets, enforce exact format/size copy, gate AI generation by provider capabilities, and remove `// @ts-nocheck` in `frontend/src/pages/Datasets.tsx`
- [X] T052 [US2] Run the US2 unit/contract/integration suites, `npm run typecheck`, and `npm run build`, then execute the selected/all/none, partial-failure, all-failed, and five-format scenarios in `specs/001-rag-system-integration/quickstart.md`

**Checkpoint**: User Stories 1 and 2 provide a complete IntelliQ evaluation task flow while old RAGFlow payloads remain functional.

---

## Phase 5: User Story 3 - 查看新系统评测报告 (Priority: P2)

**Goal**: Users can filter and open final IntelliQ reports with immutable source snapshots, successful/failed sample counts, references, warning details, and no misleading report for all-failed tasks.

**Independent Test**: Complete a mixed-result IntelliQ task, query reports by provider/connection/Assistant/knowledge base/date, open detail after disabling the connection, and verify source snapshots, denominator counts, failed samples, and a 409/no-report response for an all-failed task.

### Tests for User Story 3

- [X] T053 [P] [US3] Add failing report persistence tests for source snapshots, Agent mode, final-attempt counts, success rate, warning payloads, references, and no report row when zero samples are scoreable in `backend/tests/integration/test_report_persistence.py`
- [X] T054 [P] [US3] Add failing report API contract tests for provider/connection/Assistant/knowledge-base/date filters, pagination, legacy fields, detail shape, disabled connections, and 409 no-final-report behavior in `backend/tests/contract/test_reports_api.py`
- [X] T055 [P] [US3] Add failing integration tests for partially succeeded and all-failed report journeys plus historical readability after connection changes in `backend/tests/integration/test_intelliq_reports_flow.py`

### Implementation for User Story 3

- [X] T056 [US3] Extend report persistence and queries with source snapshots, Agent mode, total/scored/failed counts, success rate, warning payload, provider filters, and final-attempt sample details in `backend/db.py`
- [X] T057 [US3] Update report finalization, list, detail, filter validation, legacy `kb_name` projection, and 409 behavior for tasks without a final report in `backend/evaluation_db.py`
- [X] T058 [US3] Add provider/source/filter/warning/reference/report-detail response types and paginated list handling in `frontend/src/services/evaluation.ts`
- [X] T059 [US3] Update report filters, source columns, partial-failure warning, sample completion/error/reference detail, `taskId` deep-link handling, and remove `// @ts-nocheck` in `frontend/src/pages/Reports.tsx`
- [X] T060 [US3] Update recent-task/report navigation to display source snapshots instead of task names or raw IDs in `frontend/src/pages/Dashboard.tsx`
- [X] T061 [US3] Run the US3 contract/integration suites and verify filtered, disabled-connection, partial-failure, all-failed, and deep-link scenarios in `specs/001-rag-system-integration/quickstart.md`

**Checkpoint**: All three user stories are independently testable and the full evaluation/report loop is complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Complete security, deployment, documentation, compatibility, and release validation shared by all stories.

- [X] T062 [P] Add regression tests that scan serialized connections, errors, logs, tasks, reports, backups, and exports for API keys and administrator tokens in `backend/tests/unit/test_secret_redaction.py`
- [X] T063 [P] Update container/database persistence, required secrets, readiness behavior, and single-process ownership documentation/configuration in `Dockerfile` and `docker-compose.yml`
- [X] T064 [P] Prevent routine backups from bundling credential/admin encryption secrets with the encrypted database, enforce restrictive archive permissions, and fail updates on backup errors in `backup.sh` and `update.sh`
- [X] T065 [P] Update operator setup, IntelliQ connection rules, five-format dataset contract, admin-token usage, and mock-versus-live validation boundaries in `README.md`, `QUICKSTART.md`, and `CHANGELOG.md`
- [X] T066 Remove any remaining core-page `// @ts-nocheck`, resolve provider-aware TypeScript errors, and verify no page directly imports `ragflowClient` in `frontend/src/pages/Datasets.tsx`, `frontend/src/pages/Tasks.tsx`, `frontend/src/pages/Reports.tsx`, and `frontend/src/services/evaluation.ts`
- [X] T067 Run `python -m pytest backend/tests -q`, `npm run typecheck`, `npm run build`, `bash -n *.sh`, `docker-compose config`, and `./check-before-publish.sh` against the implemented files in `backend/`, `frontend/`, and repository root
- [X] T068 Execute the complete mock-provider and container-rebuild validation guide and record command results, skipped checks, and persistence evidence in `specs/001-rag-system-integration/validation-results.md`
- [X] T069 Perform an optional live IntelliQ smoke test and mandatory RAGFlow compatibility regression without storing real credentials, recording the evidence boundary in `specs/001-rag-system-integration/validation-results.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies; T002, T003, and T004 can run in parallel after T001 is understood.
- **Phase 2 Foundational**: Depends on Setup and blocks every user story. Tests T005-T009 should be written first; implementation T010-T021 follows their dependency order; T022 is the gate.
- **Phase 3 User Story 1**: Depends on Phase 2. This is the MVP and establishes the configured connection/resource boundary used by later live flows.
- **Phase 4 User Story 2**: Depends on Phase 2 and uses the US1 connection/resource APIs for the integrated journey. Its backend tests can use fixtures before US1 UI completion, but production integration depends on US1.
- **Phase 5 User Story 3**: Depends on US2 task/sample finalization because reports consume completed task data.
- **Phase 6 Polish**: Depends on all stories selected for release.

### User Story Dependencies

```text
Foundation
  └── US1: Configure and discover RAG resources (MVP)
        └── US2: Upload datasets and run evaluation tasks
              └── US3: Retrieve and inspect reports
```

- **US1**: Independently testable with a mock provider and no dataset/task/report implementation.
- **US2**: Independently testable given a preconfigured connection fixture; integrated delivery depends on US1 resource selection.
- **US3**: Independently testable using seeded task/sample data; integrated delivery depends on US2 finalization semantics.

### Within Each Phase

- Write the listed tests before implementing the behavior they cover and confirm that they fail for the expected reason.
- Complete schema/migration work before managers and services that persist new fields.
- Complete provider base/url/credential foundations before concrete adapters.
- Complete backend contracts before wiring frontend pages.
- Keep old `chat_id` and legacy report fields until all compatibility tests pass.

### Parallel Opportunities

- T005-T009 are parallel test-authoring tasks.
- T014-T017 are parallel foundational module implementations after configuration/schema interfaces are fixed.
- T023-T026 are parallel US1 test tasks.
- T031 and T032 can proceed in parallel after the US1 endpoint shapes are fixed; T033 depends on both.
- T035-T039 are parallel US2 test tasks.
- T040 and T042 can proceed in parallel; T043 depends on T042, while T041 depends on T040.
- T048 and T049 can proceed in parallel after backend task contracts stabilize; T050 and T051 depend on T049.
- T053-T055 are parallel US3 test tasks.
- T058 can proceed in parallel with backend report implementation T056-T057 once contract shapes are frozen.
- T062-T065 are parallel cross-cutting tasks after story behavior stabilizes.

---

## Parallel Example: User Story 1

```text
Task T023: Write connection API contract tests in backend/tests/contract/test_rag_connections_api.py
Task T024: Write resource API contract tests in backend/tests/contract/test_resources_api.py
Task T025: Write IntelliQ resource client tests in backend/tests/unit/test_intelliq_resources.py
Task T026: Write connection integration tests in backend/tests/integration/test_intelliq_connection_flow.py
```

## Parallel Example: User Story 2

```text
Task T035: Write dataset normalization tests in backend/tests/unit/test_dataset_normalization.py
Task T036: Write SSE parser tests in backend/tests/unit/test_intelliq_sse.py
Task T037: Write retry/session/scoring tests in backend/tests/unit/test_scoring_eligibility.py
Task T038: Write task API contract tests in backend/tests/contract/test_tasks_api.py
Task T039: Write IntelliQ task integration tests in backend/tests/integration/test_intelliq_task_flow.py
```

## Parallel Example: User Story 3

```text
Task T053: Write report persistence tests in backend/tests/integration/test_report_persistence.py
Task T054: Write report contract tests in backend/tests/contract/test_reports_api.py
Task T055: Write report journey tests in backend/tests/integration/test_intelliq_reports_flow.py
```

---

## Implementation Strategy

### MVP First: User Story 1

1. Complete T001-T004.
2. Complete and pass T005-T022.
3. Complete T023-T034.
4. Stop and validate secure connection configuration and resource discovery independently.
5. Demo the MVP without claiming task/report support.

### Incremental Delivery

1. **Foundation ready**: secure persistence, provider boundary, and RAGFlow compatibility.
2. **US1 MVP**: configure/test IntelliQ and discover resources.
3. **US2 increment**: normalize datasets and execute provider-aware tasks.
4. **US3 increment**: expose traceable reports and failure details.
5. **Release hardening**: secrets, backups, container persistence, docs, and full validation.

### Parallel Team Strategy

After T022 passes:

- Developer A owns US1 connection/resource backend and Settings integration.
- Developer B starts US2 dataset/SSE tests and normalization with connection fixtures.
- Developer C prepares US3 report contract tests and seeded persistence fixtures after US2 final shapes are frozen.

---

## Notes

- `[P]` tasks write different files and can be executed concurrently only after their stated prerequisite interfaces are stable.
- `[US1]`, `[US2]`, and `[US3]` map directly to the prioritized stories in `spec.md`.
- `backend/evaluation_db.py`, `backend/db.py`, and `frontend/src/services/evaluation.ts` are shared hotspots; tasks touching them are intentionally ordered rather than marked parallel.
- `backend/api_optimized.py` and `backend/services/unified.py` are not active runtime paths and are excluded from implementation tasks.
- Real IntelliQ validation is optional and must never be substituted for deterministic mock contract tests.
- Do not commit `.env`, API keys, administrator tokens, runtime databases, uploaded datasets, generated reports, or validation artifacts containing secrets.
