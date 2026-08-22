# Phase 0 Research: 新 RAG 系统接入

**Feature**: `001-rag-system-integration`

**Date**: 2026-08-22

## Research Scope

本研究结合功能规格、IntelliQ API 契约、当前活动后端调用链、SQLite schema、React 页面和部署脚本，解决规划阶段的技术未知项。当前活动后端路径是：

```text
backend/app.py
  -> backend/evaluation_db.py
  -> backend/db.py
  -> backend/models/database.py
  -> backend/services/evaluation_service.py
```

`backend/api_optimized.py` 与 `backend/services/unified.py` 未被 `create_app()` 注册，不作为本功能的实施入口。

## Decision 1: 分离被测 RAG Provider 与评分模型 Provider

**Decision**: 新增独立的 RAG 连接和 provider adapter 层。现有 `api_configs` 继续只服务 RAGAS 的裁判 LLM 与 embedding，不保存 IntelliQ 连接。

**Rationale**: 两类 provider 的用途、认证、资源模型、生命周期和审计要求不同。复用 `api_configs` 会导致被测系统切换影响评分模型，也无法表达知识库、Agent、连接状态和来源追溯。

**Alternatives considered**:

- 在 `EvaluationService` 中增加 IntelliQ 条件分支：改动较小，但继续扩大单体服务耦合。
- 复用 `api_configs`：字段相似但领域语义错误。
- 全面重构现有后端服务层：风险和范围超过本功能。

## Decision 2: 使用统一 Provider Adapter

**Decision**: 定义统一能力边界：连接验证、知识库列表、助手列表和单样本问答。实现 `RAGFlowProvider` 与 `IntelliQProvider`，通过 factory 根据任务来源创建。

**Rationale**: 浏览器和评测编排层不应知道 RAGFlow Bearer Token、IntelliQ `X-API-Key`、不同资源路径或不同回答协议。统一返回 `KnowledgeBaseRef`、`AssistantRef` 和 `RagQueryResult` 可隔离外部差异。

**Alternatives considered**:

- 前端分别调用两个外部系统：会暴露密钥并复制业务逻辑。
- 继续保留通用 RAGFlow 代理并增加 IntelliQ 通用代理：扩大 SSRF 和接口泄漏风险。
- 固定业务动作的 provider-neutral API：边界最小且可测试。

## Decision 3: 使用任务级 Provider 实例

**Decision**: 任务开始时解析一次连接配置和 revision，创建不可变的 task-scoped provider，并在任务结束时关闭 HTTP client。

**Rationale**: 当前全局 `EvaluationService` 缓存 RAGFlow session，存在跨样本和并发任务污染。任务级实例能够固定连接身份、复用连接池，同时避免全局可变状态。

**Alternatives considered**:

- 全局 provider 单例：资源消耗较低，但会共享连接和会话状态。
- 每个样本创建 provider：隔离最强，但重复初始化连接配置和连接池。
- 任务级 provider：在隔离、追溯与连接复用之间最平衡。

## Decision 4: 保存规范化的服务根地址

**Decision**: `rag_connections.base_url` 保存不带尾部 `/` 和 `/api/v1` 的服务根地址。输入允许是服务根地址或完整 `/api/v1` 基础地址，保存时移除单个版本前缀，由 adapter 统一追加一次。

**Rationale**: 当前 RAGFlow 配置存在输入已含 `/api/v1`、调用方又追加 `/api/v1` 的重复路径风险。规范化可以集中验证 URL 并使 endpoint 构造可测试。

**Alternatives considered**:

- 原样保存：每个调用点都要处理路径歧义。
- 保存完整 API base：可行，但当前 RAGFlow 代码和配置习惯以服务根地址为主。
- 每个 endpoint 单独配置：运维复杂且不利于接口升级。

输入中的 `/platform/api-docs`、Swagger 页面、userinfo、query 和 fragment 被明确拒绝。对外连接摘要中的 `api_url` 表示规范化服务根地址；provider 内部构造的 `api_base` 才包含一次 `/api/v1`。

## Decision 5: 使用独立连接表和加密凭据

**Decision**: 新增 `rag_connections` 和追加式 `rag_connection_audit`。API Key 使用 `cryptography` 提供的对称加密，由环境变量 `RAG_CREDENTIAL_ENCRYPTION_KEY` 提供密钥；读取 API 永不返回密钥或掩码密钥，只返回 `api_key_configured`。

**Rationale**: UI 需要维护连接，单纯环境变量无法满足保存、状态和审计。SQLite 明文保存不满足规格。独立加密密钥不能复用当前具有默认值的 Flask `SECRET_KEY`。

**Alternatives considered**:

- 仅使用 `.env`：安全简单但不能由 UI 管理和审计。
- SQLite 明文保存：不满足密钥保护要求。
- 使用系统 keyring 或外部 secret manager：当前单容器部署没有对应依赖。
- 独立加密密钥加 SQLite 密文：符合当前部署形态且可迁移到 secret manager。

## Decision 6: 限制连接 URL，禁止通用代理

**Decision**: 连接保存和每次请求前验证 URL。默认只允许 HTTPS；拒绝 URL 用户信息、query、fragment、回环、链路本地和元数据地址；私网或 HTTP 目标必须通过精确的 `RAG_PROVIDER_ALLOWED_HOSTS` 运维白名单。IntelliQ 不提供浏览器可控的任意路径代理，并禁用跨主机重定向。

**Rationale**: 管理员可配置 URL 会引入 SSRF。固定业务动作和精确白名单能够支持企业私有部署，同时避免复用当前通用代理的风险。

**Alternatives considered**:

- 信任管理员输入：仍可能通过误配置访问容器内部服务。
- 禁止所有私网：会阻断常见企业内网部署。
- 广泛私网 CIDR 白名单：边界过宽。

## Decision 7: IntelliQ 每个样本及每次重试使用独立 Session

**Decision**: 每个数据集样本生成独立 `session_id`。若在收到任何有效回答事件前发生可重试的连接错误，最多重试一次，并使用新的 session。认证、权限、请求校验错误不重试；流已开始后中断不自动重试。

**Rationale**: 样本必须互不影响。复用中断 session 可能带入部分回答、工具调用或历史上下文。流开始后重试还可能造成重复副作用和不可解释结果。

**Alternatives considered**:

- 每任务一个 session：会污染样本独立性。
- 所有错误统一重试：会放大认证错误、限流和重复执行。
- 中断后继续使用部分答案：违反评分完整性要求。

## Decision 8: 增量解析 SSE 并以明确完成信号为成功门槛

**Decision**: 使用现有 `aiohttp` 客户端增量消费响应流，以 SSE 行边界解析 UTF-8 数据。仅拼接 `answer` 事件，收集 `references`，保留中间事件摘要用于诊断；只有收到 `done: true` 才返回 `completed=true`。

**Rationale**: IntelliQ 文档明确返回 `text/event-stream`，事件可能跨网络 chunk。`aiohttp` 官方客户端支持流式迭代、独立连接与读取超时以及可控 session 生命周期。按 chunk 直接解析 JSON 会在分片边界失败。

**Alternatives considered**:

- 读取完整响应后解析：失去流式超时和取消控制，并增加内存占用。
- 将所有 `content` 字段拼接：会把 thinking 和 tool 结果计入最终答案。
- 连接关闭即成功：无法区分完成与中断。

## Decision 9: 使用结构化样本执行记录控制评分资格

**Decision**: 新增 `evaluation_sample_runs`，持久化每个样本的 attempt、session、状态、完整答案、引用、上下文和错误类别。只有 `completed` 样本进入 RAGAS 正常评分；失败样本保留在任务诊断和最终报告的失败统计中。

**Rationale**: 当前上游失败被降级为空答案并继续评分，会把执行可靠性故障误判为模型质量问题。持久化样本状态也能支持准确进度、取消和容器异常诊断。

**Alternatives considered**:

- 仅在内存中保存：进程中断后丢失诊断。
- 任一样本失败即终止全部任务：降低批量评测可用性。
- 继续空答案评分：违反规格。

## Decision 10: 任务和报告保存不可变来源快照

**Decision**: 任务保存 provider、connection ID/revision、Assistant 和知识库 ID/名称快照。报告复制该快照，并保存样本引用。任何快照都不包含 API Key。

**Rationale**: 外部资源可重命名、禁用或删除。报告展示时实时查询上游会使历史结果不可复现，也无法区分同名资源。

**Alternatives considered**:

- 只保存资源 ID：缺少可读名称和历史语义。
- 每次查询报告时请求上游：上游不可用时历史报告失效。
- 保存非敏感快照：可追溯且与上游生命周期解耦。

## Decision 11: 增量迁移并保留旧 `chat_id` 契约

**Decision**: 使用版本化、幂等 SQLite migration 增加表和列；保留 `evaluation_tasks.chat_id`。旧任务解释为 legacy RAGFlow，新任务同时写入 `assistant_id` 和兼容 `chat_id`。旧 POST payload 继续接受一个兼容周期。

**Rationale**: 当前前端、任务表和报告表依赖 `chat_id`。直接重命名或重建表会破坏历史数据和现有客户端。`CREATE TABLE IF NOT EXISTS` 本身不能迁移旧表，必须显式检查 schema version。

**Alternatives considered**:

- 删除旧字段并一次性切换：回归风险高。
- 全量重建数据库：丢失历史任务和报告。
- 增量列、读取 fallback 和兼容请求：风险最低。

## Decision 12: RAGFlow 作为环境驱动的合成连接

**Decision**: `/rag-connections` 返回一个由现有 `RAGFLOW_BASE_URL` 和 `RAGFLOW_API_KEY` 形成的只读 `ragflow-default` 合成连接，并返回一个数据库持久化的 IntelliQ 连接。第一阶段限制最多一个启用的 IntelliQ 连接。

**Rationale**: 这样可以让前端统一选择 provider，而无需迁移或在数据库中复制现有 RAGFlow 密钥。旧任务可自然映射到 `ragflow-default`。

**Alternatives considered**:

- 将 RAGFlow 密钥迁移入数据库：增加密钥迁移风险。
- 前端继续保留独立 RAGFlow 分支：provider 逻辑会继续分裂。
- 所有连接均仅使用环境变量：无法满足 IntelliQ UI 配置要求。

## Decision 13: 保留线程执行器但增加协作式控制

**Decision**: 第一阶段保留现有 daemon thread 和每任务事件循环，不引入外部队列。样本循环在每次上游调用前后检查任务取消状态；应用启动时将 stale `running` 任务标记为中断失败。

**Rationale**: 规格不要求重构调度策略。引入 Celery、Redis 或其他队列会大幅扩大部署范围，但当前取消和重启语义不能继续保持为无效操作。

**Alternatives considered**:

- 引入持久队列：更可靠，但超出本功能部署边界。
- 完全保持现状：取消、重启恢复和流中断不可验证。
- 协作式控制：在现有架构内建立可信状态边界。

## Decision 14: 使用 Provider Capabilities 控制 UI

**Decision**: 连接摘要返回能力标志。普通评测数据集上传对所有 provider 可用；现有“基于知识库 AI 生成数据集”在第一阶段仅对 RAGFlow 开启，IntelliQ 显示不可用，直到确认知识内容/分块读取契约。

**Rationale**: 已确认 IntelliQ 契约覆盖知识库、Agent 和 Agent Chat，但不能从这些接口推断知识分块导出能力。隐藏或禁用不支持功能比调用错误 endpoint 更安全。

**Alternatives considered**:

- 假设 IntelliQ 支持与 RAGFlow 相同的分块 API：没有契约依据。
- 移除 AI 生成入口：会回归 RAGFlow 能力。
- 能力驱动 UI：兼容现有能力并清晰表达限制。

## Decision 15: 建立真实的测试分层

**Decision**: 新增 `backend/tests/`，使用 pytest、pytest-asyncio、临时 SQLite 和本地 aiohttp mock server。前端门禁为移除核心页面的 `@ts-nocheck` 后执行 typecheck/build，并用 Playwright 验证关键 UI 流程。生产验证继续执行 Compose、发布检查和健康检查。

**Rationale**: 当前 `test_db.py` 是交互式脚本，pytest 未形成阻塞门禁，核心页面又跳过类型检查。SSE、迁移和密钥保护需要确定性自动测试。

**Alternatives considered**:

- 仅手工连接真实 IntelliQ：不可重复且需要真实密钥。
- 只做单元测试：无法验证 SSE 和内部 REST 契约。
- 同时引入完整前端单测框架：第一阶段会扩大依赖；先使用类型和 E2E 门禁。

## Decision 16: 修正 SQLite 持久化和并发设置

**Decision**: 数据库路径统一使用 `DATABASE_PATH`，容器默认 `/app/data/evaluation.db`。启动时若目标数据库不存在但发现旧 `/app/evaluation.db`，先备份再迁移。SQLite 连接启用 WAL、`busy_timeout` 和短事务；样本进度按状态变化或进度阈值节流写入。

**Rationale**: 当前默认数据库位于未挂载的 `/app/evaluation.db`，容器重建可能丢失连接、任务和报告。新增 sample run 会增加写入频率，必须控制锁竞争。

**Alternatives considered**:

- 保持当前路径：无法满足部署持久化。
- 直接引入 PostgreSQL：超出单容器部署和本功能范围。
- SQLite 持久卷加 WAL/节流：符合现有部署并能承载第一阶段规模。

## Decision 17: 第一阶段保持单进程生产执行模型

**Decision**: 本功能不切换到多 worker Gunicorn。继续使用当前 Supervisor 管理的单 Python 进程和线程任务模型，同时增加 readiness、stale task 恢复和优雅中断标记。多进程/持久队列作为后续独立架构工作。

**Rationale**: 当前任务通过进程内 daemon thread 启动。直接切换多 worker 可能造成任务重复领取和内存状态分裂；该问题不能在没有持久调度器的情况下安全解决。

**Alternatives considered**:

- 立即启用 Gunicorn 多 worker：吞吐更高，但任务所有权不安全。
- 本功能同时引入持久队列：可靠但显著扩大部署边界。
- 保持单进程并强化持久状态：适合当前增量交付。

## Decision 18: 使用部署级管理员令牌保护连接写操作

**Decision**: 因当前后端没有真实用户/角色校验，连接创建、更新、启停和测试端点必须验证独立的 `SMART_EVAL_ADMIN_TOKEN`。前端复用 `Authorization: Bearer` 请求头，但不把该令牌写入数据库、报告或日志。资源读取和评测任务继续遵循现有应用访问边界。

**Rationale**: 仅依赖客户端 `X-User-Id` 不能保护可替换外部 API Key 的管理操作。完整身份系统超出当前功能，但生产环境不能无鉴权开放密钥修改。

**Alternatives considered**:

- 依赖网络隔离：不能防止同网用户或浏览器请求修改配置。
- 在本功能中实现完整用户系统：超出范围。
- 部署级管理员令牌：最小可验证保护，并可在未来替换为角色权限。

## Decision 19: 由服务端解析并强制执行 Agent 知识库模式

**Decision**: Assistant 资源统一暴露 `knowledge_base_selection_mode = all | selected | none`。任务请求只提交 Assistant ID 和可选知识库 ID 列表；后端在提交时重新获取或验证 Assistant 模式。“selected”要求至少一个允许的知识库，“all”和“none”要求列表为空。

**Rationale**: Agent 模式属于上游权威配置，不能信任前端自行声明。允许 `all` 和 `none` 使用空数组，可避免 OpenAPI 将所有任务错误地约束为至少一个知识库。

**Alternatives considered**:

- 所有任务强制一个知识库：与 Agent “全部/不使用”语义冲突。
- 前端提交并决定模式：可被篡改且可能在提交前过期。
- 完全不显示知识库：无法支持“指定”模式。

## Decision 20: 固定第一阶段数据集上传契约

**Decision**: 第一阶段仅支持 JSON、JSONL、CSV、XLSX、XLS，单文件最大 10 MB。所有格式在标记 `completed` 前转换为统一 JSON 样本表示；TXT 和其他非结构化格式明确拒绝。

**Rationale**: 当前 UI、配置和实际读取路径不一致。固定格式和上限可以形成可测试契约，并保证每个显示为完成的数据集都能被任务读取。

**Alternatives considered**:

- 延续现有模糊声明：会继续出现上传成功但任务读取失败。
- 只支持 JSON：实现最简单，但不满足用户确认的表格格式范围。
- 增加 TXT：缺少明确的样本字段映射规则。

## Decision 21: 明确部分失败任务的最终化与计数

**Decision**: 每个 `sample_index` 只使用最终 attempt 参与任务统计。至少一个样本完整成功时，任务状态为 `completed`，并通过 `has_warnings=true` 表示部分失败；生成报告且质量指标分母等于成功样本数。全部样本失败时任务为 `failed`，不创建最终质量报告。

**Rationale**: attempt 行数不能作为样本数，否则重试会导致成功数与失败数之和超过总样本数。独立 warning 投影保持现有任务状态兼容，并准确表达部分完成。

**Alternatives considered**:

- 新增 `completed_with_errors` 状态：语义清晰但会扩大现有前后端状态兼容范围。
- 部分失败时标记整个任务失败：丢失成功样本的评测价值。
- 按所有 attempt 统计：会重复计算同一数据集样本。

## Resolved Technical Unknowns

- **API URL 语义**: 用户可输入服务根地址或 `/api/v1` 基础地址，数据库统一保存服务根地址。
- **认证**: IntelliQ 使用 `X-API-Key`，RAGFlow 保持 Bearer Token。
- **资源模型**: IntelliQ Knowledge Base 映射为统一知识库引用，Agent 映射为统一 Assistant 引用。
- **回答协议**: IntelliQ 使用 SSE；`done: true` 是成功门槛。
- **会话隔离**: 每样本、每尝试独立 session。
- **失败评分**: 未完整回答不进入正常评分分母。
- **凭据存储**: 新连接使用独立加密密钥和 SQLite 密文。
- **兼容策略**: 旧 RAGFlow 路径和 `chat_id` 保留，新增 provider-aware API。
- **调度边界**: 不引入新队列，只修正取消和 stale 状态。
- **持久化路径**: 使用 `DATABASE_PATH=/app/data/evaluation.db`，并检测旧容器数据库。
- **生产进程**: 第一阶段保持单进程，避免线程任务被多 worker 重复执行。
- **管理权限**: 连接写操作使用部署级管理员令牌，弥补当前无服务端角色校验的缺口。
- **知识库选择**: 服务端按 Agent 的 all/selected/none 模式决定知识库列表是否必须为空或至少一项。
- **数据集上传**: JSON、JSONL、CSV、XLSX、XLS，最大 10 MB，并统一归一化后才可评测。
