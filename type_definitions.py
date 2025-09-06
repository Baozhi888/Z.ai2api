# -*- coding: utf-8 -*-
"""
类型定义模块
定义项目中使用的所有类型
"""

from typing import Dict, Any, List, Optional, Iterator, Union, TypedDict
from enum import Enum


class ThinkTagsMode(Enum):
    """思考链处理模式枚举
    
    定义不同的思考链处理模式：
    - THINK: 标准思考模式
    - PURE: 纯内容模式
    - RAW: 原始模式
    """
    THINK = "think"
    PURE = "pure"
    RAW = "raw"


class ModelInfo(TypedDict):
    """模型信息
    
    符合 OpenAI API 格式的模型信息。
    """
    id: str
    object: str
    name: str
    created: int
    owned_by: str


class ModelListResponse(TypedDict):
    """模型列表响应
    
    符合 OpenAI API 格式的模型列表响应。
    """
    object: str
    data: List[ModelInfo]


class Message(TypedDict):
    """消息
    
    聊天消息格式。
    """
    role: str
    content: str


class ChatCompletionRequest(TypedDict):
    """聊天完成请求
    
    符合 OpenAI API 格式的聊天完成请求。
    """
    model: str
    messages: List[Message]
    stream: bool
    temperature: Optional[float]
    max_tokens: Optional[int]
    top_p: Optional[float]


class ChatCompletionChoice(TypedDict):
    """聊天完成选择
    
    聊天完成的选择项。
    """
    index: int
    message: Message
    finish_reason: str


class ChatCompletionDelta(TypedDict):
    """聊天完成增量
    
    流式响应的增量数据。
    """
    role: Optional[str]
    content: Optional[str]


class ChatCompletionChunkChoice(TypedDict):
    """聊天完成块选择
    
    流式响应的选择项。
    """
    index: int
    delta: ChatCompletionDelta


class ChatCompletionResponse(TypedDict):
    """聊天完成响应
    
    符合 OpenAI API 格式的聊天完成响应。
    """
    id: str
    object: str
    model: str
    choices: List[ChatCompletionChoice]
    usage: Dict[str, int]


class ChatCompletionChunkResponse(TypedDict):
    """聊天完成块响应
    
    符合 OpenAI API 格式的流式响应块。
    """
    id: str
    object: str
    model: str
    choices: List[ChatCompletionChunkChoice]


class UsageStats(TypedDict):
    """使用统计
    
    Token 使用统计信息。
    """
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class Features(TypedDict):
    """功能配置
    
    功能特性配置。
    """
    enable_thinking: bool


class UpstreamRequest(TypedDict):
    """上游请求
    
    发送到上游服务的请求数据。
    """
    stream: bool
    chat_id: str
    id: str
    model: str
    messages: List[Message]
    features: Features


class UpstreamData(TypedDict):
    """上游数据
    
    上游服务返回的数据格式。
    """
    phase: Optional[str]
    delta_content: Optional[str]
    edit_content: Optional[str]
    done: Optional[bool]


class UpstreamResponse(TypedDict):
    """上游响应
    
    上游服务响应格式。
    """
    data: UpstreamData


class ErrorResponse(TypedDict):
    """错误响应
    
    错误响应格式。
    """
    error: Dict[str, Any]


class StreamResult(TypedDict):
    """流式结果
    
    流式响应结果格式。
    """
    type: str
    generator: Iterator[str]
    model: str


# Anthropic API 类型定义
class AnthropicContentBlock(TypedDict):
    """Anthropic 内容块
    
    Anthropic API 的内容块格式。
    """
    type: str
    text: str


class AnthropicMessage(TypedDict):
    """Anthropic 消息
    
    Anthropic API 的消息格式。
    """
    role: str
    content: Union[str, List[AnthropicContentBlock]]


class AnthropicRequest(TypedDict):
    """Anthropic 请求
    
    Anthropic Messages API 的请求格式。
    """
    model: str
    messages: List[AnthropicMessage]
    max_tokens: int
    stream: bool
    temperature: Optional[float]
    system: Optional[Union[str, List[AnthropicContentBlock]]]


class AnthropicResponse(TypedDict):
    """Anthropic 响应
    
    Anthropic Messages API 的响应格式。
    """
    id: str
    type: str
    role: str
    content: List[AnthropicContentBlock]
    model: str
    stop_reason: Optional[str]
    usage: Dict[str, int]


class AnthropicMessageStartEvent(TypedDict):
    """Anthropic 消息开始事件
    
    流式响应的消息开始事件。
    """
    type: str
    message: Dict[str, Any]


class AnthropicContentBlockStartEvent(TypedDict):
    """Anthropic 内容块开始事件
    
    流式响应的内容块开始事件。
    """
    type: str
    index: int
    content_block: Dict[str, Any]


class AnthropicContentBlockDeltaEvent(TypedDict):
    """Anthropic 内容块增量事件
    
    流式响应的内容块增量事件。
    """
    type: str
    index: int
    delta: Dict[str, Any]


class AnthropicMessageDeltaEvent(TypedDict):
    """Anthropic 消息增量事件
    
    流式响应的消息增量事件。
    """
    type: str
    delta: Dict[str, Any]


class AnthropicMessageStopEvent(TypedDict):
    """Anthropic 消息停止事件
    
    流式响应的消息停止事件。
    """
    type: str