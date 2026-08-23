# Smart Eval - 快速开始

## 三步部署

### 1️⃣ 配置环境变量

```bash
cp .env.example .env
vi .env
```

必填项：
```bash
# 至少配置一个 LLM API Key
SILICONFLOW_API_KEY=sk-your-api-key-here

# 如果使用 RAGFlow
RAGFLOW_API_KEY=ragflow-your-key
RAGFLOW_BASE_URL=http://your-server-ip:9380/api/v1

# 如果通过页面配置 IntelliQ
# 使用 Fernet.generate_key() 生成加密密钥
RAG_CREDENTIAL_ENCRYPTION_KEY=your-fernet-key
SMART_EVAL_ADMIN_TOKEN=your-admin-token
DATABASE_PATH=data/evaluation.db
```

### 2️⃣ 启动服务

```bash
./start.sh
```

### 3️⃣ 访问系统

浏览器打开：http://localhost:5003

## 常用命令

```bash
./start.sh    # 启动服务
./stop.sh     # 停止服务
./update.sh   # 更新镜像
./backup.sh   # 备份数据

# 查看日志
docker-compose logs -f
```

## 帮助文档

详细文档请查看 [README.md](README.md)

## IntelliQ 会话验证

IntelliQ 评测任务会自动创建并清理临时会话。部署前先运行状态化 mock 生命周期测试；真实环境验证必须使用允许删除会话的隔离测试租户，并遵循 `specs/005-intelliq-session-creation/quickstart.md`，不要将真实 API Key 或 Session ID 写入文档和命令历史。
