#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试工具调用功能
验证修复后的工具调用实现
"""

import json
import time
import requests
import threading
from typing import Dict, Any


def test_openai_tool_call():
    """测试 OpenAI 格式的工具调用"""
    print("\n=== 测试 OpenAI 格式工具调用 ===")
    
    # API 端点
    url = "http://localhost:8080/v1/chat/completions"
    
    # 请求头
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer your-api-key"
    }
    
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
                        },
                        "date": {
                            "type": "string",
                            "description": "日期，格式：YYYY-MM-DD"
                        }
                    },
                    "required": ["city"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "执行数学计算",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "数学表达式，如：2 + 2 * 3"
                        }
                    },
                    "required": ["expression"]
                }
            }
        }
    ]
    
    # 测试用例
    test_cases = [
        {
            "name": "天气查询",
            "messages": [{"role": "user", "content": "请问北京今天的天气怎么样？"}],
            "stream": True
        },
        {
            "name": "数学计算",
            "messages": [{"role": "user", "content": "帮我计算 15 * 23 + 47 等于多少？"}],
            "stream": True
        },
        {
            "name": "多工具调用",
            "messages": [{"role": "user", "content": "先计算 100 除以 5，然后查询上海的天气"}],
            "stream": True
        },
        {
            "name": "非流式工具调用",
            "messages": [{"role": "user", "content": "计算 2 的 10 次方是多少？"}],
            "stream": False
        }
    ]
    
    for test_case in test_cases:
        print(f"\n--- 测试用例: {test_case['name']} ---")
        
        # 请求数据
        data = {
            "model": "glm-4.5",
            "messages": test_case["messages"],
            "tools": tools,
            "tool_choice": "auto",
            "stream": test_case["stream"]
        }
        
        try:
            print(f"发送请求到: {url}")
            print(f"请求数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # 发送请求
            response = requests.post(url, headers=headers, json=data, stream=test_case["stream"])
            
            print(f"\n响应状态: {response.status_code}")
            
            if response.status_code == 200:
                if test_case["stream"]:
                    print("\n流式响应内容:")
                    tool_calls = []
                    content = ""
                    
                    for line in response.iter_lines():
                        if line:
                            line = line.decode('utf-8')
                            if line.startswith("data: "):
                                try:
                                    data_str = line[6:]
                                    if data_str.strip() == "[DONE]":
                                        print("  流结束")
                                        break
                                    
                                    data = json.loads(data_str)
                                    
                                    # 处理不同类型的内容
                                    if "choices" in data and data["choices"]:
                                        choice = data["choices"][0]
                                        if "delta" in choice:
                                            delta = choice["delta"]
                                            
                                            # 文本内容
                                            if "content" in delta and delta["content"]:
                                                content += delta["content"]
                                                print(f"  文本: {delta['content']}")
                                            
                                            # 思考链
                                            if "thinking" in delta:
                                                thinking = delta["thinking"]
                                                if thinking.get("content"):
                                                    print(f"  思考: {thinking['content'][:50]}...")
                                                if thinking.get("signature"):
                                                    print(f"  思考签名: {thinking['signature']}")
                                            
                                            # 工具调用
                                            if "tool_calls" in delta:
                                                for tool_call in delta["tool_calls"]:
                                                    if "function" in tool_call:
                                                        func = tool_call["function"]
                                                        if func.get("name") and tool_call.get("id"):
                                                            if not any(tc["id"] == tool_call["id"] for tc in tool_calls):
                                                                tool_calls.append({
                                                                    "id": tool_call["id"],
                                                                    "name": func["name"],
                                                                    "arguments": func.get("arguments", "")
                                                                })
                                                                print(f"  工具调用: {func['name']}({func.get('arguments', '')})")
                                                            elif func.get("arguments"):
                                                                # 更新参数
                                                                for tc in tool_calls:
                                                                    if tc["id"] == tool_call["id"]:
                                                                        tc["arguments"] += func["arguments"]
                                                                        break
                                    
                                    # 检查完成原因
                                    if choice.get("finish_reason"):
                                        print(f"  完成原因: {choice['finish_reason']}")
                                    
                                except json.JSONDecodeError as e:
                                    print(f"  JSON 解析错误: {e}")
                                    print(f"  原始数据: {line}")
                    
                    print(f"\n总结:")
                    print(f"  完整内容: {content}")
                    print(f"  工具调用数量: {len(tool_calls)}")
                    for tc in tool_calls:
                        print(f"    - {tc['name']}: {tc['arguments']}")
                    
                else:
                    # 非流式响应
                    result = response.json()
                    print(f"\n响应内容: {json.dumps(result, indent=2, ensure_ascii=False)}")
                    
            else:
                print(f"错误响应: {response.text}")
                
        except Exception as e:
            print(f"请求失败: {e}")
            import traceback
            traceback.print_exc()


def test_anthropic_tool_call():
    """测试 Anthropic 格式的工具调用"""
    print("\n=== 测试 Anthropic 格式工具调用 ===")
    
    # API 端点
    url = "http://localhost:8080/v1/messages"
    
    # 请求头
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer your-api-key",
        "x-api-key": "your-api-key",
        "anthropic-version": "2023-06-01"
    }
    
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
    
    # 请求数据
    data = {
        "model": "glm-4.5v",
        "max_tokens": 1024,
        "messages": [
            {
                "role": "user",
                "content": "请问广州今天的天气怎么样？"
            }
        ],
        "tools": tools,
        "stream": True
    }
    
    print(f"发送请求到: {url}")
    print(f"请求数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
    
    try:
        # 发送请求
        response = requests.post(url, headers=headers, json=data, stream=True)
        
        print(f"\n响应状态: {response.status_code}")
        
        if response.status_code == 200:
            print("\n流式响应内容:")
            tool_calls = []
            content = ""
            
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            
                            # 处理消息开始
                            if data.get("type") == "message_start":
                                print(f"  消息开始: {data['message']['id']}")
                            
                            # 处理内容块
                            elif data.get("type") == "content_block_delta":
                                delta = data.get("delta", {})
                                
                                # 文本内容
                                if "text" in delta:
                                    content += delta["text"]
                                    print(f"  文本: {delta['text']}")
                                
                                # 工具调用
                                elif "tool_call" in delta:
                                    tool_call = delta["tool_call"]
                                    if tool_call.get("name"):
                                        print(f"  工具调用: {tool_call['name']}")
                                        if tool_call.get("id"):
                                            tool_calls.append(tool_call)
                            
                            # 处理消息增量
                            elif data.get("type") == "message_delta":
                                if "stop_reason" in data.get("delta", {}):
                                    print(f"  停止原因: {data['delta']['stop_reason']}")
                            
                            # 处理消息结束
                            elif data.get("type") == "message_stop":
                                print("  消息结束")
                                
                        except json.JSONDecodeError as e:
                            print(f"  JSON 解析错误: {e}")
                            print(f"  原始数据: {line}")
            
            print(f"\n总结:")
            print(f"  完整内容: {content}")
            print(f"  工具调用数量: {len(tool_calls)}")
            
        else:
            print(f"错误响应: {response.text}")
            
    except Exception as e:
        print(f"请求失败: {e}")
        import traceback
        traceback.print_exc()


def test_error_handling():
    """测试错误处理"""
    print("\n=== 测试错误处理 ===")
    
    url = "http://localhost:8080/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer your-api-key"
    }
    
    # 测试无效的工具定义
    invalid_tools = [
        {
            "type": "function",
            "function": {
                "name": "test",
                "description": "测试工具",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param": {
                            "type": "string"
                        }
                    },
                    "required": ["nonexistent_param"]  # 不存在的必需参数
                }
            }
        }
    ]
    
    data = {
        "model": "glm-4.5",
        "messages": [{"role": "user", "content": "测试错误处理"}],
        "tools": invalid_tools,
        "stream": True
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, stream=True)
        print(f"响应状态: {response.status_code}")
        
        if response.status_code != 200:
            print(f"预期中的错误: {response.text}")
        else:
            print("服务器接受了无效的工具定义")
            
    except Exception as e:
        print(f"请求异常: {e}")


def test_performance():
    """测试性能"""
    print("\n=== 测试性能 ===")
    
    url = "http://localhost:8080/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer your-api-key"
    }
    
    tools = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"}
                },
                "required": ["city"]
            }
        }
    }]
    
    # 并发测试
    def make_request(i):
        data = {
            "model": "glm-4.5",
            "messages": [{"role": "user", "content": f"请求 {i}: 北京天气"}],
            "tools": tools,
            "stream": False
        }
        
        start_time = time.time()
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            elapsed = time.time() - start_time
            return elapsed, response.status_code
        except Exception as e:
            elapsed = time.time() - start_time
            return elapsed, str(e)
    
    # 发送 10 个并发请求
    threads = []
    results = []
    
    for i in range(10):
        t = threading.Thread(target=lambda i=i: results.append(make_request(i)))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    # 统计结果
    total_time = 0
    success_count = 0
    
    for elapsed, status in results:
        total_time += elapsed
        if status == 200:
            success_count += 1
    
    print(f"并发请求数: 10")
    print(f"成功请求数: {success_count}")
    print(f"平均响应时间: {total_time / 10:.2f} 秒")
    print(f"总耗时: {total_time:.2f} 秒")


def main():
    """主函数"""
    print("开始测试工具调用功能...")
    
    # 检查服务是否运行
    try:
        response = requests.get("http://localhost:8080/health", timeout=5)
        if response.status_code == 200:
            print("服务运行正常")
        else:
            print("服务状态异常")
            return
    except:
        print("无法连接到服务，请确保服务在 http://localhost:8080 运行")
        return
    
    # 运行测试
    test_openai_tool_call()
    test_anthropic_tool_call()
    test_error_handling()
    test_performance()
    
    print("\n测试完成！")


if __name__ == "__main__":
    main()