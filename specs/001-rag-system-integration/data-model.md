# Data Model: 新 RAG 系统接入

**Feature**: `001-rag-system-integration`

**Date**: 2026-08-22

## Design Principles

- 被测 RAG 系统连接与评分 LLM 配置分离。
- API Key 只存在于加密连接记录和任务运行时内存中。
- 任务、报告和样本结果使用稳定 ID，并保存非敏感名称快照。
- 所有 schema 变化通过幂等 migration 应用于现有 SQLite 数据库。
- 旧 RAGFlow 任务和报告保持可读，不伪造未知的历史知识库信息。

## Entity: RagConnection

表示一个由 Smart Eval 使用的被测 RAG 系统连接。RAGFlow 默认连接是环境变量生成的合成实体，不写入此表；第一阶段数据库中最多存在一个启用的 IntelliQ 连接。

### Fields

| Field | Type | Required | Rules |
|---|---|---:|---|
| `id` | string UUID | yes | Primary key, immutable |
| `name` | string(100) | yes | Trimmed, unique among stored connections |
| `provider` | enum | yes | First phase stored value is `intelliq` |
| `base_url` | string(500) | yes | Canonical service root; no trailing slash or `/api/v1`; HTTP/HTTPS policy validated |
| `api_key_ciphertext` | text | yes | Encrypted value; never serialized to API responses |
| `api_key_fingerprint` | string(32) | yes | Non-secret fingerprint for audit/change detection; not usable for authentication |
| `enabled` | boolean | yes | Only one IntelliQ connection may be enabled in phase 1 |
| `revision` | integer | yes | Starts at 1; increments on URL, key, options or enabled-state changes |
| `validation_status` | enum | yes | `untested`, `available`, `unavailable` |
| `last_validated_at` | timestamp nullable | no | UTC timestamp |
| `last_error_category` | enum nullable | no | Sanitized connection error category |
| `last_error_message` | string(500) nullable | no | Sanitized; no request headers or key |
| `created_by` | string(100) | yes | Fixed authorization subject `deployment-admin`; never the token value |
| `created_at` | timestamp | yes | UTC |
| `updated_at` | timestamp | yes | UTC |

### Validation Rules

- `base_url` must normalize successfully and pass the SSRF target policy.
- Omitting `api_key` during update preserves the current encrypted key.
- Empty, whitespace-only or mask-looking values are rejected as replacement keys.
- An enabled connection must have a configured key.
- Key decryption failure makes the connection unavailable and must not fall back to plaintext.

### State Transitions

```text
created -> untested
untested -> available      successful validation
untested -> unavailable    failed validation
available -> unavailable   later validation or request failure
unavailable -> available   successful revalidation
enabled -> disabled        administrator action
disabled -> untested       re-enabled after configuration change
```

## Entity: RagConnectionAudit

Append-only record of non-sensitive connection changes.

| Field | Type | Required | Rules |
|---|---|---:|---|
| `id` | integer | yes | Primary key |
| `connection_id` | UUID | yes | References stored RagConnection |
| `revision` | integer | yes | Revision after the operation |
| `action` | enum | yes | `created`, `updated`, `enabled`, `disabled`, `validated` |
| `changed_fields` | JSON array | yes | Field names only; never credential values |
| `actor` | string(100) | yes | `deployment-admin`; optional untrusted caller label is stored separately |
| `caller_label` | string(100) nullable | no | Informational only; must not be treated as authenticated identity |
| `result` | enum | yes | `success`, `failure` |
| `error_category` | string nullable | no | Sanitized category |
| `created_at` | timestamp | yes | UTC |

## Entity: RagConnectionSummary

API projection for both the stored IntelliQ connection and synthetic `ragflow-default` connection.

| Field | Type | Notes |
|---|---|---|
| `id` | string | `ragflow-default` or UUID |
| `provider` | `ragflow` or `intelliq` | Stable discriminator |
| `name` | string | Display name |
| `api_url` | string | Normalized non-secret service root, without `/api/v1` |
| `api_key_configured` | boolean | Never returns key material |
| `editable` | boolean | `false` for environment-backed RAGFlow |
| `enabled` | boolean | Usable selection state |
| `status` | enum | `untested`, `available`, `unavailable` |
| `revision` | integer | Synthetic RAGFlow uses a process-start revision |
| `capabilities` | object | Resource discovery, streaming chat and AI dataset generation flags |
| `last_tested_at` | timestamp nullable | Display only |
| `error` | object nullable | Sanitized category/message |

## Entity: KnowledgeBaseRef

Normalized external knowledge base reference. It is not persisted as an authoritative resource catalog.

| Field | Type | Required | Rules |
|---|---|---:|---|
| `id` | string | yes | Upstream stable ID |
| `provider` | enum | yes | Matches connection provider |
| `connection_id` | string | yes | Matches selected connection |
| `name` | string | yes | Fallback to stable ID if upstream name missing |
| `description` | string nullable | no | Sanitized text |
| `selectable` | boolean | yes | False when disabled or inaccessible |
| `disabled_reason` | string nullable | no | User-safe reason |
| `document_count` | integer nullable | no | Provider-specific optional projection |
| `chunk_count` | integer nullable | no | Provider-specific optional projection |
| `raw_status` | string nullable | no | Diagnostic mapping only |

## Entity: AssistantRef

Normalized RAGFlow Chat or IntelliQ Agent reference.

| Field | Type | Required | Rules |
|---|---|---:|---|
| `id` | string | yes | Upstream stable ID |
| `provider` | enum | yes | Matches connection provider |
| `connection_id` | string | yes | Matches selected connection |
| `name` | string | yes | Fallback to stable ID if missing |
| `description` | string nullable | no | Sanitized text |
| `built_in` | boolean nullable | no | IntelliQ projection |
| `selectable` | boolean | yes | False for disabled or inaccessible assistants |
| `disabled_reason` | string nullable | no | User-safe reason |
| `knowledge_base_selection_mode` | enum | yes | Normalized `all`, `selected`, or `none` |

### Knowledge Base Mode Rules

- `selected`: task creation requires one or more selectable knowledge-base IDs.
- `all`: task creation requires an empty manual knowledge-base list; provider follows the Agent's full configured scope.
- `none`: task creation requires an empty list and sends no knowledge-base IDs upstream.
- Missing or unknown modes make the Assistant non-selectable until resources are refreshed.

## Entity: EvaluationDataset (clarified contract)

The existing dataset entity remains Smart Eval-owned.

| Field | Type | Required | Rules |
|---|---|---:|---|
| `file_type` | enum | yes | `json`, `jsonl`, `csv`, `xlsx`, `xls` |
| `file_size` | integer | yes | Maximum 10,485,760 bytes (10 MiB product limit) |
| `storage_path` | string | yes | Original upload or controlled temporary path |
| `normalized_storage_path` | string | yes when completed | Unified JSON sample representation used by evaluation tasks |
| `status` | enum | yes | `pending`, `processing`, `completed`, `failed` |
| `error_message` | string nullable | no | File-level or sample-level validation failure |

A dataset can enter `completed` only after format parsing, normalization and required-field validation succeed.

## Entity: EvaluationTask (extended)

Existing `evaluation_tasks` entity remains authoritative for task lifecycle.

### Existing Fields Retained

`id`, `name`, `chat_id`, `dataset_id`, `llm_model`, `embedding_model`, `metrics`, `status`, `progress`, `total_samples`, `processed_samples`, `batch_size`, `error_message`, `created_by`, `created_at`, `started_at`, `completed_at`.

### New Fields

| Field | Type | Required | Rules |
|---|---|---:|---|
| `rag_provider` | enum | yes | Default/backfill `ragflow` |
| `rag_connection_id` | string nullable | no | Legacy rows may be null; API maps them to `ragflow-default` |
| `rag_connection_revision` | integer nullable | no | Required for new provider-aware tasks |
| `assistant_id` | string nullable | no | New canonical field; legacy fallback is `chat_id` |
| `assistant_name_snapshot` | string nullable | no | Immutable display snapshot |
| `knowledge_base_ids` | JSON array | yes | Empty array for unknown legacy rows |
| `knowledge_base_names_snapshot` | JSON array | yes | Same order as IDs |
| `knowledge_base_selection_mode_snapshot` | enum nullable | no | `all`, `selected`, `none`; null only for legacy rows |
| `connection_name_snapshot` | string nullable | no | Historical display |
| `connection_base_url_snapshot` | string nullable | no | Non-secret canonical URL |
| `source_legacy` | boolean | yes | True for backfilled tasks with incomplete source identity |
| `interrupted_at` | timestamp nullable | no | Set when stale running task is recovered as failed |
| `has_warnings` | boolean | yes | True when task completed with one or more failed samples |
| `outcome` | enum nullable | no | `succeeded`, `partially_succeeded`, `failed`, `cancelled`; null before terminal state |
| `scored_sample_count` | integer | yes | Count of final successful sample attempts |
| `failed_sample_count` | integer | yes | Count of sample indices whose final attempt failed |

### Compatibility Rules

- New writes set both `assistant_id` and `chat_id` for one compatibility cycle.
- Legacy request with only `chat_id` maps to provider `ragflow`, connection `ragflow-default`, assistant ID equal to `chat_id`.
- A request containing both `rag_target` and top-level `chat_id` is rejected as ambiguous.
- Unknown historical knowledge base IDs remain empty; migration does not invent them.
- New tasks enforce mode/list consistency: selected has at least one ID; all and none have an empty list.

### State Transitions

```text
pending -> running
pending -> cancelled
running -> completed
running -> failed
running -> cancelled
running -> failed(interrupted)  application restart or stale worker recovery
failed -> pending              explicit retry creates a fresh execution attempt
```

A task is `completed` when orchestration finished and at least one sample is scoreable. Failed samples are surfaced through success rate and report warnings. If no sample is scoreable, the task is `failed` and no final quality report is created.

Terminal projection rules:

- all samples successful: `status=completed`, `outcome=succeeded`, `has_warnings=false`.
- at least one success and one failure: `status=completed`, `outcome=partially_succeeded`, `has_warnings=true`.
- zero successful samples: `status=failed`, `outcome=failed`, no final report row.

## Entity: EvaluationSampleRun

Durable execution and diagnostic state for one dataset sample attempt.

| Field | Type | Required | Rules |
|---|---|---:|---|
| `id` | integer | yes | Primary key |
| `task_id` | string | yes | References EvaluationTask |
| `sample_index` | integer | yes | Zero-based dataset order |
| `attempt` | integer | yes | Starts at 1 |
| `session_id` | string | yes | Unique per sample attempt |
| `status` | enum | yes | `pending`, `running`, `completed`, `failed`, `cancelled` |
| `question` | text | yes | Snapshot of evaluated input |
| `answer` | text nullable | no | Only complete merged answer is scoreable |
| `partial_answer` | text nullable | no | Diagnostic only; never scored |
| `contexts` | JSON array | yes | Normalized reference text |
| `references` | JSON array | yes | Structured upstream references |
| `intermediate_event_summary` | JSON object | yes | Event counts/types without credential data |
| `completed_signal_received` | boolean | yes | Must be true for completed status |
| `error_category` | enum nullable | no | Auth, permission, timeout, rate-limit, upstream, protocol or cancellation |
| `error_message` | text nullable | no | Sanitized |
| `started_at` | timestamp nullable | no | UTC |
| `completed_at` | timestamp nullable | no | UTC |

### Constraints

- Unique key: `(task_id, sample_index, attempt)`.
- Completed state requires `completed_signal_received = true` and non-empty answer.
- Failed/incomplete rows are excluded from RAGAS input.
- API Key and request headers are forbidden in all fields.

## Entity: EvaluationReport (extended)

Existing `evaluation_reports` remains the report store. Source fields are copied from the task so reports remain readable after connection changes.

### Existing Fields Retained

`task_id`, `chat_id`, `dataset_id`, `overall_scores`, `detailed_scores`, `evaluation_metadata`, `report_file_path`, `created_at`.

### New Fields

| Field | Type | Required | Rules |
|---|---|---:|---|
| `rag_provider` | enum | yes | Default/backfill `ragflow` |
| `rag_connection_id` | string nullable | no | Legacy may be null |
| `assistant_id` | string nullable | no | Legacy fallback to `chat_id` |
| `knowledge_base_ids` | JSON array | yes | Empty for unknown legacy reports |
| `source_snapshot` | JSON object | yes | Connection, assistant and KB names/IDs; no credentials |
| `scored_sample_count` | integer | yes | Denominator for quality metrics |
| `failed_sample_count` | integer | yes | Execution failures, not scored |
| `total_sample_count` | integer | yes | Dataset sample count for the task |
| `success_rate` | real | yes | `scored_sample_count / total_sample_count` |
| `warning` | JSON object nullable | no | Partial-failure code, message and failed-sample count |

### Detailed Score Shape

Each item in `detailed_scores` adds:

- `sample_index`
- `completion_status`
- `references`
- `session_id`
- `upstream_error`
- existing `user_input`, `actual_answer`, `expected_answer`, `contexts` and metric scores

`source_snapshot` also records the normalized knowledge-base selection mode so reports explain why a task has zero, one or multiple explicit knowledge-base IDs.

Final report counts use only the highest/final attempt for each `sample_index`. A report row may exist only when `scored_sample_count > 0`; otherwise the task is failed and report lookup returns no final quality report.

## Migration Model

Introduce a `schema_migrations` table if not already present:

| Field | Type | Rules |
|---|---|---|
| `version` | integer | Primary key |
| `name` | string | Human-readable migration |
| `applied_at` | timestamp | UTC |

### Migration Sequence

1. Create `rag_connections`, `rag_connection_audit`, `evaluation_sample_runs` and `schema_migrations`.
2. Add provider/source columns to `evaluation_tasks` using `PRAGMA table_info` guards.
3. Add provider/source/filter columns to `evaluation_reports` using guards.
4. Backfill task/report `rag_provider = 'ragflow'`, empty JSON arrays and legacy flags.
5. Do not populate unknown historical knowledge base names or IDs.
6. Add indexes for connection provider/status, task provider/connection/status and sample task/status.
7. Execute each migration in a transaction and record version only after success.
8. Before enabling SQLite foreign keys, detect and report legacy orphan rows; do not delete them silently.
9. Resolve the database from `DATABASE_PATH`, defaulting to the mounted `data/evaluation.db`; if only a legacy database exists outside the mounted path, back it up and migrate before serving writes.
10. Apply WAL mode and `busy_timeout`; keep migration and sample-result transactions short and retry only SQLite lock conflicts within a bounded policy.

## Relationships

```text
RagConnection 1 ---- * RagConnectionAudit
RagConnection 1 ---- * EvaluationTask       (nullable for legacy/synthetic RAGFlow)
EvaluationTask 1 ---- * EvaluationSampleRun
EvaluationTask 1 ---- 0..1 EvaluationReport
Dataset        1 ---- * EvaluationTask
EvaluationTask * ---- snapshots of KnowledgeBaseRef and AssistantRef
```
