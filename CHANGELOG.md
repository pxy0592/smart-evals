# 更新日志

## [Unreleased] - 2026-08-22

### 新增
- IntelliQ RAG 连接配置、知识库/Agent 发现和 SSE 评测适配
- Provider 来源快照、样本会话隔离、部分失败警告和报告筛选
- JSON、JSONL、CSV、XLSX、XLS 数据集统一归一化（最大 10 MiB）

### 安全与可靠性
- IntelliQ API Key 加密保存，连接写操作由部署级管理员令牌保护
- 可配置 RAG URL 增加规范化和 SSRF 防护
- SQLite 使用持久化路径、WAL、busy timeout 和增量迁移

## [1.0.0] - 2024-11-10

### 新增
- 独立的 Docker 部署目录
- 使用预构建镜像 `zxwei/knowflow-eval:latest`
- 完整的维护脚本（start.sh, stop.sh, update.sh, backup.sh）
- 详细的部署文档和快速开始指南
- MIT 开源许可证

### 改进
- 简化部署流程，三步即可完成
- 自动健康检查和服务监控
- 智能备份机制（保留最近 7 个备份）
- 完善的错误处理和日志输出

### 安全
- 环境变量与源码分离
- .gitignore 保护敏感信息
- 最小化镜像体积（源码编译为 .pyc）

---

## 版本说明

版本格式：`主版本号.次版本号.修订号`

- **主版本号**：不兼容的 API 修改
- **次版本号**：向下兼容的功能新增
- **修订号**：向下兼容的问题修正

## 镜像标签

- `latest` - 最新稳定版
- `v1.0.0` - 具体版本号（推荐生产环境使用）

## 获取更新

```bash
# 拉取最新镜像
docker-compose pull

# 更新并重启服务
./update.sh
```
