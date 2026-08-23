# Tasks: 数据集样本分页预览

**Input**: Design documents from `/specs/006-dataset-sample-pagination/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/dataset-sample-pagination.md, quickstart.md

**Tests**: 后端样本分页契约测试由计划明确要求；前端当前没有专用单元测试脚本，因此使用类型检查、生产构建和 quickstart 浏览器验收。

**Organization**: 任务按用户故事分组。由于所有 UI 工作集中在 `frontend/src/pages/Datasets.tsx`，该文件内的实现任务必须顺序执行，避免并行编辑冲突。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可与其他标记为 `[P]` 的任务并行执行（文件和前置依赖均不冲突）
- **[Story]**: 对应 spec.md 中的用户故事
- 每项任务均包含明确文件路径

## Phase 1: Setup（共享准备）

**Purpose**: 确认现有样本读取契约和预览入口，使实现严格复用已有分页能力。

- [X] T001 Review the existing sample route in `backend/evaluation_db.py`, response client in `frontend/src/services/evaluation.ts`, and preview flow in `frontend/src/pages/Datasets.tsx`; record that the implementation must use `offset`, `limit`, and `total` without adding a new endpoint.

---

## Phase 2: Foundational（阻塞性基础）

**Purpose**: 让前端拥有可类型化的分页响应，作为所有预览分页行为的单一数据契约。

**⚠️ CRITICAL**: 完成此阶段前不得开始样本预览 UI 实现。

- [X] T002 Define and use a typed dataset-sample page response containing `samples`, `total`, `limit`, and `offset` in `frontend/src/services/evaluation.ts`; keep the existing request parameters backward compatible.

**Checkpoint**: 前端可安全读取样本总数、实际偏移量和页大小；无需修改数据库、样本内容或后端路由。

---

## Phase 3: User Story 1 - 分页预览数据集样本（Priority: P1）🎯 MVP

**Goal**: 用户首次打开预览时只看到 5 条样本，并可通过分页浏览所有后续样本。

**Independent Test**: 对包含 12 条样本的数据集，样本读取契约在偏移量 0、5、10 时分别返回 5、5、2 条；UI 第 1、2、3 页分别显示样本 1–5、6–10、11–12。

### Tests for User Story 1

- [X] T003 [P] [US1] Add pagination contract coverage in `backend/tests/contract/test_dataset_samples_api.py` for a 12-sample dataset: verify `limit=5` with offsets 0, 5, and 10 returns 5, 5, and 2 samples and always reports `total=12`.

### Implementation for User Story 1

- [X] T004 [US1] Add fixed page-size, current-page, total-sample, current-offset, and request-identity state for the preview in `frontend/src/pages/Datasets.tsx`; model the state defined in `specs/006-dataset-sample-pagination/data-model.md` without persisting it.
- [X] T005 [US1] Refactor preview loading in `frontend/src/pages/Datasets.tsx` so opening a dataset loads page 1 with `limit=5`, changing pages loads `(page - 1) × 5`, and only the response matching the active dataset and page updates preview state.
- [X] T006 [US1] Render controlled pagination and continuous sample ordinals in the `数据样例` tab of `frontend/src/pages/Datasets.tsx`; each page must display at most 5 samples, and the last page must display only remaining samples.
- [X] T007 [US1] Run the focused backend contract test in `backend/tests/contract/test_dataset_samples_api.py` and perform the 12-sample page-1/page-2/page-3 scenario in `specs/006-dataset-sample-pagination/quickstart.md`.

**Checkpoint**: P1 is complete when a >5 sample dataset can be previewed page by page with exactly 5 samples per non-final page.

---

## Phase 4: User Story 2 - 明确了解预览范围和样本总量（Priority: P2）

**Goal**: 用户在预览中可辨识当前页、连续样本范围和总样本数。

**Independent Test**: 对 12 条样本，预览显示总数和当前页信息；第 3 页可辨识为最后一页并只显示剩余 2 条。

### Implementation for User Story 2

- [X] T008 [US2] Add current-page, total-sample, and page-range feedback to the pagination area in `frontend/src/pages/Datasets.tsx`, using the typed `total`, `limit`, and `offset` returned by `frontend/src/services/evaluation.ts`.
- [X] T009 [US2] Verify the 12-sample total/page/range acceptance scenario in `specs/006-dataset-sample-pagination/quickstart.md`, including continuous sample numbering across pages.

**Checkpoint**: P1 and P2 are complete when users can navigate and clearly understand which subset of the dataset they are viewing.

---

## Phase 5: User Story 3 - 小数据集和异常状态的友好处理（Priority: P3）

**Goal**: 空数据、小数据集、加载失败、快速切换和样本总数变化不会产生无效页码或显示旧页面内容。

**Independent Test**: 分别预览 0、3、5、6 条样本的数据集，并在页面加载时切换数据集或关闭预览；验证空状态、分页可用性、首屏重置和过期响应保护均正确。

### Implementation for User Story 3

- [X] T010 [US3] Update preview open, close, dataset-switch, and page-change handling in `frontend/src/pages/Datasets.tsx` to reset to page 1 when required, clear obsolete page data, and clamp an out-of-range page to a valid first page when the reported total changes.
- [X] T011 [US3] Add explicit empty and page-load error behavior in the `数据样例` tab of `frontend/src/pages/Datasets.tsx`; hide or disable invalid pagination actions and ensure a failed or stale response cannot be rendered as current-page content.
- [X] T012 [US3] Execute the 0-, 3-, 5-, and 6-sample plus rapid-switch scenarios in `specs/006-dataset-sample-pagination/quickstart.md` and record any deviations before release.

**Checkpoint**: 所有用户故事完成；边界情况不会展示无效页码、重复样本或来自另一数据集的旧响应。

---

## Phase 6: Polish & Cross-Cutting Validation

**Purpose**: 验证契约、前端构建和完整用户流程，并确保范围没有扩展到数据集生命周期之外。

- [X] T013 [P] Run the complete backend test suite with `backend/tests/` after adding `backend/tests/contract/test_dataset_samples_api.py` coverage.
- [X] T014 [P] Run `npm run typecheck` and `npm run build` from `frontend/` after updating `frontend/src/pages/Datasets.tsx` and `frontend/src/services/evaluation.ts`.
- [X] T015 Run all end-to-end scenarios in `specs/006-dataset-sample-pagination/quickstart.md`, then run `git diff --check`; confirm no changes were made outside `frontend/src/pages/Datasets.tsx`, `frontend/src/services/evaluation.ts`, `backend/tests/contract/test_dataset_samples_api.py`, and ignore rules in `.gitignore`/`.dockerignore` unless required to fix a discovered contract defect.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 可立即执行。
- **Phase 2 (Foundational)**: 依赖 T001；阻塞所有预览分页 UI 工作。
- **Phase 3 (US1)**: 依赖 T002；T003 可在 T002 完成后并行准备，T004–T006 必须按顺序编辑 `frontend/src/pages/Datasets.tsx`。
- **Phase 4 (US2)**: 依赖 US1 的 T004–T006；在已工作的分页界面上补充范围和总量反馈。
- **Phase 5 (US3)**: 依赖 US1；因与 US1/US2 共同编辑 `frontend/src/pages/Datasets.tsx`，建议在 T008 后顺序执行。
- **Phase 6 (Polish)**: 依赖所有目标用户故事完成。

### User Story Dependencies

- **US1 (P1)**: MVP；只依赖分页响应类型（T002）。
- **US2 (P2)**: 依赖 US1 的分页状态和 UI；不改变样本读取契约。
- **US3 (P3)**: 依赖 US1 的页面加载流程；负责边界状态和过期响应安全。

### Within Each User Story

- 必要的后端契约测试先于或与 UI 实现并行准备，并在完成后验证。
- 同一 `frontend/src/pages/Datasets.tsx` 文件的任务必须顺序完成。
- 完成每个用户故事后运行其独立测试标准，再进入下一优先级阶段。

## Parallel Opportunities

- T003 与 T002 后的 UI 状态设计可由不同人员并行处理，因为分别修改 `backend/tests/contract/test_dataset_samples_api.py` 与前端文件。
- T013（后端测试）和 T014（前端类型检查/构建）可在全部实现完成后并行执行。
- 其他实现任务主要集中在 `frontend/src/pages/Datasets.tsx`，不应并行修改。

## Parallel Example: User Story 1

```text
# 完成 T002 后，可并行进行：
Task: "Add pagination contract coverage in backend/tests/contract/test_dataset_samples_api.py"
Task: "Add fixed preview pagination state in frontend/src/pages/Datasets.tsx"

# 然后按顺序完成同一前端文件的加载与渲染任务：
Task: "Refactor preview loading in frontend/src/pages/Datasets.tsx"
Task: "Render controlled pagination in frontend/src/pages/Datasets.tsx"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 T001–T002，确认可用的样本分页数据契约。
2. 完成 T003–T006，实现固定每页 5 条的服务端分页预览。
3. 执行 T007，使用 12 条样本独立验证分页正确性。
4. 如需要，可在此时交付 MVP；US2 与 US3 仅增强可理解性和边界可靠性。

### Incremental Delivery

1. Setup + Foundational → 前端具备正确分页响应类型。
2. US1 → 固定 5 条分页预览可用。
3. US2 → 显示总量、页码和样本范围。
4. US3 → 处理空数据、小数据集、失败与过期响应。
5. Phase 6 → 完整回归和 quickstart 验收。

## Notes

- `[P]` 表示文件与依赖不冲突时可并行执行。
- `[US1]`、`[US2]`、`[US3]` 提供从任务到规格用户故事的可追溯性。
- 页面大小固定为 5；不得为本功能新增自定义页大小、数据集内容修改或新的样本读取端点。
