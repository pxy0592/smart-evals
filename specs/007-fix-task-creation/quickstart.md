# Quickstart: 修复评测任务创建验证

**Feature**: 007-fix-task-creation  
**Date**: 2026-08-23

## Prerequisites

- Smart Eval 已启动。
- 存在已完成的数据集。
- 存在已验证 IntelliQ 连接，以及一个可选择的智能体。
- 智能体的知识库模式和允许知识库已知。

## Automated Validation

```bash
PYTHONPYCACHEPREFIX=/tmp/smart-eval-pyc .venv/bin/python -m pytest backend/tests -q
PYTHONPYCACHEPREFIX=/tmp/smart-eval-pyc .venv/bin/python -m compileall -q backend
cd frontend && npm run typecheck && npm run build
```

**Expected**: 所有测试、后端编译、前端类型检查和构建通过。

## Valid IntelliQ Task Creation

1. 打开数据集管理页面，选择已完成数据集并点击“创建评测”。
2. 选择 IntelliQ 连接和 `selected` 模式智能体。
3. 选择一个该智能体允许的知识库，选择指标并提交。
4. **Verify**：返回任务已创建；不显示“Event loop is closed”；任务列表出现 `pending` 任务。
5. 不刷新服务，重复步骤 1–4 至少两次。
6. **Verify**：每次创建均成功，后一次不受前一次资源关闭影响。

## Invalid Target Validation

1. 使用不属于 `selected` 模式智能体的知识库提交任务。
2. **Verify**：返回结构化 validation 或 permission 错误；任务列表不增加不完整任务。
3. 暂时使上游资源读取不可用或使用无权限智能体。
4. **Verify**：返回可理解的非敏感错误；没有 Flask traceback 或事件循环错误泄漏给用户。

## Regression Validation

1. 加载 IntelliQ 助手和知识库资源。
2. **Verify**：列表正常显示并遵循智能体知识库选择规则。
3. 使用已有 RAGFlow 目标创建任务。
4. **Verify**：原有创建流程保持可用。

## Expected Outcome

有效 IntelliQ 目标可连续创建任务；创建前失败不会留下任务记录；资源读取、任务创建和其他提供者流程均不出现事件循环生命周期错误。
