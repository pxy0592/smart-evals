# Feature Specification: 数据集页面按需访问 RAG 系统

**Feature Branch**: `main`

**Created**: 2026-08-22

**Status**: Draft

**Input**: User description: "访问数据集管理页面后，只请求数据集；上传数据集只上传到 Smart Eval；创建评测任务根据用户选择的系统连接；AI 智能生成数据集根据用户选择的系统加载指定系统的知识库。"

## Clarifications

### Session 2026-08-22

- Q: Are the unified RAG connection list, connection capability, knowledge base, and assistant APIs mentioned in the Assumptions already built and available, or are they part of this feature's implementation scope? → A: APIs already exist; this feature is frontend-only session-flow changes.
- Q: When a user clicks "创建评测任务" or "AI 智能生成数据集", what is the maximum acceptable load time for the connection list before the form becomes interactive? → A: Fast (<2s) — form appears immediately with skeleton loader, connections fill in.
- Q: When the user opens a task creation or AI generation modal and the connection list API call itself fails, what should the modal show? → A: Inline error with retry button inside the modal; user can retry or close.
- Q: FR-011 states the task form must decide whether to load a connection's knowledge bases based on the selected assistant's "知识库选择模式". What are the possible modes, and how do they affect the form? → A: Binary: required / optional — show picker always, but only require selection in "required" mode.
- Q: The spec references a `generate_dataset_from_knowledge_base` capability flag on connections. Is this capability field already returned by the existing connection list API? → A: Already exists in the connection API response.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 独立浏览数据集 (Priority: P1)

作为评测人员，我打开数据集管理页面时，只希望查看和管理 Smart Eval 中已有的数据集，不希望页面自动访问任何 RAG 系统，以免未配置或不可用的外部系统影响基础数据集操作。

**Why this priority**: 数据集列表是页面的基础能力。它必须在没有 RAGFlow、IntelliQ 或其他 RAG 系统连接的情况下独立可用。

**Independent Test**: 在所有 RAG 系统均未配置或不可访问的环境中打开数据集管理页面，确认数据集列表正常加载，并确认在用户执行 RAG 相关操作前没有产生连接列表、知识库或对话助手请求。

**Acceptance Scenarios**:

1. **Given** 用户进入数据集管理页面，**When** 页面完成首次加载，**Then** 系统只请求 Smart Eval 的数据集列表，不请求任何 RAG 系统连接、知识库或对话助手。
2. **Given** RAGFlow、IntelliQ 或其他连接不可用，**When** 用户进入数据集管理页面，**Then** 数据集列表、搜索、预览和删除功能仍然可用，且页面不展示与未触发 RAG 操作相关的连接错误。
3. **Given** 页面正在轮询处理中的数据集状态，**When** 定时刷新发生，**Then** 系统只刷新 Smart Eval 数据集状态，不访问任何 RAG 系统。

---

### User Story 2 - 独立上传评测数据集 (Priority: P1)

作为评测人员，我可以将评测数据集直接上传到 Smart Eval，并完成格式校验和样本归一化，而不触发任何 RAG 系统调用。

**Why this priority**: 上传的数据属于 Smart Eval 的评测资产，与外部知识库或对话助手无关，必须能够离线于 RAG 系统完成。

**Independent Test**: 在所有 RAG 系统不可用的情况下上传一个有效数据集，确认上传、校验、归一化和列表刷新成功，并确认没有外部 RAG 请求。

**Acceptance Scenarios**:

1. **Given** 用户选择有效的评测数据集文件，**When** 用户上传文件，**Then** 文件只发送到 Smart Eval，由 Smart Eval 完成保存、校验和归一化。
2. **Given** 所有 RAG 系统均不可访问，**When** 用户上传有效数据集，**Then** 上传仍然成功，并且不会出现 RAG 系统连接错误。
3. **Given** 文件格式、大小或内容不符合数据集规则，**When** Smart Eval 拒绝上传，**Then** 错误信息只描述数据集问题，不触发或归因于任何 RAG 系统。

---

### User Story 3 - 按所选连接创建评测任务 (Priority: P1)

作为评测人员，我从数据集页面点击“创建评测任务”后，可以选择目标 RAG 系统连接；系统只加载所选连接的对话助手和知识库，并使用该连接创建评测任务。

**Why this priority**: 任务必须绑定明确的 RAG 来源，且不能因为系统默认值或旧逻辑而访问用户未选择的连接。

**Independent Test**: 配置至少两个 RAG 系统连接，从一个数据集创建任务，选择其中一个连接，确认资源请求和最终任务均只属于该连接，另一个连接没有收到请求。

**Acceptance Scenarios**:

1. **Given** 用户尚未点击“创建评测任务”，**When** 数据集页面处于普通浏览状态，**Then** 系统不加载连接、对话助手、知识库或评测指标。
2. **Given** 用户点击“创建评测任务”，**When** 任务表单打开，**Then** 系统按需获取可用 RAG 系统连接和 Smart Eval 评测指标，但在用户选择连接前不获取任何连接的知识库或对话助手。
3. **Given** 用户选择一个 RAG 系统连接，**When** 选择生效，**Then** 系统只获取该连接的对话助手；知识库是否加载由所选对话助手的知识库模式决定。
4. **Given** 用户切换到另一个连接，**When** 新连接生效，**Then** 系统清除旧连接的对话助手和知识库选择，并且只加载新连接的资源。
5. **Given** 用户完成连接、对话助手、知识库模式、数据集和指标选择，**When** 用户提交任务，**Then** 任务记录所选连接及其资源，不得回退到默认 RAGFlow 或其他连接。

---

### User Story 4 - 按所选连接生成 AI 数据集 (Priority: P2)

作为评测人员，我点击“AI 智能生成数据集”后，可以选择一个支持该能力的 RAG 系统连接；系统只加载该连接的知识库，并基于该连接生成数据集。

**Why this priority**: AI 数据集生成需要外部知识来源，但该访问必须由用户动作和明确的连接选择触发，而不是页面初始化时自动触发。

**Independent Test**: 配置两个支持情况不同的 RAG 连接，打开 AI 生成弹窗，选择支持该能力的连接，确认只加载该连接的知识库并提交带连接来源的生成请求；不支持的连接不能提交。

**Acceptance Scenarios**:

1. **Given** 用户尚未点击“AI 智能生成数据集”，**When** 数据集页面加载或刷新，**Then** 系统不获取任何 RAG 系统的知识库。
2. **Given** 用户点击“AI 智能生成数据集”，**When** 弹窗打开，**Then** 系统按需获取连接列表，并明确标识哪些连接支持基于知识库生成数据集。
3. **Given** 用户选择支持 AI 数据集生成的连接，**When** 连接选择生效，**Then** 系统只加载该连接的知识库。
4. **Given** 用户选择不支持该能力的连接，**When** 用户查看或尝试继续，**Then** 系统禁用知识库选择和生成操作，并说明该连接不支持 AI 数据集生成。
5. **Given** 用户切换 AI 生成所使用的连接，**When** 新连接生效，**Then** 系统清除旧连接的知识库选择，并且只展示新连接的知识库。
6. **Given** 用户提交 AI 数据集生成请求，**When** 请求被接受，**Then** 请求必须包含所选连接和知识库身份，生成任务不得隐式使用默认 RAGFlow。

### Edge Cases

- 数据集列表请求失败时，页面应展示 Smart Eval 数据集错误，不得尝试访问 RAG 系统作为回退。
- 用户快速打开并关闭任务或 AI 生成弹窗时，未完成的资源请求不得污染下一次打开时的表单状态。
- 用户连续切换连接时，较早连接的迟到响应不得覆盖当前连接的对话助手或知识库列表。
- 已选择的连接被停用、删除或失去权限时，提交操作必须重新验证并要求用户重新选择。
- 所选连接返回空知识库或空对话助手列表时，表单应展示连接范围内的空状态，而不是请求其他连接作为回退。
- RAG 系统资源加载失败时，数据集列表、上传、预览和删除功能必须继续可用。
- AI 数据集生成连接在弹窗打开后失去生成能力时，系统必须阻止提交并刷新能力状态。
- 用户从数据集行进入任务创建后关闭弹窗，重新打开时不得保留另一数据集或另一连接的过期资源选择。
- 任务创建或 AI 生成弹窗获取连接列表失败时，弹窗内显示错误信息和重试按钮，不得关闭弹窗或降级为静默失败。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 数据集管理页面首次加载 MUST 只请求 Smart Eval 数据集列表，不得请求 RAG 连接、知识库或对话助手。
- **FR-002**: 数据集状态轮询 MUST 只请求 Smart Eval 数据集状态，不得触发任何 RAG 系统调用。
- **FR-003**: 数据集搜索、预览、删除和批量删除 MUST 独立于所有 RAG 系统连接状态运行。
- **FR-004**: 数据集上传 MUST 只将文件和数据集元数据发送到 Smart Eval，由 Smart Eval 完成格式校验、字段校验和样本归一化。
- **FR-005**: 数据集上传、校验和归一化流程 MUST 不请求连接列表、知识库、对话助手或其他外部 RAG 资源。
- **FR-006**: RAG 系统不可用 MUST 不影响已有数据集的列表、上传、搜索、预览和删除。
- **FR-007**: 用户点击“创建评测任务”前，系统 MUST 不加载任务表单所需的连接、对话助手、知识库或评测指标。
- **FR-008**: 用户打开任务创建表单时，系统 MUST 按需加载可用连接、Smart Eval 数据集和评测指标。
- **FR-009**: 用户选择连接前，任务表单 MUST 不获取任何连接的对话助手或知识库。
- **FR-010**: 用户选择连接后，任务表单 MUST 只获取所选连接的对话助手，不得访问其他连接。
- **FR-011**: 任务表单 MUST 根据所选对话助手的知识库选择模式决定知识库选择行为。模式为二元（必选/可选）：必选模式下知识库选择器为必填，可选模式下知识库选择器可见但可跳过。两种模式下均需加载所选连接的知识库列表。
- **FR-012**: 用户切换连接或对话助手时，系统 MUST 清除所有不再属于当前选择范围的对话助手、知识库和相关校验状态。
- **FR-013**: 任务提交前 MUST 重新验证连接、对话助手和显式知识库属于同一连接，并记录该连接身份。
- **FR-014**: 系统 MUST 禁止在资源加载失败时隐式回退到默认 RAGFlow、首个连接或其他未选择连接。
- **FR-015**: 用户点击“AI 智能生成数据集”前，系统 MUST 不加载任何 RAG 系统知识库。
- **FR-016**: AI 数据集生成弹窗打开后 MUST 按需获取连接列表，并展示每个连接是否支持基于知识库生成数据集。
- **FR-017**: 用户选择支持 AI 数据集生成的连接后，系统 MUST 只获取该连接的知识库。
- **FR-018**: 不支持 AI 数据集生成的连接 MUST 不能选择知识库或提交生成请求，并须展示明确原因。
- **FR-019**: 用户切换 AI 数据集生成连接时，系统 MUST 清除旧连接的知识库列表和选择，并忽略旧连接的迟到响应。
- **FR-020**: AI 数据集生成请求 MUST 包含用户所选的连接和知识库身份，后端 MUST 使用该连接执行生成流程。
- **FR-021**: 任务创建和 AI 数据集生成资源请求 MUST 支持加载、空结果、错误和重试状态，且错误范围仅影响当前弹窗。
- **FR-022**: 关闭任务或 AI 生成弹窗 MUST 清除该操作的临时连接和资源状态，不得影响数据集页面主体状态。
- **FR-023**: 系统 MUST 防止过期或迟到的异步响应覆盖当前连接选择对应的资源。
- **FR-024**: 数据集页面 MUST 不再保留已被共享任务表单替代的旧对话助手、指标和任务表单预加载流程。

### Key Entities

- **数据集页面状态**: 表示数据集列表、搜索、轮询、预览和上传状态；不包含任何默认 RAG 资源。
- **操作会话**: 表示一次任务创建或 AI 数据集生成弹窗生命周期，包含当前选择的连接、资源加载状态和取消标识，关闭后即失效。
- **RAG 连接选择**: 表示用户在当前操作会话中明确选择的连接，包括稳定连接 ID、系统类型、启用状态和能力信息。
- **连接能力**: 表示连接是否支持知识库发现、对话助手发现和基于知识库生成数据集等功能。
- **连接范围资源**: 表示属于当前连接的对话助手或知识库，必须以连接 ID 与外部资源 ID 共同确定身份。
- **AI 数据集生成请求**: 表示基于所选连接和知识库发起的数据集生成操作，包含连接身份、知识库身份、生成数量和问题类型。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% 的数据集管理页面首次加载只产生 Smart Eval 数据集请求，在用户触发 RAG 相关操作前产生 0 次 RAG 连接或资源请求。
- **SC-002**: 100% 的数据集上传操作在连接列表和所有 RAG 系统不可用时仍可完成上传、校验和归一化。
- **SC-003**: 用户选择一个连接创建任务时，100% 的对话助手和知识库请求只发送到该连接，未选择连接收到 0 次资源请求。
- **SC-004**: 用户切换任务连接后，100% 的旧连接资源选择在新资源展示前被清除，迟到响应不会改变当前选择。
- **SC-005**: 100% 的评测任务记录用户明确选择的连接，不发生默认 RAGFlow 或首个连接隐式回退。
- **SC-006**: 用户打开 AI 数据集生成弹窗前产生 0 次 RAG 知识库请求。
- **SC-007**: AI 数据集生成期间，100% 的知识库请求和生成请求只关联用户当前选择的连接。
- **SC-008**: 100% 不支持 AI 数据集生成的连接无法提交生成请求，并在用户继续前展示能力限制原因。
- **SC-009**: 任一 RAG 系统不可用时，用户仍可在 5 秒内打开数据集页面并执行列表、上传、预览或删除操作，不出现无关的 RAG 错误阻断。
- **SC-010**: 至少 90% 的测试用户能在首次尝试中正确选择连接并完成任务创建或识别连接不支持 AI 数据集生成。
- **SC-011**: 任务创建和 AI 数据集生成弹窗打开后，连接列表在 2 秒内完成加载并渲染为可交互状态，加载期间显示骨架占位符而非空白或全屏等待。

## Assumptions

- Smart Eval 已提供统一的 RAG 连接列表、连接能力、连接范围知识库和连接范围对话助手接口。**（已确认：这些接口已存在，本功能为纯前端会话流程变更，不新增后端 API。）**
- 数据集列表、上传、预览、删除和状态轮询均由 Smart Eval 自身完成，不依赖外部 RAG 系统。
- 评测任务创建继续使用共享的连接感知任务表单。
- 连接能力是后端返回的权威信息；页面不根据系统名称猜测能力。
- 第一阶段只有声明支持 `generate_dataset_from_knowledge_base` 的连接可以用于 AI 数据集生成。**（已确认：该能力字段已存在于连接 API 响应中。）**
- 如果某个系统尚未实现 AI 数据集生成适配，页面应禁用该连接，而不是回退到 RAGFlow。
- 资源列表不在数据集页面加载时预缓存；只有用户触发对应操作后才按需加载。
- 页面主体状态与每个弹窗的操作状态相互隔离。

## Scope Boundaries

### In Scope

- 移除数据集页面初始化时的 RAG 知识库预加载。
- 移除共享任务表单启用后遗留的旧对话助手、指标和任务表单预加载流程。
- 任务创建时按用户连接选择加载对话助手和条件性知识库。
- AI 数据集生成时增加连接选择和能力检查。
- AI 数据集生成请求携带连接身份并由后端按连接路由。
- 处理连接切换、弹窗关闭和迟到响应造成的状态污染。

### Out of Scope

- 修改数据集文件格式、大小限制或样本字段规则。
- 新增或修改 RAG 系统连接管理方式。
- 新增 RAG 系统的 AI 数据集生成能力；本功能只消费已声明的能力。
- 修改评测指标算法、任务执行器或报告评分逻辑。
- 在数据集页面长期缓存所有连接的知识库或对话助手。
