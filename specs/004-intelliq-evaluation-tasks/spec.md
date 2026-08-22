# Feature Specification: 允许向 IntelliQ 系统发起评测任务

**Feature Branch**: `004-intelliq-evaluation-tasks`

**Created**: 2026-08-22

**Status**: Draft

**Input**: User description: "允许向 IntelliQ 系统发起评测任务。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 创建 IntelliQ 评测任务并获取完整报告 (Priority: P1) 🎯 MVP

用户已配置 IntelliQ 连接，连接状态正常，且已准备好已完成的数据集。用户在任务创建页面选择 IntelliQ 连接，挑选对应的 Agent 和知识库，选择评测指标后提交任务。系统通过 IntelliQ SSE 接口逐条向 Agent 提问，收集回答和上下文，完成评分后生成包含成功/失败明细的评测报告。

**Why this priority**: 这是评测功能的核心价值——让用户能够对 IntelliQ 知识库进行质量评估。当前该系统已具备后端基础设施（provider-aware 路由、SSE 查询、评分引擎），需要验证端到端流程完整可用。

**Independent Test**: 准备一个已验证的 IntelliQ 连接和一个已完成的评测数据集，创建评测任务，等待任务完成，查看评测报告确认包含评分数据和成功/失败明细。

**Acceptance Scenarios**:

1. **Given** IntelliQ 连接已配置且状态为 available，用户已打开创建评测任务对话框，**When** 用户在 RAG 系统下拉框中选择 IntelliQ 连接，**Then** 系统加载该连接下的 Agent 列表，确认 Agent 的知识库选择模式，并相应展示知识库选择器或提示信息
2. **Given** 用户已选择 IntelliQ 连接、Agent、知识库和数据集，**When** 用户提交评测任务，**Then** 系统创建任务并开始异步执行，任务列表显示"运行中"状态
3. **Given** 评测任务正在执行，**When** 所有样本处理完毕，**Then** 系统生成包含总分、各指标得分、成功样本数、失败样本数及失败原因的评测报告
4. **Given** 评测任务中有部分样本因 IntelliQ 超时或流中断而失败，**When** 任务完成，**Then** 报告仍正常生成，体现成功样本的评分和失败样本的明细

---

### User Story 2 - 任务状态跟踪与进度反馈 (Priority: P1)

用户在评测任务列表页可以实时查看 IntelliQ 评测任务的状态变化（等待中 → 运行中 → 已完成/失败），看到进度百分比和已处理样本数。

**Why this priority**: 评测任务可能需要数分钟，用户需要实时了解进展，与创建任务共同形成完整闭环。

**Independent Test**: 创建一个 IntelliQ 评测任务，在任务列表页观察状态从 pending 变为 running，进度百分比递增，最终变为 completed 或 failed。

**Acceptance Scenarios**:

1. **Given** 评测任务刚提交，**When** 用户查看任务列表，**Then** 任务状态显示"等待中"，进度为 0%
2. **Given** 评测任务正在执行，**When** 用户刷新或自动轮询任务列表，**Then** 进度百分比和已处理样本数逐步更新
3. **Given** 评测任务执行完毕，**When** 用户查看任务信息，**Then** 状态变为"已完成"，显示总样本数、成功数和失败数

---

### User Story 3 - 查看评测报告详情 (Priority: P2)

用户完成 IntelliQ 评测后，可以查看详细的评测报告，包括各指标得分、逐样本的评分明细、成功和失败样本的对比。

**Why this priority**: 报告是评测的最终产出，但依赖于任务先成功执行。作为独立故事，报告功能不应因提供者类型不同而产生差异。

**Independent Test**: 对一个已完成的 IntelliQ 评测任务，点击查看报告，验证报告包含所有预期指标得分和样本明细。

**Acceptance Scenarios**:

1. **Given** 评测任务已完成，**When** 用户点击"查看报告"，**Then** 页面展示完整的评测报告，包含各指标得分和样本明细
2. **Given** 任务有部分失败样本，**When** 用户查看报告，**Then** 失败样本列表展示失败原因和原始问题

---

### Edge Cases

- IntelliQ 连接在评测任务执行期间被禁用，当前正在执行的样本返回连接错误，任务标记为失败并记录原因
- IntelliQ 连接在评测任务执行期间被修改（revision 变更），系统检测到后拒绝执行并标记任务失败
- IntelliQ Agent 的 SSE 流返回空回答，该样本被标记为失败并将 `partial_answer` 和错误原因记录到报告中
- 用户取消正在运行的 IntelliQ 评测任务，系统停止处理并标记为"已取消"
- 选中的 IntelliQ Agent 的知识库选择模式为"全部"时，用户无需手动选择知识库，系统将 Agent 的全部知识范围纳入评测
- 选中的 IntelliQ Agent 的知识库选择模式为"不使用"时，用户无需选择知识库，评测仅基于 Agent 自身能力

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 在创建评测任务时支持通过 `rag_target` 参数指定 IntelliQ 连接及其 Agent 和知识库
- **FR-002**: 系统 MUST 在评测执行时为 IntelliQ 提供者调用 SSE Agent Chat 接口获取回答和上下文
- **FR-003**: 系统 MUST 在 IntelliQ SSE 流中正确提取回答文本、引用来源和上下文信息，用于后续评分
- **FR-004**: 系统 MUST 在评测任务完成后生成包含成功/失败样本明细的评测报告，报告格式与 RAGFlow 评测一致
- **FR-005**: 系统 MUST 在评测执行期间实时更新任务进度（已处理样本数 / 总样本数）
- **FR-006**: 系统 MUST 支持用户取消正在运行的 IntelliQ 评测任务
- **FR-007**: 系统 MUST 在 IntelliQ 连接 revision 变更后拒绝执行使用旧 revision 创建的评测任务
- **FR-008**: 前端评测任务创建表单 MUST 在用户选择 IntelliQ 连接后正确加载 Agent 列表，并根据 Agent 的知识库选择模式展示或隐藏知识库选择器
- **FR-009**: 前端评测任务列表 MUST 正确展示 IntelliQ 评测任务的状态、进度和来源信息，与其他提供者保持一致

### Key Entities

- **评测任务 (EvaluationTask)**: 包含任务 ID、名称、关联的 RAG 连接、Agent、知识库、数据集、评测指标、状态、进度、创建时间。任务来源通过 `rag_provider` 和 `rag_connection_id` 字段区分
- **评测报告 (EvaluationReport)**: 包含任务 ID、各指标得分、逐样本评分明细、成功/失败样本统计、生成时间
- **样本运行记录 (SampleRun)**: 每个样本的单独执行记录，包含问题、回答、上下文、评分、完成状态

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用户从选择 IntelliQ 连接到提交评测任务的操作流程在 2 分钟内可完成
- **SC-002**: 系统在 IntelliQ API 正常响应的前提下，对 10 个样本的评测任务在 5 分钟内完成
- **SC-003**: 评测报告包含所有选定指标的得分，评分结果与相同数据集在 RAGFlow 上的评测结果具有可比性
- **SC-004**: 任务失败时，报告中展示的失败原因能够帮助用户定位问题（是连接问题、超时还是 Agent 返回空回答）
- **SC-005**: 95% 以上的 SSE 流正常响应可被正确解析为可评分样本

## Assumptions

- IntelliQ 连接已由管理员配置完成且处于 enabled 状态
- 用于评测的数据集已完成归一化处理，包含 `question` 字段
- IntelliQ Agent Chat SSE 接口的响应格式稳定，遵循当前 API 文档定义
- 评测指标（如 Faithfulness、AnswerRelevancy 等）的计算逻辑与提供者无关，已在系统中实现