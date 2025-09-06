#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具调用错误处理
提供工具调用相关的错误处理和恢复机制
"""

import json
import time
import traceback
from typing import Dict, Any, Optional, Iterator
from utils import Logger


class ToolCallError(Exception):
    """工具调用基础异常"""
    pass


class ToolCallParseError(ToolCallError):
    """工具调用解析错误"""
    pass


class ToolCallTimeoutError(ToolCallError):
    """工具调用超时错误"""
    pass


class ToolCallExecutionError(ToolCallError):
    """工具调用执行错误"""
    pass


class ToolCallErrorHandler:
    """工具调用错误处理器
    
    提供工具调用相关的错误处理、恢复和日志记录功能
    """
    
    def __init__(self):
        self.logger = Logger("tool_call_error_handler")
        self.error_counts = {
            "parse_error": 0,
            "timeout_error": 0,
            "execution_error": 0,
            "unknown_error": 0
        }
    
    def handle_parse_error(self, error: Exception, context: Dict[str, Any] = None) -> Iterator[str]:
        """处理解析错误
        
        Args:
            error: 解析错误
            context: 错误上下文
            
        Yields:
            str: 错误事件流
        """
        self.error_counts["parse_error"] += 1
        self.logger.warning(f"工具调用解析错误: {error}, 上下文: {context}")
        
        # 生成错误事件
        error_event = {
            "id": context.get("chat_id", "error"),
            "object": "chat.completion.chunk",
            "model": context.get("model", "unknown"),
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": f"工具调用解析失败: {str(error)}"
                }
            }]
        }
        
        yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
    
    def handle_timeout_error(self, tool_id: str, timeout: float, context: Dict[str, Any] = None) -> Iterator[str]:
        """处理超时错误
        
        Args:
            tool_id: 工具调用ID
            timeout: 超时时间
            context: 错误上下文
            
        Yields:
            str: 错误事件流
        """
        self.error_counts["timeout_error"] += 1
        self.logger.warning(f"工具调用超时: {tool_id}, 超时时间: {timeout}秒")
        
        # 生成超时事件
        timeout_event = {
            "id": context.get("chat_id", "error"),
            "object": "chat.completion.chunk",
            "model": context.get("model", "unknown"),
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": f"工具调用超时: {tool_id}"
                },
                "finish_reason": "tool_calls"
            }]
        }
        
        yield f"data: {json.dumps(timeout_event, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
    
    def handle_execution_error(self, tool_id: str, error: Exception, context: Dict[str, Any] = None) -> Iterator[str]:
        """处理执行错误
        
        Args:
            tool_id: 工具调用ID
            error: 执行错误
            context: 错误上下文
            
        Yields:
            str: 错误事件流
        """
        self.error_counts["execution_error"] += 1
        self.logger.error(f"工具调用执行错误: {tool_id}, 错误: {error}")
        
        # 生成执行错误事件
        error_event = {
            "id": context.get("chat_id", "error"),
            "object": "chat.completion.chunk",
            "model": context.get("model", "unknown"),
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": f"工具调用执行失败: {str(error)}"
                },
                "finish_reason": "tool_calls"
            }]
        }
        
        yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
    
    def handle_unknown_error(self, error: Exception, context: Dict[str, Any] = None) -> Iterator[str]:
        """处理未知错误
        
        Args:
            error: 未知错误
            context: 错误上下文
            
        Yields:
            str: 错误事件流
        """
        self.error_counts["unknown_error"] += 1
        self.logger.error(f"工具调用未知错误: {error}\n{traceback.format_exc()}")
        
        # 生成未知错误事件
        error_event = {
            "id": context.get("chat_id", "error"),
            "object": "chat.completion.chunk",
            "model": context.get("model", "unknown"),
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": "工具调用发生未知错误，请稍后重试"
                },
                "finish_reason": "error"
            }]
        }
        
        yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
    
    def safe_parse_tool_call(self, content: str, context: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """安全解析工具调用
        
        Args:
            content: 要解析的内容
            context: 解析上下文
            
        Returns:
            Optional[Dict[str, Any]]: 解析结果，失败时返回None
        """
        try:
            if "<function_call>" in content:
                import re
                pattern = r'<function_call>\s*({.*?})\s*</function_call>'
                matches = re.findall(pattern, content, re.DOTALL)
                if matches:
                    return json.loads(matches[0])
            
            if "<glm_block >" in content:
                blocks = content.split("<glm_block >")
                if len(blocks) > 1 and "</glm_block>" in blocks[1]:
                    block_content = blocks[1].split("</glm_block>")[0]
                    return json.loads(block_content)
            
            return None
        except json.JSONDecodeError as e:
            self.logger.warning(f"工具调用JSON解析失败: {e}")
            return None
        except Exception as e:
            self.logger.error(f"工具调用解析未知错误: {e}")
            return None
    
    def validate_tool_call(self, tool_data: Dict[str, Any]) -> bool:
        """验证工具调用数据格式
        
        Args:
            tool_data: 工具调用数据
            
        Returns:
            bool: 是否有效
        """
        if not isinstance(tool_data, dict):
            return False
        
        # 检查必需字段
        if tool_data.get("type") != "tool_call":
            return False
        
        data = tool_data.get("data", {})
        if not isinstance(data, dict):
            return False
        
        metadata = data.get("metadata", {})
        required_fields = ["id", "name"]
        
        return all(field in metadata for field in required_fields)
    
    def get_error_stats(self) -> Dict[str, int]:
        """获取错误统计
        
        Returns:
            Dict[str, int]: 错误统计
        """
        return self.error_counts.copy()
    
    def reset_error_stats(self):
        """重置错误统计"""
        for key in self.error_counts:
            self.error_counts[key] = 0