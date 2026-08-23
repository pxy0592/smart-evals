# Contract: 评测任务创建

**Feature**: 007-fix-task-creation  
**Status**: Existing endpoint behavior hardened

## Create Evaluation Task

### Request

```text
POST /api/v1/evaluation/tasks
```

```json
{
  "dataset_id": "dataset-id",
  "metrics": ["answer_correctness"],
  "rag_target": {
    "connection_id": "connection-id",
    "assistant_id": "assistant-id",
    "knowledge_base_ids": ["kb-id"]
  }
}
```

### Success Response

```json
{
  "id": "task-id",
  "status": "pending"
}
```

**Guarantees**:

- 智能体和知识库校验已经完成。
- 任务已完整持久化，可进入后续评测。
- 创建阶段的临时提供者资源已释放，不影响后续请求。

### Failure Response

```json
{
  "error": {
    "category": "validation | permission | upstream | internal",
    "message": "user-readable non-sensitive message",
    "retryable": false
  }
}
```

| Category | Example Cause | Required Behavior |
|---|---|---|
| `validation` | 目标缺失、知识库选择不符合智能体规则 | 4xx；不创建任务 |
| `permission` | 上游拒绝访问智能体或知识库 | 明确提示权限问题；不创建任务 |
| `upstream` | 上游不可用或网络失败 | 明确提示服务不可用；不创建任务 |
| `internal` | 本地资源生命周期异常 | 不暴露堆栈；不创建任务；记录非敏感诊断 |

## Compatibility

- 现有 legacy `chat_id` 创建模式保持原有契约。
- RAGFlow 资源读取和任务创建不走 IntelliQ 请求级资源范围逻辑。
- IntelliQ 的 `none`、`selected`、`all` 知识库模式保持现有业务语义。
