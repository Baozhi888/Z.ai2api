# Z.ai2api 工具调用功能改进建议报告

## 执行摘要

基于对 JavaScript 脚本工具调用实现的深入分析，发现 Python 代码在工具调用功能上存在一些重要差异和改进空间。本报告详细分析了这些差异，并提供了具体的改进建议。

## 1. 关键差异分析

### 1.1 工具调用检测机制

**JavaScript 实现（更完善）：**
```javascript
// JS 脚本使用多重检测机制
if (data.phase === "tool_call") {
    hasToolCall = true;
    // 处理工具调用块
    const blocks = data.edit_content.split("<glm_block >");
    blocks.forEach((block, index) => {
        if (!block.includes("</glm_block>")) return;
        // 解析工具调用...
    });
} else if (data.phase === "other") {
    // 处理工具调用结束
    if (hasToolCall && data.edit_content?.startsWith("null,")) {
        // 完成工具调用处理
    }
}
```

**Python 实现（需要改进）：**
```python
# Python 实现相对简单
elif phase == "tool_call":
    has_tool_call = True
    # 缺少对工具调用结束的处理
```

### 1.2 流式工具调用处理

**JavaScript 实现的优势：**
1. **完整的工具调用生命周期管理**
   - 检测工具调用开始
   - 分块传输工具调用参数
   - 检测工具调用结束
   - 发送完成事件

2. **更智能的参数处理**
```javascript
// JS 脚本中的参数拼接逻辑
if (toolId) {
    try {
        toolArgs += '"';
        const params = JSON.parse(toolArgs);
        // 处理参数...
    } catch (e) {
        console.log("解析错误", toolArgs);
    } finally {
        toolArgs = "";
        toolId = "";
    }
}
```

## 2. 需要立即修复的问题

### 2.1 缺失的工具调用结束检测

Python 代码没有实现工具调用结束的检测机制，这会导致工具调用无法正确完成。

**改进方案：**
```python
def _handle_stream_response(self, upstream: Iterator[bytes], model: str) -> Dict[str, Any]:
    def stream_generator():
        has_tool_call = False
        tool_args = ""
        tool_id = ""
        tool_call_usage = None
        
        for data in self._parse_upstream_stream(upstream):
            chunk_data = data.get("data", {})
            phase = chunk_data.get("phase")
            
            if phase == "tool_call":
                has_tool_call = True
                # 处理工具调用...
                
            elif phase == "other":
                # 处理工具调用结束
                if has_tool_call and chunk_data.get("edit_content", "").startswith("null,"):
                    tool_args += '"'
                    has_tool_call = False
                    try:
                        params = json.loads(tool_args)
                        # 发送工具调用完成事件
                        finish_res = {
                            "choices": [{
                                "delta": {
                                    "role": "assistant",
                                    "content": None,
                                    "tool_calls": []
                                },
                                "finish_reason": "tool_calls",
                                "index": 0
                            }],
                            "usage": tool_call_usage
                        }
                        yield f"data: {json.dumps(finish_res)}\n\n"
                        yield "data: [DONE]\n\n"
                    except json.JSONDecodeError:
                        pass
```

### 2.2 工具调用参数拼接逻辑不完整

Python 代码缺少 JavaScript 脚本中的参数拼接逻辑。

**改进方案：**
```python
def _process_tool_call_block(self, block: str, block_idx: int, is_stream: bool) -> Iterator[str]:
    """处理工具调用块"""
    if not block.endswith("</glm_block>"):
        return
    
    try:
        block_content = block[:-12]  # 移除 </glm_block>
        tool_data = json.loads(block_content)
        
        if tool_data.get("type") == "tool_call":
            metadata = tool_data.get("data", {}).get("metadata", {})
            if metadata.get("id") and metadata.get("name"):
                tool_id = metadata["id"]
                tool_name = metadata["name"]
                tool_args = json.dumps(metadata.get("arguments", {}))
                
                if is_stream:
                    # 发送工具调用开始
                    start_res = {
                        "choices": [{
                            "delta": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [{
                                    "index": block_idx,
                                    "id": tool_id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_name,
                                        "arguments": ""
                                    }
                                }]
                            }
                        }]
                    }
                    yield f"data: {json.dumps(start_res)}\n\n"
                    
                    # 分块发送参数
                    chunk_size = 100
                    for i in range(0, len(tool_args), chunk_size):
                        chunk = tool_args[i:i+chunk_size]
                        args_delta = {
                            "choices": [{
                                "delta": {
                                    "tool_calls": [{
                                        "index": block_idx,
                                        "function": {
                                            "arguments": chunk
                                        }
                                    }]
                                }
                            }]
                        }
                        yield f"data: {json.dumps(args_delta)}\n\n"
```

### 2.3 缺少工具调用使用情况统计

JavaScript 脚本会跟踪工具调用的使用情况（token 消耗等）。

**改进方案：**
```python
# 在流式处理中添加使用情况跟踪
if phase == "other" and has_tool_call and chunk_data.get("usage"):
    tool_call_usage = chunk_data["usage"]
```

## 3. 功能增强建议

### 3.1 添加工具调用状态管理

```python
class ToolCallState:
    """工具调用状态管理"""
    IDLE = "idle"
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"

class ToolCallManager:
    """工具调用管理器"""
    def __init__(self):
        self.current_state = ToolCallState.IDLE
        self.active_calls = {}
        self.call_buffer = ""
    
    def start_tool_call(self, call_id: str, tool_name: str):
        """开始工具调用"""
        self.current_state = ToolCallState.STARTED
        self.active_calls[call_id] = {
            "name": tool_name,
            "arguments": "",
            "started_at": time.time()
        }
    
    def append_arguments(self, call_id: str, args_chunk: str):
        """追加参数"""
        if call_id in self.active_calls:
            self.active_calls[call_id]["arguments"] += args_chunk
    
    def complete_tool_call(self, call_id: str, usage: Dict = None):
        """完成工具调用"""
        if call_id in self.active_calls:
            self.active_calls[call_id]["completed_at"] = time.time()
            self.active_calls[call_id]["usage"] = usage
            self.current_state = ToolCallState.COMPLETED
```

### 3.2 优化思考链和工具调用的交互

JavaScript 脚本正确处理了思考链（thinking）和工具调用的交互。

**改进方案：**
```python
def _handle_thinking_and_tool_interaction(self, data: Dict[str, Any]):
    """处理思考链和工具调用的交互"""
    phase = data.get("phase")
    
    if phase == "thinking":
        # 处理思考内容
        if not self.has_thinking:
            self.has_thinking = True
        
        if data.get("delta_content"):
            thinking_content = data["delta_content"]
            # 处理思考内容...
            
    elif phase == "answer" and self.has_thinking:
        # 处理思考结束后的答案
        if data.get("edit_content") and "</details>\n" in data["edit_content"]:
            # 发送思考结束签名
            signature = str(int(time.time() * 1000))
            thinking_end = {
                "choices": [{
                    "delta": {
                        "thinking": {
                            "content": "",
                            "signature": signature
                        }
                    }
                }]
            }
            yield f"data: {json.dumps(thinking_end)}\n\n"
```

### 3.3 增强错误处理和恢复机制

```python
def _handle_tool_call_error(self, error: Exception, tool_id: str = None):
    """处理工具调用错误"""
    error_event = {
        "choices": [{
            "delta": {
                "role": "assistant",
                "content": f"工具调用失败: {str(error)}"
            }
        }],
        "finish_reason": "error"
    }
    
    if tool_id:
        error_event["choices"][0]["delta"]["tool_calls"] = [{
            "id": tool_id,
            "type": "function",
            "function": {
                "name": None,
                "arguments": None
            }
        }]
    
    yield f"data: {json.dumps(error_event)}\n\n"
```

## 4. 性能优化建议

### 4.1 工具调用缓存

```python
class ToolCallCache:
    """工具调用结果缓存"""
    def __init__(self, ttl: int = 300):
        self.cache = {}
        self.ttl = ttl
    
    def get(self, tool_name: str, arguments: Dict) -> Optional[Dict]:
        """获取缓存结果"""
        key = self._generate_key(tool_name, arguments)
        if key in self.cache:
            result, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return result
            del self.cache[key]
        return None
    
    def set(self, tool_name: str, arguments: Dict, result: Dict):
        """设置缓存"""
        key = self._generate_key(tool_name, arguments)
        self.cache[key] = (result, time.time())
```

### 4.2 并行工具调用支持

```python
import asyncio

class ParallelToolCallHandler:
    """并行工具调用处理器"""
    
    async def execute_multiple_tools(self, tool_calls: List[Dict]) -> List[Dict]:
        """并行执行多个工具调用"""
        tasks = []
        for tool_call in tool_calls:
            task = asyncio.create_task(
                self._execute_single_tool(tool_call)
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return self._process_results(results)
```

## 5. 测试建议

### 5.1 添加工具调用测试用例

```python
def test_tool_call_streaming():
    """测试流式工具调用"""
    tools = [{
        "name": "get_weather",
        "description": "获取天气信息",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string"}
            },
            "required": ["city"]
        }
    }]
    
    response = client.post("/v1/chat/completions", json={
        "model": "glm-4.5",
        "messages": [{"role": "user", "content": "北京天气怎么样？"}],
        "tools": tools,
        "stream": True
    })
    
    # 验证工具调用事件
    tool_call_events = []
    for line in response.iter_lines():
        if line.startswith(b"data: "):
            data = json.loads(line[6:])
            if "tool_calls" in data.get("choices", [{}])[0].get("delta", {}):
                tool_call_events.append(data)
    
    assert len(tool_call_events) > 0
```

### 5.2 性能测试

```python
def test_tool_call_performance():
    """测试工具调用性能"""
    import time
    
    start_time = time.time()
    response = client.post("/v1/chat/completions", json={
        "model": "glm-4.5",
        "messages": [{"role": "user", "content": "调用多个工具"}],
        "tools": [tool1, tool2, tool3],
        "stream": True
    })
    
    # 计算响应时间
    for _ in response.iter_lines():
        pass
    
    end_time = time.time()
    assert end_time - start_time < 5.0  # 响应时间应小于5秒
```

## 6. 总结

基于 JavaScript 脚本的分析，Python 代码在工具调用实现上需要以下改进：

1. **立即修复**：
   - 添加工具调用结束检测机制
   - 完善工具调用参数拼接逻辑
   - 添加工具调用使用情况统计

2. **功能增强**：
   - 实现工具调用状态管理
   - 优化思考链和工具调用的交互
   - 增强错误处理机制

3. **性能优化**：
   - 添加工具调用缓存
   - 支持并行工具调用
   - 优化流式处理性能

4. **测试完善**：
   - 添加全面的工具调用测试
   - 性能测试和基准测试

这些改进将使 Python 实现的工具调用功能更加健壮和完整，与 JavaScript 脚本保持功能对等。