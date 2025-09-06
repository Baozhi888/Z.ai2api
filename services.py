# -*- coding: utf-8 -*-
"""
业务逻辑模块
处理核心的业务逻辑
"""

import json
import time
import re
from datetime import datetime
from typing import Dict, Any, Iterator, Optional, List
from http_client import ZAIClient, HttpClientError
from content_processor import ContentProcessor, ThinkTagsMode
from multimodal_processor import MultimodalProcessor
from utils import Logger, IDGenerator, ModelFormatter
from config import config
from cache import get_cache
from performance import get_monitor, RequestTimer


class ChatService:
    """聊天服务类，处理聊天相关的业务逻辑
    
    该类遵循单一职责原则，专门处理与聊天相关的所有业务逻辑，
    包括模型列表获取、聊天完成创建等。
    """
    
    def __init__(self, zai_client: ZAIClient, content_processor: ContentProcessor, logger: Logger):
        self.zai_client = zai_client
        self.content_processor = content_processor
        self.logger = logger
        self.multimodal_processor = MultimodalProcessor(logger)
        self.cache = get_cache()
        self._models_cache_ttl = 300  # 5分钟缓存模型列表
        self._auth_token_cache_ttl = 600  # 10分钟缓存认证令牌
    
    def get_models_list(self) -> Dict[str, Any]:
        """获取模型列表
        
        Returns:
            Dict[str, Any]: 模型列表数据，符合 OpenAI API 格式
            
        Raises:
            HttpClientError: HTTP 请求失败时抛出
            Exception: 其他处理错误时抛出
        """
        with RequestTimer("/v1/models") as timer:
            # 检查缓存
            cache_key = "models_list"
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                timer.mark_cached()
                if config.debug_mode:
                    self.logger.debug("从缓存获取模型列表")
                return cached_result
            
            try:
                response = self.zai_client.get_models()
                models = []
                
                for model_data in response.get("data", []):
                    if not model_data.get("info", {}).get("is_active", True):
                        continue
                    
                    model_id = model_data.get("id")
                    model_name = model_data.get("name")
                    
                    # 格式化模型名称
                    if model_id.startswith(("GLM", "Z")):
                        model_name = model_id
                    elif not model_name or not ModelFormatter.is_english_letter(model_name[0]):
                        model_name = ModelFormatter.format_model_name(model_id)
                    
                    models.append({
                        "id": model_id,
                        "object": "model",
                        "name": model_name,
                        "created": model_data.get("info", {}).get("created_at", int(IDGenerator.generate_id().split('-')[1]) // 1e9),
                        "owned_by": "z.ai"
                    })
                
                result = {"object": "list", "data": models}
                
                # 缓存结果
                self.cache.set(cache_key, result, self._models_cache_ttl)
                if config.debug_mode:
                    self.logger.debug("模型列表已缓存，TTL: %d 秒", self._models_cache_ttl)
                
                return result
            
            except HttpClientError as e:
                self.logger.error("获取模型列表失败: %s", e)
                raise
            except Exception as e:
                self.logger.error("模型列表处理失败: %s", e)
                raise
    
    def create_chat_completion(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建聊天完成
        
        Args:
            request_data: 聊天完成请求数据
            
        Returns:
            Dict[str, Any]: 聊天完成响应数据
            
        Raises:
            HttpClientError: 上游 API 调用失败时抛出
        """
        with RequestTimer("/v1/chat/completions") as timer:
            chat_id = IDGenerator.generate_id("chat")
            msg_id = IDGenerator.generate_id("msg")
            raw_model = request_data.get("model", config.model_name)
            
            # 标准化模型名
            if raw_model.upper() in ["GLM-4", "GLM-4.5", "GLM4", "GLM45"]:
                model = "glm-4.5v"  # 使用正确的模型名
                if config.debug_mode:
                    self.logger.debug(f"模型名标准化: {raw_model} -> {model}")
            else:
                model = raw_model
                
            is_stream = request_data.get("stream", False)
            
            # 处理多模态消息
            original_messages = request_data.get("messages", [])
            
            # 处理系统消息
            processed_messages = []
            for msg in original_messages:
                processed_msg = self._process_system_message(msg)
                processed_messages.append(processed_msg)
            
            # 处理多模态内容
            processed_messages = self.multimodal_processor.process_messages(processed_messages)
            
            # 检查是否包含多模态内容
            has_multimodal = self._contains_multimodal(original_messages)
            
            # 构建更完整的请求数据
            upstream_data = {
                "stream": is_stream,
                "chat_id": chat_id,
                "id": msg_id,
                "model": model,
                "messages": processed_messages,
                "params": {},
                "features": {
                    "image_generation": False,
                    "web_search": False,
                    "auto_web_search": False,
                    "preview_mode": False,
                    "flags": [],
                    "features": [],
                    "enable_thinking": request_data.get("reasoning", False),
                },
                "variables": self._get_variables(),
                "model_item": {},
                "tools": request_data.get("tools") if not request_data.get("reasoning", False) and request_data.get("tools") else None,
            }
            
            if config.debug_mode:
                self.logger.debug("上游请求: %s", json.dumps(upstream_data, ensure_ascii=False))
            
            try:
                if is_stream:
                    # 流式请求使用流式 API
                    upstream = self.zai_client.create_chat_completion(upstream_data, chat_id)
                    return self._handle_stream_response(upstream, model)
                else:
                    # 非流式请求使用普通 API，避免等待流式响应完成
                    # 如果是多模态请求，使用更长的超时时间
                    timeout = config.multimodal_timeout if has_multimodal else config.non_stream_timeout
                    upstream = self.zai_client.create_chat_completion_normal(
                        upstream_data, 
                        chat_id, 
                        timeout=timeout
                    )
                    return self._handle_normal_response_direct(upstream, model)
            
            except HttpClientError as e:
                timer.success = False
                self.logger.error("上游 API 调用失败: %s, 请求ID: %s, 模型: %s", e, chat_id, model)
                raise Exception(f"上游调用失败: {e} (请求ID: {chat_id})")
            except Exception as e:
                timer.success = False
                self.logger.error("聊天完成处理失败: %s, 请求ID: %s, 模型: %s", e, chat_id, model)
                raise Exception(f"内部处理错误: {e} (请求ID: {chat_id})")
    
    def _handle_stream_response(self, upstream: Iterator[bytes], model: str) -> Dict[str, Any]:
        """处理流式响应
        
        Args:
            upstream: 上游流式响应数据
            model: 使用的模型名称
            
        Returns:
            Dict[str, Any]: 流式响应结果，包含生成器和模型信息
        """
        def stream_generator():
            chat_id = IDGenerator.generate_id('chatcmpl')
            content_index = 0
            has_thinking = False
            has_tool_call = False
            tool_args = ""
            tool_id = ""
            
            # 发送开始消息
            start_data = {
                'id': chat_id,
                'object': 'chat.completion.chunk',
                'model': model,
                'choices': [{'index': 0, 'delta': {'role': 'assistant'}}]
            }
            yield f"data: {json.dumps(start_data, ensure_ascii=False)}\n\n"
            
            # 处理流式内容
            for data in self._parse_upstream_stream(upstream):
                chunk_data = data.get("data", {})
                
                # 检查是否完成
                if chunk_data.get("done"):
                    # 发送结束消息
                    finish_data = {
                        'id': chat_id,
                        'object': 'chat.completion.chunk',
                        'model': model,
                        'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}],
                        'usage': chunk_data.get("usage", {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0
                        })
                    }
                    yield f"data: {json.dumps(finish_data, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    break
                
                phase = chunk_data.get("phase")
                
                # 处理思考链
                if phase == "thinking":
                    has_thinking = True
                    thinking_content = chunk_data.get("delta_content", "")
                    if thinking_content:
                        # 清理思考内容
                        if thinking_content.startswith("<details"):
                            thinking_content = re.sub(r'<summary[^>]*>.*?</summary>\n?', '', thinking_content)
                            thinking_content = re.sub(r'</?details[^>]*>', '', thinking_content)
                        
                        thinking_data = {
                            'id': chat_id,
                            'object': 'chat.completion.chunk',
                            'model': model,
                            'choices': [{
                                'index': content_index,
                                'delta': {
                                    'role': 'assistant',
                                    'thinking': {
                                        'content': thinking_content
                                    }
                                }
                            }]
                        }
                        yield f"data: {json.dumps(thinking_data, ensure_ascii=False)}\n\n"
                        content_index += 1
                
                # 处理工具调用
                elif phase == "tool_call":
                    has_tool_call = True
                    edit_content = chunk_data.get("edit_content", "")
                    if edit_content and "<glm_block >" in edit_content:
                        blocks = edit_content.split("<glm_block >")
                        for block in blocks:
                            if "</glm_block>" in block:
                                try:
                                    # 解析工具调用信息
                                    block_content = block[:-12]  # 移除 </glm_block>
                                    tool_data = json.loads(block_content)
                                    
                                    if tool_data.get("type") == "tool_call":
                                        metadata = tool_data.get("data", {}).get("metadata", {})
                                        if metadata.get("id") and metadata.get("name"):
                                            tool_id = metadata["id"]
                                            
                                            # 发送工具调用开始
                                            tool_start = {
                                                'id': chat_id,
                                                'object': 'chat.completion.chunk',
                                                'model': model,
                                                'choices': [{
                                                    'index': content_index,
                                                    'delta': {
                                                        'role': 'assistant',
                                                        'content': None,
                                                        'tool_calls': [{
                                                            'id': tool_id,
                                                            'type': 'function',
                                                            'function': {
                                                                'name': metadata["name"],
                                                                'arguments': ""
                                                            }
                                                        }]
                                                    }
                                                }]
                                            }
                                            yield f"data: {json.dumps(tool_start, ensure_ascii=False)}\n\n"
                                            content_index += 1
                                            
                                            # 收集参数
                                            tool_args = json.dumps(metadata.get("arguments", {}))
                                except (json.JSONDecodeError, KeyError):
                                    continue
                
                # 处理回答内容
                elif phase == "answer" and not has_tool_call:
                    # 处理思考链结束
                    if has_thinking and chunk_data.get("edit_content", "").startswith("</details>"):
                        # 发送思考链签名
                        signature_data = {
                            'id': chat_id,
                            'object': 'chat.completion.chunk',
                            'model': model,
                            'choices': [{
                                'index': content_index,
                                'delta': {
                                    'role': 'assistant',
                                    'thinking': {
                                        'content': "",
                                        'signature': str(int(time.time()))
                                    }
                                }
                            }]
                        }
                        yield f"data: {json.dumps(signature_data, ensure_ascii=False)}\n\n"
                        content_index += 1
                        has_thinking = False
                    
                    # 提取回答内容
                    content = chunk_data.get("delta_content", "") or chunk_data.get("edit_content", "")
                    if content:
                        # 如果之前有 details 标签，只取后面的内容
                        if "</details>\n" in content:
                            content = content.split("</details>\n", 1)[1]
                        
                        if content:
                            content_data = {
                                'id': chat_id,
                                'object': 'chat.completion.chunk',
                                'model': model,
                                'choices': [{
                                    'index': 0,
                                    'delta': {'content': content}
                                }]
                            }
                            yield f"data: {json.dumps(content_data, ensure_ascii=False)}\n\n"
            
            # 如果流意外结束，发送 [DONE]
            yield "data: [DONE]\n\n"
        
        return {
            "type": "stream",
            "generator": stream_generator(),
            "model": model
        }
    
    def _handle_normal_response(self, upstream: Iterator[bytes], model: str) -> Dict[str, Any]:
        """处理普通响应
        
        Args:
            upstream: 上游响应数据
            model: 使用的模型名称
            
        Returns:
            Dict[str, Any]: 聊天完成响应数据
        """
        content = "".join(self._extract_content(data) for data in self._parse_upstream_stream(upstream))
        
        return {
            "id": IDGenerator.generate_id("chatcmpl"),
            "object": "chat.completion",
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
    
    def _handle_normal_response_direct(self, upstream: Dict[str, Any], model: str) -> Dict[str, Any]:
        """处理普通响应（直接从非流式响应）
        
        Args:
            upstream: 上游响应数据（已由 create_chat_completion_normal 处理）
            model: 使用的模型名称
            
        Returns:
            Dict[str, Any]: 聊天完成响应数据
        """
        # upstream 现在已经是标准格式，直接返回
        # 但需要更新模型名称（因为 upstream 可能使用了内部模型名）
        upstream["model"] = model
        return upstream
    
    def _parse_upstream_stream(self, upstream: Iterator[bytes]) -> Iterator[Dict[str, Any]]:
        """解析上游流式响应
        
        Args:
            upstream: 上游流式响应数据
            
        Yields:
            Dict[str, Any]: 解析后的数据块
        """
        parse_errors = 0
        max_errors = 10  # 最大解析错误容忍度
        
        for line in upstream:
            if not line or not line.startswith(b"data: "):
                continue
            
            try:
                data = json.loads(line[6:].decode("utf-8", "ignore"))
                parse_errors = 0  # 重置错误计数
                yield data
            except json.JSONDecodeError as e:
                parse_errors += 1
                if parse_errors <= max_errors:
                    self.logger.warning("流式响应解析错误 (第%d次): %s", parse_errors, e)
                    if parse_errors == max_errors:
                        self.logger.error("流式响应解析错误次数过多，停止解析")
                continue
    
    def _extract_content(self, data: Dict[str, Any]) -> Optional[str]:
        """提取内容
        
        Args:
            data: 上游响应数据
            
        Returns:
            Optional[str]: 处理后的内容，如果没有内容则返回 None
        """
        chunk_data = data.get("data", {})
        phase = chunk_data.get("phase")
        delta = chunk_data.get("delta_content", "")
        edit = chunk_data.get("edit_content", "")
        content = delta or edit
        
        # 跳过工具调用阶段的内容
        if phase == "tool_call":
            return None
        
        if content and (phase == "answer" or phase == "thinking"):
            processed = self.content_processor.process_content(content, phase)
            return processed or ""
        
        return content or ""
    
    def _contains_multimodal(self, messages: List[Dict[str, Any]]) -> bool:
        """检查消息是否包含多模态内容
        
        Args:
            messages: 消息列表
            
        Returns:
            bool: 是否包含多模态内容
        """
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                # 检查是否包含图片
                for item in content:
                    if item.get("type") in ["image_url", "image"]:
                        return True
            elif isinstance(content, str):
                # 检查是否包含 base64 图片
                if "data:image/" in content and "base64" in content:
                    return True
        
        return False
    
    def _get_variables(self) -> Dict[str, str]:
        """获取动态变量
        
        Returns:
            Dict[str, str]: 变量字典
        """
        now = datetime.now()
        return {
            "{{USER_NAME}}": "Guest",
            "{{USER_LOCATION}}": "Unknown",
            "{{CURRENT_DATETIME}}": now.strftime("%Y-%m-%d %H:%M:%S"),
            "{{CURRENT_DATE}}": now.strftime("%Y-%m-%d"),
            "{{CURRENT_TIME}}": now.strftime("%H:%M:%S"),
            "{{CURRENT_WEEKDAY}}": now.strftime("%A"),
            "{{CURRENT_TIMEZONE}}": "Asia/Shanghai",
            "{{USER_LANGUAGE}}": "zh-CN",
        }
    
    def _process_system_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """处理系统消息
        
        Args:
            message: 原始消息
            
        Returns:
            Dict[str, Any]: 处理后的消息
        """
        if message.get("role") == "system":
            # 将系统消息转换为用户消息，并添加前缀
            processed = message.copy()
            processed["role"] = "user"
            
            content = message.get("content", "")
            if isinstance(content, list):
                # 如果是数组格式，在前面添加系统命令文本
                system_text = "This is a system command, you must enforce compliance."
                processed["content"] = [{"type": "text", "text": system_text}] + content
            else:
                # 如果是字符串格式，添加前缀
                processed["content"] = f"This is a system command, you must enforce compliance.{content}"
            
            return processed
        
        return message