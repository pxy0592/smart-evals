# Quickstart: IntelliQ 支持 AI 数据集生成

**Feature**: 003-intelliq-ai-dataset-gen  
**Date**: 2026-08-22

## Prerequisites

- Smart Eval running (Docker: `docker compose up -d`, or dev: `python backend/app.py`)
- At least one IntelliQ connection configured and validated (status: `available`)
- IntelliQ connection has at least one knowledge base with documents
- At least one API configuration (LLM provider) set as default for generation
- Node.js 20+ for frontend (if using dev mode)

## Setup

```bash
# Start backend (dev mode)
cd backend && python app.py &

# Start frontend dev server (if not using Docker)
cd frontend && npm run dev
```

For Docker: `docker compose up -d` and access at `http://localhost:5003`.

## Validation Scenarios

### VS-1: IntelliQ connection declares AI generation capability

1. Call `GET /api/v1/evaluation/rag-connections`
2. **Verify**: IntelliQ connection's `capabilities.generate_dataset_from_knowledge_base` is `true`
3. **Verify**: RAGFlow connection's `capabilities.generate_dataset_from_knowledge_base` is also `true` (unchanged)

```bash
curl -s http://localhost:5003/api/v1/evaluation/rag-connections | python3 -m json.tool | grep -A5 '"provider": "intelliq"'
```

### VS-2: AI generation modal shows IntelliQ as selectable

1. Open browser to `http://localhost:5003/datasets`
2. Click "AI 智能生成数据集"
3. **Verify**: Connection dropdown shows IntelliQ connection (not disabled)
4. **Verify**: No warning "该连接不支持 AI 数据集生成" appears when selecting IntelliQ
5. **Verify**: RAGFlow connection is still shown (disabled if `enabled: false`)

### VS-3: Knowledge bases load for IntelliQ connection

1. In the AI generation modal, select an IntelliQ connection
2. **Verify**: Knowledge base dropdown loads the connection's KBs
3. **Verify**: No error toasts appear during loading

### VS-4: AI generation succeeds with IntelliQ

1. Select an IntelliQ connection with a populated knowledge base
2. Select a knowledge base, set sample count to 3, choose question types
3. Click "生成"
4. **Verify**: Success toast: "AI 数据集生成成功"
5. **Verify**: New dataset appears in the list with status "处理中" → "已完成"
6. **Verify**: Dataset sample count matches the requested value

```bash
# Check the generated dataset
curl -s http://localhost:5003/api/v1/evaluation/datasets | python3 -m json.tool | grep -A2 "AI Generated"
```

### VS-5: Missing connection_id returns error

```bash
curl -s -X POST http://localhost:5003/api/v1/evaluation/datasets/generate/ai \
  -H "Content-Type: application/json" \
  -d '{"kb_id": "some-kb", "sample_count": 5, "question_types": ["factual"]}'
```

**Verify**: Response is `400` with `{"error": "Connection ID is required"}`

### VS-6: Invalid connection_id returns error

```bash
curl -s -X POST http://localhost:5003/api/v1/evaluation/datasets/generate/ai \
  -H "Content-Type: application/json" \
  -d '{"kb_id": "some-kb", "connection_id": "nonexistent-id", "sample_count": 5}'
```

**Verify**: Response is `400` with `{"error": "Connection not found: nonexistent-id"}`

### VS-7: RAGFlow generation still works

1. Ensure RAGFlow connection is enabled (set `RAGFLOW_API_KEY` in `.env`)
2. In the AI generation modal, select RAGFlow connection
3. Select a knowledge base, set parameters, generate
4. **Verify**: Generation succeeds as before (regression test)

### VS-8: Empty knowledge base returns failure

1. Select an IntelliQ connection with an empty knowledge base (no documents)
2. Select the empty KB, generate
3. **Verify**: Dataset status becomes "failed" with error message about no chunks/content

## Expected Outcomes

| Scenario | Expected Result |
|----------|----------------|
| VS-1 | IntelliQ capabilities show `generate_dataset_from_knowledge_base: true` |
| VS-2 | IntelliQ selectable in dropdown, no capability warning |
| VS-3 | KB list loads for IntelliQ connection |
| VS-4 | Dataset generated successfully from IntelliQ KB |
| VS-5 | 400 error for missing connection_id |
| VS-6 | 400 error for invalid connection_id |
| VS-7 | RAGFlow generation unchanged (regression) |
| VS-8 | Graceful failure for empty KB |