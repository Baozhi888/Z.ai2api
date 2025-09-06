#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试工具调用功能
"""

import json
import requests


def test_tool_call():
    """测试工具调用功能"""
    
    # API 端点
    url = "http://localhost:8089/v1/messages"
    
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
                "content": "请问北京今天的天气怎么样？"
            }
        ],
        "tools": tools,
        "tool_choice": {"type": "auto"}
    }
    
    print("发送工具调用测试请求...")
    print(f"URL: {url}")
    print(f"数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
    
    try:
        # 发送请求
        response = requests.post(url, headers=headers, json=data, stream=True)
        
        print(f"\n响应状态: {response.status_code}")
        
        if response.status_code == 200:
            print("\n流式响应内容:")
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            print(f"  事件类型: {data.get('type', 'unknown')}")
                            
                            if data.get('type') == 'content_block_delta':
                                delta = data.get('delta', {})
                                if 'text' in delta:
                                    print(f"  文本内容: {delta['text']}")
                            
                            elif data.get('type') == 'message_stop':
                                print("  消息结束")
                                
                        except json.JSONDecodeError:
                            print(f"  原始数据: {line}")
        else:
            print(f"错误响应: {response.text}")
            
    except Exception as e:
        print(f"请求失败: {e}")


if __name__ == "__main__":
    test_tool_call()