# Quickstart Validation: 新 RAG 系统接入

**Feature**: `001-rag-system-integration`

**Purpose**: 提供实施完成后的可运行验证路径。命令中的 URL、Key、资源 ID 和文件路径必须替换为测试环境值。

## 1. Prerequisites

- 工作目录：`/home/marc/Projects/smartq_eval`
- Python 3.12 环境和 `backend/requirements.txt` 依赖
- Node.js 20+ 和 `frontend/package-lock.json` 依赖
- 可写的临时 SQLite 数据库和临时数据集目录
- `RAG_CREDENTIAL_ENCRYPTION_KEY`
- `SMART_EVAL_ADMIN_TOKEN`，用于保护连接创建、更新和测试
- 可选：有效 IntelliQ API Key，用于真实环境验证
- 旧 RAGFlow 测试环境，用于兼容性回归

不要把真实 API Key 写入命令历史、spec 文件、测试 fixture 或 Git 跟踪文件。

## 2. Static and Unit Validation

### Backend

```bash
cd /home/marc/Projects/smartq_eval
python -m pytest backend/tests -q
```

必须覆盖：

- URL 规范化和 SSRF 目标策略
- API Key 加密、保留更新和日志脱敏
- SQLite migration 从旧 schema 升级且可重复执行
- IntelliQ SSE 多段 answer、references、done、error、非法 JSON、UTF-8 分片和断流
- 每样本/每尝试 session 隔离
- 失败样本不进入正常评分分母
- 旧 `chat_id` 任务 payload 兼容
- Agent `selected` 模式要求至少一个知识库，`all`/`none` 模式拒绝手动知识库 ID
- JSON、JSONL、CSV、XLSX、XLS 都归一化成功；TXT 和大于 10 MB 文件被拒绝
- 服务根地址和 `/api/v1` 地址规范化结果相同；文档/Swagger 地址被拒绝

### Frontend

移除核心页面的 `// @ts-nocheck` 后执行：

```bash
cd /home/marc/Projects/smartq_eval/frontend
npm run typecheck
npm run build
```

额外静态检查：

```bash
cd /home/marc/Projects/smartq_eval
! grep -R "^// @ts-nocheck" frontend/src/pages
! grep -R "ragflowClient" frontend/src/pages
! grep -R "/evaluation/ragflow" frontend/src/pages
```

## 3. Mocked IntelliQ Contract Validation

测试套件启动本地 aiohttp mock server，模拟：

1. `GET /api/v1/knowledge-bases`
2. `GET /api/v1/agents`
3. `POST /api/v1/agent-chat/{session_id}`
4. `text/event-stream` 响应

成功序列至少包含：

```text
references(done=false)
answer("第一段", done=false)
thinking(done=false)
answer("第二段", done=false)
answer("", done=true)
```

期望：

- 最终答案是“第一段第二段”。
- thinking 内容不进入答案。
- references 被保存并转换为 contexts。
- `completed_signal_received` 为 true。

断流序列：

```text
answer("部分答案", done=false)
<connection closes>
```

期望：

- 样本状态为 failed/incomplete。
- 部分答案只进入诊断字段。
- 样本不进入 RAGAS 正常评分输入。

## 4. Run the Application

### Source Mode

Backend:

```bash
cd /home/marc/Projects/smartq_eval
export RAG_CREDENTIAL_ENCRYPTION_KEY='<test-only-fernet-key>'
export SMART_EVAL_ADMIN_TOKEN='<test-only-admin-token>'
python backend/app.py
```

Frontend:

```bash
cd /home/marc/Projects/smartq_eval/frontend
npm run dev
```

Health check:

```bash
curl -f http://localhost:5002/health
```

### Container Mode

```bash
cd /home/marc/Projects/smartq_eval
docker-compose config
./check-before-publish.sh
./start.sh
curl -f http://localhost:5003/health
```

验证结束后：

```bash
cd /home/marc/Projects/smartq_eval
./stop.sh
```

## 5. Configure IntelliQ Through Smart Eval

将敏感值放入临时环境变量：

```bash
export SMART_EVAL_URL='http://localhost:5002/api/v1/evaluation'
export INTELLIQ_URL='https://ai-intelliq.peraglobal.com'
export INTELLIQ_API_KEY='<real-test-key>'
export SMART_EVAL_ADMIN_TOKEN='<deployment-admin-token>'
```

创建连接：

```bash
curl -sS -X POST "$SMART_EVAL_URL/rag-connections" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $SMART_EVAL_ADMIN_TOKEN" \
  --data "{\"provider\":\"intelliq\",\"name\":\"IntelliQ Test\",\"api_url\":\"$INTELLIQ_URL\",\"api_key\":\"$INTELLIQ_API_KEY\",\"enabled\":true}"
```

确认响应中没有 `api_key`、密文或请求头。记录返回的 `id`：

```bash
export CONNECTION_ID='<returned-connection-id>'
```

测试连接：

```bash
curl -sS -X POST "$SMART_EVAL_URL/rag-connections/$CONNECTION_ID/test" \
  -H "Authorization: Bearer $SMART_EVAL_ADMIN_TOKEN"
```

期望：

- 状态为 `available`。
- 返回知识库和助手数量。
- 认证失败、权限不足和地址错误有不同的安全错误类别。

## 6. Discover Resources

```bash
curl -sS "$SMART_EVAL_URL/rag-connections/$CONNECTION_ID/knowledge-bases?limit=100"
curl -sS "$SMART_EVAL_URL/rag-connections/$CONNECTION_ID/assistants?limit=100"
```

确认：

- 每个资源含 provider 和 connection ID。
- 禁用 Agent 不可选择并给出原因。
- 同名资源仍由稳定 ID 区分。
- API Key 不出现在响应或 `logs/evaluation.log`。

```bash
export KB_ID='<knowledge-base-id>'
export ASSISTANT_ID='<agent-id>'
```

## 7. Upload an Evaluation Dataset

准备一个符合现有字段契约且不超过 10,485,760 bytes 的测试文件，例如 `tmp/intelliq-eval.json`：

```bash
curl -sS -X POST "$SMART_EVAL_URL/datasets" \
  -F 'name=IntelliQ Quickstart Dataset' \
  -F 'description=Provider integration validation' \
  -F 'file=@tmp/intelliq-eval.json'
```

轮询直到状态为 `completed`。确认所有声明支持的格式都被归一化到任务可读取的统一样本文件，而不是只完成元数据统计。

分别使用 JSON、JSONL、CSV、XLSX 和 XLS fixture 重复上传。再使用 TXT 和超过 10 MB 的文件验证请求在解析前被拒绝且临时文件被清理。

每一种成功格式都必须继续创建一个最小任务，以证明归一化结果可被执行器读取，而不仅是数据集元数据显示成功。

```bash
export DATASET_ID='<uploaded-dataset-id>'
```

## 8. Create and Observe an IntelliQ Task

```bash
curl -sS -X POST "$SMART_EVAL_URL/tasks" \
  -H 'Content-Type: application/json' \
  --data "{
    \"name\": \"IntelliQ Quickstart Evaluation\",
    \"dataset_id\": \"$DATASET_ID\",
    \"metrics\": [\"faithfulness\", \"answer_relevancy\"],
    \"batch_size\": 2,
    \"rag_target\": {
      \"provider\": \"intelliq\",
      \"connection_id\": \"$CONNECTION_ID\",
      \"assistant_id\": \"$ASSISTANT_ID\",
      \"knowledge_base_ids\": [\"$KB_ID\"]
    }
  }"
```

```bash
export TASK_ID='<returned-task-id>'
curl -sS "$SMART_EVAL_URL/tasks/$TASK_ID"
```

确认：

- source snapshot 包含 IntelliQ、Agent、Knowledge Base 和连接 revision。
- 每个样本使用不同 session ID。
- 进度来自持久化样本状态。
- 取消任务后不再启动新的上游样本请求。
- 未收到 `done: true` 的样本被标记为失败且不正常评分。

重复验证三种 Agent 模式：

- `selected`: 省略或传空 `knowledge_base_ids` 返回 400；一个或多个有效 ID 成功。
- `all`: 请求不含手动知识库 ID，任务按 Agent 全部知识范围执行。
- `none`: 请求不含手动知识库 ID，上游请求不提交 `knowledge_base_ids`。
- 模式未知或提交前发生变化：任务创建被拒绝并要求刷新资源。

## 9. Retrieve the Report

```bash
curl -sS "$SMART_EVAL_URL/reports?rag_provider=intelliq&rag_connection_id=$CONNECTION_ID"
curl -sS "$SMART_EVAL_URL/reports/$TASK_ID"
```

确认：

- 报告来源为 IntelliQ。
- Assistant 和 Knowledge Base 显示创建任务时的名称快照。
- `scoredSamples + failedSamples = totalSamples`。
- 成功样本包含最终答案、contexts 和 references。
- 失败样本包含安全的错误类别，不包含部分回答评分。
- 部分失败任务状态为 completed-with-warning 语义，报告评分分母等于 `scoredSamples`；全部失败时无最终质量报告。

使用 mock SSE 构造两个聚合场景：

- 部分失败：至少一个样本收到 `done: true`，至少一个断流；任务 `completed`、`has_warnings=true`、报告存在。
- 全部失败：所有样本均未完整完成；任务 `failed`，报告详情返回无最终报告状态。
- 禁用连接或断开 IntelliQ 后，历史报告仍可读取。

## 10. RAGFlow Compatibility Regression

使用旧 payload：

```bash
curl -sS -X POST "$SMART_EVAL_URL/tasks" \
  -H 'Content-Type: application/json' \
  --data "{
    \"name\": \"Legacy RAGFlow Compatibility\",
    \"chat_id\": \"<ragflow-chat-id>\",
    \"dataset_id\": \"$DATASET_ID\",
    \"metrics\": [\"answer_relevancy\"],
    \"batch_size\": 2
  }"
```

确认：

- 旧 payload 仍成功创建。
- 任务显示 provider `ragflow` 和合成连接 `ragflow-default`。
- 旧任务和报告可读取。
- IntelliQ 连接不可用时不影响 RAGFlow 主流程。

## 11. Security and Failure Validation

必须验证：

- 错误或过期 Key 不泄露上游响应头。
- 401/403 不重试。
- 429、5xx 和连接超时只有在流开始前才允许一次受控重试。
- 回环、链路本地和未授权私网 URL 被拒绝。
- 重定向不能跳转到不同主机或受保护网段。
- GET/PUT 连接配置不会把 UI 占位值覆盖为真实密钥。
- 缺少或使用错误管理员令牌时，连接创建、更新和测试返回 401/403，且不会触发上游请求。
- 使用有效和无效管理员令牌分别验证 update、enable、disable；缺少服务端 `SMART_EVAL_ADMIN_TOKEN` 时写操作 fail closed。
- 日志、SQLite 非密文字段、任务、报告和导出文件均不包含完整 Key。
- 重建 Smart Eval 容器后，`data/evaluation.db` 中的连接、任务和报告仍存在；旧 `/app/evaluation.db` 被安全检测和迁移。

URL 规范化必须额外验证：

- `https://host` 与 `https://host/api/v1` 返回相同规范化 service root。
- `/platform/api-docs`、Swagger 页面、`/api/v1/api/v1`、userinfo、query 和 fragment 被拒绝。

## 12. Final Release Checks

```bash
cd /home/marc/Projects/smartq_eval
bash -n *.sh
docker-compose config
./check-before-publish.sh
cd frontend && npm run typecheck && npm run build
```

如果没有有效 IntelliQ Key，必须明确记录真实连接、真实 SSE 和真实报告验证未执行；mock contract tests 不能被描述为生产环境验证。
