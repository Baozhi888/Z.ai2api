#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anthropic API 使用示例
展示如何使用 /v1/messages 端点
"""

import json
import requests
from typing import Dict, Any, Optional


class AnthropicClient:
    """Anthropic API 客户端示例"""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """初始化客户端
        
        Args:
            base_url: API 基础 URL
            api_key: API 密钥（可选）
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if api_key:
            self.headers["x-api-key"] = api_key
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    def create_message(self, 
                      model: str = "claude-3-5-sonnet-20241022",
                      messages: list = None,
                      max_tokens: int = 1024,
                      stream: bool = False,
                      temperature: Optional[float] = None,
                      system: Optional[str] = None) -> Dict[str, Any]:
        """创建消息
        
        Args:
            model: 模型名称
            messages: 消息列表
            max_tokens: 最大令牌数
            stream: 是否流式响应
            temperature: 温度参数
            system: 系统提示词
            
        Returns:
            Dict[str, Any]: 响应数据
        """
        if messages is None:
            messages = [{"role": "user", "content": "Hello!"}]
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": stream
        }
        
        if temperature is not None:
            payload["temperature"] = temperature
        
        if system is not None:
            payload["system"] = system
        
        response = requests.post(
            f"{self.base_url}/v1/messages",
            headers=self.headers,
            json=payload
        )
        
        if response.status_code != 200:
            raise Exception(f"API 请求失败: {response.status_code} - {response.text}")
        
        return response.json()
    
    def create_message_stream(self, **kwargs) -> None:
        """创建流式消息
        
        Args:
            **kwargs: 传递给 create_message 的参数
        """
        kwargs["stream"] = True
        
        response = requests.post(
            f"{self.base_url}/v1/messages",
            headers=self.headers,
            json=kwargs,
            stream=True
        )
        
        if response.status_code != 200:
            raise Exception(f"API 请求失败: {response.status_code}")
        
        print("开始接收流式响应...")
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        event_type = data.get("type")
                        
                        if event_type == "message_start":
                            print(f"\n[消息开始] ID: {data['message']['id']}")
                        elif event_type == "content_block_delta":
                            text = data.get("delta", {}).get("text", "")
                            print(text, end="", flush=True)
                        elif event_type == "message_stop":
                            print("\n[消息结束]")
                            break
                            
                    except (json.JSONDecodeError, KeyError):
                        continue


def main():
    """主函数 - 演示 Anthropic API 使用"""
    
    # 初始化客户端
    # 如果服务器设置了 API 密钥，需要提供
    client = AnthropicClient("http://localhost:8089")
    
    print("🤖 Anthropic API 使用示例\n")
    
    # 示例 1: 基础对话
    print("=" * 50)
    print("示例 1: 基础对话")
    print("=" * 50)
    
    try:
        response = client.create_message(
            messages=[
                {"role": "user", "content": "你好！请用一句话介绍你自己。"}
            ],
            max_tokens=100
        )
        
        print(f"模型: {response['model']}")
        print(f"回复: {response['content'][0]['text']}")
        print(f"使用令牌: {response['usage']['input_tokens']} 输入, {response['usage']['output_tokens']} 输出")
        
    except Exception as e:
        print(f"错误: {e}")
    
    print("\n" + "=" * 50)
    print("示例 2: 带系统提示词的对话")
    print("=" * 50)
    
    try:
        response = client.create_message(
            system="你是一个专业的 Python 开发者，回答要简洁且包含代码示例。",
            messages=[
                {"role": "user", "content": "如何用 Python 实现一个快速排序算法？"}
            ],
            max_tokens=300
        )
        
        print(f"回复: {response['content'][0]['text']}")
        
    except Exception as e:
        print(f"错误: {e}")
    
    print("\n" + "=" * 50)
    print("示例 3: 流式响应")
    print("=" * 50)
    
    try:
        client.create_message_stream(
            messages=[
                {"role": "user", "content": "请创作一个关于 AI 的小故事，分成三个段落。"}
            ],
            max_tokens=500
        )
        
    except Exception as e:
        print(f"错误: {e}")
    
    print("\n" + "=" * 50)
    print("示例 4: 使用内容块格式")
    print("=" * 50)
    
    try:
        response = client.create_message(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请解释以下概念：\n"},
                        {"type": "text", "text": "1. 机器学习\n"},
                        {"type": "text", "text": "2. 深度学习\n"},
                        {"type": "text", "text": "3. 强化学习"}
                    ]
                }
            ],
            max_tokens=400
        )
        
        print(f"回复: {response['content'][0]['text']}")
        
    except Exception as e:
        print(f"错误: {e}")
    
    print("\n" + "=" * 50)
    print("示例 5: 多轮对话")
    print("=" * 50)
    
    try:
        # 第一轮
        response1 = client.create_message(
            messages=[
                {"role": "user", "content": "我喜欢编程，特别是 Python。给我一些建议。"}
            ],
            max_tokens=200
        )
        
        assistant_reply = response1['content'][0]['text']
        print(f"助手: {assistant_reply}")
        
        # 第二轮（包含之前的对话）
        response2 = client.create_message(
            messages=[
                {"role": "user", "content": "我喜欢编程，特别是 Python。给我一些建议。"},
                {"role": "assistant", "content": assistant_reply},
                {"role": "user", "content": "谢谢！能推荐一些具体的项目吗？"}
            ],
            max_tokens=300
        )
        
        print(f"助手: {response2['content'][0]['text']}")
        
    except Exception as e:
        print(f"错误: {e}")


if __name__ == "__main__":
    main()