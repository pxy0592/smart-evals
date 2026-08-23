# Tasks: 修复评测任务创建

**Input**: Design documents from `/specs/007-fix-task-creation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/task-creation.md, quickstart.md

**Tests**: 计划明确要求 pytest 覆盖请求级异步资源范围、连续 IntelliQ 创建、失败不落库和 RAGFlow 回归；前端使用类型检查和生产构建进行回归验证。

**Organization**: 任务按用户故事分组。`backend/evaluation_db.py` 的异步运行器、任务创建和资源路由共享同一文件，相关实现任务必须顺序执行。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可与其他标记为 `[P]` 的任务并行执行（文件和依赖不冲突）
- **[Story]**: 对应 spec.md 中的用户故事
- 每项任务均包含明确文件路径

## Phase 1: Setup（共享准备）

**Purpose**: 锁定现有故障路径和不应变化的范围。

- [X] T001 Review the async bridge, task-creation validation, and resource routes in `backend/evaluation_db.py`; record every provider operation that currently crosses a separately created event loop and must be moved into a request-scoped provider operation.

---

## Phase 2: Foundational（阻塞性基础）

**Purpose**: 建立请求级提供者运行/清理边界，避免 aiohttp 客户端跨已关闭事件循环复用。

**⚠️ CRITICAL**: 完成此阶段前不得改造任务创建或资源路由调用方式。

- [X] T002 Implement a single-loop provider-operation helper in `backend/evaluation_db.py` that creates/uses/closes one provider within the same event loop and preserves non-sensitive structured failures for callers.
- [X] T003 [P] Add loop-scope lifecycle tests in `backend/tests/unit/test_async_provider_scope.py` proving provider cleanup completes before its event loop is closed and a subsequent operation receives a fresh valid scope.

**Checkpoint**: 所有后端调用点均可在单个请求级异步范围内执行多个提供者操作并完成清理，不复用已关闭循环绑定的客户端资源。

---

## Phase 3: User Story 1 - 成功创建 IntelliQ 评测任务（Priority: P1）🎯 MVP

**Goal**: 有效 IntelliQ 目标可连续创建评测任务，不再出现 `Event loop is closed`。

**Independent Test**: 使用 `selected` 模式 IntelliQ 智能体连续创建任务，验证每次返回 pending 任务，且任务记录包含选择的智能体与知识库快照。

### Tests for User Story 1

- [X] T004 [P] [US1] Add consecutive IntelliQ task-creation regression coverage in `backend/tests/contract/test_tasks_api.py` that exercises assistant lookup and selected knowledge-base validation twice without an event-loop error.
- [X] T005 [P] [US1] Add an integration scenario in `backend/tests/integration/test_intelliq_task_flow.py` that creates 10 valid IntelliQ tasks sequentially using one connection fixture and asserts 10 persisted pending tasks.

### Implementation for User Story 1

- [X] T006 [US1] Refactor the IntelliQ branch of `create_evaluation_task()` in `backend/evaluation_db.py` so assistant lookup, configured knowledge-base lookup, validation, and provider cleanup execute in one request-scoped provider operation.
- [X] T007 [US1] Preserve the selected assistant, knowledge-base IDs, names, connection revision, and mode snapshots when `backend/evaluation_db.py` persists a successfully validated task.
- [X] T008 [US1] Run the focused task-creation tests in `backend/tests/contract/test_tasks_api.py` and `backend/tests/integration/test_intelliq_task_flow.py` to verify the MVP independently.

**Checkpoint**: 有效 IntelliQ `selected` 目标可以连续创建任务；每个任务均为 pending 且不存在事件循环错误。

---

## Phase 4: User Story 2 - 获得可操作的创建失败反馈（Priority: P2）

**Goal**: 创建前资源或配置失败返回安全、可理解的结构化结果，并且不留下不完整任务。

**Independent Test**: 模拟 IntelliQ 权限、上游和内部生命周期失败，验证响应不含 traceback、类别正确、数据库中没有新增任务。

### Tests for User Story 2

- [X] T009 [P] [US2] Extend `backend/tests/contract/test_tasks_api.py` with permission, upstream, and internal-lifecycle failure cases that assert a structured error response and unchanged task count.

### Implementation for User Story 2

- [X] T010 [US2] Update create-task error handling in `backend/evaluation_db.py` to map expected provider failures into validation, permission, or upstream responses and to convert unexpected lifecycle failures into a non-sensitive internal error response.
- [X] T011 [US2] Add non-sensitive request diagnostics in `backend/evaluation_db.py` that associate creation failures with connection ID, assistant ID, and selected knowledge-base IDs without recording credentials or stack traces in API responses.
- [X] T012 [US2] Run the invalid-target scenarios in `specs/007-fix-task-creation/quickstart.md` and confirm no incomplete task records are created.

**Checkpoint**: 用户可区分配置/权限/上游失败；内部事件循环细节不出现在 API 响应中；失败请求不落库。

---

## Phase 5: User Story 3 - 保持既有资源选择与评测流程可用（Priority: P3）

**Goal**: 请求级生命周期修复不破坏 IntelliQ 资源列表、后续评测执行或 RAGFlow 流程。

**Independent Test**: 连续读取 IntelliQ 助手和知识库资源后创建任务，并执行 RAGFlow 创建任务回归用例。

### Tests for User Story 3

- [X] T013 [P] [US3] Add resource-route lifecycle regression coverage in `backend/tests/contract/test_resources_api.py` for repeated IntelliQ assistant and assistant-scoped knowledge-base requests.
- [X] T014 [P] [US3] Add or extend RAGFlow task-creation regression coverage in `backend/tests/contract/test_tasks_api.py` to prove its existing creation contract remains unchanged.

### Implementation for User Story 3

- [X] T015 [US3] Refactor IntelliQ resource routes in `backend/evaluation_db.py` to use the request-scoped provider helper for list-assistants and list-knowledge-bases operations, including cleanup in the same event loop.
- [X] T016 [US3] Keep the legacy RAGFlow route and task-creation paths in `backend/evaluation_db.py` outside IntelliQ-specific lifecycle handling, preserving their existing behavior.
- [X] T017 [US3] Execute the resource and RAGFlow regression scenarios in `specs/007-fix-task-creation/quickstart.md`.

**Checkpoint**: IntelliQ resources still load correctly, valid created tasks can proceed to evaluation, and RAGFlow creation remains unaffected.

---

## Phase 6: Polish & Cross-Cutting Validation

**Purpose**: 验证完整后端回归、前端兼容性、Docker 运行时和 quickstart 场景。

- [X] T018 [P] Run the complete backend suite under `backend/tests/`, including new request-scope, task-creation, and resource-route tests.
- [X] T019 [P] Run backend compile and shell checks for `backend/` and root `*.sh`, then run `git diff --check`.
- [X] T020 [P] Run `npm run typecheck` and `npm run build` from `frontend/` to verify `frontend/src/components/EvaluationTaskForm.tsx` and `frontend/src/services/evaluation.ts` remain compatible.
- [X] T021 Rebuild and start the Docker image from `Dockerfile`, verify `/health`, and complete the valid, invalid, consecutive-creation, resource-loading, and RAGFlow checks in `specs/007-fix-task-creation/quickstart.md`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 可立即执行。
- **Phase 2 (Foundational)**: 依赖 T001；阻塞所有调用点改造。
- **Phase 3 (US1)**: 依赖 T002；T004–T005 可在 T002 后并行准备，T006–T007 顺序修改 `backend/evaluation_db.py`。
- **Phase 4 (US2)**: 依赖 US1 的创建范围实现；T009 可在 T006 后并行编写。
- **Phase 5 (US3)**: 依赖 T002；因共享 `backend/evaluation_db.py`，建议在 US1/US2 的同文件实现完成后顺序执行。
- **Phase 6 (Polish)**: 依赖全部目标用户故事。

### User Story Dependencies

- **US1 (P1)**: MVP；依赖请求级 provider 生命周期基础。
- **US2 (P2)**: 依赖 US1 的创建路径，用于确保失败安全且不落库。
- **US3 (P3)**: 依赖基础生命周期实现；与 US1/US2 共享后端文件，顺序集成以避免冲突。

### Within Each User Story

- 明确要求的测试任务先于对应实现任务完成。
- `backend/evaluation_db.py` 任务必须顺序编辑。
- 完成每个用户故事后执行其独立验证，再进入下一优先级阶段。

## Parallel Opportunities

- T003 与 T002 的实现可并行，因为测试与实现文件不同。
- T004、T005 可在 T002 后并行准备，分别修改契约和集成测试文件。
- T009 可在 US1 创建范围完成后与其错误处理准备并行。
- T013、T014 可并行，因为分别覆盖资源路由与 RAGFlow 回归。
- T018、T019、T020 可在所有实现完成后并行执行。

## Parallel Example: User Story 1

```text
# 完成 T002 后，可并行进行：
Task: "Add consecutive IntelliQ task-creation coverage in backend/tests/contract/test_tasks_api.py"
Task: "Add 10-task IntelliQ integration coverage in backend/tests/integration/test_intelliq_task_flow.py"

# 然后顺序修改共享任务创建路径：
Task: "Refactor create_evaluation_task() in backend/evaluation_db.py"
Task: "Preserve validated task snapshots in backend/evaluation_db.py"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 T001–T003，建立并验证请求级 provider 生命周期。
2. 完成 T004–T007，修复 IntelliQ 创建任务路径。
3. 执行 T008，验证有效目标可连续创建任务。
4. 如需要，可在此处交付阻塞问题的 MVP。

### Incremental Delivery

1. Setup + Foundational → 提供者资源不会跨关闭事件循环复用。
2. US1 → 有效 IntelliQ 任务可连续创建。
3. US2 → 失败安全、无半成品任务、用户可操作反馈。
4. US3 → 资源加载与 RAGFlow 回归保护。
5. Phase 6 → 全量验证和 Docker 验收。

## Notes

- `[P]` 表示文件和前置依赖不冲突时可并行执行。
- `[US1]`、`[US2]`、`[US3]` 提供从任务到规格用户故事的追溯。
- 禁止通过不关闭事件循环或向浏览器暴露 IntelliQ 凭证来规避问题。
