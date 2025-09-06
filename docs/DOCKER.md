# Docker 部署指南

本文档介绍如何使用 Docker 部署 Z.ai2api 服务。

## 快速开始

### 1. 环境准备

确保你的系统已安装：
- Docker 20.10+
- Docker Compose 2.0+

### 2. 获取项目

```bash
git clone https://github.com/Baozhi888/Z.ai2api.git
cd Z.ai2api
```

### 3. 配置环境变量

```bash
# 复制环境变量模板
cp .env.docker .env

# 编辑配置文件
nano .env
```

必须配置的变量：
- `ZAI_UPSTREAM_TOKEN`: 你的 Z.ai API 令牌
- `ZAI_API_KEY`: API 访问密钥（用于保护你的服务）

### 4. 启动服务

#### 方式一：独立运行

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

#### 方式二：使用 Nginx 反向代理（推荐）

```bash
# 使用带 Nginx 的配置
docker-compose -f docker-compose-with-nginx.yml up -d
```

### 5. 验证服务

```bash
# 健康检查
curl http://localhost:8089/health

# 测试 API
curl -X POST http://localhost:8089/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "glm-4.5v",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'
```

## 配置说明

### 环境变量

所有配置都可以通过环境变量设置，详见 `.env.docker` 文件。

### 端口配置

- 独立模式：直接映射端口到宿主机
- Nginx 模式：Nginx 监听 80/443 端口，代理到内部服务

### 日志管理

```bash
# 查看应用日志
docker-compose logs zai2api

# 查看 Nginx 日志（如果使用）
docker-compose logs nginx
```

日志文件会挂载到宿主机的 `./logs` 目录。

### 数据持久化

- 日志文件：`./logs`
- 无需其他持久化存储（所有数据在内存中）

## 生产环境部署

### 1. 使用 Nginx 反向代理

生产环境建议使用 `docker-compose-with-nginx.yml` 配置：

```bash
docker-compose -f docker-compose-with-nginx.yml up -d
```

### 2. SSL 配置

1. 准备 SSL 证书文件
2. 修改 `nginx/conf.d/zai2api.conf`，取消 HTTPS 配置注释
3. 将证书文件挂载到 `/etc/nginx/ssl`

### 3. 安全建议

1. **修改默认端口**：避免使用默认端口
2. **设置强密码**：为 `ZAI_API_KEY` 设置复杂的值
3. **启用防火墙**：只开放必要的端口
4. **定期更新**：及时更新 Docker 镜像
5. **监控日志**：定期检查访问日志

### 4. 性能优化

1. **调整资源限制**：
```yaml
# 在 docker-compose.yml 中添加
deploy:
  resources:
    limits:
      cpus: '1.0'
      memory: 512M
```

2. **使用多实例**：
```yaml
# 使用 docker-compose scale
docker-compose up -d --scale zai2api=3
```

## 常见问题

### 1. 容器启动失败

```bash
# 查看错误日志
docker-compose logs zai2api

# 检查配置
docker-compose config
```

### 2. API 请求超时

增加超时配置：
```env
ZAI_REQUEST_TIMEOUT=120
ZAI_STREAM_TIMEOUT=300
```

### 3. 内存使用过高

调整缓存配置：
```env
ZAI_CACHE_MAX_SIZE=500
ZAI_CONTENT_CACHE_TTL=1800
```

### 4. 无法获取模型列表

1. 检查 `ZAI_UPSTREAM_TOKEN` 是否正确
2. 确认网络可以访问 `https://chat.z.ai`
3. 尝试禁用匿名令牌：`ZAI_ANON_TOKEN_ENABLED=false`

## 更新服务

```bash
# 拉取最新代码
git pull origin main

# 重新构建镜像
docker-compose build

# 重启服务
docker-compose up -d
```

## 备份和恢复

### 备份

只需要备份配置文件：
```bash
# 备份配置
cp .env .env.backup
```

### 恢复

```bash
# 恢复配置
cp .env.backup .env

# 重启服务
docker-compose up -d
```

## 卸载

```bash
# 停止并删除容器
docker-compose down

# 删除镜像
docker rmi zai2api_zai2api

# 删除数据卷（如果需要）
docker volume rm zai2api_logs
```