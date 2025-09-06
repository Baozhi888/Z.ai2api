# -*- coding: utf-8 -*-
"""
多模态消息处理模块
处理 OpenAI 和 Anthropic 格式的多模态消息转换
"""

from typing import Dict, Any, List, Union
import re
import base64
from utils import Logger


class MultimodalProcessor:
    """多模态消息处理器
    
    将不同格式的多模态消息转换为 Z.ai API 可接受的格式。
    """
    
    def __init__(self, logger: Logger):
        self.logger = logger
    
    def process_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """处理消息列表，转换多模态格式
        
        Args:
            messages: 原始消息列表
            
        Returns:
            List[Dict[str, Any]]: 处理后的消息列表
        """
        processed_messages = []
        
        for msg in messages:
            processed_msg = msg.copy()
            
            # 处理 content 字段
            if isinstance(msg.get("content"), list):
                # OpenAI 多模态格式
                processed_msg["content"] = self._process_openai_multimodal(msg["content"])
            elif isinstance(msg.get("content"), str):
                # 普通文本格式，检查是否包含图片
                processed_msg["content"] = self._process_text_content(msg["content"])
            
            processed_messages.append(processed_msg)
        
        return processed_messages
    
    def _process_openai_multimodal(self, content_list: List[Dict[str, Any]]) -> Union[str, List[Dict[str, Any]]]:
        """处理 OpenAI 格式的多模态内容
        
        Args:
            content_list: OpenAI 格式的内容列表
            
        Returns:
            Union[str, List[Dict[str, Any]]]: 转换后的内容
        """
        # 检查是否包含图片
        has_image = any(item.get("type") == "image_url" for item in content_list)
        
        if not has_image:
            # 如果没有图片，直接返回文本
            text_parts = [item.get("text", "") for item in content_list if item.get("type") == "text"]
            return "\n".join(text_parts)
        
        # 如果有图片，保留原始格式
        # Z.ai API 可能直接支持这种格式
        return content_list
    
    def _process_text_content(self, content: str) -> str:
        """处理纯文本内容
        
        Args:
            content: 文本内容
            
        Returns:
            str: 处理后的文本内容
        """
        # 检查是否包含 base64 图片
        base64_pattern = r'data:image/([^;]+);base64,([A-Za-z0-9+/=]+)'
        
        def replace_base64(match):
            img_format = match.group(1)
            img_data = match.group(2)
            return f"[{img_format.upper()}图片附件]"
        
        content = re.sub(base64_pattern, replace_base64, content)
        return content
    
    def _extract_image_info(self, image_url: str) -> str:
        """从图片 URL 中提取信息
        
        Args:
            image_url: 图片 URL
            
        Returns:
            str: 图片信息描述
        """
        # 解析 data URL 格式：data:image/<format>;base64,<data>
        if image_url.startswith("data:image/"):
            parts = image_url.split(",")
            if len(parts) == 2:
                meta_part = parts[0]
                # 提取图片格式
                if ";base64" in meta_part:
                    img_format = meta_part.split("/")[-1].split(";")[0]
                    return f"{img_format.upper()}格式"
        
        return "图片"
    
    def process_anthropic_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """处理 Anthropic 格式的多模态消息
        
        Args:
            messages: Anthropic 格式的消息列表
            
        Returns:
            List[Dict[str, Any]]: 转换后的消息列表
        """
        processed_messages = []
        
        for msg in messages:
            processed_msg = msg.copy()
            
            # 处理 content 字段
            if isinstance(msg.get("content"), list):
                # Anthropic 多模态格式
                processed_msg["content"] = self._process_anthropic_multimodal(msg["content"])
            
            processed_messages.append(processed_msg)
        
        return processed_messages
    
    def _process_anthropic_multimodal(self, content_list: List[Dict[str, Any]]) -> Union[str, List[Dict[str, Any]]]:
        """处理 Anthropic 格式的多模态内容
        
        Args:
            content_list: Anthropic 格式的内容列表
            
        Returns:
            Union[str, List[Dict[str, Any]]]: 转换后的内容
        """
        # 检查是否包含图片
        has_image = any(item.get("type") == "image" for item in content_list)
        
        if not has_image:
            # 如果没有图片，直接返回文本
            text_parts = [item.get("text", "") for item in content_list if item.get("type") == "text"]
            return "\n".join(text_parts)
        
        # 如果有图片，转换为 OpenAI 格式
        # 因为 Z.ai API 可能更熟悉这种格式
        converted_content = []
        
        for item in content_list:
            if item.get("type") == "text":
                converted_content.append({
                    "type": "text",
                    "text": item.get("text", "")
                })
            elif item.get("type") == "image":
                source = item.get("source", {})
                if source.get("type") == "base64":
                    media_type = source.get("media_type", "image/jpeg")
                    data = source.get("data", "")
                    converted_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{data}"
                        }
                    })
        
        return converted_content