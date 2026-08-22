# Quickstart: 数据集页面按需访问 RAG 系统

**Feature**: 002-dataset-provider-flow  
**Date**: 2026-08-22

## Prerequisites

- Smart Eval backend running (dev: `python backend/app.py`, or Docker: `docker-compose up`)
- At least one RAG system connection configured (IntelliQ or RAGFlow)
- At least one dataset uploaded to Smart Eval
- Node.js 20+ and npm dependencies installed (`cd frontend && npm ci`)

## Setup

```bash
# Start backend
cd backend && python app.py &

# Start frontend dev server
cd frontend && npm run dev
```

Navigate to `http://localhost:5173` and go to the Datasets page.

## Validation Scenarios

### VS-1: Page load is RAG-free

1. Open browser DevTools Network tab
2. Navigate to the Datasets page
3. **Verify**: Only `GET /evaluation/datasets` appears in the network log
4. **Verify**: No requests to `/evaluation/rag-connections`, `/evaluation/knowledgebases`, or any RAG system endpoint

### VS-2: Dataset upload works without RAG

1. Stop all RAG system services (or disconnect them)
2. Upload a valid CSV/JSON dataset
3. **Verify**: Upload succeeds, dataset appears in the list
4. **Verify**: No RAG-related errors appear in the UI or console

### VS-3: Task creation loads connections on-demand

1. Click "创建评测" on any dataset row
2. **Verify**: Modal opens with skeleton placeholders for the connection dropdown
3. **Verify**: Within 2 seconds, skeleton is replaced by actual connection list
4. **Verify**: Network tab shows `GET /evaluation/rag-connections` was called only after clicking

### VS-4: Task creation loads per-connection resources

1. In the task creation modal, select a connection
2. **Verify**: Assistant dropdown loads with that connection's assistants
3. **Verify**: Network tab shows `GET /evaluation/rag-connections/{id}/assistants`
4. Select an assistant with `knowledge_base_selection_mode === 'selected'`
5. **Verify**: KB selector appears and loads KBs for that connection
6. Fill in remaining fields and submit
7. **Verify**: Task is created successfully; check the network request body includes `rag_target`

### VS-5: Connection switch clears stale state

1. Open task creation modal, select Connection A, then select an assistant
2. Switch to Connection B
3. **Verify**: Assistant dropdown resets (no Connection A assistant remains)
4. **Verify**: KB selector is cleared
5. **Verify**: Network tab shows a new assistant fetch for Connection B, and the previous request was aborted

### VS-6: AI generation requires capable connection

1. Click "AI 智能生成数据集"
2. **Verify**: Each connection shows whether it supports AI generation (capability badge)
3. Select a connection that does NOT support AI generation
4. **Verify**: KB selector and submit button are disabled; reason is shown
5. Select a connection that DOES support AI generation
6. **Verify**: KB selector loads that connection's knowledge bases
7. Select a KB, set sample count, choose question types, submit
8. **Verify**: Generation request succeeds; network body includes `connection_id`

### VS-7: Modal close cleans up state

1. Open task creation modal, select a connection and assistant
2. Close the modal
3. Re-open the modal (on the same or different dataset)
4. **Verify**: Previous connection/assistant selections are NOT retained
5. **Verify**: Connections are loaded fresh from the API

### VS-8: RAG system failure doesn't break dataset operations

1. Make all RAG connections unavailable (stop services or use invalid URLs)
2. **Verify**: Dataset list loads normally
3. **Verify**: Upload, preview, and delete still work
4. Open task creation modal
5. **Verify**: Modal shows error state with retry button for connection list
6. Click retry — error persists
7. **Verify**: Closing the modal and returning to dataset list works fine

## Expected Outcomes

- 0 RAG API calls on dataset page load
- Dataset CRUD operations independent of RAG availability
- Task creation and AI generation fully connection-scoped
- No stale data from previous connections
- No implicit fallback to default RAGFlow