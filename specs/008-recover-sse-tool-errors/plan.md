# Implementation Plan: 恢复可恢复 SSE 工具错误

**Branch**: `008-recover-sse-tool-errors` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-recover-sse-tool-errors/spec.md`

## Summary

修复 IntelliQ SSE 聚合器将所有 `error` 事件立即判定为样本失败的问题。聚合器将识别未完成且带工具调用标识的工具级错误，记录去重后的非敏感诊断并继续读取 SSE；若后续收到非空完成答案或完成事件，则样本成功并进入评分。真正终止错误、协议错误和无最终答案流继续失败。恢复诊断将随样本运行和报告详情保存，便于区分“最终失败”与“已恢复成功”。

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: aiohttp、asyncio、Flask、SQLite

**Storage**: SQLite 评测样本运行记录与报告详情；需要为工具错误诊断提供兼容的持久化字段

**Testing**: pytest 单元测试（SSE 聚合）、集成/契约测试（样本运行与报告持久化）、后端编译检查；前端 TypeScript 检查和生产构建用于报告读取兼容性回归

**Target Platform**: Linux Docker 容器中的 Flask Web 服务

**Project Type**: Web application（React 前端 + Flask 后端）

**Performance Goals**: 可恢复工具错误不增加额外重试或等待；聚合器持续按原始流速消费事件，并在最终完成事件到达后返回结果

**Constraints**:
- 不重放、修改或暴露上游工具调用参数。
- 仅将 `done=false` 且具备工具调用标识的错误视为可恢复。
- 诊断中不得保存凭证、原始敏感参数或内部堆栈。
- 保持正常答案、引用、上下文、终止错误和协议错误既有语义。
- 对历史数据库保持迁移兼容，不破坏已有样本运行和报告读取。

**Scale/Scope**: 覆盖 IntelliQ SSE 聚合、样本结果传递、样本运行持久化和报告详情；不修改 IntelliQ 智能体、工具 schema 或知识库内容。

## Constitution Check

项目 constitution 仍为未填写模板，未定义可执行的额外门禁。设计复用现有 SSE 聚合、RagQueryResult、样本运行和报告持久化路径，仅增加可审计工具诊断与终止判定，不引入新服务或依赖。

**Pre-Phase 0 Gate**: PASS — 未发现可执行 constitution 约束冲突。

## Project Structure

### Documentation (this feature)

```text
specs/008-recover-sse-tool-errors/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── sse-tool-diagnostics.md
└── tasks.md                 # Created later by $speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── services/
│   ├── rag_providers/
│   │   ├── base.py                     # Query-result diagnostic contract
│   │   └── sse.py                      # Recoverable/terminal SSE error aggregation
│   └── evaluation_service.py           # Carry diagnostics into success and failure details
├── models/
│   └── database.py                     # Sample-run diagnostic persistence and migration compatibility
├── evaluation_db.py                     # Persisted sample-run/report result exposure
└── tests/
    ├── unit/
    │   └── test_intelliq_sse.py        # Event classification, recovery and terminal failure tests
    ├── integration/
    │   └── test_intelliq_task_flow.py  # Recovered result retained through evaluation workflow
    └── contract/
        └── test_reports_api.py         # Report/task diagnostic response compatibility

frontend/
└── src/
    ├── pages/Reports.tsx               # Existing report reader regression only
    └── services/evaluation.ts          # Existing report type/client regression only
```

**Structure Decision**: 采用现有 IntelliQ SSE 聚合器作为唯一事件判定位置；通过 RagQueryResult 将诊断交给评测服务，再写入已有样本运行和报告详情。前端不参与上游 SSE 消费，只需保持对新增诊断字段的兼容。

## Complexity Tracking

无 constitution 违规或额外复杂度需要记录。

## Post-Phase 1 Constitution Check

PASS — 设计不新增外部端点、服务、凭证传递或第三方依赖；仅为现有样本状态增加兼容诊断数据。
