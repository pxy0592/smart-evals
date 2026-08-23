# Phase 0 Research: IntelliQ 评测前自动创建会话

**Feature**: `005-intelliq-session-creation`

**Date**: 2026-08-23

## Current-State Evidence

当前代码已具备核心调用顺序：`IntelliQProvider.query_sample()` 创建真实 Session，使用上游返回的 `data.id` 调用 Agent Chat，并把已创建 Session 累积在任务级 provider 实例中。`EvaluationService.evaluate_with_provider()` 在样本循环的 `finally` 中调用 `provider.cleanup_sessions()`，因此正常完成、样本失败和样本边界取消均会进入清理。

本计划不重复实现该主链路，而是补齐以下可靠性缺口：

- 样本运行记录当前保存的是本地 correlation ID，而不是真实 IntelliQ Session ID。
- Session 创建失败被压缩为泛化错误，丢失 HTTP 状态与安全错误摘要。
- 批量清理只检查 HTTP 200，未校验业务 `success` 字段。
- 清理请求前清空内存 Session 列表，失败后无法补偿。
- Stateful mock 和集成测试尚未证明 Session 创建、Chat ID 校验、批量删除和取消路径。

## Decision 1: Provider owns Session creation; evaluator owns lifecycle finalization

**Decision**: `IntelliQProvider.query_sample()` 继续负责创建 Session 并使用真实返回 ID 发起 Agent Chat。`EvaluationService.evaluate_with_provider()` 继续在 `finally` 中触发 provider 清理，确保所有样本处理路径都进入清理。

**Rationale**: Session API 是 IntelliQ 特有行为，放在通用 evaluator 会污染 RAGFlow。样本循环外的 `finally` 能在成功、失败和协作式取消后统一收尾。

**Alternatives considered**:

- 在 evaluator 中创建 Session: 会将 IntelliQ 细节扩散到所有 provider。
- 每个 `query_sample()` 结束时立即删除: 无法满足任务级批量删除且增加请求数。
- 维持任务级 provider 加 finally: 保持 provider 隔离并支持批量清理。

## Decision 2: Persist actual IntelliQ Session IDs and cleanup state

**Decision**: 为 `evaluation_sample_runs` 增加或明确 `provider_session_id`、`session_creation_status`、`session_cleanup_status`、`session_cleanup_error` 和 `session_cleanup_attempts`。现有 `session_id` 保留为本地样本尝试关联 ID。

**Rationale**: 本地 correlation ID 不能用于 IntelliQ 控制台排查或补偿删除。持久化真实 Session ID 和清理状态可防止进程或容器异常后永久丢失待清理资源。

**Alternatives considered**:

- 仅在内存记录 Session ID: 最小改动，但进程退出后无法补偿清理。
- 将真实 ID 覆盖现有 `session_id`: 会失去本地尝试关联语义。
- 增加 provider session ledger: 可追溯、可补偿，满足长期资源治理。

## Decision 3: Session creation is non-idempotent by default

**Decision**: 不对 `POST /sessions` 做盲目自动重试。若连接超时或无法确认服务端是否已创建 Session，当前尝试记录为失败；只有 IntelliQ 后续提供幂等键或查询契约后才引入自动重试。

**Rationale**: 客户端超时可能发生在服务端已创建 Session 之后。自动重试会创建无法追踪的重复 Session，反而扩大残留风险。

**Alternatives considered**:

- 对所有 429/5xx/超时按 `max_retries` 重试: 可能产生孤儿 Session。
- 永远不处理短暂故障: 可用性较差，但当前比错误重复创建更安全。
- 有上游幂等支持后有限重试: 后续增强方向。

## Decision 4: Session creation returns a structured, redacted result

**Decision**: `_create_session()` 返回成功 Session ID 或结构化 `ProviderError`，保留 `http_status`、上游业务错误码、脱敏且截断的错误 message/details 及 retryable 标志。

**Rationale**: 当前返回 `None` 后只能形成泛化错误，无法满足会话创建失败诊断和样本报告追溯。

**Alternatives considered**:

- 只写日志: 报告和样本诊断缺少根因。
- 保存完整上游响应: 可能泄露敏感字段。
- 保存结构化、脱敏摘要: 满足诊断与安全边界。

## Decision 5: Cleanup is durable best effort with business-success validation

**Decision**: 批量删除前按任务聚合已成功创建且未清理的真实 Session ID，稳定去重并分批。只有 HTTP 2xx 且响应业务 `success=true` 才标记清理成功。失败 ID 保留为 `cleanup_failed`，由任务结束后的补偿清理和服务启动恢复流程再次尝试；清理失败不得改写已完成评测的业务 outcome。

**Rationale**: 当前实现只判断 HTTP 200 且请求前清空内存列表，导致 `200 + success:false` 被误判成功、网络失败无法补偿。

**Alternatives considered**:

- HTTP 200 即成功: 不可靠。
- 清理失败使评测任务失败: 与规格 FR-005 冲突。
- 持久化 pending/failed 清理并补偿: 保持评测结果与资源治理解耦。

## Decision 6: Cancellation remains cooperative in this phase

**Decision**: 取消后不开始新的样本；在创建 Session 后、发送 Agent Chat 前再次检查取消；活跃 SSE 流不承诺即时终止，等待现有请求结束、超时或失败后进入 finally 清理。

**Rationale**: 当前没有已验证的 IntelliQ 取消生成契约。不能假设断开本地客户端会安全终止上游生成。

**Alternatives considered**:

- 立即关闭 SSE 并假设上游取消: 未经验证，可能留下执行中的远程会话。
- 完全忽略取消: 会在取消后继续创建新 Session。
- 协作式取消加收尾清理: 当前范围内最安全。

## Decision 7: Stateful mock is the release gate

**Decision**: 将 `backend/tests/mock_intelliq_server.py` 扩展为状态化 mock，维护已创建 Session、已删除批次和请求审计。未创建 Session 的 Agent Chat 返回业务错误 `code:1003`。

**Rationale**: 当前 mock 接受任何 Session ID，无法检测本功能要解决的根因。真实 IntelliQ smoke test 只作为受控补充，不能替代自动化回归。

**Alternatives considered**:

- 仅手工 curl 验证: 不可重复、依赖真实凭据。
- 仅 mock SSE: 无法验证 Session 生命周期。
- Stateful session mock: 能覆盖创建、Chat、删除、失败和取消。

## Resolved Technical Unknowns

- Session 创建成功条件: HTTP 2xx、业务 `success=true`、`data.id` 为非空字符串。
- Agent Chat 前置条件: 使用同一 IntelliQ API Key 创建成功返回的真实 Session ID。
- 清理对象: 仅当前任务成功创建的真实 IntelliQ Session ID。
- 清理成功条件: HTTP 2xx 且业务 `success=true`。
- 创建重试: 当前不做盲目重试。
- 清理失败: 记录安全 warning 并持久化待补偿状态，不影响已完成评分。
- 取消语义: 样本边界协作式取消，活跃 SSE 不承诺即时中断。
- 真实外部契约: 批量上限、部分删除、未知 ID、额外租户头及上游取消接口须在受控 smoke test 中记录，不阻塞本地 mock 契约实现。
