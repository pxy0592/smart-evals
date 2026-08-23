# Data Model: 数据集样本分页预览

**Feature**: 006-dataset-sample-pagination  
**Date**: 2026-08-23

## Existing Entity: 数据集样本

一条存储在数据集中的可预览记录。常见字段包括问题、参考答案、上下文和其他保留字段；本功能不修改这些字段或其存储方式。

| Field | Meaning | Rules for this feature |
|---|---|---|
| `question` | 样本问题 | 原样展示 |
| `expected_answer` | 可选参考答案 | 有值时原样展示 |
| `contexts` | 可选上下文列表 | 有值时原样展示 |
| additional fields | 其他样本字段 | 不因分页而丢失或修改 |

## View Model: 样本预览分页状态

仅存在于用户当前预览会话中，不写入数据库。

| Field | Meaning | Validation / Rule |
|---|---|---|
| `datasetId` | 当前预览的数据集标识 | 每次打开或切换预览时更新 |
| `currentPage` | 当前页面，按 1 开始计数 | 最小值为 1；不得超过由总数计算的最后页 |
| `pageSize` | 单页样本数量 | 固定为 5 |
| `offset` | 当前页在样本序列中的起始位置 | `(currentPage - 1) × pageSize` |
| `totalSamples` | 当前可读取的样本总数 | 来自样本读取结果；用于计算总页数 |
| `samples` | 当前页样本列表 | 长度为 0 至 5；只对应 `datasetId` 与 `currentPage` |
| `loadState` | 加载状态 | `idle`、`loading`、`ready` 或 `error` |
| `requestIdentity` | 当前读取请求的身份 | 仅与当前 `datasetId` 和页面匹配的结果可以更新预览 |

## Relationships

```text
Dataset (1) ── contains ──> DatasetSample (0..N)
Dataset (1) ── viewed through ──> SamplePreviewPage (0..N pages per preview session)
SamplePreviewPage (1) ── displays ──> DatasetSample (0..5)
```

## State Transitions

| Trigger | Previous State | New State | Expected Result |
|---|---|---|---|
| Open preview | any | loading page 1 | 清空先前页内容，读取前 5 条 |
| Page change | ready / error | loading selected page | 保留正确的预览目标，读取对应偏移量 |
| Page result accepted | loading | ready | 显示最多 5 条当前页样本及总数 |
| Page result fails | loading | error | 显示明确失败反馈，不把失败页当作成功内容 |
| Switch dataset or reopen | any | loading page 1 | 旧请求结果不可覆盖新数据集 |
| Total shrinks below current page | ready / loading | loading valid page | 回到第 1 页并显示有效样本范围 |
| Close preview | any | idle | 结束当前预览会话；重开从第 1 页开始 |
