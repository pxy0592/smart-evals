# Implementation Plan: IntelliQ 评测前自动创建会话

**Branch**: `005-intelliq-session-creation` | **Date**: 2026-08-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-intelliq-session-creation/spec.md`

## Summary

IntelliQ agent-chat API requires a pre-created session. Currently `IntelliQProvider.query_sample()` generates a random UUID as `session_id` and sends it directly to `POST /api/v1/agent-chat/{session_id}`, which always fails with `code:1003 "Session not found"`. The fix adds a `POST /api/v1/sessions` call before the agent-chat call, and a `DELETE /api/v1/sessions/batch` cleanup after the evaluation task completes.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Flask 3.x, aiohttp (async HTTP client), SQLite

**Storage**: SQLite (`data/evaluation.db`) — no schema changes needed

**Testing**: pytest (backend/tests/), manual curl verification for IntelliQ API

**Target Platform**: Linux server (Docker Compose)

**Project Type**: Web application (Flask backend + React frontend)

**Performance Goals**: Session creation ~100ms, not in hot path (1 call per sample)

**Constraints**: Max 300s total timeout per sample (existing aiohttp timeout), must not break existing RAGFlow provider

**Scale/Scope**: 1-2 files changed, ~50 lines of code, no database migrations

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution is a placeholder template with no defined principles. No gates to evaluate.

## Project Structure

### Documentation (this feature)

```text
specs/005-intelliq-session-creation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output ($speckit-tasks command)
```

### Source Code (repository root)

```text
backend/
├── services/
│   ├── rag_providers/
│   │   └── intelliq.py          # PRIMARY: Add session creation & cleanup
│   └── evaluation_service.py    # POSSIBLE: Add session cleanup hook
└── tests/
    ├── unit/
    │   └── test_intelliq_provider.py
    └── integration/
        └── test_evaluation_intelliq.py
```
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
