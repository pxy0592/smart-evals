# Data Model: IntelliQ 评测前自动创建会话

**Feature**: `005-intelliq-session-creation`

**Date**: 2026-08-23

## Scope

本功能不改变评测数据集、RAG 连接或报告的业务实体。它扩展现有 `evaluation_sample_runs` 的会话可追溯性与清理状态，使临时 IntelliQ Session 可以在正常完成、失败、取消和服务重启后被安全管理。

## Entity: EvaluationSampleRun (extended)

每个样本尝试保留本地关联和上游会话两类身份。

| Field | Type | Required | Rules |
|---|---|---:|---|
| `id` | integer | yes | 现有样本运行主键 |
| `task_id` | string | yes | 当前评测任务 |
| `sample_index` | integer | yes | 数据集中的样本序号 |
| `attempt` | integer | yes | 当前样本尝试次数 |
| `session_id` | string | yes | Smart Eval 本地 correlation ID，不等于 IntelliQ Session ID |
| `provider_session_id` | string nullable | no | IntelliQ 成功创建后返回的真实 Session ID；创建失败时为空 |
| `session_creation_status` | enum | yes | `pending`, `created`, `failed` |
| `session_cleanup_status` | enum | yes | `not_required`, `pending`, `cleaned`, `failed` |
| `session_cleanup_error` | string nullable | no | 脱敏、截断的清理错误摘要 |
| `session_cleanup_attempts` | integer | yes | 已执行的清理尝试次数 |
| `status` | enum | yes | 样本问答状态 |
| `answer` | text nullable | no | 仅完整且可评分的最终答案 |
| `partial_answer` | text nullable | no | 失败诊断，不参与评分 |
| `error_category` | enum nullable | no | 包含 `session_creation`、`upstream`、`protocol`、`cancelled` 等 |
| `error_message` | text nullable | no | 不含 API Key、认证头或未受控完整响应 |

### Validation Rules

- `provider_session_id` 只能由 IntelliQ 成功创建会话后的实际响应写入。
- `session_creation_status=created` 必须同时具有非空 `provider_session_id`。
- `session_creation_status=failed` 不得发起 Agent Chat，也不进入 cleanup。
- `session_cleanup_status=pending` 只适用于已成功创建且尚未确认删除的 IntelliQ Session。
- `session_cleanup_status=cleaned` 需要批量删除响应同时满足 HTTP 2xx 与业务 `success=true`。
- 任何清理状态不得影响样本的评分资格或已完成任务的 outcome。

## Entity: TaskSessionCleanupSummary

任务结束时聚合当前任务尚未清理的 IntelliQ Session。

| Field | Type | Description |
|---|---|---|
| `task_id` | string | 关联任务 |
| `provider` | enum | 仅 `intelliq` 需要该汇总 |
| `created_session_count` | integer | 成功创建的真实 Session 数量 |
| `cleanup_candidate_count` | integer | 去重后的待删除 ID 数量 |
| `cleanup_status` | enum | `not_required`, `cleaned`, `failed`, `pending_retry` |
| `cleanup_warning` | object nullable | 失败类别、尝试次数和安全摘要 |
| `completed_at` | timestamp | 清理流程最后更新时间 |

该汇总可作为任务 warning 或报告 metadata 的投影；真实待清理 ID 仍以 `EvaluationSampleRun.provider_session_id` 为权威。

## Session Lifecycle

```text
[Sample starts]
  -> pending
  -> creating
  -> created(provider_session_id recorded)
  -> agent_chat_running
  -> chat_completed | chat_failed | task_cancelled
  -> cleanup_pending
  -> cleaned | cleanup_failed

Creation failure:
  pending -> creating -> creation_failed
```

## Task-Level Cleanup Lifecycle

```text
[Sample loop exits]
  -> collect current task's created + pending Session IDs
  -> deduplicate and batch delete
  -> cleaned
     or
  -> cleanup_failed / pending_retry

[Service startup or retry worker]
  -> collect pending_retry IDs
  -> retry cleanup without changing completed task outcome
```

## Relationships

```text
EvaluationTask 1 --- * EvaluationSampleRun
EvaluationSampleRun 0..1 --- 1 IntelliQ provider Session
EvaluationTask 0..1 --- 1 TaskSessionCleanupSummary projection
```

## Migration

Additive migration only:

1. Add the five Session lifecycle columns to `evaluation_sample_runs` with safe defaults.
2. Existing rows retain their current `session_id` as local correlation IDs.
3. Existing completed historical rows receive `session_cleanup_status=not_required` unless they can be reliably identified as IntelliQ session runs.
4. Add an index for pending cleanup lookup by task and cleanup status.
5. Migration is idempotent and does not rewrite historical report answers or scores.
