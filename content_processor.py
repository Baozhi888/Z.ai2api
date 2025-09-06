# -*- coding: utf-8 -*-
"""
内容处理模块
专门处理思考链内容的转换逻辑
遵循单一职责原则
"""

import re
import zlib
from typing import Optional, Tuple
from enum import Enum
from cache import get_cache
from type_definitions import ThinkTagsMode


class ContentProcessor:
    """内容处理器，专门处理思考链内容转换
    
    该类遵循单一职责原则，专门处理思考链内容的格式转换，
    支持多种处理模式（think、pure、raw）。
    """
    
    def __init__(self, mode: ThinkTagsMode = ThinkTagsMode.THINK):
        self.mode = mode
        self.history_phase = "thinking"
        self.cache = get_cache()
        self._content_cache_ttl = 1800  # 30分钟缓存内容处理结果
    
    def process_content(self, content: str, phase: str) -> str:
        """处理内容，根据模式转换思考链格式
        
        Args:
            content: 原始内容
            phase: 内容阶段（thinking、answer 等）
            
        Returns:
            str: 处理后的内容
        """
        if not content:
            return content
            
        # 特殊处理思考链内容
        if phase == "thinking":
            # 如果是思考阶段，提取思考内容
            if content.startswith("<details"):
                # 从 details 标签中提取思考内容
                summary_match = re.search(r'<summary[^>]*>(.*?)</summary>', content)
                if summary_match:
                    # 如果有 summary，移除它，只保留内容
                    content = re.sub(r'<summary[^>]*>.*?</summary>\n?', '', content)
                # 移除 details 标签
                content = re.sub(r'</?details[^>]*>', '', content)
                # 清理格式
                content = content.strip()
                
        elif phase == "answer":
            # 如果是回答阶段，检查是否包含思考链的结束标记
            if "</details>\n" in content:
                # 分离思考和回答内容
                parts = content.split("</details>\n", 1)
                if len(parts) > 1:
                    content = parts[1]  # 只取回答部分
        
        # 生成缓存键（使用更高效的 CRC32 哈希）
        cache_key = self._generate_cache_key(content, phase)
        
        # 检查缓存
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        # 根据模式处理内容
        if self.mode == ThinkTagsMode.THINK:
            content = self._process_think_mode(content, phase)
        elif self.mode == ThinkTagsMode.PURE:
            content = self._process_pure_mode(content, phase)
        elif self.mode == ThinkTagsMode.RAW:
            content = self._process_raw_mode(content, phase)
        
        # 缓存结果
        self.cache.set(cache_key, content, self._content_cache_ttl)
        
        return content
    
    def _generate_cache_key(self, content: str, phase: str) -> str:
        """生成缓存键（使用高效的 CRC32 哈希）
        
        Args:
            content: 原始内容
            phase: 内容阶段
            
        Returns:
            str: 缓存键
        """
        # 使用 CRC32 代替 MD5，性能更好
        content_part = content[:100]  # 只取前100个字符，避免长内容影响性能
        hash_input = f"{content_part}:{self.mode.value}:{phase}"
        crc32_hash = zlib.crc32(hash_input.encode('utf-8'))
        return f"content_process:{crc32_hash:x}"
    
    def _clean_base_content(self, content: str) -> str:
        """清理基础内容
        
        Args:
            content: 原始内容
            
        Returns:
            str: 清理后的内容
        """
        content = re.sub(r"(?s)<details[^>]*?>.*?</details>", "", content)
        content = content.replace("</thinking>", "").replace("<Full>", "").replace("</Full>", "")
        return content
    
    def _process_think_mode(self, content: str, phase: str) -> str:
        """处理 think 模式
        
        Args:
            content: 原始内容
            phase: 内容阶段
            
        Returns:
            str: 处理后的内容
        """
        if phase == "thinking":
            content = content.lstrip("> ").replace("\n>", "\n").strip()
        
        content = re.sub(r'\n?<summary>.*?</summary>\n?', '', content)
        content = re.sub(r"<details[^>]*>\n?", "</think>\n\n", content)
        content = re.sub(r"\n?</details>", "\n\n</think>", content)
        
        if phase == "answer":
            return self._handle_think_answer_transition(content)
        
        return content
    
    def _process_pure_mode(self, content: str, phase: str) -> str:
        """处理 pure 模式
        
        Args:
            content: 原始内容
            phase: 内容阶段
            
        Returns:
            str: 处理后的内容
        """
        if phase == "thinking":
            content = re.sub(r'\n?<summary>.*?</summary>', '', content)
        
        content = re.sub(r"<details[^>]*>\n?", "<details type=\"reasoning\">", content)
        content = re.sub(r"\n?</details>", "\n\n></details>", content)
        
        if phase == "answer":
            return self._handle_pure_answer_transition(content)
        
        content = re.sub(r"</?details[^>]*>", "", content)
        return content
    
    def _process_raw_mode(self, content: str, phase: str) -> str:
        """处理 raw 模式
        
        Args:
            content: 原始内容
            phase: 内容阶段
            
        Returns:
            str: 处理后的内容
        """
        if phase == "thinking":
            content = re.sub(r'\n?<summary>.*?</summary>', '', content)
        
        content = re.sub(r"<details[^>]*>\n?", "<details type=\"reasoning\" open><div>\n\n", content)
        content = re.sub(r"\n?</details>", "\n\n</div></details>", content)
        
        if phase == "answer":
            return self._handle_raw_answer_transition(content)
        
        return content
    
    def _handle_think_answer_transition(self, content: str) -> str:
        """处理 think 模式的回答过渡
        
        Args:
            content: 原始内容
            
        Returns:
            str: 处理后的内容
        """
        match = re.search(r"(?s)^(.*?</think>)(.*)$", content)
        if match:
            before, after = match.groups()
            if after.strip():
                if self.history_phase == "thinking":
                    newline = "\n"
                    return f"{newline}{newline}</think>{newline}{newline}{after.lstrip(newline)}"
                elif self.history_phase == "answer":
                    return ""
            else:
                return "\n\n</think>"
        return content
    
    def _handle_pure_answer_transition(self, content: str) -> str:
        """处理 pure 模式的回答过渡
        
        Args:
            content: 原始内容
            
        Returns:
            str: 处理后的内容
        """
        match = re.search(r"(?s)^(.*?</details>)(.*)$", content)
        if match:
            before, after = match.groups()
            if after.strip():
                if self.history_phase == "thinking":
                    newline = "\n"
                    return f"{newline}{newline}{after.lstrip(newline)}"
                elif self.history_phase == "answer":
                    return ""
            else:
                return ""
        return re.sub(r"</?details[^>]*>", "", content)
    
    def _handle_raw_answer_transition(self, content: str) -> str:
        """处理 raw 模式的回答过渡
        
        Args:
            content: 原始内容
            
        Returns:
            str: 处理后的内容
        """
        match = re.search(r"(?s)^(.*?</details>)(.*)$", content)
        if match:
            before, after = match.groups()
            if after.strip():
                if self.history_phase == "thinking":
                    newline = "\n"
                    return f"{newline}{newline}</details>{newline}{newline}{after.lstrip(newline)}"
                elif self.history_phase == "answer":
                    return ""
            else:
                return self._generate_raw_summary(before)
        return content
    
    def _generate_raw_summary(self, before: str) -> str:
        """生成 raw 模式的总结
        
        Args:
            before: 原始内容
            
        Returns:
            str: 生成的总结内容
        """
        summary_match = re.search(r"(?s)<summary>.*?</summary>", before)
        duration_match = re.search(r'duration="(\d+)"', before)
        
        if summary_match:
            return f"\n\n</div>{summary_match.group()}</details>\n\n"
        elif duration_match:
            duration = duration_match.group(1)
            return f'\n\n</div><summary>Thought for {duration} seconds</summary></details>\n\n'
        else:
            return "\n\n</div></details>"