# Data Model: 恢复可恢复 SSE 工具错误

**Feature**: 008-recover-sse-tool-errors  
**Date**: 2026-08-23

## Entity: 工具错误诊断

一次 SSE 工具调用发生的可恢复错误摘要。

| Field | Meaning | Validation / Privacy Rule |
|---|---|---|
| `tool_call_id` | 上游工具调用标识 | 可选；用于去重和关联，不包含凭证 |
| `tool_name` | 工具名称 | 可选；仅保留上游工具标识 |
| `message` | 错误摘要 | 截断；不保存原始参数、凭证或内部堆栈 |
| `recovered` | 是否在同一流中获得最终成功答案 | 终态确定后写入 |
| `event_count` | 合并后的重复次数 | 最小值为 1 |

**Identity rule**: `tool_call_id + message` 为首选去重键；工具调用标识缺失时，使用 `tool_name + message`。

## Extended Entity: 样本查询结果

已有样本结果新增 `tool_errors`，与答案、引用、上下文和最终错误并列。

| Field | Meaning |
|---|---|
| `completed` | 是否得到完整最终答案 |
| `score_eligible` | 是否可进入评分 |
| `answer` / `partial_answer` | 聚合后的最终或部分答案 |
| `references` / `contexts` | 聚合后的检索证据 |
| `tool_errors` | 可恢复工具错误诊断列表 |
| `error` | 最终终止错误；恢复成功时为空 |

## Persisted Entity: 样本运行记录

样本运行记录增加可选工具错误诊断字段，以便任务状态接口和报告详情读取。历史记录缺少该字段时视为 `[]`。

## Report Detail

成功详情和失败详情均可包含 `tool_errors`：

- 成功详情：`completion_status = completed`，每条诊断 `recovered = true`；
- 失败详情：`completion_status = failed`，诊断 `recovered = false`，并保留最终错误。

## State Transitions

```text
stream start
  -> normal events / answer fragments
  -> recoverable tool error -> append or merge diagnostic -> continue stream
  -> terminal error -> failed result
  -> completed answer or complete with non-empty answer -> completed result
  -> stream end without complete non-empty answer -> failed result
```

## Invariants

- 只有完整非空最终答案可以使样本成功。
- 可恢复工具错误不能覆盖最终成功状态。
- 终止错误覆盖先前的可恢复错误，样本最终失败。
- 诊断不得包含原始工具参数、凭证或完整内部堆栈。
