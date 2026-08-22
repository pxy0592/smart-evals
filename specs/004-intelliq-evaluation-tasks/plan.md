# Implementation Plan: 允许向 IntelliQ 系统发起评测任务

**Branch**: `004-intelliq-evaluation-tasks` | **Date**: 2026-08-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-intelliq-evaluation-tasks/spec.md`

## Summary

Enable users to create and execute evaluation tasks against IntelliQ RAG systems. The backend infrastructure is already provider-agnostic — `create_evaluation_task()` accepts `rag_target` with `connection_id`, `run_evaluation_task()` resolves the provider and calls `evaluate_with_provider()`, and `IntelliQProvider.query_sample()` already implements SSE agent chat with answer/context extraction. This plan focuses on: (1) verifying the frontend form correctly handles IntelliQ connections, (2) ensuring error handling and edge cases are robust, (3) confirming end-to-end flow works for task creation, execution, progress tracking, and report generation.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.7 / React 18.3 (frontend)

**Primary Dependencies**: Flask 3.x, aiohttp (async IntelliQ SSE), RAGAS (evaluation scoring), Ant Design 5.24 (frontend UI)

**Storage**: SQLite via `data/evaluation.db`. Existing tables: `evaluation_tasks`, `evaluation_reports`, `sample_runs`. No schema changes needed.

**Testing**: pytest for backend (existing suite under `backend/tests/`). Manual end-to-end validation via Docker Compose.

**Target Platform**: Docker container (Linux), browser (modern evergreen)

**Project Type**: Full-stack web application (Flask REST API + React SPA)

**Performance Goals**: 10-sample evaluation task completes within 5 minutes (assuming IntelliQ API latency < 10s per sample). SSE parsing per sample < 100ms.

**Constraints**: 
- Must not break existing RAGFlow evaluation task flow
- IntelliQ SSE stream may be slow or contain partial data — aggregator must handle gracefully
- Task cancellation must clean up resources (provider connection, event loop)
- Revision check must prevent execution with stale connection credentials

**Scale/Scope**: ~3 files changed (backend: 0, frontend: 2-3); < 150 lines net new. Primarily verification and minor UI adjustments.

## Constitution Check

*No constitution file found at `.specify/memory/constitution.md`. Proceeding without gates.*

## Project Structure

### Documentation (this feature)

```text
specs/004-intelliq-evaluation-tasks/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── evaluation_db.py               # create_evaluation_task() + run_evaluation_task() — ALREADY provider-agnostic
├── services/
│   ├── evaluation_service.py      # evaluate_with_provider() — ALREADY provider-agnostic
│   └── rag_providers/
│       ├── intelliq.py            # query_sample() SSE — ALREADY implemented
│       └── sse.py                 # aggregate_intelliq_sse() — ALREADY implemented
└── tests/                         # (no new tests; existing contract tests cover provider-agnostic flow)

frontend/
└── src/
    ├── components/
    │   └── EvaluationTaskForm.tsx  # Verify IntelliQ connection handling; may need minor adjustments
    ├── pages/
    │   └── Tasks.tsx              # Verify task list displays IntelliQ provider info correctly
    └── services/
        └── evaluation.ts          # Already sends rag_target structure; verify no changes needed
```

**Structure Decision**: The evaluation task pipeline is already fully provider-agnostic. The `create_evaluation_task()` route has been designed to accept `rag_target` with `connection_id` for any provider since feature 002. `run_evaluation_task()` resolves the provider via `create_provider()` and calls `evaluate_with_provider()` which iterates samples through `provider.query_sample()`. For IntelliQ, this calls the SSE agent chat implementation added in feature 003. The frontend work is verification-focused: ensure the `EvaluationTaskForm` properly loads IntelliQ connections, agents, and knowledge bases, and that the task list displays provider information correctly.

## Complexity Tracking

*No violations to justify.*
