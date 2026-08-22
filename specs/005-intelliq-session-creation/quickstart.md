# Quickstart: IntelliQ 评测前自动创建会话

**Feature**: 005-intelliq-session-creation
**Date**: 2026-08-22

## Prerequisites

- IntelliQ server running at `http://192.168.88.104:18080`
- Valid IntelliQ API key
- SmartQ Eval Docker container running (`docker-compose up -d`)
- An IntelliQ connection configured in SmartQ Eval
- A completed dataset in SmartQ Eval

## Validation Steps

### 1. Verify Session Creation API (manual)

```bash
curl -s -X POST 'http://192.168.88.104:18080/api/v1/sessions' \
  -H 'X-API-Key: sk-xxxxx' \
  -H 'Content-Type: application/json' \
  -d '{"title": "Eval Test", "description": "Quickstart validation"}' | python3 -m json.tool
```

**Expected**: `{"success": true, "data": {"id": "<uuid>", ...}}`

### 2. Verify Session Deletion API (manual)

```bash
curl -s -X DELETE 'http://192.168.88.104:18080/api/v1/sessions/batch' \
  -H 'X-API-Key: sk-xxxxx' \
  -H 'Content-Type: application/json' \
  -d '{"ids": ["<session-id-from-step-1>"]}' | python3 -m json.tool
```

**Expected**: `{"success": true, "message": "Sessions deleted successfully"}`

### 3. Verify Agent Chat with Created Session (manual)

```bash
# Create session
SESSION_ID=$(curl -s -X POST 'http://192.168.88.104:18080/api/v1/sessions' \
  -H 'X-API-Key: sk-xxxxx' \
  -H 'Content-Type: application/json' \
  -d '{"title": "Eval Chat Test"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

# Agent chat with created session
curl -s -N -X POST "http://192.168.88.104:18080/api/v1/agent-chat/${SESSION_ID}" \
  -H 'X-API-Key: sk-xxxxx' \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -d '{"query": "你好", "agent_id": "<agent-id>", "agent_enabled": true, "channel": "api"}'
```

**Expected**: SSE stream with `answer` events containing response text.

### 4. End-to-End Evaluation Task

1. Open SmartQ Eval at `http://localhost:5003`
2. Navigate to "评测任务"
3. Create a new evaluation task:
   - Select an IntelliQ connection
   - Select an Agent
   - Select knowledge bases (or use "all" mode)
   - Select a dataset
   - Choose metrics
   - Submit
4. Wait for the task to complete
5. Open the evaluation report

**Expected**: Task completes successfully (status "已完成"), report contains scoring data with success/failure breakdown. No "Session not found" errors.

### 5. Verify Session Cleanup

After task completion, check the IntelliQ sessions list via the API:

```bash
curl -s 'http://192.168.88.104:18080/api/v1/sessions' \
  -H 'X-API-Key: sk-xxxxx' | python3 -c "
import sys, json
data = json.load(sys.stdin)
eval_sessions = [s for s in data.get('data', []) if 'SmartQ Eval' in (s.get('title') or '')]
print(f'Residual eval sessions: {len(eval_sessions)}')
"
```

**Expected**: `Residual eval sessions: 0` (all evaluation sessions have been cleaned up).

### 6. Run Unit Tests

```bash
docker-compose exec smart-eval python -m pytest backend/tests/unit/test_intelliq_provider.py -v
```

**Expected**: All tests pass, including new tests for session creation and cleanup.