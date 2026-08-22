# Quickstart: 允许向 IntelliQ 系统发起评测任务

**Feature**: 004-intelliq-evaluation-tasks
**Date**: 2026-08-22

## Prerequisites

- Smart Eval running (Docker: `docker compose up -d`, or dev: `python backend/app.py`)
- At least one IntelliQ connection configured, enabled, and validated (status: `available`)
- At least one IntelliQ Agent with a known `knowledge_base_selection_mode`
- At least one completed dataset with normalized samples (e.g., from AI generation in feature 003)
- At least one API configuration (LLM provider) set as default for RAGAS scoring
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

### VS-1: Create IntelliQ evaluation task via API

1. List available connections to find the IntelliQ connection ID:

```bash
curl -s http://localhost:5003/api/v1/evaluation/rag-connections | python3 -c "
import json,sys
data=json.load(sys.stdin)
for c in data['connections']:
    if c['provider'] == 'intelliq':
        print(f\"IntelliQ: {c['id']} ({c['name']})\")"
```

2. List agents for that connection:

```bash
CONN_ID="<connection-id-from-step-1>"
curl -s "http://localhost:5003/api/v1/evaluation/rag-connections/$CONN_ID/assistants?limit=100" | python3 -c "
import json,sys
data=json.load(sys.stdin)
for a in data['items']:
    print(f\"Agent: {a['id']} ({a['name']}) mode={a['knowledge_base_selection_mode']} selectable={a['selectable']}\")"
```

3. List completed datasets:

```bash
curl -s "http://localhost:5003/api/v1/evaluation/datasets?status=completed&limit=100" | python3 -c "
import json,sys
data=json.load(sys.stdin)
for d in data['datasets']:
    print(f\"Dataset: {d['id']} ({d['name']}) samples={d['num_samples']}\")"
```

4. Create the task:

```bash
curl -s -X POST http://localhost:5003/api/v1/evaluation/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "IntelliQ Eval Quickstart",
    "dataset_id": "<dataset-id>",
    "metrics": ["faithfulness", "answer_relevancy"],
    "batch_size": 10,
    "rag_target": {
        "provider": "intelliq",
        "connection_id": "<connection-id>",
        "assistant_id": "<agent-id>",
        "knowledge_base_ids": ["<kb-id-1>", "<kb-id-2>"]
    }
}' | python3 -m json.tool
```

**Expected**: HTTP 201, response includes `"status": "pending"`, `"rag_provider": "intelliq"`, `"source_legacy": false`.

### VS-2: Monitor task progress via API

```bash
TASK_ID="<task-id-from-vs-1>"
curl -s "http://localhost:5003/api/v1/evaluation/tasks/$TASK_ID" | python3 -c "
import json,sys
t=json.load(sys.stdin)
print(f\"Status: {t['status']} | Progress: {t['progress']}% | {t.get('processed_samples',0)}/{t.get('total_samples',0)}\")
if t.get('error_message'):
    print(f\"Error: {t['error_message']}\")"
```

**Expected**: Status transitions from `pending` → `running` → `completed` (or `failed`). Progress increases from 0 to 100. If some samples fail, `has_warnings: true` and `outcome: "partially_succeeded"`.

### VS-3: View evaluation report

```bash
TASK_ID="<task-id>"
curl -s "http://localhost:5003/api/v1/evaluation/tasks/$TASK_ID/report" | python3 -c "
import json,sys
r=json.load(sys.stdin)
print('Overall Scores:', json.dumps(r.get('overall_scores',{}), indent=2))
print(f\"Success: {r['evaluation_metadata']['success_count']}/{r['evaluation_metadata']['total_count']}\")
print(f\"Failed: {r['evaluation_metadata']['failed_count']}\")
print()
for s in r.get('detailed_scores',[]):
    status = s.get('completion_status','?')
    question = s.get('user_input','')[:60]
    print(f\"  [{status}] {question}...\")
    if s.get('upstream_error'):
        print(f\"    Error: {s['upstream_error']}\")"
```

**Expected**: Report contains `overall_scores` with values for each requested metric, `detailed_scores` array with one entry per sample (including failed ones with `upstream_error`).

### VS-4: Cancel a running task

```bash
TASK_ID="<task-id>"  # must be running
curl -s -X POST "http://localhost:5003/api/v1/evaluation/tasks/$TASK_ID/cancel" | python3 -m json.tool
```

**Expected**: HTTP 200, `{"message": "Task cancelled", "task_id": "..."}`. After a moment, task status becomes `"cancelled"`.

### VS-5: Frontend — full task creation flow

1. Open browser to `http://localhost:5003/tasks`
2. Click "创建评测任务"
3. **Verify**: RAG 系统 dropdown shows all enabled connections, including IntelliQ connections labeled with `(intelliq)`
4. Select an IntelliQ connection
5. **Verify**: Agent dropdown loads the connection's agents
6. Select an agent with `selected` mode
7. **Verify**: Knowledge base multi-select appears below the agent dropdown
8. Select at least one knowledge base
9. Select a completed dataset
10. Select metrics (e.g., Faithfulness, Answer Relevancy)
11. Click "创建任务"
12. **Verify**: Success toast, task appears in list with `pending` status
13. **Verify**: Task progresses through `running` → `completed`, progress bar updates
14. After completion, click the task name to view report
15. **Verify**: Report shows overall scores, per-sample details, and any failed samples with error descriptions

### VS-6: Revision change rejection

1. Create a task against an IntelliQ connection (as in VS-1)
2. Before the task starts executing, modify the connection (e.g., update the API key)
3. **Verify**: When the task begins execution, it fails with `"RAG connection revision changed before execution"`
4. Check the task status:

```bash
curl -s "http://localhost:5003/api/v1/evaluation/tasks/$TASK_ID" | python3 -c "import json,sys; t=json.load(sys.stdin); print(t['status'], t.get('error_message',''))"
```

**Expected**: `failed RAG connection revision changed before execution`

### VS-7: Empty knowledge_base_ids for "all" mode agent

1. Find an IntelliQ agent with `knowledge_base_selection_mode: "all"`:

```bash
curl -s "http://localhost:5003/api/v1/evaluation/rag-connections/$CONN_ID/assistants?limit=100" | python3 -c "
import json,sys
for a in json.load(sys.stdin)['items']:
    if a['knowledge_base_selection_mode'] == 'all' and a['selectable']:
        print(a['id'], a['name'])"
```

2. Create a task with empty `knowledge_base_ids`:

```bash
curl -s -X POST http://localhost:5003/api/v1/evaluation/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "All KB Mode Test",
    "dataset_id": "<dataset-id>",
    "metrics": ["faithfulness"],
    "rag_target": {
        "provider": "intelliq",
        "connection_id": "<connection-id>",
        "assistant_id": "<all-mode-agent-id>",
        "knowledge_base_ids": []
    }
}' | python3 -m json.tool
```

**Expected**: HTTP 201 (success). If `knowledge_base_ids` is non-empty for an `all` mode agent, expect HTTP 400 with `"all 模式不能手动提交知识库"`.

### VS-8: SSE error handling — empty answer

1. Create a dataset with a question that produces no meaningful answer from IntelliQ
2. Run the evaluation task
3. **Verify**: The sample appears in `detailed_scores` with `completion_status: "failed"` and `score_eligible: false`
4. **Verify**: The report still generates successfully with `outcome: "partially_succeeded"` and a `warning` object