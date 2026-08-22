# Research: 允许向 IntelliQ 系统发起评测任务

**Feature**: 004-intelliq-evaluation-tasks
**Date**: 2026-08-22

## Decision 1: 后端评测任务管道无需变更 — 已完全 provider-agnostic

**Decision**: 后端评测任务创建和执行管道不做任何代码变更。现有 `create_evaluation_task()` → `run_evaluation_task()` → `evaluate_with_provider()` → `provider.query_sample()` 链路已完全支持任意提供者。

**Rationale**:
- `create_evaluation_task()` (evaluation_db.py:688) 接受 `rag_target.connection_id`，通过 `create_provider()` 解析提供者，验证 Agent 和知识库可访问性，存储 `task_source` 含 provider/revision/mode 快照。
- `run_evaluation_task()` (evaluation_db.py:778) 通过 `create_provider()` 创建提供者实例，调用 `scoring_service.evaluate_with_provider()`，传入 `cancellation_check` 回调。
- `evaluate_with_provider()` (evaluation_service.py:317) 遍历样本，调用 `provider.query_sample()`，根据 `score_eligible` 分离成功/失败样本，执行 RAGAS 评分，合并最终报告。
- `IntelliQProvider.query_sample()` (intelliq.py:196) 已实现 SSE agent chat，含超时 (Timeouterror)、协议错误 (非 text/event-stream)、上游错误 (HTTP 非 200) 的完整处理。

**Alternatives considered**:
- 在 `evaluate_with_provider()` 中为 IntelliQ 添加特殊分支 — 拒绝，破坏 provider-agnostic 设计，增加维护成本。
- 新增 `IntelliQEvaluationTask` 类 — 拒绝，当前 `EvaluationTask` 模型已通过 `rag_provider` 字段区分提供者，无需额外抽象。

## Decision 2: 前端任务列表增加提供者信息展示

**Decision**: 在 `Tasks.tsx` 的表格列中增加"RAG 系统"列，显示 `source_snapshot.connection_name` 和 `source_snapshot.provider`，帮助用户区分 IntelliQ 和 RAGFlow 任务。

**Rationale**:
- 当前任务列表 `columns` 中"对话助手"列显示 `kbName`（即 `assistant_name_snapshot`），但未显示提供者名称。
- 后端 API 已返回 `source_snapshot` 包含 `provider`、`connection_name`、`connection_base_url` 等字段。
- 用户同时有 IntelliQ 和 RAGFlow 任务时，需要直观区分任务来源。

**Alternatives considered**:
- 在任务名称中嵌入提供者信息 — 拒绝，任务名称是用户自定义的，不应污染。
- 使用 Tag 颜色区分提供者 — 可作为补充方案，但不替代文字展示。

## Decision 3: SSE 错误处理已满足需求，无需增强

**Decision**: `aggregate_intelliq_sse()` 和 `query_sample()` 的现有错误处理覆盖了所有边界情况，无需额外增强。

**Rationale**:
- SSE 解析失败（无效 JSON）→ `SSEProtocolError` → `RagQueryResult(error=ProviderError("protocol", ...))` → `score_eligible=False` → 进入 `failed_details`
- HTTP 非 200 → `RagQueryResult(error=ProviderError("upstream", ...))` → 同上
- 非 text/event-stream Content-Type → `RagQueryResult(error=ProviderError("protocol", ...))` → 同上
- 超时 → `RagQueryResult(error=ProviderError("timeout", ...))` → 同上
- SSE 流中 `response_type: "error"` → `RagQueryResult(error=ProviderError("upstream", ...), partial_answer=...)` → 同上
- 空回答（无 answer 事件）→ `completed=True` 但 `answer` 为空 → `aggregate_intelliq_sse` 返回 `score_eligible=False` → 进入 `failed_details`
- 网络异常 → `RagQueryResult(error=ProviderError("upstream", ...))` → 同上

**Alternatives considered**:
- 对空回答进行重试 — 拒绝，SSE 流已完整接收，重试不会改变结果；应由用户在报告中查看失败原因后决定是否重试整个任务。
- 对超时进行自动重试 — 拒绝，可能掩盖真实的 API 性能问题，且 SSE 流是长连接，重试成本高。

## Decision 4: 任务取消和连接 revision 校验已 provider-agnostic

**Decision**: 现有 `cancel_task()` 路由和 `run_evaluation_task()` 中的 revision 校验逻辑不需要任何变更。

**Rationale**:
- `cancel_task()` (evaluation_db.py:1544) 直接设置任务状态为 `cancelled`，后台线程的 `cancelled()` 回调在每次样本处理前检查状态。
- revision 校验在 `run_evaluation_task()` 中：`if task.get("rag_connection_revision") and connection.get("revision") != task.get("rag_connection_revision")` → 标记任务失败。这对所有提供者一致生效。
- 连接被禁用的场景：`run_evaluation_task()` 在开始时就解析连接，之后即使连接被禁用，已创建的 provider 实例仍可继续使用（因为 api_key 已加载）。若连接被完全删除，后续 SSE 调用会失败并正常记录到 `failed_details`。

**Alternatives considered**: N/A — 现有实现已满足需求。

## Decision 5: 前端 EvaluationTaskForm 已就绪，无需变更

**Decision**: `EvaluationTaskForm` 组件已完全支持 IntelliQ 评测任务创建，无需代码变更。

**Rationale**:
- 连接下拉框通过 `ragConnectionApi.list()` 获取所有 enabled 连接，包含 IntelliQ 连接（已在 feature 002/003 中验证）。
- Agent 加载通过 `ragResourceApi.listAssistants(connectionId)` 调用，后端路由到 `IntelliQProvider.list_assistants()`。
- 知识库选择根据 `knowledge_base_selection_mode` 动态展示/隐藏（`selected` → 多选下拉框，`all`/`none` → Alert 提示）。
- 提交时发送 `rag_target: { provider, connection_id, assistant_id, knowledge_base_ids }`，后端 `create_evaluation_task()` 正确处理。
- 唯一的细微差异：IntelliQ 连接的 `provider` 值为 `"intelliq"`，RAGFlow 为 `"ragflow"`，但表单本身不关心此值。

**Alternatives considered**: N/A — 表单已就绪。

## Decision 6: 知识库选择模式处理已完整

**Decision**: 前端和后端对三种知识库选择模式（`selected`、`all`、`none`）的处理已完整，无需变更。

**Rationale**:
- 前端 `EvaluationTaskForm`：
  - `selected` 模式 → 展示知识库多选下拉框，必填
  - `all` 模式 → 展示 Alert "该 Agent 使用全部可用知识范围"
  - `none` 模式 → 展示 Alert "该 Agent 不使用知识库"
- 后端 `create_evaluation_task()`：
  - `selected` 模式 → 验证 `knowledge_base_ids` 非空，校验每个 kb_id 属于该连接且 Agent 可访问
  - `all`/`none` 模式 → 拒绝 `knowledge_base_ids` 非空请求
- 后端 `IntelliQProvider.query_sample()`：
  - `selected` 模式 → 将 `knowledge_base_ids` 传入 SSE payload
  - `all`/`none` 模式 → 不传 `knowledge_base_ids`，由 IntelliQ Agent 自行决定知识范围

**Alternatives considered**: N/A — 实现已完整。