# -*- coding: utf-8 -*-
"""
Anthropic API 兼容层
提供与 Anthropic Messages API 完全兼容的接口
"""

import json
import time
import uuid
from typing import Dict, Any, List, Optional, Union, Iterator

from flask import request, jsonify, Response, stream_with_context
from werkzeug.exceptions import Unauthorized, BadRequest, InternalServerError

from type_definitions import (
    AnthropicRequest, AnthropicResponse, AnthropicMessage,
    AnthropicContentBlock, AnthropicMessageStartEvent,
    AnthropicContentBlockStartEvent, AnthropicContentBlockDeltaEvent,
    AnthropicMessageDeltaEvent, AnthropicMessageStopEvent,
    Message, UpstreamRequest
)
from services import ChatService
from content_processor import ContentProcessor
from multimodal_processor import MultimodalProcessor
from utils import Logger, ResponseHelper, IDGenerator
from config import config


class AnthropicAPIHandler:
    """Anthropic API 处理器
    
    处理 Anthropic Messages API 格式的请求和响应。
    遵循单一职责原则，专门处理 Anthropic API 格式转换。
    """
    
    def __init__(self, chat_service: ChatService, content_processor: ContentProcessor):
        """初始化处理器
        
        Args:
            chat_service: 聊天服务实例
            content_processor: 内容处理器实例
        """
        self.chat_service = chat_service
        self.content_processor = content_processor
        self.multimodal_processor = MultimodalProcessor(Logger("multimodal"))
        self.logger = Logger("anthropic_api")
    
    def handle_messages(self) -> Response:
        """处理 /v1/messages 请求
        
        Returns:
            Response: Flask 响应对象
        """
        try:
            # 验证 API 密钥
            self._validate_api_key()
            
            # 解析请求
            anthropic_request = self._parse_request()
            
            # 转换为内部格式
            upstream_request = self._convert_to_upstream(anthropic_request)
            
            # 处理请求
            if anthropic_request.get("stream", False):
                return self._handle_streaming(upstream_request, anthropic_request)
            else:
                return self._handle_non_streaming(upstream_request, anthropic_request)
                
        except Unauthorized as e:
            return jsonify({"error": {"type": "authentication_error", "message": str(e)}}), 401
        except BadRequest as e:
            return jsonify({"error": {"type": "invalid_request_error", "message": str(e)}}), 400
        except Exception as e:
            self.logger.error(f"处理 Anthropic 请求时发生错误: {e}")
            return jsonify({"error": {"type": "internal_error", "message": "Internal server error"}}), 500
    
    def _validate_api_key(self) -> None:
        """验证 API 密钥
        
        Raises:
            Unauthorized: 当 API 密钥无效时
        """
        # 从请求头获取 API 密钥
        api_key = None
        x_api_key = request.headers.get("x-api-key")
        authorization = request.headers.get("authorization")
        
        if x_api_key:
            api_key = x_api_key
        elif authorization and authorization.startswith("Bearer "):
            api_key = authorization[7:]
        
        # 验证 API 密钥
        if config.anthropic_api_key and api_key != config.anthropic_api_key:
            raise Unauthorized("Invalid API key")
    
    def _parse_request(self) -> AnthropicRequest:
        """解析请求体
        
        Returns:
            AnthropicRequest: 解析后的请求对象
            
        Raises:
            BadRequest: 当请求格式无效时
        """
        try:
            data = request.get_json()
            if not data:
                raise BadRequest("Missing request body")
            
            # 验证必需字段
            required_fields = ["model", "messages", "max_tokens"]
            for field in required_fields:
                if field not in data:
                    raise BadRequest(f"Missing required field: {field}")
            
            # 设置默认值
            data.setdefault("stream", False)
            data.setdefault("temperature", None)
            
            return data
            
        except Exception as e:
            raise BadRequest(f"Invalid request format: {e}")
    
    def _convert_to_upstream(self, anthropic_request: AnthropicRequest) -> UpstreamRequest:
        """将 Anthropic 请求转换为上游请求格式
        
        Args:
            anthropic_request: Anthropic 请求对象
            
        Returns:
            UpstreamRequest: 转换后的上游请求
        """
        # 生成 ID
        chat_id, msg_id = IDGenerator.generate_id("chat"), IDGenerator.generate_id("msg")
        
        # 映射模型
        requested_model = anthropic_request["model"]
        model = config.anthropic_model_mapping.get(
            requested_model,
            config.model_name
        )
        
        # 调试日志
        self.logger.debug(f"Anthropic 模型映射: {requested_model} -> {model}")
        
        # 转换消息
        messages: List[Message] = []
        
        # 处理 system 消息
        if anthropic_request.get("system"):
            system_content = anthropic_request["system"]
            if isinstance(system_content, list):
                # 处理内容块数组
                system_text = ""
                for block in system_content:
                    if block.get("type") == "text":
                        system_text += block.get("text", "")
                system_content = system_text
            
            messages.append({
                "role": "system",
                "content": system_content
            })
        
        # 转换用户和助手消息
        messages = self.multimodal_processor.process_anthropic_messages(anthropic_request["messages"])
        
        # 构建上游请求
        upstream_request: UpstreamRequest = {
            "stream": True,  # 总是使用流式以获得更好的性能
            "chat_id": chat_id,
            "id": msg_id,
            "model": model,
            "messages": messages,
            "features": {
                "enable_thinking": True
            }
        }
        
        return upstream_request
    
    def _handle_streaming(self, upstream_request: UpstreamRequest, 
                         anthropic_request: AnthropicRequest) -> Response:
        """处理流式请求
        
        Args:
            upstream_request: 上游请求
            anthropic_request: Anthropic 请求
            
        Returns:
            Response: 流式响应
        """
        def generate() -> Iterator[str]:
            """生成流式响应"""
            request_id = f"msg_{uuid.uuid4().hex}"
            usage = {"input_tokens": 0, "output_tokens": 0}
            
            try:
                # 发送 message_start 事件
                message_start: AnthropicMessageStartEvent = {
                    "type": "message_start",
                    "message": {
                        "id": request_id,
                        "type": "message",
                        "role": "assistant",
                        "content": [],
                        "model": anthropic_request["model"],
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": usage
                    }
                }
                yield f"event: {message_start['type']}\ndata: {json.dumps(message_start['message'])}\n\n"
                
                # 发送 content_block_start 事件
                content_start: AnthropicContentBlockStartEvent = {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {
                        "type": "text",
                        "text": ""
                    }
                }
                yield f"event: {content_start['type']}\ndata: {json.dumps(content_start)}\n\n"
                
                # 处理上游流式响应
                result = self.chat_service.create_chat_completion(upstream_request)
                
                for chunk in result["generator"]:
                    try:
                        # chunk 是 SSE 格式: "data: {json}"
                        if chunk.startswith("data: "):
                            data_str = chunk[6:]  # 移除 "data: " 前缀
                            if data_str == "[DONE]":
                                break
                            
                            data = json.loads(data_str)
                            
                            # 从标准 OpenAI 格式中提取内容
                            delta_content = ""
                            if "choices" in data and data["choices"]:
                                choice = data["choices"][0]
                                if "delta" in choice:
                                    delta = choice["delta"]
                                    # 内容可能在 content 或 role 字段中
                                    if "content" in delta:
                                        delta_content = delta["content"]
                                    elif "role" in delta and delta["role"] == "assistant":
                                        # 跳过角色消息
                                        continue
                            
                            if delta_content:
                                # 处理思考链内容（检查是否包含思考标签）
                                if "<think>" in delta_content or "</think>" in delta_content:
                                    processed_content = self.content_processor.process_content(delta_content, "thinking")
                                else:
                                    processed_content = delta_content
                                
                                if processed_content:
                                    usage["output_tokens"] += len(processed_content) // 4
                                    
                                    # 发送 content_block_delta 事件
                                    content_delta: AnthropicContentBlockDeltaEvent = {
                                        "type": "content_block_delta",
                                        "index": 0,
                                        "delta": {
                                            "type": "text_delta",
                                            "text": processed_content
                                        }
                                    }
                                    yield f"event: {content_delta['type']}\ndata: {json.dumps(content_delta)}\n\n"
                    
                    except (json.JSONDecodeError, KeyError, UnicodeDecodeError):
                        continue
                
                # 发送结束事件
                content_stop: AnthropicMessageStopEvent = {
                    "type": "content_block_stop",
                    "index": 0
                }
                yield f"event: {content_stop['type']}\ndata: {json.dumps(content_stop)}\n\n"
                
                message_delta: AnthropicMessageDeltaEvent = {
                    "type": "message_delta",
                    "delta": {
                        "stop_reason": "end_turn",
                        "stop_sequence": None,
                        "usage": {
                            "input_tokens": usage["input_tokens"],
                            "output_tokens": usage["output_tokens"]
                        }
                    }
                }
                yield f"event: {message_delta['type']}\ndata: {json.dumps(message_delta)}\n\n"
                
                message_stop: AnthropicMessageStopEvent = {
                    "type": "message_stop"
                }
                yield f"event: {message_stop['type']}\ndata: {json.dumps(message_stop)}\n\n"
                
            except Exception as e:
                self.logger.error(f"流式响应生成错误: {e}")
                # 发送错误事件
                error_data = {
                    "type": "error",
                    "error": {
                        "type": "internal_error",
                        "message": "Stream processing error"
                    }
                }
                yield f"event: {error_data['type']}\ndata: {json.dumps(error_data)}\n\n"
        
        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, x-api-key"
            }
        )
    
    def _handle_non_streaming(self, upstream_request: UpstreamRequest,
                             anthropic_request: AnthropicRequest) -> Response:
        """处理非流式请求
        
        Args:
            upstream_request: 上游请求
            anthropic_request: Anthropic 请求
            
        Returns:
            Response: 非流式响应
        """
        try:
            # 获取完整响应
            self.logger.debug(f"开始处理非流式请求，上游请求: {upstream_request}")
            result = self.chat_service.create_chat_completion(upstream_request)
            self.logger.debug(f"获取到上游响应结果: {type(result)}")
            
            # 收集所有内容
            full_content = ""
            chunk_count = 0
            empty_chunks = 0
            generator = result["generator"]
            self.logger.debug(f"开始处理生成器，类型: {type(generator)}")
            
            for chunk in generator:
                chunk_count += 1
                try:
                    # chunk 是 SSE 格式: "data: {json}"
                    if not chunk or not isinstance(chunk, str):
                        self.logger.warning(f"Invalid chunk {chunk_count}: {type(chunk)}, content: {repr(chunk)}")
                        continue
                        
                    if not chunk.startswith("data: "):
                        self.logger.debug(f"Chunk {chunk_count} not starting with 'data: ': {repr(chunk[:100])}")
                        continue
                    
                    data_str = chunk[6:]  # 移除 "data: " 前缀
                    if data_str == "[DONE]":
                        self.logger.debug(f"Stream completed after {chunk_count} chunks")
                        break
                    
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Chunk {chunk_count} JSON decode error: {e}, data: {repr(data_str[:200])}")
                        continue
                    
                    self.logger.debug(f"Chunk {chunk_count}: {data}")
                    
                    # 从标准 OpenAI 格式中提取内容
                    delta_content = ""
                    if "choices" in data and data["choices"]:
                        choice = data["choices"][0]
                        if "delta" in choice:
                            delta = choice["delta"]
                            # 内容可能在 content 或 role 字段中
                            if "content" in delta:
                                delta_content = delta["content"]
                            elif "role" in delta and delta["role"] == "assistant":
                                # 跳过角色消息
                                self.logger.debug(f"Chunk {chunk_count}: Skipping role message")
                                continue
                            else:
                                self.logger.debug(f"Chunk {chunk_count}: Delta has no content: {delta}")
                        else:
                            self.logger.debug(f"Chunk {chunk_count}: Choice has no delta: {choice}")
                    else:
                        self.logger.debug(f"Chunk {chunk_count}: No choices in data: {list(data.keys())}")
                    
                    self.logger.debug(f"Chunk {chunk_count}: Delta content: {repr(delta_content)}")
                    
                    if delta_content:
                        # 处理思考链内容（检查是否包含思考标签）
                        if "</think>" in delta_content or "</think>" in delta_content:
                            try:
                                processed_content = self.content_processor.process_content(delta_content, "thinking")
                                self.logger.debug(f"Chunk {chunk_count}: Processed thinking content: {repr(processed_content)}")
                            except Exception as e:
                                self.logger.error(f"Chunk {chunk_count}: Content processing error: {e}")
                                processed_content = delta_content  # 使用原始内容作为后备
                        else:
                            processed_content = delta_content
                            self.logger.debug(f"Chunk {chunk_count}: Raw content: {repr(processed_content)}")
                        
                        if processed_content:
                            full_content += processed_content
                            self.logger.debug(f"Chunk {chunk_count}: Added content, total length: {len(full_content)}")
                        else:
                            self.logger.debug(f"Chunk {chunk_count}: No content after processing")
                    else:
                        empty_chunks += 1
                        self.logger.debug(f"Chunk {chunk_count}: No delta content (empty chunks: {empty_chunks})")
                    
                except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as e:
                    self.logger.error(f"Chunk {chunk_count} parsing error: {type(e).__name__}: {e}")
                    self.logger.debug(f"Chunk {chunk_count} raw content: {repr(chunk[:500])}")
                    continue
                except Exception as e:
                    self.logger.error(f"Chunk {chunk_count} unexpected error: {type(e).__name__}: {e}")
                    continue
            
            self.logger.info(f"Stream processing completed:")
            self.logger.info(f"  - Total chunks processed: {chunk_count}")
            self.logger.info(f"  - Empty chunks: {empty_chunks}")
            self.logger.info(f"  - Final content length: {len(full_content)}")
            self.logger.info(f"  - Final content preview: {repr(full_content[:200])}")
            
            if not full_content:
                self.logger.warning("No content collected from stream")
                # 返回错误响应
                return jsonify({
                    "id": f"msg_{uuid.uuid4().hex}",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "text", "text": "抱歉，处理请求时出现错误，请稍后重试。"}],
                    "model": anthropic_request["model"],
                    "stop_reason": "error",
                    "usage": {"input_tokens": 0, "output_tokens": 0}
                })
            
            # 构建响应
            response: AnthropicResponse = {
                "id": f"msg_{uuid.uuid4().hex}",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": full_content}],
                "model": anthropic_request["model"],
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": len(str(anthropic_request.get("messages", []))) // 4,
                    "output_tokens": len(full_content) // 4
                }
            }
            
            return jsonify(response)
            
        except Exception as e:
            import traceback
            self.logger.error(f"非流式响应处理错误: {e}")
            self.logger.error(f"错误详情: {traceback.format_exc()}")
            raise InternalServerError(f"Failed to process request: {str(e)}")