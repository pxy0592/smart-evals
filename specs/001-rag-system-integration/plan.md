# Implementation Plan: 新 RAG 系统接入

**Branch**: `001-rag-system-integration` | **Date**: 2026-08-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-rag-system-integration/spec.md`

## Summary

为 Smart Eval 增加 IntelliQ 被测 RAG 系统，同时保持现有 RAGFlow、数据集、RAGAS 评分和报告流程兼容。实施采用独立 RAG connection 模型和 provider adapter：后端统一管理连接、资源发现和样本问答；IntelliQ adapter 使用 `X-API-Key`、知识库/Agent 接口及 SSE 流；任务按 Agent 的 all/selected/none 知识库模式创建不可变来源快照，每个样本使用独立 session，并且只有明确完成的回答进入正常评分。数据集固定支持五种结构化格式和 10 MB 上限。SQLite 使用增量 migration，旧 `chat_id` 请求和历史 RAGFlow 记录继续可读。

## Technical Context

**Language/Version**: Python 3.12（生产 Docker），TypeScript 5.7，React 18.3

**Primary Dependencies**: Flask 3、aiohttp 3、requests 2、pandas 2、Ragas 0.2-0.3、LangChain OpenAI、React Router 6、Ant Design 5、Axios 1；新增 `cryptography` 用于 RAG 连接凭据加密，pytest/pytest-asyncio 用于测试

**Storage**: 配置驱动的 SQLite，容器默认 `/app/data/evaluation.db`（连接、任务、报告和样本执行状态，WAL + busy timeout）；`tmp/datasets` 中的归一化数据集 JSON；`tmp/evaluation/reports` 中的报告 JSON

**Testing**: 新增 backend pytest 单元/迁移/契约/集成测试；aiohttp 本地 mock SSE server；前端移除核心页面 `@ts-nocheck` 后执行 `npm run typecheck` 和 `npm run build`；Playwright 主流程验证；现有 `bash -n *.sh`、`docker-compose config`、`check-before-publish.sh` 和健康检查

**Target Platform**: Linux 单容器部署，Nginx + Flask + 静态 React 前端；开发环境可分离运行前后端

**Project Type**: 前后端一体化 Web application / evaluation service

**Performance Goals**: 正常上游且资源不超过 100 条时，95% 的知识库和助手刷新在 5 秒内返回；连接测试在 10 秒内给出分类结果；报告在任务完成后 10 秒内可访问；上游样本请求使用可配置的任务内有限并发，默认不超过 2

**Constraints**: 保持 RAGFlow 旧路径和 `chat_id` payload 兼容；IntelliQ API Key 不得出现在响应、日志、任务或报告；连接写操作必须通过部署级管理员令牌；Agent 知识库模式由服务端重新验证，selected 至少一项而 all/none 必须为空；上传仅支持 JSON/JSONL/CSV/XLSX/XLS 且最大 10 MB；仅 `done: true` 的完整回答可评分；样本会话隔离；禁止任意外部代理和未授权 SSRF 目标；不引入外部任务队列或多进程 worker；第一阶段最多一个启用的 IntelliQ 连接

**Scale/Scope**: 一个环境驱动的合成 RAGFlow 连接和一个可编辑 IntelliQ 连接；现有 5 个主要页面；最多 100 个资源单次发现；五种结构化上传格式、单文件 10 MB；任务规模以当前数据集/AI 生成最多 100 个样本为首要验证范围

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

项目 constitution 仍为未填写模板，没有已批准的额外原则或强制门禁。以下门禁来自仓库 `AGENTS.md` 和功能规格：

| Gate | Pre-Research | Post-Design | Evidence |
|---|---|---|---|
| 保持部署仓库边界和现有单容器工作流 | PASS | PASS | 未新增服务容器或外部队列；改动局限于现有 backend/frontend 和依赖 |
| 保持原有 RAGFlow 和历史数据兼容 | PASS | PASS | 合成 `ragflow-default`、旧 `chat_id` payload、增量 migration 和 legacy fallback |
| 密钥和运行数据不得提交或泄露 | PASS | PASS | 加密凭据、只返回 `api_key_configured`、脱敏错误、quickstart 使用占位变量 |
| 外部集成必须有契约和失败边界 | PASS | PASS | IntelliQ 参考、OpenAPI、normalized result schema、SSE 完成/错误规则 |
| 任务和报告结论必须可追溯 | PASS | PASS | connection revision、资源快照、sample run、report source snapshot |
| 所有规划未知项必须在 Phase 0 解决 | PASS | PASS | `research.md` 无 `NEEDS CLARIFICATION` |
| 验证必须区分 mock、静态和真实运行 | PASS | PASS | quickstart 明确 mock 与真实 IntelliQ 验证边界 |
| 数据库和凭据在容器更新后仍安全持久 | PASS | PASS | `DATABASE_PATH` 指向 `/app/data`、旧路径迁移、WAL、外部加密密钥与管理员令牌 |

**Gate Result**: PASS。没有需要豁免的 constitution violation。

## Architecture

### Runtime Flow

```text
React Settings / Task Form / Reports
        |
        v
/api/v1/evaluation/rag-connections/*
/api/v1/evaluation/tasks
/api/v1/evaluation/reports
        |
        v
evaluation_db.py routes
        |
        +--> RagConnectionService --> CredentialCipher --> SQLite
        |
        +--> RagProviderFactory
                +--> RAGFlowProvider  --> Bearer + JSON completion
                +--> IntelliQProvider --> X-API-Key + SSE
        |
        v
Task-scoped provider + EvaluationService orchestration
        |
        +--> evaluation_sample_runs
        +--> completed samples --> RAGAS
        +--> report source snapshot + detailed results
```

### Component Decisions

1. **Active implementation path only**: Implement routes in `backend/evaluation_db.py` and persistence in `backend/db.py` / `backend/models/database.py`. Do not implement only in inactive `api_optimized.py` or `services/unified.py`.
2. **Provider-neutral browser API**: Remove page dependence on `ragflowClient`; browsers call fixed Smart Eval endpoints only.
3. **Connection domain separated from evaluator LLM**: Existing Settings LLM configuration remains unchanged; add a separate RAG systems tab and API.
4. **Task form unification**: Extract one shared provider-aware task form used from Tasks and Datasets to avoid two divergent implementations.
5. **Capabilities**: RAGFlow retains AI dataset generation; IntelliQ supports resource discovery and streaming evaluation only until a knowledge-content contract is verified.
6. **Durable sample state**: Persist sample attempts so progress, cancellation, errors and scoring denominators are observable.
7. **Migration before behavior**: Add idempotent schema migrations and legacy backfills before provider-aware writes.
8. **Persistent database path**: Make `DATABASE_PATH` authoritative, migrate legacy `/app/evaluation.db`, enable WAL/busy timeout and throttle progress writes.
9. **Minimal admin authorization**: Protect connection create/update/enable/test operations with `SMART_EVAL_ADMIN_TOKEN`; do not treat `X-User-Id` as authorization.
10. **Single process for phase 1**: Do not switch the container to multi-worker Gunicorn until task ownership is backed by a durable scheduler.
11. **Agent mode is authoritative**: Normalize Agent mode to all/selected/none and revalidate on submit; only selected exposes a one-or-more knowledge-base selector.
12. **Dataset contract is exact**: Normalize JSON, JSONL, CSV, XLSX and XLS into a common sample JSON and enforce 10 MB before parsing.
13. **Partial failure uses warning projection**: Keep task status `completed` when at least one sample is scoreable, set `has_warnings`, and count only each sample's final attempt; zero scoreable samples produce a failed task and no final report.
14. **URL terminology is fixed**: User input is `api_url`; persisted and returned value is normalized `service_root`; provider calls use `{service_root}/api/v1` exactly once. Documentation and Swagger paths are invalid.

### Clarification Alignment

| Clarification | Plan Alignment |
|---|---|
| Deployment admin authorization | create/update/enable/disable/test use `SMART_EVAL_ADMIN_TOKEN`; audit subject is `deployment-admin` |
| Partial sample failures | completed + warning with successful-sample denominator; all failed means failed/no report |
| Agent knowledge-base mode | all/selected/none is server-authoritative and snapshotted |
| Dataset upload | JSON, JSONL, CSV, XLSX, XLS; maximum 10,485,760 bytes and normalize before completed |
| IntelliQ URL | accept root or `/api/v1`, store service root, reject docs/Swagger/userinfo/query/fragment |

## Project Structure

### Documentation (this feature)

```text
specs/001-rag-system-integration/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── smart-eval-rag-integration.openapi.yaml
│   └── rag-provider-result.schema.json
├── references/
│   └── intelliq-api-contract.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── app.py
├── evaluation_db.py                 # active REST routes and task runner integration
├── config.py                        # new credential/allowlist/runtime settings
├── db.py                            # active managers and provider-aware queries
├── models/
│   └── database.py                  # schema migrations and persistence primitives
├── services/
│   ├── evaluation_service.py        # provider-neutral scoring orchestration
│   ├── ai_dataset_generator.py      # remains RAGFlow-only via capability gate
│   ├── credential_cipher.py         # new encrypted credential boundary
│   └── rag_providers/
│       ├── __init__.py
│       ├── base.py                  # protocol and normalized domain results
│       ├── factory.py
│       ├── ragflow.py
│       ├── intelliq.py
│       ├── sse.py
│       └── url_policy.py
└── tests/
    ├── conftest.py                  # temporary DB and mock upstream fixtures
    ├── unit/
    │   ├── test_credential_cipher.py
    │   ├── test_url_policy.py
    │   ├── test_intelliq_sse.py
    │   └── test_scoring_eligibility.py
    ├── contract/
    │   ├── test_rag_connections_api.py
    │   ├── test_resources_api.py
    │   └── test_tasks_reports_api.py
    ├── integration/
    │   ├── test_intelliq_task_flow.py
    │   ├── test_ragflow_legacy_flow.py
    │   └── test_database_migrations.py
    └── fixtures/
        └── sse/

frontend/
├── src/
│   ├── components/
│   │   ├── RagConnectionForm.tsx
│   │   └── EvaluationTaskForm.tsx
│   ├── pages/
│   │   ├── Settings.tsx
│   │   ├── Datasets.tsx
│   │   ├── Tasks.tsx
│   │   └── Reports.tsx
│   └── services/
│       └── evaluation.ts            # provider-aware types and internal API client
└── package.json

.env.example                         # encryption key and exact-host allowlist guidance
Dockerfile                           # copies new backend modules; dependency install unchanged structurally
docker-compose.yml                   # passes environment values through existing env_file
backup.sh                            # must not archive credential/admin secrets with encrypted DB
```

**Structure Decision**: 保留当前 Flask + React 双目录结构和单容器部署。新模块只在活动 backend service path 中增加 provider、凭据和测试边界；前端通过共享 task form 和统一 service types 集中 provider 逻辑。`api_optimized.py` 与 `services/unified.py` 不作为实施目标，除非后续单独决定删除或合并重复架构。

## Phase 0 Output

- [research.md](research.md)
- 所有 Technical Context 未知项已解决。
- IntelliQ 外部契约仍要求在目标部署 Swagger 上做实现前复核，但该动作是验证任务，不是未解决的设计选择。

## Phase 1 Output

- [data-model.md](data-model.md)
- [contracts/smart-eval-rag-integration.openapi.yaml](contracts/smart-eval-rag-integration.openapi.yaml)
- [contracts/rag-provider-result.schema.json](contracts/rag-provider-result.schema.json)
- [quickstart.md](quickstart.md)

## Implementation Sequence

1. 修正 `DATABASE_PATH` 持久化、旧数据库检测、WAL/busy timeout，再建立 schema migration、连接表、审计表、sample run 和历史 backfill。
2. 建立 credential cipher、URL policy、provider protocol 和 normalized result。
3. 实现 RAGFlow adapter 并用旧流程回归，先证明 adapter 抽象不改变现有行为。
4. 实现 IntelliQ 资源发现、SSE 解析、session 隔离和错误分类。
5. 增加管理员令牌保护的连接写 API、资源 REST API 和 OpenAPI contract tests。
6. 修复五种数据集格式的上传前 10 MiB 校验、统一归一化和临时文件清理。
7. 扩展任务创建、Agent 知识库模式校验、执行、取消、最终 attempt 聚合、部分失败 warning 和评分资格。
8. 扩展报告来源、筛选、成功/失败计数和详细样本结果；全部失败时不创建最终报告。
9. 更新前端类型和 Settings RAG 系统配置。
10. 提取共享任务表单，并更新 Datasets/Tasks/Reports provider 交互；仅 selected 模式展示知识库多选，all/none 清空选择。
11. 移除核心页面 `@ts-nocheck`，完成 typecheck/build/Playwright 验证。
12. 完成 Docker 持久化重建、备份敏感信息边界、发布脚本、真实 IntelliQ 和旧 RAGFlow 回归。

## Complexity Tracking

没有 constitution violation。新增 provider adapter、连接实体和 sample run 表是满足多 provider 隔离、密钥保护、SSE 完成语义和样本级追溯的最小必要复杂度；未引入新服务、消息队列或第二套前端设计系统。
