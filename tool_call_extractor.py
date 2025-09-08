#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具调用提取器
从模型响应中提取和验证工具调用
"""

import json
import re
import uuid
from typing import Optional, List, Dict, Any, Tuple
from utils import Logger


class ToolCallExtractor:
    """工具调用提取器
    
    负责从模型响应中提取工具调用，支持多种格式：
    - JSON 代码块格式
    - 内联 JSON 格式
    - 自然语言格式
    """
    
    # 编译正则表达式以提高性能
    JSON_FENCE_PATTERN = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
    JSON_INLINE_PATTERN = re.compile(r"(\{[^{}]{0,10000}\"tool_calls\".*?\})", re.DOTALL)
    FUNCTION_LINE_PATTERN = re.compile(
        r"调用函数\s*[：:]\s*([\w\-\.]+)\s*(?:参数|arguments)[：:]\s*(\{.*?\})", 
        re.DOTALL
    )
    
    def __init__(self, max_json_scan: int = 200000):
        """初始化提取器
        
        Args:
            max_json_scan: 最大 JSON 扫描长度
        """
        self.logger = Logger("tool_call_extractor")
        self.max_json_scan = max_json_scan
    
    def extract_tool_calls(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """从文本中提取工具调用
        
        Args:
            text: 要分析的文本
            
        Returns:
            Optional[List[Dict[str, Any]]]: 提取的工具调用列表，如果没有则返回 None
        """
        if not text:
            return None
        
        # 限制扫描长度以提高性能
        sample = text[:self.max_json_scan]
        
        # 尝试从 JSON 代码块提取
        tool_calls = self._extract_from_json_fence(sample)
        if tool_calls:
            self.logger.debug(f"从 JSON 代码块提取到 {len(tool_calls)} 个工具调用")
            return tool_calls
        
        # 尝试从内联 JSON 提取
        tool_calls = self._extract_from_inline_json(sample)
        if tool_calls:
            self.logger.debug(f"从内联 JSON 提取到 {len(tool_calls)} 个工具调用")
            return tool_calls
        
        # 尝试从自然语言格式提取
        tool_calls = self._extract_from_natural_language(sample)
        if tool_calls:
            self.logger.debug(f"从自然语言格式提取到 {len(tool_calls)} 个工具调用")
            return tool_calls
        
        return None
    
    def strip_tool_json_from_text(self, text: str) -> str:
        """从文本中移除工具调用 JSON
        
        Args:
            text: 包含工具调用的文本
            
        Returns:
            str: 移除工具调用后的文本
        """
        def drop_if_toolcalls(match: re.Match) -> str:
            """如果匹配包含 tool_calls，则删除"""
            block = match.group(1)
            try:
                data = json.loads(block)
                if "tool_calls" in data:
                    return ""
            except Exception:
                pass
            return match.group(0)
        
        # 移除包含 tool_calls 的 JSON 代码块
        new_text = self.JSON_FENCE_PATTERN.sub(drop_if_toolcalls, text)
        
        # 移除内联的 tool_calls JSON
        new_text = self.JSON_INLINE_PATTERN.sub("", new_text)
        
        return new_text.strip()
    
    def validate_tool_call(self, tool_call: Dict[str, Any]) -> bool:
        """验证工具调用格式
        
        Args:
            tool_call: 工具调用数据
            
        Returns:
            bool: 是否有效
        """
        # 检查基本结构
        if not isinstance(tool_call, dict):
            return False
        
        # 检查必需字段
        if "type" not in tool_call:
            return False
        
        if tool_call["type"] != "function":
            return False
        
        # 检查 function 字段
        function = tool_call.get("function")
        if not isinstance(function, dict):
            return False
        
        # 检查函数名
        if "name" not in function:
            return False
        
        # 检查参数（可选，但如果存在必须是字符串）
        if "arguments" in function:
            arguments = function["arguments"]
            if not isinstance(arguments, str):
                # 尝试转换为字符串
                try:
                    function["arguments"] = json.dumps(arguments)
                except Exception:
                    return False
        
        # 确保有 ID
        if "id" not in tool_call:
            tool_call["id"] = self._generate_tool_id()
        
        return True
    
    def normalize_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """标准化工具调用格式
        
        Args:
            tool_calls: 原始工具调用列表
            
        Returns:
            List[Dict[str, Any]]: 标准化后的工具调用列表
        """
        normalized = []
        
        for tool_call in tool_calls:
            # 验证格式
            if not self.validate_tool_call(tool_call):
                self.logger.warning(f"无效的工具调用格式: {tool_call}")
                continue
            
            # 确保有 ID
            if "id" not in tool_call:
                tool_call["id"] = self._generate_tool_id()
            
            # 确保 arguments 是字符串
            function = tool_call.get("function", {})
            if "arguments" in function and not isinstance(function["arguments"], str):
                try:
                    function["arguments"] = json.dumps(function["arguments"], ensure_ascii=False)
                except Exception as e:
                    self.logger.warning(f"无法序列化参数: {e}")
                    function["arguments"] = "{}"
            
            normalized.append(tool_call)
        
        return normalized
    
    def _extract_from_json_fence(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """从 JSON 代码块提取工具调用
        
        Args:
            text: 要分析的文本
            
        Returns:
            Optional[List[Dict[str, Any]]]: 提取的工具调用列表
        """
        matches = self.JSON_FENCE_PATTERN.findall(text)
        
        for json_str in matches:
            try:
                data = json.loads(json_str)
                if "tool_calls" in data and isinstance(data["tool_calls"], list):
                    return self.normalize_tool_calls(data["tool_calls"])
            except json.JSONDecodeError:
                continue
        
        return None
    
    def _extract_from_inline_json(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """从内联 JSON 提取工具调用
        
        Args:
            text: 要分析的文本
            
        Returns:
            Optional[List[Dict[str, Any]]]: 提取的工具调用列表
        """
        match = self.JSON_INLINE_PATTERN.search(text)
        
        if match:
            json_str = match.group(1)
            try:
                data = json.loads(json_str)
                if "tool_calls" in data and isinstance(data["tool_calls"], list):
                    return self.normalize_tool_calls(data["tool_calls"])
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _extract_from_natural_language(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """从自然语言格式提取工具调用
        
        Args:
            text: 要分析的文本
            
        Returns:
            Optional[List[Dict[str, Any]]]: 提取的工具调用列表
        """
        match = self.FUNCTION_LINE_PATTERN.search(text)
        
        if match:
            function_name = match.group(1).strip()
            arguments_str = match.group(2).strip()
            
            try:
                # 验证参数是有效的 JSON
                json.loads(arguments_str)
                
                tool_call = {
                    "id": self._generate_tool_id(),
                    "type": "function",
                    "function": {
                        "name": function_name,
                        "arguments": arguments_str
                    }
                }
                
                return [tool_call]
            except json.JSONDecodeError:
                self.logger.warning(f"无法解析函数参数: {arguments_str}")
        
        return None
    
    def _generate_tool_id(self) -> str:
        """生成工具调用 ID
        
        Returns:
            str: 工具调用 ID
        """
        return f"call_{uuid.uuid4().hex[:12]}"