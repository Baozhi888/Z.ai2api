# Z.ai2api 部署指南

## 部署方式

- [传统部署](#传统部署)
- [Docker 部署](#docker-部署-推荐)

## 传统部署

### 环境配置

### 1. 复制配置文件

```bash
cp .env.example .env
```

### 2. 配置环境变量

编辑 `.env` 文件，根据你的需求修改配置：

```bash
# ===== 基础配置 =====
# API 基础URL
ZAI_API_BASE=https://chat.z.ai

# 服务端口
ZAI_PORT=8080

# 调试模式 (true/false)
ZAI_DEBUG_MODE=false

# ===== 认证配置 =====
# 上游API令牌
ZAI_UPSTREAM_TOKEN=your-upstream-token-here

# 是否启用匿名令牌模式 (true/false)
ZAI_ANON_TOKEN_ENABLED=true

# ===== 访问密钥配置 =====
# API访问密钥（用于保护API端点）
# 生成一个强密码作为API密钥
ZAI_API_KEY=your-secret-api-key-here

# 是否启用API密钥验证 (true/false)
ZAI_API_KEY_ENABLED=true

# ===== 模型配置 =====
# 默认模型名称
ZAI_MODEL_NAME=GLM-4.5

# 思考标签处理模式 (think/pure/raw)
ZAI_THINK_TAGS_MODE=think

# ===== 性能配置 =====
# 模型列表缓存时间（秒）
ZAI_MODELS_CACHE_TTL=300

# 认证令牌缓存时间（秒）
ZAI_AUTH_TOKEN_CACHE_TTL=600

# 内容处理缓存时间（秒）
ZAI_CONTENT_CACHE_TTL=3600

# ===== 缓存配置 =====
# 缓存默认TTL（秒）
ZAI_CACHE_DEFAULT_TTL=300

# 缓存最大大小
ZAI_CACHE_MAX_SIZE=1000

# ===== 日志配置 =====
# 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
ZAI_LOG_LEVEL=INFO

# ===== 安全配置 =====
# 允许的CORS来源（多个用逗号分隔）
ZAI_CORS_ORIGINS=*

# 请求超时时间（秒）
ZAI_REQUEST_TIMEOUT=60

# 流式响应超时时间（秒）
ZAI_STREAM_TIMEOUT=120

# ===== 高级配置 =====
# 启用性能监控 (true/false)
ZAI_ENABLE_PERFORMANCE_MONITORING=true

# 启用请求追踪 (true/false)
ZAI_ENABLE_REQUEST_TRACING=true

# 最大并发请求数
ZAI_MAX_CONCURRENT_REQUESTS=100
```

## VPS 部署

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置服务

使用 systemd 创建服务文件：

```bash
sudo nano /etc/systemd/system/zai2api.service
```

内容如下：

```ini
[Unit]
Description=Z.ai2api Service
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/Z.ai2api
Environment=PATH=/path/to/Z.ai2api/venv/bin
ExecStart=/path/to/Z.ai2api/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3. 启动服务

```bash
# 重载 systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start zai2api

# 设置开机自启
sudo systemctl enable zai2api

# 查看服务状态
sudo systemctl status zai2api
```

### 4. 配置 Nginx 反向代理（可选）

```bash
sudo nano /etc/nginx/sites-available/zai2api
```

配置文件内容：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 支持流式响应
        proxy_buffering off;
        proxy_cache off;
    }
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/zai2api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 使用 API 密钥

当 `ZAI_API_KEY_ENABLED=true` 时，所有 API 请求都需要在请求头中包含 API 密钥：

```bash
curl -X POST http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-api-key-here" \
  -d '{
    "model": "GLM-4.5",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## 健康检查

服务提供了一个健康检查端点，不需要 API 密钥：

```bash
curl http://127.0.0.1:8080/health
```

响应：
```json
{
  "status": "ok",
  "service": "Z.ai2api"
}
```

## 安全建议

1. **API 密钥安全**
   - 使用强密码作为 API 密钥
   - 定期更换 API 密钥
   - 不要将 API 密钥提交到版本控制

2. **网络安全**
   - 使用 HTTPS（配置 Nginx + SSL 证书）
   - 限制 CORS 来源
   - 使用防火墙限制访问

3. **监控**
   - 监控服务日志
   - 设置性能告警
   - 定期检查资源使用情况

## 故障排除

### 1. 服务无法启动
- 检查端口是否被占用
- 确认 Python 环境和依赖是否正确安装
- 查看 `.env` 文件格式是否正确

### 2. API 返回 401 错误
- 确认 `Authorization` 头格式正确
- 检查 API 密钥是否正确
- 确认 `ZAI_API_KEY_ENABLED` 设置

### 3. 上游 API 错误
- 检查 `ZAI_UPSTREAM_TOKEN` 是否有效
- 确认网络连接正常
- 查看 Z.ai 服务状态

---

## Docker 部署（推荐）

### 1. 准备环境

确保已安装 Docker 和 Docker Compose：

```bash
# Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. 配置环境变量

创建 `.env` 文件：

```bash
cp .env.example .env
nano .env
```

至少需要配置以下变量：

```bash
# 必须配置
ZAI_UPSTREAM_TOKEN=your-upstream-token-here
ZAI_API_KEY=your-secret-api-key-here
ZAI_API_KEY_ENABLED=true

# 可选配置
ZAI_API_BASE=https://chat.z.ai
ZAI_MODEL_NAME=GLM-4.5
```

### 3. 基础部署

仅部署 API 服务：

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 4. 完整部署（包含 Nginx）

部署 API 服务 + Nginx 反向代理：

```bash
# 启动所有服务（包括 Nginx）
docker-compose --profile nginx up -d

# 查看 Nginx 日志
docker-compose logs -f nginx
```

### 5. 生产环境配置

#### 使用 SSL 证书

1. 创建 SSL 目录：
```bash
mkdir ssl
# 将证书文件复制到 ssl/ 目录
# cert.pem 和 key.pem
```

2. 修改 `nginx.conf`，取消 HTTPS 部分的注释

3. 启动服务：
```bash
docker-compose --profile nginx up -d
```

#### 使用环境变量文件

创建生产环境配置文件 `.env.prod`：

```bash
# 生产环境配置
ZAI_DEBUG_MODE=false
ZAI_LOG_LEVEL=WARNING
ZAI_API_KEY_ENABLED=true
ZAI_CORS_ORIGINS=https://your-domain.com
ZAI_ENABLE_PERFORMANCE_MONITORING=true
```

使用自定义配置启动：

```bash
docker-compose --env-file .env.prod up -d
```

### 6. 管理命令

```bash
# 查看运行状态
docker-compose ps

# 重启服务
docker-compose restart

# 更新镜像
docker-compose pull
docker-compose up -d --force-recreate

# 清理未使用的资源
docker system prune -a
```

### 7. 监控和日志

```bash
# 查看实时日志
docker-compose logs -f zai2api

# 查看健康状态
curl http://localhost:8080/health

# 进入容器
docker exec -it zai2api bash
```

### 8. 备份和恢复

```bash
# 备份
docker-compose down
tar -czf backup-$(date +%Y%m%d).tar.gz .env ssl/ logs/

# 恢复
tar -xzf backup-20240101.tar.gz
docker-compose up -d
```

### 9. 故障排除

#### 容器启动失败
```bash
# 检查容器状态
docker-compose ps

# 查看错误日志
docker-compose logs zai2api

# 检查端口占用
netstat -tlnp | grep 8080
```

#### API 无法访问
- 检查防火墙设置
- 确认端口映射正确
- 验证环境变量配置

#### 内存不足
```bash
# 限制容器内存使用
# 在 docker-compose.yml 中添加
deploy:
  resources:
    limits:
      memory: 512M
```

### 10. 性能优化

#### 调整 Docker 资源限制
```yaml
# 在 docker-compose.yml 的 zai2api 服务中添加
deploy:
  resources:
    limits:
      cpus: '1.0'
      memory: 512M
    reservations:
      cpus: '0.5'
      memory: 256M
```

#### 使用多阶段构建优化镜像大小
已包含在 Dockerfile 中，自动使用 Python slim 镜像。

#### 日志轮转
```yaml
# 在 docker-compose.yml 中添加
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```