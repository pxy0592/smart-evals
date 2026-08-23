# Implementation Plan: 数据集样本分页预览

**Branch**: `006-dataset-sample-pagination` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-dataset-sample-pagination/spec.md`

## Summary

在数据集管理页面的样例预览中引入服务端分页浏览：每次请求和展示固定 5 条样本，使用现有样本读取能力返回的总数驱动页码导航。预览切换到另一数据集、关闭后重开或数据总量变化时回到有效的第 1 页；页面切换期间只接受当前数据集和当前页的结果，避免延迟响应覆盖正在查看的内容。该功能不改变数据集内容、生成、上传、删除、评测任务或服务端存储。

## Technical Context

**Language/Version**: TypeScript 5.7、React 18；Python 3.12（仅对既有样本读取契约进行回归验证）

**Primary Dependencies**: Ant Design 5、Axios；Flask 现有数据集样本读取路由

**Storage**: SQLite 数据集元数据与本地 JSON 样本文件；本功能不新增或变更持久化数据

**Testing**: 后端 pytest 契约测试；前端 TypeScript 类型检查和生产构建；浏览器端手工验收

**Target Platform**: 现代桌面浏览器；Docker 部署的 Smart Eval Web 应用

**Project Type**: Web application（React 单页前端 + Flask 后端）

**Performance Goals**: 在正常服务状态下，切换样本页面后 2 秒内显示对应 5 条样本或明确失败反馈

**Constraints**:
- 页面大小固定为 5 条，不提供用户自定义页大小。
- 复用既有样本读取接口的 `offset`、`limit` 和 `total` 语义，不新增服务端接口。
- 每次预览打开、切换数据集或关闭后重开均从第 1 页开始。
- 不得让旧数据集或旧页面的异步返回覆盖当前预览。

**Scale/Scope**: 仅影响数据集管理页面的样例预览与其前端服务类型；单页最多读取和渲染 5 条样本。

## Constitution Check

项目 constitution 仍是未填写的模板，未定义可执行的架构、测试或治理门禁。本功能遵循现有项目结构和最小变更原则：复用既有样本分页能力、没有新增依赖、没有数据库迁移、没有改变权限或接口版本。

**Pre-Phase 0 Gate**: PASS — 未发现可执行 constitution 约束冲突。

## Project Structure

### Documentation (this feature)

```text
specs/006-dataset-sample-pagination/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── dataset-sample-pagination.md
└── tasks.md                 # Created later by $speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── evaluation_db.py                         # Existing sample read route; contract regression only
└── tests/
    └── contract/
        └── test_dataset_samples_api.py      # Add or extend pagination contract coverage

frontend/
└── src/
    ├── pages/
    │   └── Datasets.tsx                     # Preview state, page changes, sample ordinal, pagination UI
    └── services/
        ├── api.ts                           # Existing Axios request configuration support
        └── evaluation.ts                    # Dataset sample response typing and request parameters
```

**Structure Decision**: 采用现有 React 前端与 Flask 后端结构。业务实现集中在数据集预览页面；后端样本读取路由已经支持偏移量、单页数量和总数，仅需通过契约测试锁定其分页语义。不存在数据模型迁移或新服务模块。

## Complexity Tracking

无 constitution 违规或额外复杂度需要记录。

## Post-Phase 1 Constitution Check

PASS — 设计继续复用已存在的样本读取契约和前端组件体系；没有新增依赖、数据存储、后端端点或权限模型。
