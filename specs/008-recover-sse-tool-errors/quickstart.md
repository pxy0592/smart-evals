# Quickstart: 恢复可恢复 SSE 工具错误验证

**Feature**: 008-recover-sse-tool-errors  
**Date**: 2026-08-23

## Prerequisites

- Smart Eval 后端依赖已安装。
- IntelliQ SSE 聚合单元测试可运行。
- 如进行真实验证，存在能够在工具错误后继续输出答案的 IntelliQ 智能体。

## Automated Validation

```bash
PYTHONPYCACHEPREFIX=/tmp/smart-eval-pyc .venv/bin/python -m pytest backend/tests -q
PYTHONPYCACHEPREFIX=/tmp/smart-eval-pyc .venv/bin/python -m compileall -q backend
cd frontend && npm run typecheck && npm run build
```

**Expected**: 测试覆盖恢复成功、终止失败、空答案失败、诊断去重和报告持久化；后端编译与前端回归通过。

## Recovery Scenario

1. 运行模拟流：工具错误 → 工具错误 → 成功工具结果 → 非空完成答案。
2. **Verify**：样本为 completed 且可评分；最终答案完整保留。
3. **Verify**：结果包含两条已恢复工具诊断，不包含原始参数。

## Terminal Failure Scenario

1. 运行明确完成的错误流，或工具错误后没有非空最终答案的流。
2. **Verify**：样本为 failed，最终错误可见，诊断不标记为已恢复。

## Real IntelliQ Regression Scenario

1. 使用包含工具调用的 IntelliQ 智能体创建小规模评测任务。
2. 当工具先报错、后续自行修正并返回最终答案时，等待任务完成。
3. **Verify**：该样本计入执行成功率；报告详情展示恢复工具诊断。
4. 验证真正终止的 IntelliQ 错误仍按失败统计。

## Expected Outcome

Smart Eval 不再因可恢复工具错误丢弃最终有效答案，同时保留足够、非敏感的诊断来审计 IntelliQ 工具稳定性。
