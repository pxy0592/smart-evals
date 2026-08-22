# Feature Specification: IntelliQ 评测前自动创建会话

**Feature Branch**: `005-intelliq-session-creation`

**Created**: 2026-08-22

**Status**: Draft

**Input**: User description: "访问 IntelliQ API 文档，对于 agent-chat 需要先创建一个 session"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - IntelliQ 评测任务自动创建会话并成功执行 (Priority: P1) 🎯 MVP

当用户对 IntelliQ 连接发起评测任务时，系统在每条样本评测前自动调用 IntelliQ `POST /api/v1/sessions` 创建会话，使用返回的 `session_id` 调用 `POST /api/v1/agent-chat/{session_id}` 进行 SSE 问答。评测任务完成后，系统清理不再需要的会话。

**Why this priority**: 这是阻塞性修复——当前所有 IntelliQ 评测任务均因缺少会话而失败（返回 `code:1003, "Session not found"`），导致 004-intelliq-evaluation-tasks 的 7 个 E2E 验证任务无法完成。

**Independent Test**: 准备一个已验证的 IntelliQ 连接和一个已完成的数据集，创建评测任务，验证任务能够成功完成并生成包含评分数据的报告。

**Acceptance Scenarios**:

1. **Given** IntelliQ 连接已配置且状态正常，**When** 评测执行引擎调用 `IntelliQProvider.query_sample()`，**Then** 系统先调用 `POST /api/v1/sessions` 创建会话，获取有效的 `session_id`，再使用该 ID 调用 `POST /api/v1/agent-chat/{session_id}`
2. **Given** 会话创建成功，**When** agent-chat SSE 流正常返回，**Then** 评测结果包含回答、引用和上下文信息，与之前的行为一致
3. **Given** 会话创建失败（网络错误、API Key 无效等），**When** 评测执行，**Then** 该样本被标记为失败，`upstream_error` 记录会话创建失败的具体原因

---

### User Story 2 - 会话资源清理 (Priority: P2)

评测任务完成后，系统清理为评测创建的临时会话，避免在 IntelliQ 服务端积累大量无用的会话记录。

**Why this priority**: 虽然不是阻塞性问题，但长期运行会在 IntelliQ 服务端积累大量评测会话，影响用户体验和资源管理。

**Independent Test**: 完成一个评测任务后，检查 IntelliQ 服务端不会残留评测创建的会话。

**Acceptance Scenarios**:

1. **Given** 评测任务完成（无论成功或失败），**When** 所有样本处理完毕，**Then** 系统调用 `DELETE /api/v1/sessions/batch` 批量删除评测过程中创建的所有会话
2. **Given** 会话删除失败（网络错误等），**When** 评测任务结束，**Then** 系统记录警告日志但不影响评测任务的成功状态

---

### Edge Cases

- 会话创建返回的 `session_id` 格式与当前 UUID 生成方式不一致时，系统使用 API 返回的实际 ID
- 同一评测任务的多条样本各自使用独立的会话，互不干扰
- 会话创建 API 限流时，系统按重试策略处理（已有 `max_retries` 机制）
- 评测任务被取消时，已创建的会话仍需清理

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 在通过 IntelliQ Agent Chat 接口进行问答前，先调用 `POST /api/v1/sessions` 创建会话，再使用返回的 `session_id` 调用 `POST /api/v1/agent-chat/{session_id}`
- **FR-002**: 会话创建请求 MUST 包含合适的 `title`（如 "SmartQ Eval - {timestamp}"）和 `description`（如 "Auto-created session for evaluation"），便于在 IntelliQ 界面识别
- **FR-003**: 系统 MUST 在会话创建失败时返回明确的错误信息，包含 HTTP 状态码和响应体
- **FR-004**: 系统 MUST 在评测任务的所有样本处理完毕后，调用 `DELETE /api/v1/sessions/batch` 批量删除创建的会话
- **FR-005**: 会话删除失败 MUST NOT 影响评测任务的成功状态，仅记录警告日志
- **FR-006**: 系统 MUST 在评测任务被取消时，仍尝试清理已创建的会话

### Key Entities

- **Session**: IntelliQ 对话容器，通过 `POST /api/v1/sessions` 创建，包含 `id`、`title`、`description`、`tenant_id` 等字段。评测中每条样本使用独立的 Session。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: IntelliQ 评测任务能够成功完成，不再出现 "Session not found" (code:1003) 错误
- **SC-002**: 评测报告包含完整的评分数据（各指标得分、成功/失败样本明细）
- **SC-003**: 评测完成后 IntelliQ 服务端不残留评测创建的会话
- **SC-004**: 004-intelliq-evaluation-tasks 中被阻塞的 7 个 E2E 验证任务（T012-T014, T017, T020, T026）能够通过

## Assumptions

- IntelliQ `POST /api/v1/sessions` 端点已可用且稳定（已通过 curl 验证）
- IntelliQ `DELETE /api/v1/sessions/batch` 端点已可用（API 文档中已列出）
- 评测使用的 API Key 具有创建和删除会话的权限
- 每条评测样本使用独立会话，不依赖会话历史

## API Reference

### Session Creation

```
POST /api/v1/sessions
Headers: X-API-Key, Content-Type: application/json
Body: {"title": "string (optional)", "description": "string (optional)"}
Response: {"success": true, "data": {"id": "uuid", "title": "...", ...}}
```

### Session Batch Deletion

```
DELETE /api/v1/sessions/batch
Headers: X-API-Key, Content-Type: application/json
Body: {"ids": ["uuid1", "uuid2", ...]}
Response: {"success": true, "message": "Sessions deleted successfully"}
```

### Agent Chat (existing, unchanged)

```
POST /api/v1/agent-chat/{session_id}
Headers: X-API-Key, Content-Type: application/json, Accept: text/event-stream
Body: {"query": "...", "agent_id": "...", "agent_enabled": true, "knowledge_base_ids": [...], "channel": "api"}
Response: SSE stream (text/event-stream)
```