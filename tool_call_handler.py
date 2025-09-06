#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具调用支持模块
为 Anthropic API 提供工具调用功能
"""

import json
import time
from typing import Dict, Any, List, Optional

from utils import Logger


class ToolCallHandler:
    """工具调用处理器
    
    处理 Anthropic 格式的工具调用请求和响应。
    """
    
    def __init__(self):
        self.logger = Logger("tool_call")
    
    def extract_tool_calls_from_response(self, response_text: str) -> List[Dict[str, Any]]:
        """从响应文本中提取工具调用
        
        Args:
            response_text: 响应文本
            
        Returns:
            List[Dict[str, Any]]: 工具调用列表
        """
        tool_calls = []
        
        # 查找工具调用模式
        # Z.ai 可能使用特定的格式来表示工具调用
        if "<function_call>" in response_text:
            # 解析函数调用
            import re
            pattern = r'<function_call>\s*({.*?})\s*</function_call>'
            matches = re.findall(pattern, response_text, re.DOTALL)
            
            for match in matches:
                try:
                    tool_data = json.loads(match)
                    if tool_data.get("type") == "tool_call":
                        metadata = tool_data.get("data", {}).get("metadata", {})
                        if metadata.get("id") and metadata.get("name"):
                            tool_calls.append({
                                "id": metadata["id"],
                                "type": "function",
                                "function": {
                                    "name": metadata["name"],
                                    "arguments": json.dumps(metadata.get("arguments", {}))
                                }
                            })
                except (json.JSONDecodeError, KeyError):
                    continue
        
        return tool_calls
    
    def format_tool_use_content(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """格式化工具使用内容
        
        Args:
            tool_name: 工具名称
            tool_input: 工具输入
            
        Returns:
            str: 格式化后的内容
        """
        return f"使用工具 {tool_name}，参数：{json.dumps(tool_input, ensure_ascii=False)}"
    
    def create_tool_result_block(self, tool_call_id: str, tool_name: str, result: Any) -> Dict[str, Any]:
        """创建工具结果块
        
        Args:
            tool_call_id: 工具调用 ID
            tool_name: 工具名称
            result: 工具执行结果
            
        Returns:
            Dict[str, Any]: 工具结果块
        """
        return {
            "type": "tool_result",
            "tool_use_id": tool_call_id,
            "content": json.dumps(result, ensure_ascii=False) if result else ""
        }