# 工具调用功能增强说明

## 概述

Z.ai2api 项目已经实现了完整的工具调用功能，支持 OpenAI 和 Anthropic 两种 API 格式。经过本次增强，工具调用功能更加健壮和完整。

## 主要改进

### 1. 工具调用生命周期管理

新增了 `ToolCallManager` 类，专门管理工具调用的完整生命周期：

- **开始工具调用**: 记录工具调用开始，生成唯一 ID
- **参数拼接**: 支持大参数的分块传输
- **完成工具调用**: 正确处理工具调用结束，生成完成事件
- **状态管理**: 跟踪工具调用的各种状态

### 2. 增强的错误处理

新增了 `ToolCallErrorHandler` 类，提供完善的错误处理机制：

- **解析错误**: 处理 JSON 解析失败等解析错误
- **超时错误**: 处理工具调用超时
- **执行错误**: 处理工具执行过程中的错误
- **未知错误**: 处理其他未预期的错误

### 3. 性能监控增强

在 `PerformanceMetrics` 中添加了工具调用相关的统计：

- 工具调用次数统计
- 工具调用成功率
- 平均 Token 消耗量

### 4. 思考链和工具调用交互优化

- 当有活跃工具调用时，自动跳过 answer 阶段的内容处理
- 确保工具调用和思考链的正确交互

## 使用示例

### OpenAI 格式

```python
import requests

# 工具定义
tools = [
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
]

# 发送请求
response = requests.post(
    "http://localhost:8080/v1/chat/completions",
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer your-api-key"
    },
    json={
        "model": "glm-4.5",
        "messages": [
            {"role": "user", "content": "请问北京今天的天气怎么样？"}
        ],
        "tools": tools,
        "tool_choice": "auto",
        "stream": True
    },
    stream=True
)

# 处理流式响应
for line in response.iter_lines():
    if line.startswith(b"data: "):
        data = json.loads(line[6:])
        if "choices" in data:
            choice = data["choices"][0]
            if "tool_calls" in choice.get("delta", {}):
                # 处理工具调用
                for tool_call in choice["delta"]["tool_calls"]:
                    print(f"工具调用: {tool_call}")
```

### Anthropic 格式

```python
import requests

# 工具定义
tools = [
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

# 发送请求
response = requests.post(
    "http://localhost:8080/v1/messages",
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer your-api-key",
        "x-api-key": "your-api-key",
        "anthropic-version": "2023-06-01"
    },
    json={
        "model": "glm-4.5v",
        "max_tokens": 1024,
        "messages": [
            {"role": "user", "content": "请问广州今天的天气怎么样？"}
        ],
        "tools": tools,
        "stream": True
    },
    stream=True
)

# 处理流式响应
for line in response.iter_lines():
    if line.startswith("data: "):
        data = json.loads(line[6:])
        if data.get("type") == "content_block_delta":
            delta = data.get("delta", {})
            if "tool_call" in delta:
                # 处理工具调用
                tool_call = delta["tool_call"]
                print(f"工具调用: {tool_call}")
```

## 测试

运行测试脚本验证功能：

```bash
python test_tool_call_enhanced.py
```

测试脚本包含以下测试用例：
- OpenAI 格式工具调用（流式/非流式）
- Anthropic 格式工具调用
- 错误处理测试
- 性能测试

## 配置

确保在 `config.py` 中启用了必要的配置：

```python
# 工具调用相关配置
ZAI_ENABLE_TOOL_CALLING = True  # 启用工具调用
ZAI_TOOL_CALL_TIMEOUT = 30      # 工具调用超时时间（秒）
```

## 注意事项

1. **工具定义格式**: 确保工具定义符合 OpenAI 或 Anthropic 的格式要求
2. **参数验证**: 所有必需参数必须在工具定义中明确声明
3. **错误处理**: 客户端应正确处理工具调用相关的错误
4. **流式处理**: 工具调用支持流式传输，客户端需要正确处理流式事件

## 故障排除

### 常见问题

1. **工具调用不被触发**
   - 检查工具定义是否正确
   - 确保用户消息明确表达了使用工具的意图

2. **工具调用解析失败**
   - 检查工具参数是否符合 schema
   - 查看日志获取详细错误信息

3. **流式响应中断**
   - 检查网络连接
   - 确认客户端正确处理了 `[DONE]` 消息

### 日志查看

工具调用相关的日志会被记录，可以通过以下方式查看：

```bash
# 查看应用日志
tail -f logs/app.log | grep "tool_call"

# 查看错误日志
tail -f logs/error.log | grep "tool"
```

## 性能优化建议

1. **工具缓存**: 对于频繁调用的工具，考虑实现结果缓存
2. **并发控制**: 避免同时发起过多的工具调用
3. **超时设置**: 根据实际需要调整工具调用超时时间
4. **批量处理**: 对于可以批量处理的工具，尽量批量调用