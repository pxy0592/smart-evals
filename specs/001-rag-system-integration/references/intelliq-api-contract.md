# IntelliQ API 契约参考

**来源**: https://ai-intelliq.peraglobal.com/platform/api-docs

**核对日期**: 2026-08-22

**用途**: 为 `001-rag-system-integration` 的后续规划和实现提供已确认的外部接口边界。若页面文档与部署环境的 Swagger 文档存在差异，以部署环境 Swagger 为准。

## 已确认的公共约定

- API 示例统一使用 `/api/v1` 路径前缀。
- 常规业务 API 使用请求头 `X-API-Key` 进行身份认证。
- 文档说明 API Key 代表账户身份并具有对应账户的 API 访问权限，因此 Smart Eval 不得在日志、错误信息、页面或报告中暴露完整密钥。
- 文档将服务自带的 Swagger UI 标记为最权威参考；进入实现阶段时，需要针对目标部署环境再次核对 Swagger 契约。

## 与本功能直接相关的接口

### 获取知识库

- **请求**: `GET /api/v1/knowledge-bases`
- **认证**: `X-API-Key`
- **用途**: 获取当前租户拥有或当前调用身份可见的知识库。
- **可选参数**: `agent_id`，用于按共享 Agent 的可见范围过滤知识库。
- **响应特征**: `data` 为知识库数组；资源具有稳定 ID，并可能包含知识数量、分块数量、处理中数量、共享数量和置顶状态等聚合字段。

### 获取对话助手

- **请求**: `GET /api/v1/agents`
- **认证**: `X-API-Key`
- **用途**: 获取当前租户可见的内置 Agent 和自定义 Agent。
- **响应特征**:
  - `data` 为 Agent 数组。
  - Agent 至少包含稳定 ID、名称、描述、内置标志和配置。
  - 响应还可能包含 `disabled_own_agent_ids`，用于标识当前租户主动隐藏的自有 Agent。
  - Agent 配置可能通过 `kb_selection_mode` 表达知识库选择范围。

### 发起评测问答

- **请求**: `POST /api/v1/agent-chat/{session_id}`
- **认证**: `X-API-Key`
- **用途**: 使用指定 Agent 和知识库完成单个评测样本的问答。
- **必填输入**: `query`。
- **本功能相关可选输入**:
  - `knowledge_base_ids`: 本次问答使用的知识库 ID 列表。
  - `agent_id`: 本次问答使用的 Agent ID。
  - `agent_enabled`: 是否启用 Agent 模式。
  - `channel`: 可标识为 API 来源。
- **响应传输**: Server-Sent Events，内容类型为 `text/event-stream`。
- **本功能需要处理的响应类型**:
  - `references`: 知识库检索引用。
  - `answer`: 最终回答内容，可能由多个事件分段组成。
  - `error`: 上游处理错误。
  - `thinking`、`tool_call`、`tool_result`、`reflection`: 可用于诊断，但不应被拼入最终答案。
- **完成判定**: 流事件通过 `done: true` 表示完成。连接关闭但未收到完成标记时，不得把样本视为成功。

## Smart Eval 责任边界

- 评测数据集继续上传和保存到 Smart Eval，不属于 IntelliQ 知识文档上传流程。
- 评测任务的排队、状态、进度、取消和失败记录由 Smart Eval 管理。
- 评测指标计算、报告生成、报告存储和报告查询由 Smart Eval 管理。
- IntelliQ 为评测任务提供知识库、Agent 和样本回答能力。

## 规划阶段必须确认

- 配置项中的 API URL 是要求填写服务根地址，还是完整的 `/api/v1` 基础地址；实现必须统一规范化，避免路径重复。
- 目标部署环境 Swagger 中上述端点的实际响应字段、分页行为、错误码和限流策略。
- SSE 断开后的重试策略，以及重试是否复用同一 `session_id`。
- 每个评测样本的会话隔离方案，确保一个样本的历史不会影响另一个样本。
- `disabled_own_agent_ids`、Agent 的知识库选择模式以及共享 Agent 权限如何映射为 Smart Eval 中的可选状态。
