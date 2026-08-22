# Implementation Plan: IntelliQ 支持 AI 数据集生成

**Branch**: `003-intelliq-ai-dataset-gen` | **Date**: 2026-08-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-intelliq-ai-dataset-gen/spec.md`

## Summary

Enable IntelliQ RAG connections to support AI dataset generation. Currently, only RAGFlow connections can generate AI datasets — the capability flag is hardcoded to `false` for all IntelliQ connections, and the `AIDatasetGenerator` is hardwired to RAGFlow's HTTP API. This plan refactors the generation pipeline to be provider-agnostic: capabilities are sourced from the actual provider, chunk retrieval is provider-aware, and the backend route accepts a `connection_id` parameter.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.7 / React 18.3 (frontend)

**Primary Dependencies**: Flask 3.x, aiohttp (async providers), requests (sync generator), langchain_openai (LLM calls), Ant Design 5.24

**Storage**: No schema changes. Existing `rag_connections` table stores provider credentials.

**Testing**: Existing test suite under `backend/tests/`. Unit tests for refactored generator; contract tests for API route changes.

**Target Platform**: Docker container (Linux), browser (modern evergreen)

**Project Type**: Full-stack web application (Flask REST API + React SPA)

**Performance Goals**: Chunk retrieval from IntelliQ within 5s (same as RAGFlow); LLM generation per QA pair within 10s

**Constraints**: 
- Must not break existing RAGFlow AI generation flow
- Sync/async boundary: generator runs in background thread (sync); providers are async (aiohttp)
- IntelliQ API chunk retrieval endpoint must be verified

**Scale/Scope**: ~5 files changed (backend: 4, frontend: 0-1); < 200 lines net new

## Constitution Check

*No constitution file found at `.specify/memory/constitution.md`. Proceeding without gates.*

## Project Structure

### Documentation (this feature)

```text
specs/003-intelliq-ai-dataset-gen/
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
├── services/
│   ├── ai_dataset_generator.py    # Primary refactor target
│   ├── rag_connection_service.py  # Fix hardcoded capabilities
│   └── rag_providers/
│       ├── base.py                # (unchanged, referenced)
│       ├── factory.py             # (unchanged, referenced)
│       ├── intelliq.py            # Add capability + chunk retrieval
│       └── ragflow.py             # Add chunk retrieval method
└── evaluation_db.py               # Backend route: accept connection_id

frontend/
└── src/
    ├── pages/
    │   └── Datasets.tsx           # (already sends connection_id, minor verify)
    └── services/
        └── evaluation.ts          # (already has connection_id param, no change)
```

**Structure Decision**: Backend-heavy change. The frontend already sends `connection_id` in the AI generation request (implemented in feature 002). The work is in: (1) fixing capability declarations, (2) refactoring the generator to be provider-aware, (3) wiring the backend route to resolve connections.

## Complexity Tracking

*No violations to justify.*