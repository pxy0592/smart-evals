# Quickstart: 数据集样本分页预览验证

**Feature**: 006-dataset-sample-pagination  
**Date**: 2026-08-23

## Prerequisites

- Smart Eval 已启动并且数据集管理页面可访问。
- 至少准备一个包含 12 条或更多样本的数据集；另准备包含 0、3、5 和 6 条样本的数据集用于边界验证。
- 前端依赖已安装。

## Static Checks

```bash
cd frontend && npm run typecheck && npm run build
PYTHONPYCACHEPREFIX=/tmp/smart-eval-pyc .venv/bin/python -m pytest backend/tests -q
```

**Expected**: 前端类型检查和生产构建成功；后端测试成功，包括样本分页契约覆盖。

## Service Contract Check

对一个有 12 条样本的数据集分别读取三个页面：

```bash
curl -sS 'http://localhost:5003/api/v1/evaluation/datasets/<dataset-id>/samples?offset=0&limit=5'
curl -sS 'http://localhost:5003/api/v1/evaluation/datasets/<dataset-id>/samples?offset=5&limit=5'
curl -sS 'http://localhost:5003/api/v1/evaluation/datasets/<dataset-id>/samples?offset=10&limit=5'
```

**Expected**:

| Request offset | Returned samples | Reported total |
|---:|---:|---:|
| 0 | 5 | 12 |
| 5 | 5 | 12 |
| 10 | 2 | 12 |

## Browser Validation

1. 打开数据集管理页面，并预览包含 12 条样本的数据集。
2. **Verify**：第 1 页只显示样本 1 至 5，并显示总样本数和分页位置。
3. 切换到第 2 页。
4. **Verify**：只显示样本 6 至 10；样本序号连续且不显示第 1 页内容。
5. 切换到第 3 页。
6. **Verify**：只显示样本 11 至 12，没有空白或重复样本。
7. 关闭预览后重新打开同一数据集。
8. **Verify**：预览回到第 1 页。
9. 依次预览 0、3、5 和 6 条样本的数据集。
10. **Verify**：空数据集显示空状态；3 和 5 条样本没有无效翻页；6 条样本有 2 页且最后一页只显示 1 条。
11. 在加载某页时立即切换数据集或关闭预览。
12. **Verify**：不会显示前一个数据集或旧页的延迟返回内容。

## Expected Outcome

用户可以每次浏览最多 5 条样本，访问任意有效页，并在 2 秒内看到对应页内容或明确的失败反馈；数据集管理、上传、生成、删除和评测任务行为保持不变。
