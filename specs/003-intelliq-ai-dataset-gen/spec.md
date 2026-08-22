# Feature Specification: IntelliQ 支持 AI 数据集生成

**Feature Branch**: `003-intelliq-ai-dataset-gen`

**Created**: 2026-08-22

**Status**: Draft

**Input**: User description: "IntelliQ 支持 AI 数据集生成"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 基于 IntelliQ 知识库一键生成评测数据集 (Priority: P1) 🎯 MVP

用户已配置 IntelliQ 连接，连接状态正常（已验证）。用户打开数据集管理页面，点击"AI 智能生成数据集"，在连接下拉框中选择 IntelliQ 连接。系统不再提示"该连接不支持 AI 数据集生成"，而是加载该连接下的知识库列表。用户选择目标知识库、设置生成数量和问题类型后，点击"生成"，系统基于 IntelliQ 知识库的内容自动生成评测问答数据集。

**Why this priority**: 这是功能的核心价值——让 IntelliQ 用户也能使用 AI 生成功能。当前只有 RAGFlow 支持，限制了产品的适用范围。

**Independent Test**: 配置一个有效的 IntelliQ 连接，打开 AI 生成模态框，选择 IntelliQ 连接，选择知识库，提交生成请求，验证数据集成功创建并包含基于 IntelliQ 知识库内容生成的问答对。

**Acceptance Scenarios**:

1. **Given** IntelliQ 连接已配置且状态为 available，**When** 用户打开 AI 智能生成数据集模态框并展开连接下拉框，**Then** IntelliQ 连接可被选择（不禁用），且不显示"该连接不支持"警告
2. **Given** 用户选择了 IntelliQ 连接，**When** 连接下拉框值变更，**Then** 系统加载该 IntelliQ 连接下的知识库列表并显示在下拉框中
3. **Given** 用户已选择 IntelliQ 连接和知识库，并设置了生成参数，**When** 用户点击"生成"按钮，**Then** 系统从 IntelliQ 知识库获取内容片段，通过 LLM 生成指定数量的问答对，并创建新的数据集
4. **Given** AI 生成任务已提交，**When** 生成完成，**Then** 数据集列表显示新数据集，状态为"已完成"，样本数等于用户指定的数量

---

### User Story 2 - 连接能力声明与反映 (Priority: P1)

IntelliQ 连接在系统中正确声明其支持 AI 数据集生成的能力。管理后台和前端界面能够准确反映这一能力，使 IntelliQ 连接在 AI 生成场景下可用。

**Why this priority**: 能力声明是功能的入口——如果能力标识不正确，前端无法正确展示和交互。

**Independent Test**: 调用 RAG 连接列表 API，验证 IntelliQ 连接的 `capabilities.generate_dataset_from_knowledge_base` 为 `true`；前端 AI 生成模态框中选择 IntelliQ 时不显示能力不足警告。

**Acceptance Scenarios**:

1. **Given** 系统中存在一个 IntelliQ 连接，**When** 查询连接列表或连接详情，**Then** 返回的 `capabilities.generate_dataset_from_knowledge_base` 为 `true`
2. **Given** IntelliQ 连接的能力声明为支持，**When** 前端渲染 AI 生成模态框的连接选项，**Then** IntelliQ 连接在能力检查中通过，不显示警告提示

---

### User Story 3 - 后端 AI 生成路由支持连接参数 (Priority: P2)

AI 数据集生成的后端接口能够根据传入的 `connection_id` 参数区分使用哪个 RAG 系统作为知识库来源，而非始终使用 RAGFlow。

**Why this priority**: 这是后端基础设施改造，是实现 US1 的技术前提。作为独立故事，它确保后端路由能正确解析和路由到不同提供者。

**Independent Test**: 向 AI 生成 API 发送请求，传入 `connection_id` 参数指向 IntelliQ 连接，验证后端能正确解析连接并调用 IntelliQ 提供者获取知识库数据。

**Acceptance Scenarios**:

1. **Given** 请求中包含 `connection_id` 参数，**When** 后端处理 AI 生成请求，**Then** 根据 `connection_id` 解析对应的 RAG 连接及其提供者
2. **Given** 解析出的提供者是 IntelliQ，**When** 获取知识库内容，**Then** 使用 IntelliQ 提供者的 API（而非 RAGFlow API）获取数据
3. **Given** 请求中未提供 `connection_id` 或提供了无效的 `connection_id`，**When** 后端处理请求，**Then** 返回明确的错误信息

---

### Edge Cases

- IntelliQ 连接的知识库列表为空时，用户选择 IntelliQ 后知识库下拉框显示空状态提示
- IntelliQ 连接的知识库中无可用文档/chunks 时，AI 生成失败并返回有意义的错误信息
- IntelliQ 的 API 超时或返回错误时，生成任务应标记为失败而非无限等待
- 用户在生成过程中关闭模态框，后端生成任务不受影响（异步执行）
- 同时存在 RAGFlow 和 IntelliQ 连接时，两者均在 AI 生成下拉框中可选，互不干扰

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: IntelliQ 提供者 MUST 声明 `generate_dataset_from_knowledge_base: true` 能力
- **FR-002**: 系统 MUST 在返回 IntelliQ 连接摘要时，动态反映提供者的实际能力，而非硬编码为 `false`
- **FR-003**: AI 数据集生成后端接口 MUST 接受并处理 `connection_id` 参数
- **FR-004**: 系统 MUST 根据 `connection_id` 解析对应的 RAG 连接，获取其提供者类型和凭证
- **FR-005**: 当提供者为 IntelliQ 时，系统 MUST 使用 IntelliQ API 获取知识库的内容片段
- **FR-006**: 获取知识库内容后，生成流程 MUST 与现有 RAGFlow 流程一致（通过 LLM 生成问答对）
- **FR-007**: 前端 AI 生成模态框 MUST 在连接下拉框中展示 IntelliQ 连接（不禁用），并允许选择其知识库
- **FR-008**: 当 IntelliQ 知识库无可用内容时，生成任务 MUST 标记为失败并记录错误原因
- **FR-009**: 未提供 `connection_id` 或 `connection_id` 无效时，API MUST 返回 400 错误

### Key Entities

- **RAG 连接 (RagConnection)**：已存在，包含 `provider`、`api_url`、`api_key`、`capabilities` 等属性。本次变更需确保 `capabilities.generate_dataset_from_knowledge_base` 反映实际提供者能力
- **AI 生成任务 (AIDatasetGeneration)**：一次生成请求，包含 `connection_id`、`kb_id`、`sample_count`、`question_types` 参数，异步生成数据集
- **知识库内容片段 (KB Chunk)**：从知识库中提取的文本片段，作为 LLM 生成问答对的上下文材料

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用户能够在 AI 生成模态框中选择 IntelliQ 连接并进行完整的生成流程（从选择连接到数据集创建完成）
- **SC-002**: AI 生成基于 IntelliQ 知识库的数据集，生成成功率不低于 RAGFlow 同等场景
- **SC-003**: 生成的知识库问答对内容与所选 IntelliQ 知识库主题相关（非通用/模板化内容）
- **SC-004**: 从用户点击"生成"到数据集状态变为"处理中"的响应时间不超过 3 秒（异步任务即时返回）

## Assumptions

- IntelliQ API 已提供知识库内容的查询接口，能够返回文档片段（chunks）
- 现有的 LLM 调用逻辑（`AIDatasetGenerator.generate_qa_pair_with_llm`）可复用，只需替换知识库内容来源
- 前端 `generateAIDataset` API 调用已支持 `connection_id` 参数（已在前一个 feature 中实现）
- 生成任务的异步处理机制（线程池）保持不变
- IntelliQ 连接已通过验证（状态为 `available`），API 凭证有效