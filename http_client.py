# -*- coding: utf-8 -*-
"""
HTTP 客户端模块
处理所有 HTTP 请求逻辑
遵循单一职责原则和依赖倒置原则
"""

import json
import re
import time
import requests
import atexit
import signal
import threading
from typing import Dict, Any, Optional, Iterator
from abc import ABC, abstractmethod
from config import config
from cache import get_cache


class HttpClientInterface(ABC):
    """HTTP 客户端接口，遵循依赖倒置原则
    
    定义了 HTTP 客户端的基本操作接口，便于实现不同的 HTTP 客户端。
    """
    
    @abstractmethod
    def get(self, url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 8) -> Dict[str, Any]:
        """发送 GET 请求
        
        Args:
            url: 请求 URL
            headers: 请求头，可选
            timeout: 超时时间（秒），默认 8 秒
            
        Returns:
            Dict[str, Any]: 响应数据
        """
        pass
    
    @abstractmethod
    def post_stream(self, url: str, json_data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, timeout: int = 60) -> Iterator[bytes]:
        """发送流式 POST 请求
        
        Args:
            url: 请求 URL
            json_data: JSON 请求数据
            headers: 请求头，可选
            timeout: 超时时间（秒），默认 60 秒
            
        Returns:
            Iterator[bytes]: 流式响应数据
        """
        pass
    
    @abstractmethod
    def post(self, url: str, json_data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> Dict[str, Any]:
        """发送普通 POST 请求
        
        Args:
            url: 请求 URL
            json_data: JSON 请求数据
            headers: 请求头，可选
            timeout: 超时时间（秒），默认 30 秒
            
        Returns:
            Dict[str, Any]: 响应数据
        """
        pass


class RequestsHttpClient(HttpClientInterface):
    """基于 requests 的 HTTP 客户端实现
    
    使用 requests 库实现 HTTP 客户端接口，提供基本的 HTTP 请求功能。
    使用 Session 复用连接，提高性能。
    实现上下文管理器协议，确保资源正确释放。
    """
    
    def __init__(self, base_headers: Optional[Dict[str, str]] = None):
        self.base_headers = base_headers or {}
        self.session = requests.Session()
        self.cache = get_cache()
        self._closed = False
        self._lock = threading.RLock()
        
        # 注册清理函数
        atexit.register(self.close)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # 配置连接池
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,  # 增加连接池大小
            pool_maxsize=50,     # 增加最大连接数
            max_retries=3,
            pool_block=False    # 非阻塞模式
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
    
    def _check_closed(self):
        """检查客户端是否已关闭"""
        with self._lock:
            if self._closed:
                raise RuntimeError("HTTP 客户端已关闭")
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        self.close()
    
    def _safe_iter_lines(self, response):
        """安全的迭代器，确保响应被正确关闭"""
        try:
            for line in response.iter_lines():
                yield line
        finally:
            response.close()
    
    def close(self):
        """关闭 HTTP 客户端，释放资源"""
        with self._lock:
            if not self._closed:
                try:
                    if hasattr(self, 'session') and self.session:
                        self.session.close()
                except Exception:
                    pass  # 忽略关闭时的异常
                self._closed = True
    
    def __del__(self):
        """析构函数，确保资源释放"""
        self.close()
    
    def get(self, url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 8) -> Dict[str, Any]:
        """发送 GET 请求"""
        self._check_closed()
        merged_headers = {**self.base_headers, **(headers or {})}
        try:
            response = self.session.get(url, headers=merged_headers, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise HttpClientError(f"GET 请求超时: {url}", "timeout")
        except requests.exceptions.ConnectionError:
            raise HttpClientError(f"GET 请求连接失败: {url}", "connection_error")
        except requests.exceptions.HTTPError as e:
            raise HttpClientError(f"GET 请求 HTTP 错误 {e.response.status_code}: {url}", "http_error")
        except requests.RequestException as e:
            raise HttpClientError(f"GET 请求失败: {e}", "request_error")
    
    def post_stream(self, url: str, json_data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, timeout: int = 60) -> Iterator[bytes]:
        """发送流式 POST 请求"""
        self._check_closed()
        merged_headers = {**self.base_headers, **(headers or {})}
        try:
            response = self.session.post(url, json=json_data, headers=merged_headers, stream=True, timeout=timeout)
            response.raise_for_status()
            return self._safe_iter_lines(response)
        except requests.exceptions.Timeout:
            raise HttpClientError(f"POST 流式请求超时: {url}", "timeout")
        except requests.exceptions.ConnectionError:
            raise HttpClientError(f"POST 流式请求连接失败: {url}", "connection_error")
        except requests.exceptions.HTTPError as e:
            raise HttpClientError(f"POST 流式请求 HTTP 错误 {e.response.status_code}: {url}", "http_error")
        except requests.RequestException as e:
            raise HttpClientError(f"POST 流式请求失败: {e}", "request_error")
    
    def post(self, url: str, json_data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> Dict[str, Any]:
        """发送普通 POST 请求"""
        self._check_closed()
        merged_headers = {**self.base_headers, **(headers or {})}
        try:
            response = self.session.post(url, json=json_data, headers=merged_headers, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise HttpClientError(f"POST 请求超时: {url}", "timeout")
        except requests.exceptions.ConnectionError:
            raise HttpClientError(f"POST 请求连接失败: {url}", "connection_error")
        except requests.exceptions.HTTPError as e:
            raise HttpClientError(f"POST 请求 HTTP 错误 {e.response.status_code}: {url}", "http_error")
        except requests.RequestException as e:
            raise HttpClientError(f"POST 请求失败: {e}", "request_error")


class HttpClientError(Exception):
    """HTTP 客户端异常"""
    
    def __init__(self, message: str, error_type: str = "request_error"):
        super().__init__(message)
        self.error_type = error_type
        self.message = message
    
    def __str__(self):
        return self.message

    
# 添加上下文管理器支持
def _context_manager(self):
    """上下文管理器支持"""
    return self


def _enter(self):
    """进入上下文"""
    return self


def _exit(self, exc_type, exc_val, exc_tb):
    """退出上下文，确保资源释放"""
    self.close()


# 为 RequestsHttpClient 添加上下文管理器方法
RequestsHttpClient.__enter__ = _enter
RequestsHttpClient.__exit__ = _exit
RequestsHttpClient.__context_manager = property(_context_manager)


class ZAIClient:
    """Z.ai API 客户端，专门处理 Z.ai 相关的 API 调用
    
    该类封装了与 Z.ai API 交互的所有逻辑，包括认证、模型获取、聊天完成等。
    遵循单一职责原则，专门处理 Z.ai 相关的 API 调用。
    """
    
    def __init__(self, http_client: HttpClientInterface):
        self.http_client = http_client
        from cache import get_cache
        self.cache = get_cache()
    
    def get_auth_token(self) -> str:
        """获取认证令牌
        
        优先尝试获取匿名 token，失败时使用配置的上游 token。
        使用缓存避免频繁请求。
        
        Returns:
            str: 认证令牌
        """
        if not config.anon_token_enabled:
            return config.upstream_token
        
        # 检查缓存
        cache_key = "auth_token"
        cached_token = self.cache.get(cache_key)
        if cached_token:
            if config.debug_mode:
                print("从缓存获取认证令牌")
            return cached_token
        
        try:
            # 使用更完整的浏览器请求头来模拟真实浏览器请求
            auth_headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
                "Referer": f"{config.api_base}/",
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "application/json",
                "Origin": config.api_base,
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "X-FE-Version": "prod-fe-1.0.77",
            }
            
            response = self.http_client.get(
                f"{config.api_base}/api/v1/auths/", 
                headers=auth_headers
            )
            token = response.get("token")
            if token:
                # 缓存令牌10分钟
                self.cache.set(cache_key, token, 600)
                if config.debug_mode:
                    print("认证令牌已缓存")
                return token
        except Exception as e:
            if config.debug_mode:
                print(f"匿名 token 获取失败: {e}")
        
        return config.upstream_token
    
    def get_models(self) -> Dict[str, Any]:
        """获取模型列表
        
        Returns:
            Dict[str, Any]: 模型列表数据
        """
        headers = {"Authorization": f"Bearer {self.get_auth_token()}"}
        return self.http_client.get(f"{config.api_base}/api/models", headers=headers)
    
    def create_chat_completion(self, data: Dict[str, Any], chat_id: str) -> Iterator[bytes]:
        """创建聊天完成
        
        Args:
            data: 聊天完成数据
            chat_id: 聊天 ID
            
        Returns:
            Iterator[bytes]: 流式响应数据
        """
        headers = {
            "Authorization": f"Bearer {self.get_auth_token()}",
            "Referer": f"{config.api_base}/c/{chat_id}"
        }
        return self.http_client.post_stream(
            f"{config.api_base}/api/chat/completions",
            json_data=data,
            headers=headers
        )
    
    def create_chat_completion_normal(self, data: Dict[str, Any], chat_id: str, timeout: int = 30) -> Dict[str, Any]:
        """创建非流式聊天完成
        
        注意：Z.ai API 即使设置 stream=false 仍然返回流式格式，
        所以这里需要特殊处理。
        
        Args:
            data: 聊天完成数据
            chat_id: 聊天 ID
            timeout: 超时时间（秒）
            
        Returns:
            Dict[str, Any]: 响应数据
        """
        # 强制使用流式请求，但收集完整响应
        data["stream"] = True
        
        headers = {
            "Authorization": f"Bearer {self.get_auth_token()}",
            "Referer": f"{config.api_base}/c/{chat_id}"
        }
        
        # 获取流式响应并收集所有内容
        response = self.http_client.post_stream(
            f"{config.api_base}/api/chat/completions",
            json_data=data,
            headers=headers,
            timeout=timeout
        )
        
        # 收集所有数据
        full_content = ""
        thinking_content = ""
        tool_calls = []
        error_msg = None
        usage = None
        current_phase = None
        
        for chunk in response:
            try:
                # 解析 SSE 格式（chunk 是 bytes）
                if chunk.startswith(b"data: "):
                    data_str = chunk[6:]  # 移除 "data: " 前缀
                    if data_str == b"[DONE]":
                        continue
                    
                    data = json.loads(data_str.decode('utf-8', 'ignore'))
                    
                    # 提取内容
                    if "data" in data:
                        inner_data = data["data"]
                        if isinstance(inner_data, dict):
                            current_phase = inner_data.get("phase", current_phase)
                            
                            # 检查错误
                            if "error" in inner_data:
                                error_msg = inner_data["error"].get("detail", "Unknown error")
                            
                            # 处理思考链
                            if current_phase == "thinking":
                                thinking_delta = inner_data.get("delta_content", "")
                                if thinking_delta:
                                    # 清理思考内容
                                    if thinking_delta.startswith("<details"):
                                        thinking_delta = re.sub(r'<summary[^>]*>.*?</summary>\n?', '', thinking_delta)
                                        thinking_delta = re.sub(r'</?details[^>]*>', '', thinking_delta)
                                    thinking_content += thinking_delta
                            
                            # 处理工具调用
                            elif current_phase == "tool_call":
                                edit_content = inner_data.get("edit_content", "")
                                if edit_content and "<glm_block >" in edit_content:
                                    blocks = edit_content.split("<glm_block >")
                                    for block in blocks:
                                        if "</glm_block>" in block:
                                            try:
                                                block_content = block[:-12]  # 移除 </glm_block>
                                                tool_data = json.loads(block_content)
                                                
                                                if tool_data.get("type") == "tool_call":
                                                    metadata = tool_data.get("data", {}).get("metadata", {})
                                                    if metadata.get("id") and metadata.get("name"):
                                                        tool_calls.append({
                                                            "id": metadata["id"],
                                                            "type": "function",
                                                            "function": {
                                                                "name": metadata["name"],
                                                                "arguments": json.dumps(metadata.get("arguments", {}))
                                                            }
                                                        })
                                            except (json.JSONDecodeError, KeyError):
                                                continue
                            
                            # 处理回答内容
                            elif current_phase == "answer":
                                # 提取内容
                                delta_content = inner_data.get("delta_content", "")
                                edit_content = inner_data.get("edit_content", "")
                                content = delta_content or edit_content
                                
                                if content:
                                    # 如果包含思考链结束标记，只取后面的内容
                                    if "</details>\n" in content:
                                        content = content.split("</details>\n", 1)[1]
                                    full_content += content
                            
                            # 收集使用统计
                            if inner_data.get("usage"):
                                usage = inner_data["usage"]
                            
                            if inner_data.get("done", False):
                                break
            except (json.JSONDecodeError, KeyError):
                continue
        
        # 构建消息对象
        message = {
            "role": "assistant",
            "content": full_content if not error_msg else "抱歉，服务暂时不可用，请稍后重试。"
        }
        
        # 添加思考链
        if thinking_content:
            message["thinking"] = {
                "content": thinking_content,
                "signature": str(int(time.time()))
            }
        
        # 添加工具调用
        if tool_calls:
            message["tool_calls"] = tool_calls
        
        # 构建响应格式
        result = {
            "id": f"chatcmpl-{chat_id}",
            "object": "chat.completion",
            "model": data.get("model", "glm-4.5v"),
            "choices": [{
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if tool_calls else "stop"
            }],
            "usage": usage or {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
        
        return result