# Data Model: 修复评测任务创建

**Feature**: 007-fix-task-creation  
**Date**: 2026-08-23

## Existing Entity: 评测任务创建请求

用户提交的评测目标，在任务记录写入前完成资源读取和业务校验。

| Field | Meaning | Validation Rule |
|---|---|---|
| `connectionId` | 已启用的 RAG 连接 | 必须存在且可用 |
| `assistantId` | 目标智能体 | 必须存在、可选择且配置有效 |
| `knowledgeBaseIds` | 用户选择的知识库 | 必须符合智能体的 `none`、`selected` 或 `all` 规则 |
| `datasetId` | 已完成数据集 | 必须存在且可用于评测 |
| `metrics` | 选定评测指标 | 至少包含一个有效指标 |

## Request-Scoped Entity: 提供者资源范围

不持久化，仅用于一次资源读取或任务创建校验。

| Field | Meaning | Lifecycle Rule |
|---|---|---|
| `provider` | 当前 RAG 提供者实例 | 仅供单次请求的异步工作单元使用 |
| `eventLoop` | 执行资源读取的事件循环 | 资源创建、使用和关闭均在该循环有效期间完成 |
| `operationState` | `created`、`active`、`closing`、`closed` | `closed` 后不得再使用 provider 的客户端资源 |
| `operationError` | 非敏感错误结果 | 返回给路由前完成结构化映射 |

## Existing Entity: 评测任务

仅在创建请求校验通过后保存。保留已存在的目标快照、连接修订版本、智能体、知识库、数据集和指标字段。

## State Transitions

```text
received
  -> validating connection / assistant / knowledge bases
  -> validation failed -> structured failure; no task persisted
  -> validation passed -> task persisted as pending
  -> returned to caller

provider scope: created -> active -> closing -> closed
```

## Invariants

- 已关闭的 provider 资源不得被任何后续异步工作单元重用。
- 校验失败时没有可见的新评测任务记录。
- 每次创建请求拥有独立的提供者资源范围。
- 任务创建成功后，后续评测运行时资源生命周期与本次创建范围分离。
