# Tasks: 恢复可恢复 SSE 工具错误

**Input**: Design documents from `/specs/008-recover-sse-tool-errors/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/sse-tool-diagnostics.md, quickstart.md

**Tests**: 计划明确要求 SSE 单元测试、样本运行/报告持久化测试和正常/终止流回归；前端类型检查与构建用于新增结果字段兼容性回归。

**Organization**: 任务按用户故事分组。SSE 聚合、结果数据模型、评测服务和样本运行持久化形成顺序数据流，涉及同一文件的任务必须顺序执行。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可与其他标记为 `[P]` 的任务并行执行（文件和依赖不冲突）
- **[Story]**: 对应 spec.md 中的用户故事
- 每项任务均包含明确文件路径

## Phase 1: Setup（共享准备）

**Purpose**: 确认当前 SSE 事件分类、样本结果传递和样本运行持久化路径。

- [X] T001 Review error handling in `backend/services/rag_providers/sse.py`, result fields in `backend/services/rag_providers/base.py`, persistence in `backend/models/database.py`, and report/result propagation in `backend/services/evaluation_service.py` and `backend/evaluation_db.py`.

---

## Phase 2: Foundational（阻塞性基础）

**Purpose**: 定义工具错误诊断的数据契约和历史数据兼容策略，作为恢复成功和报告审计的共同基础。

**⚠️ CRITICAL**: 完成此阶段前不得改变 SSE error 终止行为。

- [X] T002 Add a bounded, non-sensitive tool-error diagnostic contract to `backend/services/rag_providers/base.py`, including fields for tool call identity, tool name, message, recovery state, and duplicate-event count.
- [X] T003 [P] Add database migration and persistence coverage for optional sample-run tool diagnostics in `backend/models/database.py` and `backend/tests/integration/test_database_migrations.py`.

**Checkpoint**: 查询结果、样本运行和历史数据库均可兼容读取空或已存在的工具错误诊断。

---

## Phase 3: User Story 1 - 接受工具错误后的最终成功回答（Priority: P1）🎯 MVP

**Goal**: 工具错误后只要智能体产生完整最终答案，样本仍成功并可进入评分。

**Independent Test**: 模拟两次工具错误、一次成功工具结果和最终完成答案；验证结果成功、答案完整、两条诊断被保留且标记为已恢复。

### Tests for User Story 1

- [X] T004 [P] [US1] Add recovered-tool-error SSE fixtures in `backend/tests/unit/test_intelliq_sse.py` covering two `done=false` tool errors followed by final answer and complete events.
- [X] T005 [P] [US1] Add evaluation workflow coverage in `backend/tests/integration/test_intelliq_task_flow.py` that preserves a recovered successful result as score-eligible with tool diagnostics.

### Implementation for User Story 1

- [X] T006 [US1] Refactor `aggregate_intelliq_sse()` in `backend/services/rag_providers/sse.py` to classify unfinished tool-associated errors as recoverable, merge diagnostics by the contract key, and continue consuming the stream.
- [X] T007 [US1] Update `RagQueryResult` construction in `backend/services/rag_providers/sse.py` and `backend/services/rag_providers/base.py` so final non-empty answer completion marks recovered diagnostics as recovered and preserves answer, references, contexts, and event counts.
- [X] T008 [US1] Propagate recovered diagnostics through successful sample details in `backend/services/evaluation_service.py` without changing score eligibility for a completed non-empty answer.
- [X] T009 [US1] Run the focused recovery tests in `backend/tests/unit/test_intelliq_sse.py` and `backend/tests/integration/test_intelliq_task_flow.py`.

**Checkpoint**: 可恢复工具错误不再提前终止样本；最终答案被保留并可进入评分。

---

## Phase 4: User Story 2 - 保持真正终止错误为失败（Priority: P2）

**Goal**: 恢复策略不会将终止错误、协议错误或无最终答案流误记为成功。

**Independent Test**: 明确完成的 error、非工具 error、工具错误后无答案、以及截断答案流都失败，并保留正确最终错误。

### Tests for User Story 2

- [X] T010 [P] [US2] Extend `backend/tests/unit/test_intelliq_sse.py` with terminal error, non-tool error, duplicate tool error, empty completion, and incomplete stream cases.

### Implementation for User Story 2

- [X] T011 [US2] Implement terminal-error and complete-event rules in `backend/services/rag_providers/sse.py`, ensuring only a complete non-empty answer can override earlier recoverable diagnostics.
- [X] T012 [US2] Preserve final failure details and mark unrecovered diagnostics in `backend/services/evaluation_service.py` for failed sample results.
- [X] T013 [US2] Run terminal-flow scenarios from `specs/008-recover-sse-tool-errors/quickstart.md` and verify they remain non-score-eligible.

**Checkpoint**: 真正失败仍失败；恢复成功不会掩盖后续终止错误；空答案永不进入评分。

---

## Phase 5: User Story 3 - 在报告中保留可审计工具诊断（Priority: P3）

**Goal**: 样本运行、任务详情和报告详情均可区分恢复成功与最终失败，并显示去重后的非敏感工具诊断。

**Independent Test**: 恢复成功样本在样本运行和报告详情中展示已恢复工具错误；最终失败样本展示未恢复诊断与最终错误；历史无字段记录可正常读取。

### Tests for User Story 3

- [X] T014 [P] [US3] Add sample-run persistence and backward-compatible read coverage in `backend/tests/integration/test_database_migrations.py` for `tool_errors`.
- [X] T015 [P] [US3] Add task/report response compatibility coverage in `backend/tests/contract/test_reports_api.py` and `backend/tests/integration/test_report_persistence.py` for recovered and unrecovered tool diagnostics.

### Implementation for User Story 3

- [X] T016 [US3] Persist and decode tool diagnostics in `backend/models/database.py` and `backend/db.py` for evaluation sample runs while treating missing historical values as an empty list.
- [X] T017 [US3] Include `tool_errors` in completed and failed detailed results in `backend/services/evaluation_service.py` and in task/report response assembly in `backend/evaluation_db.py`.
- [X] T018 [US3] Verify `frontend/src/services/evaluation.ts` and `frontend/src/pages/Reports.tsx` remain compatible with additive diagnostics, adding type/render support only if required for existing report consumers.
- [X] T019 [US3] Run the report and sample-run diagnostic scenarios in `specs/008-recover-sse-tool-errors/quickstart.md`.

**Checkpoint**: 用户可审计恢复工具错误；历史报告与样本运行继续可读；敏感原始工具参数未被持久化。

---

## Phase 6: Polish & Cross-Cutting Validation

**Purpose**: 验证正常流、恢复流、终止流、数据库迁移和 Docker 运行时不回归。

- [X] T020 [P] Run the complete backend suite under `backend/tests/`, including SSE, sample-run migration, report, task-flow, and secret-redaction tests.
- [X] T021 [P] Run backend compile and shell checks for `backend/` and root `*.sh`, then run `git diff --check`.
- [X] T022 [P] Run `npm run typecheck` and `npm run build` from `frontend/` to verify report consumers remain compatible.
- [X] T023 Rebuild and start the Docker image from `Dockerfile`, verify `/health`, and complete recovered-flow and terminal-flow checks in `specs/008-recover-sse-tool-errors/quickstart.md`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 可立即执行。
- **Phase 2 (Foundational)**: 依赖 T001；阻塞聚合器、评测服务和持久化变更。
- **Phase 3 (US1)**: 依赖 T002；T004–T005 可在基础契约完成后并行编写，T006–T008 按数据流顺序实施。
- **Phase 4 (US2)**: 依赖 US1 聚合器改造；确保恢复规则不改变终止失败语义。
- **Phase 5 (US3)**: 依赖 US1/US2 最终结果形态；T014–T015 可并行准备，T016–T018 按持久化到消费顺序实施。
- **Phase 6 (Polish)**: 依赖所有目标用户故事完成。

### User Story Dependencies

- **US1 (P1)**: MVP；依赖基础工具诊断契约。
- **US2 (P2)**: 依赖 US1 的恢复分类，确保失败边界不回归。
- **US3 (P3)**: 依赖 US1/US2 的最终结果，负责持久化和展示兼容性。

### Within Each User Story

- 明确要求的测试先于对应实现任务完成。
- `backend/services/rag_providers/sse.py` 的恢复与终止规则必须顺序修改。
- 成功和失败结果传播完成后再修改持久化与报告消费者。

## Parallel Opportunities

- T003 可与 T002 并行准备，因为分别修改数据库测试和结果数据契约。
- T004 与 T005 可并行，因为分别覆盖 SSE 单元流和评测工作流。
- T010 可与 US1 完成后的结果传播准备并行。
- T014 与 T015 可并行，因为分别覆盖样本运行迁移和报告契约。
- T020、T021、T022 可在全部实现完成后并行执行。

## Parallel Example: User Story 1

```text
# 完成 T002 后，可并行进行：
Task: "Add recovered-tool-error SSE fixtures in backend/tests/unit/test_intelliq_sse.py"
Task: "Add recovered result workflow coverage in backend/tests/integration/test_intelliq_task_flow.py"

# 然后按数据流顺序完成：
Task: "Refactor aggregate_intelliq_sse() in backend/services/rag_providers/sse.py"
Task: "Propagate recovered diagnostics in backend/services/evaluation_service.py"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 T001–T003，定义工具诊断和数据库兼容边界。
2. 完成 T004–T008，使恢复后的最终答案成功进入评分。
3. 执行 T009，验证浏览器中观察到的“工具错误后修正并回答”流程不再被误判失败。
4. 如需要，可先交付 MVP；US2 和 US3 再补强失败边界与审计能力。

### Incremental Delivery

1. Setup + Foundational → 可安全表示工具诊断。
2. US1 → 恢复工具错误后的最终答案成功。
3. US2 → 真正终止错误与空答案仍失败。
4. US3 → 运行记录和报告中可审计恢复诊断。
5. Phase 6 → 完整回归和 Docker 验收。

## Notes

- `[P]` 表示文件和前置依赖不冲突时可并行执行。
- `[US1]`、`[US2]`、`[US3]` 提供从任务到规格用户故事的追溯。
- 不允许通过忽略终止错误、重放 IntelliQ 工具调用或持久化原始工具参数来实现恢复。
