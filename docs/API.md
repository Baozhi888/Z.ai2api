# Z.ai2api API 文档

## 概述

Z.ai2api 提供了与 OpenAI API 完全兼容的接口，让开发者可以轻松地将 Z.ai 的能力集成到自己的应用中。

## 基础信息

- **基础 URL**: `http://localhost:8080`
- **API 版本**: v1
- **认证方式**: Bearer Token
- **内容类型**: application/json

## 认证

所有 API 请求都需要在请求头中包含有效的 API 密钥：

```http
Authorization: Bearer your-api-key
```

如果未提供或 API 密钥无效，将返回 401 错误。

## 端点列表

### 1. 健康检查

检查服务是否正常运行。

**端点**: `GET /health`

**认证**: 不需要

**响应示例**:
```json
{
  "status": "ok",
  "service": "Z.ai2api",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### 2. 获取模型列表

获取所有可用的模型列表。

**端点**: `GET /v1/models`

**认证**: 需要

**响应示例**:
```json
{
  "object": "list",
  "data": [
    {
      "id": "GLM-4.5",
      "object": "model",
      "created": 1640995200,
      "owned_by": "zai"
    },
    {
      "id": "GLM-4-Air",
      "object": "model",
      "created": 1640995200,
      "owned_by": "zai"
    }
  ]
}
```

### 3. 创建聊天完成

创建一个新的聊天完成。

**端点**: `POST /v1/chat/completions`

**认证**: 需要

**请求参数**:

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `model` | string | 是 | 要使用的模型 ID |
| `messages` | array | 是 | 消息列表 |
| `stream` | boolean | 否 | 是否使用流式响应，默认 false |
| `temperature` | number | 否 | 温度参数，0-2，默认 0.7 |
| `max_tokens` | number | 否 | 最大令牌数 |
| `top_p` | number | 否 | 核采样，默认 1 |
| `stop` | string/array | 否 | 停止序列 |
| `presence_penalty` | number | 否 | 存在惩罚，默认 0 |
| `frequency_penalty` | number | 否 | 频率惩罚，默认 0 |

**消息对象格式**:

```json
{
  "role": "system|user|assistant",
  "content": "消息内容"
}
```

**请求示例**:
```json
{
  "model": "GLM-4.5",
  "messages": [
    {
      "role": "system",
      "content": "你是一个友好的助手。"
    },
    {
      "role": "user",
      "content": "请解释什么是人工智能。"
    }
  ],
  "temperature": 0.7,
  "max_tokens": 1000
}
```

**响应示例** (非流式):
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1640995200,
  "model": "GLM-4.5",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "人工智能（AI）是计算机科学的一个分支，旨在创造能够执行通常需要人类智能的任务的系统..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 150,
    "total_tokens": 175
  }
}
```

### 4. 流式聊天完成

创建流式聊天完成，实时接收响应。

**端点**: `POST /v1/chat/completions`

**认证**: 需要

**请求参数**: 与普通聊天完成相同，但 `stream` 必须设为 `true`。

**请求示例**:
```json
{
  "model": "GLM-4.5",
  "messages": [
    {
      "role": "user",
      "content": "写一首关于春天的诗"
    }
  ],
  "stream": true
}
```

**流式响应格式**:

```http
data: {"id": "chatcmpl-abc123", "object": "chat.completion.chunk", "created": 1640995200, "model": "GLM-4.5", "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": null}]}

data: {"id": "chatcmpl-abc123", "object": "chat.completion.chunk", "created": 1640995200, "model": "GLM-4.5", "choices": [{"index": 0, "delta": {"content": "春"}, "finish_reason": null}]}

data: {"id": "chatcmpl-abc123", "object": "chat.completion.chunk", "created": 1640995200, "model": "GLM-4.5", "choices": [{"index": 0, "delta": {"content": "天"}, "finish_reason": null}]}

...

data: {"id": "chatcmpl-abc123", "object": "chat.completion.chunk", "created": 1640995200, "model": "GLM-4.5", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}

data: [DONE]
```

### 5. 性能指标

获取服务性能指标。

**端点**: `GET /metrics`

**认证**: 需要

**响应示例**:
```json
{
  "uptime": 3600,
  "requests_total": 1000,
  "requests_per_second": 0.28,
  "cache_stats": {
    "hits": 800,
    "misses": 200,
    "hit_rate": 0.8,
    "size": 150
  },
  "memory_usage": {
    "rss": 67108864,
    "vms": 134217728
  },
  "cpu_usage": 0.05
}
```

## 错误处理

所有错误响应都遵循 OpenAI API 格式：

```json
{
  "error": {
    "message": "错误描述信息",
    "type": "error_type",
    "code": "error_code",
    "param": null
  }
}
```

### 常见错误码

| HTTP 状态码 | 错误类型 | 说明 |
|------------|----------|------|
| 400 | invalid_request_error | 请求格式错误或参数无效 |
| 401 | invalid_api_key | API 密钥无效或缺失 |
| 403 | insufficient_permissions | 权限不足 |
| 404 | not_found | 请求的资源不存在 |
| 429 | rate_limit_exceeded | 请求频率超限 |
| 500 | server_error | 服务器内部错误 |
| 502 | upstream_error | 上游服务错误 |
| 503 | service_unavailable | 服务暂时不可用 |

### 错误示例

```json
{
  "error": {
    "message": "Invalid API key. Please check your API key and try again.",
    "type": "invalid_api_key",
    "code": "invalid_api_key"
  }
}
```

## 请求限制

- **最大并发请求数**: 100（可配置）
- **请求超时时间**: 60 秒（可配置）
- **流式响应超时**: 120 秒（可配置）
- **最大令牌数**: 根据模型而定

## 思考链处理

Z.ai2api 支持三种思考链处理模式，通过 `ZAI_THINK_TAGS_MODE` 环境变量配置：

### 1. think 模式（默认）

将思考内容转换为友好的格式：

```json
{
  "choices": [
    {
      "message": {
        "content": "🤔\n\n用户想要了解人工智能...\n\n人工智能是..."
      }
    }
  ]
}
```

### 2. pure 模式

保留原始引用格式：

```json
{
  "choices": [
    {
      "message": {
        "content": "> 用户想要了解人工智能...\n\n人工智能是..."
      }
    }
  ]
}
```

### 3. raw 模式

完整的 HTML 思考链展示：

```json
{
  "choices": [
    {
      "message": {
        "content": "<details type=\"reasoning\" open><div>\n\n用户想要了解人工智能...\n\n</div><summary>Thought for 1 seconds</summary></details>\n\n人工智能是..."
      }
    }
  ]
}
```

## 使用示例

### Python

```python
import requests
import json

# 配置
API_URL = "http://localhost:8080/v1/chat/completions"
API_KEY = "your-api-key"

# 请求头
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 请求数据
data = {
    "model": "GLM-4.5",
    "messages": [
        {"role": "user", "content": "你好！"}
    ]
}

# 发送请求
response = requests.post(API_URL, headers=headers, json=data)
result = response.json()

print(result["choices"][0]["message"]["content"])
```

### 流式响应（Python）

```python
import requests

API_URL = "http://localhost:8080/v1/chat/completions"
API_KEY = "your-api-key"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

data = {
    "model": "GLM-4.5",
    "messages": [
        {"role": "user", "content": "讲个故事"}
    ],
    "stream": True
}

response = requests.post(API_URL, headers=headers, json=data, stream=True)

for line in response.iter_lines():
    if line:
        line = line.decode('utf-8')
        if line.startswith("data: "):
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                content = chunk["choices"][0]["delta"].get("content", "")
                print(content, end="", flush=True)
            except:
                pass
```

### cURL

```bash
# 普通请求
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "GLM-4.5",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

# 流式请求
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "GLM-4.5",
    "messages": [{"role": "user", "content": "Tell me a joke"}],
    "stream": true
  }'
```

### JavaScript (Fetch API)

```javascript
// 普通请求
async function chat(message) {
  const response = await fetch('http://localhost:8080/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer your-api-key',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model: 'GLM-4.5',
      messages: [{ role: 'user', content: message }]
    })
  });
  
  const data = await response.json();
  return data.choices[0].message.content;
}

// 流式请求
async function streamChat(message) {
  const response = await fetch('http://localhost:8080/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer your-api-key',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model: 'GLM-4.5',
      messages: [{ role: 'user', content: message }],
      stream: true
    })
  });
  
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') return;
        
        try {
          const parsed = JSON.parse(data);
          const content = parsed.choices[0].delta.content || '';
          process.stdout.write(content);
        } catch (e) {
          // 忽略解析错误
        }
      }
    }
  }
}
```

## 最佳实践

1. **错误处理**: 始终检查响应状态码并妥善处理错误
2. **重试机制**: 对于 5xx 错误，实现指数退避重试
3. **流式响应**: 对于长文本生成，使用流式响应提升用户体验
4. **令牌管理**: 监控使用量，避免超出限制
5. **缓存利用**: 重复的请求可以利用缓存提高性能

## SDK 兼容性

Z.ai2api 完全兼容 OpenAI 的 SDK，你可以直接使用 OpenAI 的官方 SDK：

### OpenAI Python SDK

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-api-key",
    base_url="http://localhost:8080/v1"
)

response = client.chat.completions.create(
    model="GLM-4.5",
    messages=[
        {"role": "user", "content": "Hello!"}
    ]
)

print(response.choices[0].message.content)
```

### OpenAI Node.js SDK

```javascript
const OpenAI = require('openai');

const openai = new OpenAI({
  apiKey: 'your-api-key',
  baseURL: 'http://localhost:8080/v1'
});

async function main() {
  const completion = await openai.chat.completions.create({
    model: 'GLM-4.5',
    messages: [{ role: 'user', content: 'Hello!' }]
  });
  
  console.log(completion.choices[0].message.content);
}

main();
```

## 更新日志

API 的更新将通过版本号和变更日志进行管理。请关注项目的 releases 页面获取最新更新。