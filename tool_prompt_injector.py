#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具提示注入器
负责将工具定义注入到消息中，引导模型正确调用工具
"""

import json
from typing import List, Dict, Any, Optional, Union
from utils import Logger


class ToolPromptInjector:
    """工具提示注入器
    
    该类负责将工具定义转换为自然语言提示，并注入到消息中，
    帮助模型理解如何正确调用工具。
    """
    
    def __init__(self):
        self.logger = Logger("tool_prompt_injector")
        
    def format_tools_for_prompt(self, tools: List[Dict[str, Any]]) -> str:
        """将工具定义格式化为提示文本
        
        Args:
            tools: 工具定义列表
            
        Returns:
            str: 格式化后的提示文本
        """
        if not tools:
            return ""
        
        lines = []
        
        # 构建工具描述
        for tool in tools:
            if tool.get("type") != "function":
                continue
                
            function_def = tool.get("function", {})
            if not function_def:
                continue
                
            name = function_def.get("name", "unknown")
            description = function_def.get("description", "")
            parameters = function_def.get("parameters", {})
            
            # 构建工具描述
            tool_desc = [f"- {name}: {description}"]
            
            # 构建参数描述
            properties = parameters.get("properties", {})
            required = set(parameters.get("required", []) or [])
            
            for param_name, param_info in properties.items():
                param_type = param_info.get("type", "any")
                param_desc = param_info.get("description", "")
                is_required = " (required)" if param_name in required else " (optional)"
                
                # 处理枚举类型
                if "enum" in param_info:
                    enum_values = ", ".join(str(v) for v in param_info["enum"])
                    param_desc = f"{param_desc} [可选值: {enum_values}]"
                
                tool_desc.append(f"  - {param_name} ({param_type}){is_required}: {param_desc}")
            
            lines.append("\n".join(tool_desc))
        
        if not lines:
            return ""
        
        # 构建完整的工具提示
        prompt = (
            "\n\n可用的工具函数:\n" + 
            "\n".join(lines) +
            "\n\n如果需要调用工具，请仅用以下 JSON 结构回复（不要包含多余文本）:\n"
            "```json\n"
            "{\n"
            '  "tool_calls": [\n'
            "    {\n"
            '      "id": "call_xxx",\n'
            '      "type": "function",\n'
            '      "function": {\n'
            '        "name": "function_name",\n'
            '        "arguments": "{\\"param1\\": \\"value1\\"}"\n'
            "      }\n"
            "    }\n"
            "  ]\n"
            "}\n"
            "```\n"
            "注意：arguments 必须是 JSON 字符串格式。"
        )
        
        return prompt
    
    def inject_tools_into_messages(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """将工具提示注入到消息中
        
        Args:
            messages: 原始消息列表
            tools: 工具定义列表
            tool_choice: 工具选择策略
            
        Returns:
            List[Dict[str, Any]]: 注入工具提示后的消息列表
        """
        if not tools:
            return messages
        
        # 格式化工具提示
        tools_prompt = self.format_tools_for_prompt(tools)
        if not tools_prompt:
            return messages
        
        processed_messages = []
        has_system = any(msg.get("role") == "system" for msg in messages)
        
        # 注入工具提示到系统消息
        if has_system:
            for msg in messages:
                if msg.get("role") == "system":
                    # 将工具提示添加到系统消息
                    processed_msg = dict(msg)
                    content = self._append_to_content(msg.get("content"), tools_prompt)
                    processed_msg["content"] = content
                    processed_messages.append(processed_msg)
                else:
                    processed_messages.append(msg)
        else:
            # 创建新的系统消息
            system_msg = {
                "role": "system",
                "content": "你是一个有用的助手。" + tools_prompt
            }
            processed_messages = [system_msg] + messages
        
        # 处理 tool_choice 策略
        if tool_choice and processed_messages and processed_messages[-1].get("role") == "user":
            last_msg = dict(processed_messages[-1])
            
            if tool_choice == "required":
                # 强制使用工具
                additional_prompt = "\n\n请使用提供的工具函数来处理这个请求。"
                last_msg["content"] = self._append_to_content(
                    last_msg.get("content"), 
                    additional_prompt
                )
            elif tool_choice == "auto":
                # 自动决定是否使用工具
                additional_prompt = "\n\n请根据需要使用提供的工具函数。"
                last_msg["content"] = self._append_to_content(
                    last_msg.get("content"), 
                    additional_prompt
                )
            elif isinstance(tool_choice, dict) and tool_choice.get("type") == "function":
                # 指定特定工具
                function_name = tool_choice.get("function", {}).get("name")
                if function_name:
                    additional_prompt = f"\n\n请使用 {function_name} 函数来处理这个请求。"
                    last_msg["content"] = self._append_to_content(
                        last_msg.get("content"), 
                        additional_prompt
                    )
            
            processed_messages[-1] = last_msg
        
        return processed_messages
    
    def process_tool_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """处理包含工具调用结果的消息
        
        将 tool/function 角色的消息转换为助手可理解的格式
        
        Args:
            messages: 包含工具调用结果的消息列表
            
        Returns:
            List[Dict[str, Any]]: 处理后的消息列表
        """
        processed = []
        
        for msg in messages:
            role = msg.get("role")
            
            if role in ("tool", "function"):
                # 将工具结果转换为助手消息
                tool_name = msg.get("name", "unknown")
                tool_content = self._content_to_str(msg.get("content", ""))
                
                processed_msg = {
                    "role": "assistant",
                    "content": f"工具 {tool_name} 返回结果:\n```json\n{tool_content}\n```"
                }
                processed.append(processed_msg)
            else:
                # 确保 content 是字符串格式
                processed_msg = dict(msg)
                if isinstance(processed_msg.get("content"), list):
                    processed_msg["content"] = self._content_to_str(processed_msg["content"])
                processed.append(processed_msg)
        
        return processed
    
    def _append_to_content(self, original: Any, extra: str) -> Any:
        """向内容追加文本
        
        Args:
            original: 原始内容（字符串或数组）
            extra: 要追加的文本
            
        Returns:
            Any: 追加后的内容
        """
        if isinstance(original, str):
            return original + extra
        elif isinstance(original, list):
            # 处理数组格式的内容
            new_content = list(original)
            if new_content and isinstance(new_content[-1], dict) and new_content[-1].get("type") == "text":
                # 追加到最后一个文本元素
                new_content[-1]["text"] = new_content[-1].get("text", "") + extra
            else:
                # 添加新的文本元素
                new_content.append({"type": "text", "text": extra})
            return new_content
        else:
            return extra
    
    def _content_to_str(self, content: Any) -> str:
        """将内容转换为字符串
        
        Args:
            content: 内容（可能是字符串或数组）
            
        Returns:
            str: 字符串格式的内容
        """
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    parts.append(item)
            return " ".join(parts)
        else:
            return ""