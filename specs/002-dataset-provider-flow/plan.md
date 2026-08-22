# Implementation Plan: 数据集页面按需访问 RAG 系统

**Branch**: `002-dataset-provider-flow` | **Date**: 2026-08-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-dataset-provider-flow/spec.md`

## Summary

Refactor the Datasets page to load RAG system resources (connections, assistants, knowledge bases) only on explicit user action — not on page load. Task creation and AI dataset generation must require the user to select a specific RAG connection before fetching any of that connection's resources. This is a pure frontend session-flow change; all needed backend APIs already exist.

## Technical Context

**Language/Version**: TypeScript 5.7, React 18.3

**Primary Dependencies**: Ant Design 5.24, React Router 6.30, Axios 1.8

**Storage**: N/A (no new storage; connection/resource data fetched on-demand from backend)

**Testing**: N/A (no existing frontend test suite; manual verification per quickstart.md)

**Target Platform**: Browser (modern evergreen browsers)

**Project Type**: React SPA (single-page application), frontend-only change

**Performance Goals**: Connection list loads within 2s of modal open; skeleton placeholders shown during load

**Constraints**: No new backend endpoints; no changes to dataset file format rules; no changes to metric evaluation logic

**Scale/Scope**: 1 page component (`Datasets.tsx`) + 2 modal forms (task creation, AI generation); < 500 lines changed

## Constitution Check

*No constitution file found at `.specify/memory/constitution.md`. Proceeding without gates.*

## Project Structure

### Documentation (this feature)

```text
specs/002-dataset-provider-flow/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (speckit-tasks)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── pages/
│   │   └── Datasets.tsx          # Primary change target
│   ├── components/
│   │   └── EvaluationTaskForm.tsx # Already connection-aware; minor updates
│   └── services/
│       └── evaluation.ts          # Already has ragConnectionApi, ragResourceApi
```

**Structure Decision**: Single-page frontend change. `Datasets.tsx` is the sole orchestrator; `EvaluationTaskForm.tsx` is already connection-aware and needs only minor wiring adjustments. Backend services require no changes.

## Complexity Tracking

*No violations to justify.*
