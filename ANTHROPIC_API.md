# Anthropic API 支持

Z.ai2api 现在完全兼容 Anthropic Messages API 格式！您可以使用任何支持 Anthropic API 的客户端来访问 Z.ai 的服务。

## 快速开始

### 1. 基本请求

```bash
curl -X POST http://localhost:8089/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 100,
    "messages": [
      {"role": "user", "content": "Hello, world!"}
    ]
  }'
```

### 2. 流式响应

```bash
curl -X POST http://localhost:8089/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 100,
    "stream": true,
    "messages": [
      {"role": "user", "content": "Tell me a joke"}
    ]
  }'
```

## 支持的功能

### ✅ 已实现

- [x] 完整的 Messages API 格式兼容
- [x] 流式和非流式响应
- [x] 系统提示词（system prompt）
- [x] 内容块格式（content blocks）
- [x] API 密钥认证
- [x] 温度参数控制
- [x] 模型映射（将 Anthropic 模型名映射到 Z.ai 模型）
- [x] 思考链处理
- [x] 完整的错误处理

### 🔄 支持的模型

以下 Anthropic 模型名会被自动映射到 Z.ai 的模型：

- `claude-3-5-sonnet-20241022` → `glm-4.5v`
- `claude-3-haiku-20240307` → `glm-4.5v`
- `claude-3-opus-20240229` → `glm-4.5v`
- `claude-2.1` → `glm-4.5v`

## 配置

在 `.env` 文件中添加以下配置：

```env
# Anthropic API 密钥（可选）
ZAI_ANTHROPIC_API_KEY=your-anthropic-api-key
```

如果设置了 `ZAI_ANTHROPIC_API_KEY`，访问 `/v1/messages` 端点需要提供此密钥。如果未设置，将使用 `ZAI_API_KEY` 或不进行验证。

## Python 客户端示例

```python
import requests

# 非流式请求
response = requests.post(
    "http://localhost:8089/v1/messages",
    headers={
        "Content-Type": "application/json",
        "x-api-key": "your-api-key"
    },
    json={
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 100,
        "messages": [
            {"role": "user", "content": "你好！"}
        ]
    }
)

print(response.json())
```

## 兼容的客户端

以下客户端可以无缝使用：

- Anthropic 官方 Python SDK
- LangChain Anthropic 集成
- LlamaIndex Anthropic 集成
- OpenAI Python 客户端（通过适配器）
- 任何支持 Anthropic API 的工具

## 测试

运行兼容性测试：

```bash
python test_anthropic_api.py --url http://localhost:8089
```

## 注意事项

1. **模型映射**：所有 Anthropic 模型名都会映射到 Z.ai 的 `glm-4.5v` 模型
2. **令牌计算**：使用简单的字符数除以 4 来估算令牌数
3. **流式响应**：总是启用上游的流式响应以获得更好的性能
4. **思考链**：自动处理 Z.ai 的思考链输出，转换为友好格式

## 示例代码

查看 `examples/anthropic_usage_example.py` 获取更多使用示例。