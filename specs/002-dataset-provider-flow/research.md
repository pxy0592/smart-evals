# Research: 数据集页面按需访问 RAG 系统

**Feature**: 002-dataset-provider-flow  
**Date**: 2026-08-22

## Decision 1: Use existing `ragConnectionApi` and `ragResourceApi` directly from Datasets.tsx

**Decision**: Wire `Datasets.tsx` to call `ragConnectionApi.list()` and `ragResourceApi.listAssistants()` / `ragResourceApi.listKnowledgeBases()` on-demand, bypassing the legacy `chatApi` and `knowledgeBaseApi` facades.

**Rationale**:
- The unified API layer (`ragConnectionApi`, `ragResourceApi`) already exists and is provider-neutral.
- The legacy `chatApi` hardcodes RAGFlow as the only provider, which violates FR-005/FR-014 (no implicit fallback to RAGFlow).
- `knowledgeBaseApi.list()` fetches all knowledge bases eagerly — this is exactly the preload behavior we must remove per FR-001/FR-015.
- `EvaluationTaskForm.tsx` already uses the unified APIs, proving the pattern works.

**Alternatives considered**:
- Keep `chatApi` and patch it to be lazy — rejected because it's hardcoded to RAGFlow and would need a full rewrite anyway.
- Create a new `sessionApi` abstraction — rejected as over-engineering; the existing APIs are sufficient.

## Decision 2: Session-scoped state management via local hooks in Datasets.tsx

**Decision**: Use React `useState` + `useEffect` within `Datasets.tsx` for each modal's session state. No global state, no Redux/Zustand.

**Rationale**:
- Each modal's state is ephemeral and scoped to its lifecycle (FR-022).
- The existing `EvaluationTaskForm` pattern already uses local state successfully.
- Global state would risk cross-contamination between sessions (violates FR-022/FR-023).
- AbortController on unmount handles stale response prevention (FR-023).

**Alternatives considered**:
- Redux/Zustand store — rejected as overkill for two modals; increases risk of state leakage.
- React Context per modal — rejected as equivalent to local state but more complex.

## Decision 3: Stale response prevention via AbortController

**Decision**: Use `AbortController` attached to each modal session. Cancel in-flight requests on: connection switch, assistant switch, modal close.

**Rationale**:
- FR-023 requires preventing stale responses from overwriting current state.
- FR-019 requires ignoring late responses from old connections.
- AbortController is the standard browser API for this; Axios supports it via `signal`.
- Simpler than request-ID-based deduplication (which would still waste bandwidth).

**Alternatives considered**:
- Request-ID tracking with response comparison — rejected as more complex, still wastes bandwidth.
- Debounce/throttle — rejected as it only delays but doesn't prevent stale overwrites.

## Decision 4: AI generation modal uses same connection picker pattern as task form

**Decision**: The AI generation modal reuses the same connection → resource loading pattern: select connection → load knowledge bases → submit with connection identity.

**Rationale**:
- Both modals follow the same "user selects connection → system loads that connection's resources" flow.
- The `capabilities.generate_dataset_from_knowledge_base` field already exists on connections (confirmed in clarifications).
- DRY: the connection picker, loading states, and error handling can be shared or patterned identically.

**Alternatives considered**:
- Separate AI generation service with its own connection discovery — rejected; reuses existing APIs.
- Pre-filter connections by capability on load — rejected; the spec says to show all connections and indicate which support generation (FR-016).

## Decision 5: Skeleton loading for connection list

**Decision**: Use Ant Design `Skeleton` component inside the modal while connections load.

**Rationale**:
- SC-011 requires skeleton placeholders, not blank modals.
- Ant Design's `Skeleton` is already available in the dependency tree.
- Simple to implement: conditionally render `<Skeleton>` vs `<Select>` based on loading state.

**Alternatives considered**:
- `Spin` (full-page spinner) — rejected as it blocks the modal entirely, which is worse UX.
- Custom skeleton — rejected as unnecessary when Ant Design provides one.