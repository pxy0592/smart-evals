# API Contract: AI Dataset Generation

**Feature**: 003-intelliq-ai-dataset-gen  
**Date**: 2026-08-22

## POST /api/v1/evaluation/datasets/generate/ai

Initiates AI dataset generation from a knowledge base. The request is processed asynchronously; the response returns immediately with a new dataset in "processing" status.

### Request

```json
{
  "kb_id": "string (required) - Knowledge base ID within the selected connection",
  "connection_id": "string (required) - RAG connection ID (e.g., a UUID for IntelliQ, or 'ragflow-default' for RAGFlow)",
  "sample_count": "int (optional, default 10, range 1-100) - Number of QA pairs to generate",
  "question_types": ["string[] (optional, default ['factual','analytical']) - Question type categories"]
}
```

**Valid question_types**: `factual`, `analytical`, `application`, `comparison`, `explanation`

### Response (201 Created)

```json
{
  "id": "uuid",
  "name": "AI Generated Dataset - 20260822_143000",
  "description": "AI generated dataset from knowledge base {kb_id} with {sample_count} samples",
  "file_name": "ai_generated.json",
  "file_type": ".json",
  "file_size": 0,
  "storage_path": "tmp/datasets/{uuid}.json",
  "num_samples": 0,
  "has_reference": false,
  "has_contexts": false,
  "sample_fields": [],
  "status": "processing",
  "progress": 0,
  "created_by": "ai-generator",
  "created_at": "2026-08-22T14:30:00"
}
```

### Error Responses

| Status | Condition | Body |
|--------|-----------|------|
| 400 | `kb_id` missing | `{"error": "Knowledge base ID is required"}` |
| 400 | `connection_id` missing | `{"error": "Connection ID is required"}` |
| 400 | `connection_id` invalid/not found | `{"error": "Connection not found: {id}"}` |
| 400 | `sample_count` < 1 or > 100 | `{"error": "Sample count must be between 1 and 100"}` |
| 400 | Connection provider does not support `generate_dataset_from_knowledge_base` | `{"error": "Connection does not support AI dataset generation"}` |
| 500 | Internal error | `{"error": "Failed to generate AI dataset"}` |

### Async Completion

The background thread:
1. Resolves the connection from `connection_id` via `RagConnectionService`
2. Creates the provider via `create_provider(connection, api_key)`
3. Calls `provider.get_chunks(kb_id, limit)` to retrieve content
4. Calls `AIDatasetGenerator.generate_dataset_from_kb()` with the provider
5. Writes the generated JSON to `tmp/datasets/{dataset_id}.json`
6. Updates dataset status to `"completed"` (success) or `"failed"` (error)

### Backward Compatibility

- **Before**: `connection_id` was optional and ignored (always used RAGFlow)
- **After**: `connection_id` is required. Existing callers must be updated to include it.
- The frontend already sends `connection_id` (implemented in feature 002).

## Provider Contract: RagProvider.get_chunks()

```python
def get_chunks(self, kb_id: str, limit: int) -> list[dict[str, Any]]:
    """Retrieve knowledge base content chunks for AI dataset generation.

    Args:
        kb_id: Knowledge base identifier (provider-scoped).
        limit: Maximum number of chunks to return.

    Returns:
        List of chunk dicts, each with:
        - id: str (unique chunk identifier)
        - content: str (text content, required)
        - doc_name: str (source document name)
        - doc_id: str (source document identifier)
        - dataset_id: str (knowledge base identifier)
        - page_number: int (optional)
        - positions: list (optional)
    """
```

### RAGFlow Implementation

Wraps existing `AIDatasetGenerator._get_chunks_from_dataset()` logic:
- `GET /api/v1/datasets/{kb_id}/documents` → list documents
- `GET /api/v1/datasets/{kb_id}/documents/{doc_id}/chunks` → get chunks per document
- Uses `self.api_key` for Bearer auth

### IntelliQ Implementation

- `GET /api/v1/knowledge-bases/{kb_id}/documents` → list documents
- `GET /api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/chunks` → get chunks per document
- Uses `self.api_key` for X-API-Key auth
- Uses `asyncio.run()` internally to bridge async HTTP to sync method
- Falls back to empty list if endpoints are not available (documented as NEEDS VERIFICATION in research.md)