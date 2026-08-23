# Contract: 数据集样本分页预览

**Feature**: 006-dataset-sample-pagination  
**Status**: Existing read contract consumed by the preview UI

## Sample Page Read

### Request

```text
GET /api/v1/evaluation/datasets/{dataset_id}/samples?offset={offset}&limit=5
```

| Input | Required | Meaning | Rule |
|---|---:|---|---|
| `dataset_id` | Yes | 要预览的数据集 | 必须对应现有数据集 |
| `offset` | Yes | 当前页起始位置 | 第 1 页为 0；后续页按 5 递增 |
| `limit` | Yes | 请求的样本数量 | 本功能固定为 5 |

### Success Response

```json
{
  "samples": ["最多 5 条样本"],
  "total": 12,
  "limit": 5,
  "offset": 5
}
```

| Output | Meaning | Consumer Rule |
|---|---|---|
| `samples` | 当前页样本列表 | 显示为当前页内容，长度为 0 至 5 |
| `total` | 当前可读取样本总数 | 计算页数和分页范围 |
| `limit` | 本次实际页大小 | 预览期望为 5 |
| `offset` | 本次实际起始位置 | 用于连续样本序号与结果匹配 |

### Error Responses

| Status | Condition | Preview Behavior |
|---:|---|---|
| 404 | 数据集或样本文件不存在 | 显示明确的样本不可用/找不到提示，不显示成功内容 |
| 500 | 样本读取失败 | 显示明确失败提示，允许用户重试或返回已成功页面 |

## UI Pagination Contract

- 首次打开、切换到另一数据集、关闭后重开时，读取 `offset=0&limit=5`。
- 用户选择第 `N` 页时，读取 `offset=(N-1)×5&limit=5`。
- 当 `total` 为 0 时显示空状态；当 `total` 为 1 至 5 时不提供可前往的额外页面。
- 如果响应不再对应当前数据集或当前页，客户端必须忽略该响应。
- 样本显示序号从 `offset+1` 开始，保证跨页连续。
