# 工具调用功能说明

本文档说明如何在 Z.ai2api 中使用工具调用功能。

## 概述

Z.ai2api 支持 OpenAI 和 Anthropic API 格式的工具调用（Function Calling）。这允许 AI 模型调用外部工具来完成特定任务。

## 支持的端点

- `/v1/chat/completions` - OpenAI 格式
- `/v1/messages` - Anthropic 格式

## 使用方法

### OpenAI 格式示例

```bash
curl -X POST http://localhost:8089/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "glm-4.5v",
    "messages": [
      {
        "role": "user",
        "content": "北京今天天气怎么样？"
      }
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "get_weather",
          "description": "获取指定城市的天气信息",
          "parameters": {
            "type": "object",
            "properties": {
              "city": {
                "type": "string",
                "description": "城市名称"
              }
            },
            "required": ["city"]
          }
        }
      }
    ],
    "tool_choice": "auto"
  }'
```

### Anthropic 格式示例

```bash
curl -X POST http://localhost:8089/v1/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -H "x-api-key": your-api-key \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "glm-4.5v",
    "max_tokens": 1024,
    "messages": [
      {
        "role": "user",
        "content": "北京今天天气怎么样？"
      }
    ],
    "tools": [
      {
        "name": "get_weather",
        "description": "获取指定城市的天气信息",
        "input_schema": {
          "type": "object",
          "properties": {
            "city": {
              "type": "string",
              "description": "城市名称"
            }
          },
          "required": ["city"]
        }
      }
    ]
  }'
```

## 响应格式

### OpenAI 格式响应

工具调用会在响应中包含 `tool_calls` 字段：

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "我来帮您查询北京的天气信息。",
        "tool_calls": [
          {
            "id": "call_abc123",
            "type": "function",
            "function": {
              "name": "get_weather",
              "arguments": "{\"city\": \"北京\"}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ]
}
```

### Anthropic 格式响应

```json
{
  "id": "msg_abc123",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "我来帮您查询北京的天气信息。"
    }
  ],
  "stop_reason": "tool_use"
}
```

## 注意事项

1. **工具定义**: 工具定义必须符合相应 API 的格式要求
2. **参数验证**: 模型可能会生成无效的参数，需要在客户端进行验证
3. **执行权限**: 工具调用需要客户端实际执行，代理只负责转发
4. **错误处理**: 如果工具执行失败，需要将错误信息返回给模型

## 限制

1. Z.ai 模型对工具调用的支持可能有限
2. 工具调用的具体格式取决于上游模型的实现
3. 某些高级功能（如并行工具调用）可能不支持

## 调试

启用调试模式可以查看更多详细信息：

```bash
# 在 .env 中设置
ZAI_DEBUG_MODE=true
```

然后查看容器日志：

```bash
docker logs -f zai2api
```