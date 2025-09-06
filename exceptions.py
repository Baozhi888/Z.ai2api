# -*- coding: utf-8 -*-
"""
自定义异常模块
定义项目中使用的所有异常类型
"""

from enum import Enum
from typing import Optional, Any


class ErrorCode(Enum):
    """错误代码枚举"""
    
    # 认证错误
    INVALID_API_KEY = "invalid_api_key"
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
    AUTHENTICATION_FAILED = "authentication_failed"
    
    # 请求错误
    INVALID_REQUEST = "invalid_request_error"
    MISSING_PARAMETER = "missing_parameter"
    INVALID_PARAMETER_VALUE = "invalid_parameter_value"
    
    # 资源错误
    RESOURCE_NOT_FOUND = "not_found"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    
    # 上游服务错误
    UPSTREAM_ERROR = "upstream_error"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    UPSTREAM_CONNECTION_ERROR = "upstream_connection_error"
    
    # 系统错误
    SERVER_ERROR = "server_error"
    INTERNAL_ERROR = "internal_error"
    TIMEOUT_ERROR = "timeout"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


class ZAIException(Exception):
    """ZAI 基础异常类"""
    
    def __init__(
        self, 
        message: str, 
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        status_code: int = 500,
        details: Optional[dict] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "message": self.message,
            "type": self.error_code.value,
            "code": self.error_code.value,
            "param": self.details.get("param"),
            **self.details
        }


class AuthenticationError(ZAIException):
    """认证异常"""
    
    def __init__(self, message: str = "认证失败", details: Optional[dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.AUTHENTICATION_FAILED,
            status_code=401,
            details=details
        )


class AuthorizationError(ZAIException):
    """授权异常"""
    
    def __init__(self, message: str = "权限不足", details: Optional[dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            status_code=403,
            details=details
        )


class ValidationError(ZAIException):
    """验证异常"""
    
    def __init__(self, message: str, param: Optional[str] = None, details: Optional[dict] = None):
        full_details = {"param": param, **(details or {})}
        super().__init__(
            message=message,
            error_code=ErrorCode.INVALID_REQUEST,
            status_code=400,
            details=full_details
        )


class NotFoundError(ZAIException):
    """资源未找到异常"""
    
    def __init__(self, message: str = "资源未找到", details: Optional[dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            status_code=404,
            details=details
        )


class UpstreamError(ZAIException):
    """上游服务异常"""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.UPSTREAM_ERROR,
            status_code=502,
            details=details
        )


class UpstreamTimeoutError(UpstreamError):
    """上游超时异常"""
    
    def __init__(self, message: str = "上游服务超时", details: Optional[dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.UPSTREAM_TIMEOUT,
            status_code=504,
            details=details
        )


class RateLimitError(ZAIException):
    """速率限制异常"""
    
    def __init__(self, message: str = "请求频率超限", details: Optional[dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            status_code=429,
            details=details
        )


class ServerError(ZAIException):
    """服务器内部错误"""
    
    def __init__(self, message: str = "内部服务器错误", details: Optional[dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.SERVER_ERROR,
            status_code=500,
            details=details
        )


class TimeoutError(ZAIException):
    """超时异常"""
    
    def __init__(self, message: str = "请求超时", details: Optional[dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.TIMEOUT_ERROR,
            status_code=504,
            details=details
        )


def handle_http_client_error(error: Exception) -> ZAIException:
    """处理 HTTP 客户端错误，转换为 ZAI 异常"""
    from http_client import HttpClientError
    
    if isinstance(error, HttpClientError):
        error_type = getattr(error, 'error_type', 'request_error')
        
        if error_type == 'timeout':
            return UpstreamTimeoutError(str(error))
        elif error_type == 'connection_error':
            return UpstreamError(f"上游连接失败: {error}")
        elif error_type == 'http_error':
            return UpstreamError(str(error))
        else:
            return UpstreamError(str(error))
    
    # 其他未知错误
    return ServerError(f"未知错误: {error}")