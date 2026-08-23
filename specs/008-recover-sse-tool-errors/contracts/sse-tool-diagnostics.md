# Contract: SSE 工具错误诊断

**Feature**: 008-recover-sse-tool-errors  
**Status**: Additive result and report contract

## SSE Classification Contract

| Incoming Event | Classification | Aggregator Behavior |
|---|---|---|
| `error`, `done=false`, includes tool call identifier | Recoverable tool error | Record diagnostic and continue stream |
| `error`, `done=true` | Terminal error | Return failed result |
| `error`, no tool call identifier and no later final answer | Terminal error | Return failed result |
| `answer`, non-empty content | Answer fragment | Append answer content |
| `answer`, completion signal | Successful completion when answer is non-empty | Return completed result |
| `complete`, completion signal with accumulated answer | Successful completion | Return completed result |
| Stream end with no complete non-empty answer | Protocol failure | Return failed result |

## Result Additions

Existing sample result payloads gain an optional field:

```json
{
  "completion_status": "completed",
  "tool_errors": [
    {
      "tool_call_id": "call-123",
      "tool_name": "list_knowledge_chunks",
      "message": "knowledge not found",
      "recovered": true,
      "event_count": 1
    }
  ]
}
```

## Compatibility Rules

- Consumers that do not read `tool_errors` continue to receive existing answer, context, reference, completion and error fields.
- Missing `tool_errors` in historical results is interpreted as an empty list.
- Diagnostic messages are bounded summaries; raw SSE tool arguments are not persisted.
