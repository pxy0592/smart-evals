# 发布检查清单

发布 `docker-deploy` 仓库到 GitHub 前的检查事项。

## 📋 发布前检查

### 1. 文档完整性

- [ ] README.md 内容完整且准确
- [ ] QUICKSTART.md 步骤可执行
- [ ] CHANGELOG.md 版本信息正确
- [ ] CONTRIBUTING.md 联系方式已更新
- [ ] LICENSE 文件存在

### 2. 配置文件

- [ ] .env.example 包含所有必需变量
- [ ] .env.example 不包含真实 API Key
- [ ] docker-compose.yml 镜像名称正确：`zxwei/knowflow-eval:latest`
- [ ] .gitignore 规则完整
- [ ] .dockerignore 规则适当

### 3. 脚本功能

- [ ] start.sh 可执行且功能正常
- [ ] stop.sh 可执行且功能正常
- [ ] update.sh 可执行且功能正常
- [ ] backup.sh 可执行且功能正常
- [ ] 所有脚本有执行权限 (chmod +x)

### 4. 镜像验证

- [ ] 镜像已推送到 Docker Hub
- [ ] 镜像可以正常拉取：`docker pull zxwei/knowflow-eval:latest`
- [ ] 镜像运行正常
- [ ] 健康检查通过

### 5. 敏感信息检查

- [ ] 没有真实的 API Key
- [ ] 没有密码或密钥
- [ ] 没有个人邮箱（除非有意公开）
- [ ] 没有内网 IP 地址
- [ ] data/、logs/、tmp/ 目录为空或不存在

### 6. 链接更新

- [ ] README.md 中的仓库链接已更新为 pxy0592/smart-evals
- [ ] README.md 中的邮箱已更新
- [ ] GitHub Issues 链接正确
- [ ] Docker Hub 链接正确

### 7. 测试验证

- [ ] 在干净的环境测试部署流程
- [ ] `./start.sh` 成功启动服务
- [ ] 访问 http://localhost:5003 正常
- [ ] 健康检查通过：http://localhost:5003/health
- [ ] `./stop.sh` 正常停止服务

## 🚀 发布步骤

### Step 1: 最终检查

```bash
cd docker-deploy

# 检查文件
ls -la

# 确认 .env 不存在（只有 .env.example）
ls -la .env

# 检查脚本权限
ls -l *.sh

# 验证没有敏感信息
grep -r "sk-" . --exclude-dir=.git || echo "No API keys found"
```

### Step 2: 初始化 Git

```bash
# 进入目录
cd docker-deploy

# 初始化
git init

# 添加所有文件
git add .

# 首次提交
git commit -m "Initial commit: Smart Eval Docker Deployment v1.0.0

- Complete deployment documentation
- Automated maintenance scripts
- Docker Compose configuration
- Environment variable templates
- MIT License"
```

### Step 3: 创建远程仓库

在 GitHub 上创建新仓库：
- 仓库名：`smart-eval-deploy`
- 描述：`smart Eval - RAG 评估系统 Docker 部署`
- 可见性：Public
- **不要**勾选 Initialize with README（我们已有）

### Step 4: 推送到 GitHub

```bash
# 添加远程仓库
git remote add origin https://github.com/pxy0592/smart-evals.git

# 推送到主分支
git branch -M main
git push -u origin main

# 创建版本标签
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

### Step 5: 配置仓库设置

在 GitHub 仓库页面：

1. **About** (点击仓库右侧的齿轮图标)
   - Description: `Smart Eval - RAG 评估系统 Docker 部署`
   - Website: `https://hub.docker.com/r/zxwei/knowflow-eval`
   - Topics: `docker`, `rag`, `evaluation`, `llm`, `docker-compose`

2. **Issues**
   - 启用 Issues
   - 添加 Issue 模板（可选）

3. **Discussions** (可选)
   - 启用 Discussions 方便用户交流

4. **Security**
   - 添加 SECURITY.md（可选）

### Step 6: 创建 Release

1. 访问仓库的 Releases 页面
2. 点击 "Create a new release"
3. 填写信息：
   - Tag: `v1.0.0`
   - Title: `v1.0.0 - Initial Release`
   - Description: 从 CHANGELOG.md 复制内容
4. 发布 Release

### Step 7: 添加徽章（可选）

在 README.md 顶部添加：

```markdown
[![Docker Image](https://img.shields.io/badge/docker-pxy0592%2Fsmart--eval-blue)](https://hub.docker.com/r/pxy0592/smart-evals)
[![Docker Pulls](https://img.shields.io/docker/pulls/pxy0592/smart-evals)](https://hub.docker.com/r/pxy0592/smart-evals)
[![GitHub release](https://img.shields.io/github/v/release/pxy0592/smart-evals)](https://github.com/pxy0592/smart-evals/releases)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
```

## 📢 发布后

### 1. 测试公开访问

```bash
# 在新目录克隆仓库
cd /tmp
git clone https://github.com/pxy0592RAG/smart-evals.git
cd smart-evals

# 测试部署流程
cp .env.example .env
# 编辑 .env 添加测试 API Key
./start.sh
```

### 2. 宣传推广

- 在相关论坛/社区分享
- 更新 Docker Hub 仓库描述
- 撰写博客文章（可选）
- 社交媒体分享（可选）

### 3. 维护计划

- 定期更新镜像
- 响应 Issues
- 审查 Pull Requests
- 更新文档

## 🔄 后续更新流程

发布新版本时：

```bash
# 1. 更新 CHANGELOG.md
vi CHANGELOG.md

# 2. 提交更改
git add .
git commit -m "Release v1.1.0: [描述更新内容]"

# 3. 创建标签
git tag -a v1.1.0 -m "Release v1.1.0"

# 4. 推送
git push origin main
git push origin v1.1.0

# 5. 在 GitHub 创建新 Release
```

## ✅ 检查完成

所有检查项完成后，即可发布！

---

**注意**：发布后仓库 URL 将公开，请确保：
- 没有敏感信息
- 文档准确完整
- 脚本经过测试
- 镜像可正常使用
