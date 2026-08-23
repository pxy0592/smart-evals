# Implementation Plan: IntelliQ 评测前自动创建会话

**Branch**: `005-intelliq-session-creation` | **Date**: 2026-08-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-intelliq-session-creation/spec.md`

## Summary

当前 IntelliQ provider 已实现“创建 Session -> Agent Chat -> finally 批量清理”的核心路径。本功能的剩余工作是将其从静态接入提升为可追溯、可诊断、可补偿的会话生命周期：持久化真实 IntelliQ Session ID，保留创建失败的结构化诊断，以业务 `success` 判定批量删除，持久化 cleanup 状态，并通过状态化 mock 验证创建、Chat、删除、失败和取消路径。

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Flask 3、aiohttp 3、SQLite、pytest、pytest-asyncio

**Storage**: SQLite `data/evaluation.db`；扩展现有 `evaluation_sample_runs`，无需引入新服务或外部队列

**Testing**: Stateful aiohttp mock、provider unit tests、任务集成测试、RAGFlow 回归测试、受控 IntelliQ smoke test

**Target Platform**: Linux Docker Compose 单容器部署

**Project Type**: Flask evaluation service with React frontend unchanged for this feature

**Performance Goals**: 每个样本最多创建一个 IntelliQ Session；清理仅删除当前任务成功创建的去重 Session；清理失败不延迟或回滚评分结果

**Constraints**: 不盲目重试非幂等 `POST /sessions`；不泄露 API Key、认证头或完整未受控错误响应；RAGFlow 行为不变；取消保持协作式，不承诺即时终止活跃 SSE；Session 清理必须不影响已确定任务 outcome

**Scale/Scope**: 当前任务样本数范围内的 Session 生命周期；批量删除依据受控 smoke test 确认上游最大批次，默认实现可分批；修改 provider、评测服务、样本运行持久化、启动补偿和测试 mock

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

项目 constitution 仍为未填写模板，没有额外的已批准原则。按仓库治理和规格实施以下门禁：

| Gate | Pre-Research | Post-Design | Evidence |
|---|---|---|---|
| 保持 RAGFlow 兼容 | PASS | PASS | provider base 保留 no-op cleanup，RAGFlow 无 IntelliQ Session 调用 |
| 不泄露凭据或认证头 | PASS | PASS | 结构化脱敏错误、样本和清理记录均禁止保存 API Key/headers |
| 会话资源可追溯且不误删 | PASS | PASS | provider_session_id、任务范围聚合、仅删除成功创建的真实 ID |
| 失败不伪造业务成功 | PASS | PASS | 创建失败不发 Chat；cleanup 需 HTTP 2xx 加业务 success=true |
| 验证区分 mock 与真实环境 | PASS | PASS | Stateful mock 是自动化门禁，真实 smoke test 为受控补充 |

**Gate Result**: PASS。

## Architecture

```text
EvaluationService.evaluate_with_provider()
        |
        | per sample
        v
IntelliQProvider.query_sample()
        |
        +--> POST /sessions
        |      -> provider_session_id persisted
        |
        +--> POST /agent-chat/{provider_session_id}
        |      -> SSE result / failure diagnostic
        |
        v
finally: provider.cleanup_sessions()
        |
        +--> collect created + pending Session IDs for current task
        +--> DELETE /sessions/batch
        +--> mark cleaned or cleanup_failed

Startup compensation
        |
        +--> find pending/failed IntelliQ cleanup records
        +--> retry deletion without changing task outcome
```

## Project Structure

### Documentation

```text
specs/005-intelliq-session-creation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── intelliq-session-api.md
└── tasks.md
```

### Source Code

```text
backend/
├── services/
│   ├── rag_providers/
│   │   ├── base.py
│   │   └── intelliq.py
│   └── evaluation_service.py
├── models/
│   └── database.py
├── db.py
├── evaluation_db.py
└── tests/
    ├── mock_intelliq_server.py
    ├── unit/
    │   ├── test_intelliq_resources.py
    │   └── test_intelliq_sse.py
    └── integration/
        └── test_intelliq_session_lifecycle.py
```

**Structure Decision**: Session lifecycle behavior remains in the IntelliQ provider and provider-agnostic evaluation service. Persistence additions are limited to existing sample-run records and startup cleanup compensation. No frontend route, public API surface, task queue, or RAGFlow adapter redesign is required.

## Phase 0 Output

- [research.md](research.md) resolves lifecycle ownership, non-idempotent creation, structured errors, cleanup success semantics, cancellation, and stateful mock strategy.

## Phase 1 Output

- [data-model.md](data-model.md)
- [contracts/intelliq-session-api.md](contracts/intelliq-session-api.md)
- [quickstart.md](quickstart.md)

## Implementation Sequence

1. Add additive sample-run Session lifecycle migration and database helpers.
2. Refactor IntelliQ Session creation to return structured success/failure and preserve real provider Session IDs.
3. Harden batch cleanup success checks, failure retention, batching, and redirection policy.
4. Persist provider Session IDs and cleanup states as samples finish.
5. Add startup/task-end compensation cleanup for pending Session IDs.
6. Extend stateful mock and automated unit/integration coverage.
7. Run controlled IntelliQ smoke test and RAGFlow regression, recording evidence boundaries.

## Complexity Tracking

No constitution violation. The additive Session lifecycle fields are required to meet the specification's cleanup and diagnosability requirements across cancellation and process recovery; an in-memory-only list is insufficient for reliable compensation.
