# Quickstart Validation: IntelliQ 评测前自动创建会话

**Feature**: `005-intelliq-session-creation`

**Purpose**: 验证 Smart Eval 使用真实 IntelliQ Session 进行 Agent Chat，并在任务结束后安全清理临时 Session。

## 1. Prerequisites

- 工作目录：`/home/marc/Projects/smartq_eval`
- 已配置 IntelliQ 连接，且 API Key 具有创建、Agent Chat 和删除 Session 权限。
- 使用隔离 IntelliQ 测试租户，允许删除测试 Session。
- 已配置临时 Smart Eval 数据库和数据集目录，不使用生产数据库。
- 不将 API Key、管理员令牌或真实 Session ID 写入 Git、测试 fixture 或长期日志。

## 2. Stateful Mock Validation

首先运行不依赖真实 IntelliQ 凭据的测试：

```bash
cd /home/marc/Projects/smartq_eval
.venv/bin/python -m pytest \
  backend/tests/unit/test_intelliq_resources.py \
  backend/tests/unit/test_intelliq_sse.py \
  backend/tests/unit/test_scoring_eligibility.py \
  backend/tests/integration/test_intelliq_session_lifecycle.py -v
```

Stateful mock 必须维护已创建 Session 和已删除批次，并验证：

1. 两个成功样本创建两个不同的真实 provider Session ID。
2. Agent Chat 仅接受已创建的 Session ID；未创建 ID 返回业务错误 `1003`。
3. Chat URL 使用创建接口返回的实际 ID，而不是 Smart Eval 本地 correlation ID。
4. 一次评测结束时，只发起一次批量删除，且 `ids` 等于本任务创建的真实 ID 去重集合。
5. Session 创建失败时，Agent Chat 调用次数为 0。
6. Chat SSE 失败后，已创建 Session 仍进入批量清理。
7. 清理失败保留安全 warning，但不改变已经确定的任务 outcome。
8. 取消发生在样本之间时，不再创建新 Session，已创建 Session 仍会清理。
9. RAGFlow provider 不调用 IntelliQ `/sessions` 或 `/sessions/batch`。

## 3. Controlled IntelliQ Smoke Test

只在明确允许清理的 IntelliQ 测试环境执行。将凭据保存在临时 shell 环境变量中：

```bash
export INTELLIQ_API_BASE='https://<intelliq-host>/api/v1'
export INTELLIQ_API_KEY='<test-only-key>'
```

创建 Session：

```bash
CREATE_RESPONSE=$(curl -sS -X POST "$INTELLIQ_API_BASE/sessions" \
  -H "X-API-Key: $INTELLIQ_API_KEY" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  --data '{"title":"SmartQ Eval Smoke Test","description":"Temporary validation session"}')
printf '%s\n' "$CREATE_RESPONSE"
```

确认响应为 HTTP 2xx，且业务 `success=true`、`data.id` 非空。将 ID 临时保存在当前 shell：

```bash
SESSION_ID=$(printf '%s' "$CREATE_RESPONSE" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["id"])')
```

使用该真实 ID 发起 Agent Chat：

```bash
curl -sS -N -X POST "$INTELLIQ_API_BASE/agent-chat/$SESSION_ID" \
  -H "X-API-Key: $INTELLIQ_API_KEY" \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  --data '{"query":"请用简体中文回复：会话验证是否成功？","agent_id":"<agent-id>","agent_enabled":true,"channel":"api"}'
```

无论 Agent Chat 成功还是失败，当前 shell 退出前都必须清理创建的 Session：

```bash
curl -sS -X DELETE "$INTELLIQ_API_BASE/sessions/batch" \
  -H "X-API-Key: $INTELLIQ_API_KEY" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  --data "{\"ids\":[\"$SESSION_ID\"]}"
```

验证真实环境时记录但不假设以下未确认行为：批量最大 ID 数、已删除 ID 语义、部分删除响应、429/5xx 重试、额外租户 Header 和 Agent Chat 取消接口。

## 4. Smart Eval Task Validation

1. 启动 Smart Eval，使用 2-3 条小型评测数据集。
2. 创建 IntelliQ 评测任务并选择一个 Agent。
3. 确认每个样本运行记录写入真实 IntelliQ `provider_session_id`。
4. 确认每个 Agent Chat 使用对应真实 Session ID。
5. 完成任务后确认报告评分分母只包含收到完整 SSE 完成信号的样本。
6. 确认会话清理状态为 `cleaned`，或在失败时显示安全 cleanup warning。
7. 验证以下异常场景：
   - 第一个 Session 创建失败。
   - 第二个样本的 Agent Chat SSE 中断。
   - 在样本之间取消任务。
   - 批量删除返回非 2xx 或业务 `success=false`。
8. 确认上述异常不会泄露 API Key、Authorization Header 或完整未受控上游响应。

## 5. RAGFlow Regression

```bash
cd /home/marc/Projects/smartq_eval
.venv/bin/python -m pytest backend/tests/integration/test_ragflow_legacy_flow.py -v
```

确认 RAGFlow 不调用 IntelliQ Session 创建或批量删除接口。

## 6. Completion Criteria

- Stateful mock 生命周期测试全部通过。
- 真实受控 smoke test 不再出现 `Session not found (code:1003)`。
- 任务成功、部分失败、全部失败和取消路径均执行会话清理尝试。
- 清理失败不改变任务的既有业务 outcome。
- 未完成的 cleanup 记录可被后续补偿流程发现。
