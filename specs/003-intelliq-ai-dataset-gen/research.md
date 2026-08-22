# Research: IntelliQ 支持 AI 数据集生成

**Feature**: 003-intelliq-ai-dataset-gen  
**Date**: 2026-08-22

## Decision 1: 在 RagProvider 基类中添加 `get_chunks` 方法 (同步包装器)

**Decision**: 在 `RagProvider` 基类中定义同步方法 `get_chunks(kb_id, limit)` 用于获取知识库内容片段。每个提供者负责实现自己的 chunk 检索逻辑。`AIDatasetGenerator` 通过 `create_provider()` 获取提供者实例，调用 `get_chunks()` 替代直接访问 RAGFlow API。

**Rationale**:
- 当前 `AIDatasetGenerator` 直接调用 `self.ragflow_base_url` 和硬编码的 RAGFlow API 端点，无法支持其他提供者。
- 将 chunk 检索抽象到 `RagProvider` 基类，使每个提供者以自己协议获取内容，`AIDatasetGenerator` 只关心返回的 chunk 列表。
- 方法设为同步是因为 `AIDatasetGenerator` 在后台线程中运行（Flask 线程池），异步 `aiohttp` 调用需要桥接。

**Alternatives considered**:
- 在 `AIDatasetGenerator` 中硬编码每种提供者的 URL 模式 — 拒绝，违反抽象原则，不能复用 `IntelliQProvider` 已有的认证和重试逻辑。
- 创建独立的 `ChunkProvider` 接口 — 拒绝，过度抽象；chunk 检索是 `RagProvider` 的自然职责。
- 使整个生成管道异步化 — 拒绝，需要重写 `evaluation_db.py` 的路由和 Flask 的 sync/async 模型，超出本功能范围。

## Decision 2: 使用 `asyncio.run()` 桥接异步提供者到同步生成器

**Decision**: 在 `IntelliQProvider.get_chunks()` 内部使用 `asyncio.run()` 运行异步 HTTP 调用，以确保方法签名保持同步，兼容 `AIDatasetGenerator` 的线程模型。

**Rationale**:
- `IntelliQProvider` 的所有 HTTP 方法都是 `async`（使用 `aiohttp`），而 `AIDatasetGenerator` 在后台线程中同步运行。
- `asyncio.run()` 在后台线程中安全可用（每个线程有独立的事件循环），是在不重构整个管道的前提下最简单的桥接方案。
- 影响范围小：只有 `get_chunks()` 方法需要这个桥接，其他 `IntelliQProvider` 方法保持异步供评测管道使用。

**Alternatives considered**:
- 将 `AIDatasetGenerator` 改为异步 — 拒绝，需要修改 `evaluation_db.py` 的 `generate_async` 线程函数和 Flask 路由，影响范围过大。
- 使用 `requests` 库在 `IntelliQProvider` 中新增同步 HTTP 方法 — 拒绝，代码重复，需要维护两套 HTTP 客户端。
- 使用 `nest_asyncio` — 拒绝，引入额外依赖，且已有线程隔离的事件循环足够。

## Decision 3: IntelliQ chunk 检索 API 路径

**Decision**: 使用 `GET /api/v1/knowledge-bases/{kb_id}/documents` 获取文档列表，再通过 `GET /api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/chunks` 获取每个文档的 chunks。如果 IntelliQ 部署环境未提供这些端点，回退到直接使用知识库列表响应中的 `knowledge_count` 和 `chunk_count` 元数据并返回空结果。

**Rationale**:
- IntelliQ 的 API 契约（`specs/001-rag-system-integration/references/intelliq-api-contract.md`）未明确列出 chunk 检索端点，但 `list_knowledge_bases` 返回 `knowledge_count` 和 `chunk_count` 表明存在文档/分块模型。
- RAGFlow 使用 `/datasets/{id}/documents` 和 `/documents/{id}/chunks` 模式，IntelliQ 很可能使用类似的 RESTful 模式。
- 该路径需要在实际 IntelliQ 部署环境的 Swagger 文档中验证，若不存在则作为配置项标记。

**Alternatives considered**:
- 使用 Agent Chat 接口获取引用内容 — 拒绝，需要构造问题并等待 SSE 流完成，开销大且不可控。
- 仅从 `list_knowledge_bases` 的元数据生成 — 拒绝，无法获取实际文档内容，无法生成有意义的问答对。

## Decision 4: RagConnectionService._summary() 动态获取能力

**Decision**: 修改 `RagConnectionService._summary()` 方法，使用 `create_provider()` 获取提供者实例，读取其 `capabilities` 属性，而非硬编码固定的能力字典。

**Rationale**:
- 当前 `_summary()` 硬编码 `generate_dataset_from_knowledge_base: False, streaming_chat: True` 用于所有 DB 连接（均为 IntelliQ）。
- 这导致即使 `IntelliQProvider` 声明了 `generate_dataset_from_knowledge_base=True`，API 返回的仍是 `false`。
- 使用 `create_provider()` 并读取 `capabilities.__dict__` 确保 API 响应与提供者实际能力一致，单一事实来源。

**Alternatives considered**:
- 直接在 `_summary()` 中硬编码 `True` — 拒绝，仍然是硬编码，只是改了值，未能解决根本问题。
- 在数据库表中存储能力 — 拒绝，能力是代码定义的静态属性，不应持久化到数据库。

## Decision 5: 前端无需改动

**Decision**: 前端 `Datasets.tsx` 和 `evaluation.ts` 已在 feature 002 中实现了 `connection_id` 参数传递。本次后端变更后，前端无需修改即可正常工作。

**Rationale**:
- `datasetApi.generateAIDataset()` 已接受 `connection_id` 参数。
- `handleGenerateSubmit()` 已传递 `connection_id: genSelectedConnectionId!`。
- 下拉框禁用逻辑已在之前的 bug 修复中改为仅检查 `enabled` 状态。
- 能力警告提示已存在（当 `genCapable` 为 `false` 时显示）。

**Alternatives considered**: N/A — 前端已就绪。