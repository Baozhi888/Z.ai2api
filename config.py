# -*- coding: utf-8 -*-
"""
配置管理模块
遵循 DRY 原则，集中管理所有配置项
支持从 .env 文件加载配置
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

# 尝试加载 python-dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()  # 加载 .env 文件
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


@dataclass
class AppConfig:
    """应用配置类，遵循单一职责原则
    
    集中管理所有应用配置，支持从环境变量加载。
    遵循单一职责原则，专门处理配置管理。
    """
    # ===== 基础配置 =====
    api_base: str = "https://chat.z.ai"
    port: int = 8089
    upstream_token: str = "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjMxNmJjYjQ4LWZmMmYtNGExNS04NTNkLWYyYTI5YjY3ZmYwZiIsImVtYWlsIjoiR3Vlc3QtMTc1NTg0ODU4ODc4OEBndWVzdC5jb20ifQ.PktllDySS3trlyuFpTeIZf-7hl8Qu1qYF3BxjgIul0BrNux2nX9hVzIjthLXKMWAf9V0qM8Vm_iyDqkjPGsaiQ"
    model_name: str = "glm-4.5v"
    debug_mode: bool = True
    think_tags_mode: str = "think"
    anon_token_enabled: bool = True
    
    # ===== 性能配置 =====
    models_cache_ttl: int = 300
    auth_token_cache_ttl: int = 600
    content_cache_ttl: int = 3600
    
    # ===== 缓存配置 =====
    cache_default_ttl: int = 300
    cache_max_size: int = 1000
    
    # ===== 日志配置 =====
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # ===== 安全配置 =====
    cors_origins: str = "*"
    request_timeout: int = 60
    stream_timeout: int = 120
    # 非流式请求的超时时间（用于连通性测试）
    non_stream_timeout: int = 30
    # 多模态请求的超时时间（图片处理需要更长时间）
    multimodal_timeout: int = 300
    
    # ===== 访问密钥配置 =====
    api_key: Optional[str] = None
    api_key_enabled: bool = False
    
    # ===== Anthropic API 配置 =====
    anthropic_api_key: Optional[str] = None
    anthropic_model_mapping: Dict[str, str] = field(default_factory=lambda: {
        "claude-3-5-sonnet-20241022": "glm-4.5v",
        "claude-4.0-sonnet-20241022": "glm-4.5v",  # 添加 claude-4.0 支持
        "claude-3-haiku-20240307": "glm-4.5v",
        "claude-3-opus-20240229": "glm-4.5v",
        "claude-2.1": "glm-4.5v",
        # 默认映射，任何未指定的模型都映射到 glm-4.5v
    })
    
    # ===== 工具调用配置 =====
    function_call_enabled: bool = True
    max_json_scan: int = 200000
    sse_heartbeat_seconds: float = 15.0
    include_thinking: bool = False
    tool_call_timeout: int = 30
    tool_call_retry_count: int = 2
    tool_call_retry_backoff: float = 0.6
    
    # ===== 高级配置 =====
    enable_performance_monitoring: bool = True
    enable_request_tracing: bool = True
    max_concurrent_requests: int = 100
    
    # ===== 开发配置 =====
    auto_reload: bool = False
    show_errors_detail: bool = True
    
    @property
    def browser_headers(self) -> Dict[str, str]:
        """浏览器请求头配置
        
        Returns:
            Dict[str, str]: 浏览器请求头字典
        """
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/139.0.0.0",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "X-FE-Version": "prod-fe-1.0.76",
            "sec-ch-ua": '"Not;A=Brand";v="99", "Edge";v="139"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Origin": self.api_base,
        }
    
    @classmethod
    def from_env(cls) -> 'AppConfig':
        """从环境变量加载配置
        
        Returns:
            AppConfig: 从环境变量加载的配置实例
        """
        def str_to_bool(value, default: bool) -> bool:
            """将字符串转换为布尔值"""
            if value is None:
                return default
            return value.lower() in ("true", "1", "yes", "on")
        
        return cls(
            # ===== 基础配置 =====
            api_base=os.getenv("ZAI_API_BASE", cls.api_base),
            port=int(os.getenv("ZAI_PORT", cls.port)),
            upstream_token=os.getenv("ZAI_UPSTREAM_TOKEN", cls.upstream_token),
            model_name=os.getenv("ZAI_MODEL_NAME", cls.model_name),
            debug_mode=str_to_bool(os.getenv("ZAI_DEBUG_MODE"), cls.debug_mode),
            think_tags_mode=os.getenv("ZAI_THINK_TAGS_MODE", cls.think_tags_mode),
            anon_token_enabled=str_to_bool(os.getenv("ZAI_ANON_TOKEN_ENABLED"), cls.anon_token_enabled),
            
            # ===== 性能配置 =====
            models_cache_ttl=int(os.getenv("ZAI_MODELS_CACHE_TTL", cls.models_cache_ttl)),
            auth_token_cache_ttl=int(os.getenv("ZAI_AUTH_TOKEN_CACHE_TTL", cls.auth_token_cache_ttl)),
            content_cache_ttl=int(os.getenv("ZAI_CONTENT_CACHE_TTL", cls.content_cache_ttl)),
            
            # ===== 缓存配置 =====
            cache_default_ttl=int(os.getenv("ZAI_CACHE_DEFAULT_TTL", cls.cache_default_ttl)),
            cache_max_size=int(os.getenv("ZAI_CACHE_MAX_SIZE", cls.cache_max_size)),
            
            # ===== 日志配置 =====
            log_level=os.getenv("ZAI_LOG_LEVEL", cls.log_level),
            log_format=os.getenv("ZAI_LOG_FORMAT", cls.log_format),
            
            # ===== 安全配置 =====
            cors_origins=os.getenv("ZAI_CORS_ORIGINS", cls.cors_origins),
            request_timeout=int(os.getenv("ZAI_REQUEST_TIMEOUT", cls.request_timeout)),
            stream_timeout=int(os.getenv("ZAI_STREAM_TIMEOUT", cls.stream_timeout)),
            non_stream_timeout=int(os.getenv("ZAI_NON_STREAM_TIMEOUT", cls.non_stream_timeout)),
            multimodal_timeout=int(os.getenv("ZAI_MULTIMODAL_TIMEOUT", cls.multimodal_timeout)),
            
            # ===== 访问密钥配置 =====
            api_key=os.getenv("ZAI_API_KEY"),
            api_key_enabled=str_to_bool(os.getenv("ZAI_API_KEY_ENABLED"), cls.api_key_enabled),
            
            # ===== Anthropic API 配置 =====
            anthropic_api_key=os.getenv("ZAI_ANTHROPIC_API_KEY"),
            
            # ===== 工具调用配置 =====
            function_call_enabled=str_to_bool(os.getenv("ZAI_FUNCTION_CALL_ENABLED"), cls.function_call_enabled),
            max_json_scan=int(os.getenv("ZAI_MAX_JSON_SCAN", cls.max_json_scan)),
            sse_heartbeat_seconds=float(os.getenv("ZAI_SSE_HEARTBEAT_SECONDS", cls.sse_heartbeat_seconds)),
            include_thinking=str_to_bool(os.getenv("ZAI_INCLUDE_THINKING"), cls.include_thinking),
            tool_call_timeout=int(os.getenv("ZAI_TOOL_CALL_TIMEOUT", cls.tool_call_timeout)),
            tool_call_retry_count=int(os.getenv("ZAI_TOOL_CALL_RETRY_COUNT", cls.tool_call_retry_count)),
            tool_call_retry_backoff=float(os.getenv("ZAI_TOOL_CALL_RETRY_BACKOFF", cls.tool_call_retry_backoff)),
            
            # ===== 高级配置 =====
            enable_performance_monitoring=str_to_bool(os.getenv("ZAI_ENABLE_PERFORMANCE_MONITORING"), cls.enable_performance_monitoring),
            enable_request_tracing=str_to_bool(os.getenv("ZAI_ENABLE_REQUEST_TRACING"), cls.enable_request_tracing),
            max_concurrent_requests=int(os.getenv("ZAI_MAX_CONCURRENT_REQUESTS", cls.max_concurrent_requests)),
            
            # ===== 开发配置 =====
            auto_reload=str_to_bool(os.getenv("ZAI_AUTO_RELOAD"), cls.auto_reload),
            show_errors_detail=str_to_bool(os.getenv("ZAI_SHOW_ERRORS_DETAIL"), cls.show_errors_detail),
        )
    
    def validate(self) -> None:
        """验证配置的有效性
        
        Raises:
            ValueError: 当配置无效时抛出
        """
        if self.port < 1 or self.port > 65535:
            raise ValueError(f"端口号必须在 1-65535 之间，当前值: {self.port}")
        
        if self.models_cache_ttl < 0:
            raise ValueError(f"模型缓存TTL必须大于等于0，当前值: {self.models_cache_ttl}")
        
        if self.cache_max_size < 1:
            raise ValueError(f"缓存大小必须大于0，当前值: {self.cache_max_size}")
        
        if self.think_tags_mode not in ["think", "pure", "raw"]:
            raise ValueError(f"思考标签模式必须是 think、pure 或 raw，当前值: {self.think_tags_mode}")
        
        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError(f"日志级别无效，当前值: {self.log_level}")


# 全局配置实例
config = AppConfig.from_env()