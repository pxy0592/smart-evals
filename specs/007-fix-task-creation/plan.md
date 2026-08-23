# Implementation Plan: 修复评测任务创建

**Branch**: `007-fix-task-creation` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-fix-task-creation/spec.md`

## Summary

修复 IntelliQ 评测任务创建中的异步资源生命周期错误。创建任务前需要连续读取智能体和知识库资源；这些操作必须在同一有效请求资源范围内完成并在关闭事件循环前清理连接，避免后续调用复用已绑定到关闭事件循环的资源。创建前校验失败必须返回结构化错误且不写入任务；RAGFlow 与后续评测执行流程保持不变。

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Flask、aiohttp、asyncio、cryptography

**Storage**: SQLite 任务与连接元数据；本功能不新增表、不迁移数据

**Testing**: pytest 单元测试、集成/契约 API 测试、后端编译检查；前端 TypeScript 检查和生产构建用于回归验证

**Target Platform**: Linux Docker 容器中的 Flask Web 服务

**Project Type**: Web application（React 前端 + Flask 后端）

**Performance Goals**: 在正常上游响应条件下，创建有效任务在 3 秒内返回任务记录或结构化失败结果

**Constraints**:
- 不向浏览器暴露 IntelliQ 凭证。
- 同一个 aiohttp 客户端资源只能在其所属的有效事件循环内使用和关闭。
- 校验失败不得创建任务记录。
- 不改变已有评测任务、报告、数据集或运行时评分规则。
- 保持 IntelliQ 与 RAGFlow 资源加载和任务创建兼容。

**Scale/Scope**: 仅覆盖任务创建请求中的资源读取、校验、清理和错误映射；需支持同一连接的连续创建请求。

## Constitution Check

项目 constitution 仍为未填写模板，未定义可执行的额外门禁。设计遵循最小改动：复用既有提供者抽象与持久化模型，修复请求级异步资源边界，不引入依赖、数据库迁移或新的公开端点。

**Pre-Phase 0 Gate**: PASS — 未发现可执行 constitution 约束冲突。

## Project Structure

### Documentation (this feature)

```text
specs/007-fix-task-creation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── task-creation.md
└── tasks.md                 # Created later by $speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── evaluation_db.py
│   ├── create_evaluation_task()          # Task request validation and persistence
│   └── async provider runner helpers     # Event-loop ownership and cleanup boundary
├── services/
│   └── rag_providers/
│       └── intelliq.py                   # aiohttp provider lifecycle compatibility
└── tests/
    ├── contract/
    │   └── test_tasks_api.py             # API error/no-partial-task contract coverage
    ├── integration/
    │   └── test_intelliq_task_flow.py    # Consecutive IntelliQ task creation and execution regression
    └── unit/
        ├── test_intelliq_resources.py    # Provider resource lifetime behavior
        └── test_async_provider_scope.py  # New loop-scope helper coverage

frontend/
└── src/
    ├── components/EvaluationTaskForm.tsx # Existing task creation UI; regression only unless error mapping needs display adjustment
    └── services/evaluation.ts            # Existing task-creation client; regression only
```

**Structure Decision**: 采用现有 Flask 路由、提供者抽象和 SQLite 任务管理结构。核心变更集中在后端请求级 async 生命周期；前端不持有上游凭证，通常无需更改请求模型。测试按资源生命周期、API 契约与连续创建流程分层覆盖。

## Complexity Tracking

无 constitution 违规或额外复杂度需要记录。

## Post-Phase 1 Constitution Check

PASS — 设计不新增服务、端点、数据存储或依赖；所有临时资源均限于既有请求处理范围。
