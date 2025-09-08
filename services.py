# -*- coding: utf-8 -*-
"""
业务逻辑模块
处理核心的业务逻辑
"""

import json
import time
import re
import uuid
from datetime import datetime
from typing import Dict, Any, Iterator, Optional, List
from http_client import ZAIClient, HttpClientError
from content_processor import ContentProcessor, ThinkTagsMode
from multimodal_processor import MultimodalProcessor
from utils import Logger, IDGenerator, ModelFormatter
from config import config
from cache import get_cache
from performance import get_monitor, RequestTimer
from tool_call_manager import ToolCallManager
from tool_call_error_handler import ToolCallErrorHandler, ToolCallParseError
from tool_prompt_injector import ToolPromptInjector
from tool_call_extractor import ToolCallExtractor


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
        self.tool_call_manager = ToolCallManager()
        self.tool_call_error_handler = ToolCallErrorHandler()
        self.tool_prompt_injector = ToolPromptInjector()
        self.tool_call_extractor = ToolCallExtractor(config.max_json_scan)
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
            
            # 提取工具相关参数
            tools = request_data.get("tools", [])
            tool_choice = request_data.get("tool_choice")
            has_tools = bool(tools)
            
            # 处理多模态消息
            original_messages = request_data.get("messages", [])
            
            # 如果有工具，注入提示（在处理系统消息之前）
            if tools and config.function_call_enabled and tool_choice != "none":
                messages_with_tools = self.tool_prompt_injector.inject_tools_into_messages(
                    original_messages, tools, tool_choice
                )
                self.logger.debug(f"已注入工具提示，工具数量: {len(tools)}")
            else:
                messages_with_tools = original_messages
            
            # 处理包含工具结果的消息
            messages_with_tools = self.tool_prompt_injector.process_tool_messages(messages_with_tools)
            
            # 处理系统消息
            processed_messages = []
            for msg in messages_with_tools:
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
                # 注意：因为已经在消息中注入了工具提示，这里不再传递tools给上游
                # "tools": request_data.get("tools") if not request_data.get("reasoning", False) else None,
            }
            
            if config.debug_mode:
                self.logger.debug("上游请求: %s", json.dumps(upstream_data, ensure_ascii=False))
                if has_tools:
                    self.logger.debug("工具调用已启用（通过提示注入），工具数量: %d", len(tools))
                    for i, tool in enumerate(tools):
                        self.logger.debug("工具 %d: %s", i + 1, tool.get("function", {}).get("name", "未知"))
                else:
                    self.logger.debug("工具调用未启用")
            
            try:
                if is_stream:
                    # 流式请求使用流式 API
                    upstream = self.zai_client.create_chat_completion(upstream_data, chat_id)
                    return self._handle_stream_response_enhanced(upstream, model, tools, tool_choice)
                else:
                    # 非流式请求使用普通 API，避免等待流式响应完成
                    # 如果是多模态请求，使用更长的超时时间
                    timeout = config.multimodal_timeout if has_multimodal else config.non_stream_timeout
                    upstream = self.zai_client.create_chat_completion_normal(
                        upstream_data, 
                        chat_id, 
                        timeout=timeout
                    )
                    return self._handle_normal_response_enhanced(upstream, model, tools, tool_choice)
            
            except HttpClientError as e:
                timer.success = False
                self.logger.error("上游 API 调用失败: %s, 请求ID: %s, 模型: %s", e, chat_id, model)
                raise Exception(f"上游调用失败: {e} (请求ID: {chat_id})")
            except Exception as e:
                timer.success = False
                self.logger.error("聊天完成处理失败: %s, 请求ID: %s, 模型: %s", e, chat_id, model)
                raise Exception(f"内部处理错误: {e} (请求ID: {chat_id})")
            finally:
                # 如果有工具调用，记录统计
                if has_tools and hasattr(self, 'tool_call_manager'):
                    monitor = get_monitor()
                    tool_call_count = len(self.tool_call_manager.active_calls)
                    if tool_call_count > 0:
                        # 获取工具调用的平均 token 使用量
                        total_tokens = sum(
                            call.get("usage", {}).get("total_tokens", 0) 
                            for call in self.tool_call_manager.active_calls.values()
                        )
                        monitor.metrics.increment_tool_calls(total_tokens // tool_call_count if tool_call_count > 0 else 0)
    
    def _handle_stream_response_enhanced(self, upstream: Iterator[bytes], model: str, 
                                        tools: List[Dict[str, Any]], tool_choice: Any) -> Dict[str, Any]:
        """处理流式响应（增强版）
        
        Args:
            upstream: 上游流式响应数据
            model: 使用的模型名称
            tools: 工具列表
            tool_choice: 工具选择策略
            
        Returns:
            Dict[str, Any]: 流式响应结果
        """
        def stream_generator():
            # 判断是否需要缓冲（有工具时缓冲所有内容）
            buffering_mode = bool(tools) and config.function_call_enabled
            buffer_content = ""
            last_heartbeat = time.time()
            
            chat_id = IDGenerator.generate_id('chatcmpl')
            created_ts = int(time.time())
            content_index = 0
            has_thinking = False
            
            # 重置工具调用管理器
            self.tool_call_manager.reset_state()
            
            # 发送开始消息
            start_data = {
                'id': chat_id,
                'object': 'chat.completion.chunk',
                'created': created_ts,
                'model': model,
                'choices': [{'index': 0, 'delta': {'role': 'assistant'}}]
            }
            yield f"data: {json.dumps(start_data, ensure_ascii=False)}\n\n"
            
            # 处理流式内容
            for data in self._parse_upstream_stream(upstream):
                # 心跳检查
                if time.time() - last_heartbeat >= config.sse_heartbeat_seconds:
                    yield ": keep-alive\n\n"
                    last_heartbeat = time.time()
                
                chunk_data = data.get("data", {})
                
                # 检查是否完成
                if chunk_data.get("done"):
                    # 流结束，处理缓冲内容
                    if buffering_mode and buffer_content:
                        # 尝试提取工具调用
                        tool_calls = self.tool_call_extractor.extract_tool_calls(buffer_content)
                        
                        if tool_calls:
                            # 发送工具调用
                            tool_chunk = {
                                'id': chat_id,
                                'object': 'chat.completion.chunk',
                                'created': created_ts,
                                'model': model,
                                'choices': [{
                                    'index': 0,
                                    'delta': {
                                        'content': None,  # 重要：有工具调用时 content 必须为 null
                                        'tool_calls': tool_calls
                                    }
                                }]
                            }
                            yield f"data: {json.dumps(tool_chunk, ensure_ascii=False)}\n\n"
                            finish_reason = "tool_calls"
                        else:
                            # 没有工具调用，发送纯文本
                            cleaned_content = self.tool_call_extractor.strip_tool_json_from_text(buffer_content)
                            if cleaned_content:
                                text_chunk = {
                                    'id': chat_id,
                                    'object': 'chat.completion.chunk',
                                    'created': created_ts,
                                    'model': model,
                                    'choices': [{
                                        'index': 0,
                                        'delta': {'content': cleaned_content}
                                    }]
                                }
                                yield f"data: {json.dumps(text_chunk, ensure_ascii=False)}\n\n"
                            finish_reason = "stop"
                    else:
                        finish_reason = "stop"
                    
                    # 发送结束块
                    finish_data = {
                        'id': chat_id,
                        'object': 'chat.completion.chunk',
                        'created': created_ts,
                        'model': model,
                        'choices': [{
                            'index': 0,
                            'delta': {},
                            'finish_reason': finish_reason
                        }],
                        'usage': chunk_data.get("usage", {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0
                        })
                    }
                    yield f"data: {json.dumps(finish_data, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    break
                
                # 提取内容
                content = self._extract_content(data)
                if not content:
                    continue
                
                if buffering_mode:
                    # 缓冲模式：累积内容
                    buffer_content += content
                else:
                    # 非缓冲模式：直接发送
                    # 处理思考链
                    phase = chunk_data.get("phase")
                    if phase == "thinking":
                        has_thinking = True
                        if not config.include_thinking:
                            continue  # 跳过思考内容
                        
                        thinking_data = {
                            'id': chat_id,
                            'object': 'chat.completion.chunk',
                            'created': created_ts,
                            'model': model,
                            'choices': [{
                                'index': content_index,
                                'delta': {
                                    'role': 'assistant',
                                    'thinking': {'content': content}
                                }
                            }]
                        }
                        yield f"data: {json.dumps(thinking_data, ensure_ascii=False)}\n\n"
                        content_index += 1
                    else:
                        # 普通内容
                        content_chunk = {
                            'id': chat_id,
                            'object': 'chat.completion.chunk',
                            'created': created_ts,
                            'model': model,
                            'choices': [{
                                'index': 0,
                                'delta': {'content': content}
                            }]
                        }
                        yield f"data: {json.dumps(content_chunk, ensure_ascii=False)}\n\n"
            
            # 如果流意外结束，发送 [DONE]
            yield "data: [DONE]\n\n"
        
        return {
            "type": "stream",
            "generator": stream_generator(),
            "model": model
        }
    
    def _handle_normal_response_enhanced(self, upstream: Dict[str, Any], model: str,
                                        tools: List[Dict[str, Any]], tool_choice: Any) -> Dict[str, Any]:
        """处理普通响应（增强版）
        
        Args:
            upstream: 上游响应数据
            model: 使用的模型名称
            tools: 工具列表
            tool_choice: 工具选择策略
            
        Returns:
            Dict[str, Any]: 聊天完成响应数据
        """
        # 提取内容
        content = ""
        if "choices" in upstream and upstream["choices"]:
            message = upstream["choices"][0].get("message", {})
            content = message.get("content", "")
        
        # 检查工具调用
        tool_calls = None
        finish_reason = "stop"
        
        if tools and config.function_call_enabled:
            tool_calls = self.tool_call_extractor.extract_tool_calls(content)
            if tool_calls:
                # 清理内容中的工具调用 JSON
                content = self.tool_call_extractor.strip_tool_json_from_text(content)
                finish_reason = "tool_calls"
        
        # 构建响应（严格遵循 OpenAI 格式）
        message_obj = {
            "role": "assistant",
            "content": None if tool_calls else (content or "")  # 有工具调用时 content 必须为 null
        }
        
        if tool_calls:
            message_obj["tool_calls"] = tool_calls
        
        response = {
            "id": IDGenerator.generate_id("chatcmpl"),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": message_obj,
                "finish_reason": finish_reason
            }],
            "usage": upstream.get("usage", {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            })
        }
        
        return response
    
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
            
            # 重置工具调用管理器
            self.tool_call_manager.reset_state()
            
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
                    # 优先从上游响应获取实际的完成原因
                    finish_reason = chunk_data.get("finish_reason")
                    if self.tool_call_manager.has_active_calls() and not finish_reason:
                        finish_reason = "tool_calls"
                    elif not finish_reason:
                        finish_reason = "stop"
                    
                    finish_data = {
                        'id': chat_id,
                        'object': 'chat.completion.chunk',
                        'model': model,
                        'choices': [{'index': 0, 'delta': {}, 'finish_reason': finish_reason}],
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
                    edit_content = chunk_data.get("edit_content", "")
                    if edit_content and "<glm_block >" in edit_content:
                        blocks = edit_content.split("<glm_block >")
                        for block_idx, block in enumerate(blocks):
                            if "</glm_block>" in block:
                                try:
                                    # 解析工具调用信息
                                    block_content = block[:-12]  # 移除 </glm_block>
                                    
                                    # 使用错误处理器安全解析
                                    tool_data = self.tool_call_error_handler.safe_parse_tool_call(
                                        block_content, 
                                        {"chat_id": chat_id, "model": model}
                                    )
                                    
                                    if not tool_data:
                                        # 解析失败，跳过这个块
                                        continue
                                        
                                    # 验证工具调用数据
                                    if not self.tool_call_error_handler.validate_tool_call(tool_data):
                                        self.logger.warning(f"无效的工具调用数据: {tool_data}")
                                        continue
                                    
                                    if tool_data.get("type") == "tool_call":
                                        metadata = tool_data.get("data", {}).get("metadata", {})
                                        if metadata.get("id") and metadata.get("name"):
                                            # 生成唯一的工具调用ID以确保符合API规范
                                            tool_id = f"call_{uuid.uuid4().hex[:12]}"
                                            
                                            # 使用工具调用管理器开始工具调用
                                            tool_call = self.tool_call_manager.start_tool_call(
                                                tool_id, metadata["name"], block_idx
                                            )
                                            
                                            # 发送工具调用开始
                                            tool_start = {
                                                'id': chat_id,
                                                'object': 'chat.completion.chunk',
                                                'model': model,
                                                'choices': [{
                                                    'index': 0,  # 使用固定索引
                                                    'delta': {
                                                        'role': 'assistant',
                                                        'content': None,
                                                        'tool_calls': [tool_call]
                                                    }
                                                }]
                                            }
                                            yield f"data: {json.dumps(tool_start, ensure_ascii=False)}\n\n"
                                            
                                            # 收集参数并分块发送
                                            tool_args = json.dumps(metadata.get("arguments", {}))
                                            if tool_args:
                                                chunk_size = 100
                                                for i in range(0, len(tool_args), chunk_size):
                                                    chunk = tool_args[i:i+chunk_size]
                                                    
                                                    # 使用工具调用管理器追加参数
                                                    arg_deltas = self.tool_call_manager.append_arguments(tool_id, chunk)
                                                    
                                                    if arg_deltas:
                                                        for arg_delta in arg_deltas:
                                                            tool_args_data = {
                                                                'id': chat_id,
                                                                'object': 'chat.completion.chunk',
                                                                'model': model,
                                                                'choices': [{
                                                                    'index': 0,
                                                                    'delta': {
                                                                        'role': 'assistant',
                                                                        'content': None,
                                                                        'tool_calls': [arg_delta]
                                                                    }
                                                                }]
                                                            }
                                                            yield f"data: {json.dumps(tool_args_data, ensure_ascii=False)}\n\n"
                                except ToolCallParseError as e:
                                    # 处理解析错误
                                    for error_event in self.tool_call_error_handler.handle_parse_error(
                                        e, {"chat_id": chat_id, "model": model}
                                    ):
                                        yield error_event
                                except Exception as e:
                                    # 处理其他错误
                                    for error_event in self.tool_call_error_handler.handle_unknown_error(
                                        e, {"chat_id": chat_id, "model": model}
                                    ):
                                        yield error_event
                
                # 处理工具调用结束和其他阶段
                elif phase == "other":
                    if self.tool_call_manager.has_active_calls():
                        # 处理工具调用结束
                        edit_content = chunk_data.get("edit_content", "")
                        if edit_content and edit_content.startswith("null,"):
                            # 获取工具调用使用情况
                            tool_call_usage = chunk_data.get("usage")
                            
                            # 完成所有活跃的工具调用
                            for tool_id in list(self.tool_call_manager.active_calls.keys()):
                                if not self.tool_call_manager.active_calls[tool_id]["completed"]:
                                    # 完成工具调用
                                    complete_delta = self.tool_call_manager.complete_tool_call(tool_id, tool_call_usage)
                                    
                                    if complete_delta:
                                        # 发送工具调用完成事件
                                        finish_res = {
                                            'id': chat_id,
                                            'object': 'chat.completion.chunk',
                                            'model': model,
                                            'choices': [{
                                                'index': 0,
                                                'delta': {
                                                    'role': 'assistant',
                                                    'content': None,
                                                    'tool_calls': [complete_delta]
                                                },
                                                'finish_reason': 'tool_calls'
                                            }]
                                        }
                                        
                                        # 添加使用情况信息
                                        if tool_call_usage:
                                            finish_res['usage'] = tool_call_usage
                                        
                                        yield f"data: {json.dumps(finish_res, ensure_ascii=False)}\n\n"
                            
                            # 发送流结束标记
                            yield "data: [DONE]\n\n"
                            
                            # 结束流处理
                            return
                
                # 处理回答内容
                elif phase == "answer":
                    # 如果有活跃的工具调用，跳过处理
                    if self.tool_call_manager.has_active_calls():
                        continue
                        
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