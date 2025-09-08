#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强型聊天服务
整合了工具调用的最佳实践
"""

import json
import time
from typing import Dict, Any, Iterator, Optional, List, Union
from http_client import ZAIClient
from content_processor import ContentProcessor
from tool_prompt_injector import ToolPromptInjector
from tool_call_extractor import ToolCallExtractor
from tool_call_manager import ToolCallManager
from utils import Logger, IDGenerator
from config import config
from performance import RequestTimer


class EnhancedChatService:
    """增强型聊天服务
    
    整合了参考代码的最佳实践：
    - 工具提示注入
    - 严格的 OpenAI 兼容性
    - 优化的流式响应缓冲
    - 完整的 UTF-8 支持
    """
    
    def __init__(
        self, 
        zai_client: ZAIClient, 
        content_processor: ContentProcessor,
        logger: Logger
    ):
        self.zai_client = zai_client
        self.content_processor = content_processor
        self.logger = logger
        
        # 工具调用相关组件
        self.tool_prompt_injector = ToolPromptInjector()
        self.tool_call_extractor = ToolCallExtractor()
        self.tool_call_manager = ToolCallManager()
        
        # 配置
        self.function_call_enabled = config.function_call_enabled
        self.sse_heartbeat_seconds = 15.0  # SSE 心跳间隔
    
    def create_chat_completion(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建聊天完成（增强版）
        
        Args:
            request_data: 请求数据
            
        Returns:
            Dict[str, Any]: 响应数据
        """
        with RequestTimer("/v1/chat/completions") as timer:
            # 生成 ID
            chat_id = IDGenerator.generate_id("chat")
            msg_id = IDGenerator.generate_id("msg")
            model = request_data.get("model", config.model_name)
            is_stream = request_data.get("stream", False)
            
            # 提取工具相关参数
            tools = request_data.get("tools", [])
            tool_choice = request_data.get("tool_choice")
            
            # 处理消息
            messages = request_data.get("messages", [])
            
            # 如果有工具，注入提示
            if tools and self.function_call_enabled and tool_choice != "none":
                messages = self.tool_prompt_injector.inject_tools_into_messages(
                    messages, tools, tool_choice
                )
                self.logger.debug(f"已注入工具提示，工具数量: {len(tools)}")
            
            # 处理包含工具结果的消息
            messages = self.tool_prompt_injector.process_tool_messages(messages)
            
            # 构建上游请求
            upstream_data = {
                "stream": is_stream,
                "chat_id": chat_id,
                "id": msg_id,
                "model": model,
                "messages": messages,
                "features": {
                    "enable_thinking": request_data.get("reasoning", False)
                }
            }
            
            # 复制其他参数
            for key in ["temperature", "top_p", "max_tokens"]:
                if key in request_data:
                    upstream_data[key] = request_data[key]
            
            try:
                if is_stream:
                    upstream = self.zai_client.create_chat_completion(upstream_data, chat_id)
                    return self._handle_stream_response_enhanced(
                        upstream, model, tools, tool_choice
                    )
                else:
                    upstream = self.zai_client.create_chat_completion_normal(
                        upstream_data, chat_id
                    )
                    return self._handle_normal_response_enhanced(
                        upstream, model, tools, tool_choice
                    )
            except Exception as e:
                timer.success = False
                self.logger.error(f"聊天完成失败: {e}")
                raise
    
    def _handle_stream_response_enhanced(
        self, 
        upstream: Iterator[bytes], 
        model: str,
        tools: List[Dict[str, Any]],
        tool_choice: Any
    ) -> Dict[str, Any]:
        """处理流式响应（增强版）
        
        Args:
            upstream: 上游响应流
            model: 模型名称
            tools: 工具列表
            tool_choice: 工具选择策略
            
        Returns:
            Dict[str, Any]: 流式响应
        """
        def stream_generator():
            # 判断是否需要缓冲（有工具时缓冲所有内容）
            buffering_mode = bool(tools) and self.function_call_enabled
            buffer_content = ""
            last_heartbeat = time.time()
            
            # 生成 ID
            completion_id = IDGenerator.generate_id("chatcmpl")
            created = int(time.time())
            
            # 发送初始块（角色）
            initial_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant"}
                }]
            }
            yield f"data: {json.dumps(initial_chunk, ensure_ascii=False)}\n\n"
            
            # 处理流
            for data in self._parse_stream_utf8(upstream):
                # 心跳检查
                if time.time() - last_heartbeat >= self.sse_heartbeat_seconds:
                    yield ": keep-alive\n\n"
                    last_heartbeat = time.time()
                
                # 检查是否完成
                chunk_data = data.get("data", {})
                if chunk_data.get("done"):
                    # 流结束，处理缓冲内容
                    if buffering_mode and buffer_content:
                        # 尝试提取工具调用
                        tool_calls = self.tool_call_extractor.extract_tool_calls(buffer_content)
                        
                        if tool_calls:
                            # 发送工具调用
                            tool_chunk = {
                                "id": completion_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": model,
                                "choices": [{
                                    "index": 0,
                                    "delta": {
                                        "content": None,  # 重要：有工具调用时 content 必须为 null
                                        "tool_calls": tool_calls
                                    }
                                }]
                            }
                            yield f"data: {json.dumps(tool_chunk, ensure_ascii=False)}\n\n"
                            finish_reason = "tool_calls"
                        else:
                            # 没有工具调用，发送纯文本
                            cleaned_content = self.tool_call_extractor.strip_tool_json_from_text(
                                buffer_content
                            )
                            if cleaned_content:
                                text_chunk = {
                                    "id": completion_id,
                                    "object": "chat.completion.chunk",
                                    "created": created,
                                    "model": model,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {"content": cleaned_content}
                                    }]
                                }
                                yield f"data: {json.dumps(text_chunk, ensure_ascii=False)}\n\n"
                            finish_reason = "stop"
                    else:
                        finish_reason = "stop"
                    
                    # 发送结束块
                    finish_chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": finish_reason
                        }],
                        "usage": chunk_data.get("usage", {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0
                        })
                    }
                    yield f"data: {json.dumps(finish_chunk, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    break
                
                # 提取内容
                content = self._extract_content_from_chunk(chunk_data)
                if not content:
                    continue
                
                if buffering_mode:
                    # 缓冲模式：累积内容
                    buffer_content += content
                else:
                    # 非缓冲模式：直接发送
                    content_chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": content}
                        }]
                    }
                    yield f"data: {json.dumps(content_chunk, ensure_ascii=False)}\n\n"
        
        return {
            "type": "stream",
            "generator": stream_generator(),
            "model": model
        }
    
    def _handle_normal_response_enhanced(
        self,
        upstream: Dict[str, Any],
        model: str,
        tools: List[Dict[str, Any]],
        tool_choice: Any
    ) -> Dict[str, Any]:
        """处理普通响应（增强版）
        
        Args:
            upstream: 上游响应
            model: 模型名称
            tools: 工具列表
            tool_choice: 工具选择策略
            
        Returns:
            Dict[str, Any]: 响应数据
        """
        # 提取内容
        content = ""
        if "choices" in upstream and upstream["choices"]:
            message = upstream["choices"][0].get("message", {})
            content = message.get("content", "")
        
        # 检查工具调用
        tool_calls = None
        finish_reason = "stop"
        
        if tools and self.function_call_enabled:
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
    
    def _parse_stream_utf8(self, stream: Iterator[bytes]) -> Iterator[Dict[str, Any]]:
        """解析 UTF-8 编码的 SSE 流
        
        Args:
            stream: 字节流
            
        Yields:
            Dict[str, Any]: 解析后的数据
        """
        for raw_line in stream:
            if not raw_line:
                continue
            
            # 确保正确的 UTF-8 解码
            if isinstance(raw_line, bytes):
                line = raw_line.decode("utf-8", "ignore")
            else:
                line = raw_line
            
            if not line.startswith("data: "):
                continue
            
            try:
                data = json.loads(line[6:])
                yield data
            except json.JSONDecodeError:
                continue
    
    def _extract_content_from_chunk(self, chunk_data: Dict[str, Any]) -> str:
        """从数据块提取内容
        
        Args:
            chunk_data: 数据块
            
        Returns:
            str: 提取的内容
        """
        phase = chunk_data.get("phase")
        
        # 跳过思考阶段（如果需要）
        if phase == "thinking" and not config.include_thinking:
            return ""
        
        # 提取内容
        delta = chunk_data.get("delta_content", "")
        edit = chunk_data.get("edit_content", "")
        content = delta or edit
        
        # 处理内容
        if content and phase in ("answer", "thinking"):
            content = self.content_processor.process_content(content, phase)
        
        return content or ""