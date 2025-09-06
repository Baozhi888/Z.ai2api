#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具调用管理器
管理工具调用的状态和参数拼接
"""

import json
import time
import uuid
from typing import Dict, Any, List, Optional
from utils import Logger


class ToolCallManager:
    """工具调用管理器
    
    管理工具调用的生命周期，包括：
    - 工具调用开始
    - 参数拼接
    - 工具调用结束
    - 状态管理
    """
    
    def __init__(self):
        self.logger = Logger("tool_call_manager")
        self.active_calls: Dict[str, Dict[str, Any]] = {}
        self.call_buffer: str = ""
        self.current_state = "idle"
        
    def start_tool_call(self, tool_id: str, tool_name: str, index: int) -> Dict[str, Any]:
        """开始工具调用
        
        Args:
            tool_id: 工具调用ID
            tool_name: 工具名称
            index: 工具调用索引
            
        Returns:
            Dict[str, Any]: 工具调用开始事件
        """
        self.current_state = "tool_call"
        self.active_calls[tool_id] = {
            "name": tool_name,
            "index": index,
            "arguments": "",
            "started_at": time.time(),
            "completed": False
        }
        
        return {
            "id": tool_id,
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": ""
            }
        }
    
    def append_arguments(self, tool_id: str, args_chunk: str) -> Optional[List[Dict[str, Any]]]:
        """追加参数
        
        Args:
            tool_id: 工具调用ID
            args_chunk: 参数块
            
        Returns:
            Optional[List[Dict[str, Any]]]: 参数增量事件列表
        """
        if tool_id not in self.active_calls:
            return None
            
        self.active_calls[tool_id]["arguments"] += args_chunk
        self.call_buffer += args_chunk
        
        # 返回参数增量事件
        return [{
            "index": self.active_calls[tool_id]["index"],
            "function": {
                "arguments": args_chunk
            }
        }]
    
    def complete_tool_call(self, tool_id: str, usage: Dict[str, Any] = None) -> Dict[str, Any]:
        """完成工具调用
        
        Args:
            tool_id: 工具调用ID
            usage: 使用情况统计
            
        Returns:
            Dict[str, Any]: 工具调用完成事件
        """
        if tool_id in self.active_calls:
            self.active_calls[tool_id]["completed"] = True
            self.active_calls[tool_id]["completed_at"] = time.time()
            self.active_calls[tool_id]["usage"] = usage
            
            # 解析完整的参数
            try:
                if self.call_buffer.endswith('"'):
                    self.call_buffer = self.call_buffer[:-1]
                arguments = json.loads(self.call_buffer)
                self.active_calls[tool_id]["parsed_arguments"] = arguments
            except json.JSONDecodeError:
                self.logger.warning(f"无法解析工具调用参数: {self.call_buffer}")
                arguments = {}
            
            # 重置缓冲区
            self.call_buffer = ""
            
            return {
                "index": self.active_calls[tool_id]["index"],
                "function": {
                    "name": None,
                    "arguments": arguments
                }
            }
        
        return {}
    
    def reset_state(self):
        """重置状态"""
        self.active_calls.clear()
        self.call_buffer = ""
        self.current_state = "idle"
    
    def get_active_call_count(self) -> int:
        """获取活跃的工具调用数量"""
        return len([call for call in self.active_calls.values() if not call["completed"]])
    
    def has_active_calls(self) -> bool:
        """是否有活跃的工具调用"""
        return self.get_active_call_count() > 0