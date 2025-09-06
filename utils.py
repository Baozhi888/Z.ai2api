# -*- coding: utf-8 -*-
"""
日志和工具模块
提供统一的日志记录和工具函数
"""

import logging
import json
import uuid
import random
import string
from datetime import datetime
from typing import Any, Dict, Optional
from config import config


class Logger:
    """日志管理器
    
    提供统一的日志记录接口，支持调试模式切换。
    遵循单一职责原则，专门处理日志记录。
    """
    
    def __init__(self, name: str = __name__, debug_mode: bool = None):
        """初始化日志管理器
        
        Args:
            name: 日志器名称
            debug_mode: 调试模式，None 时使用配置值
        """
        self.debug_mode = debug_mode if debug_mode is not None else config.debug_mode
        self.logger = logging.getLogger(name)
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志配置"""
        # 避免重复配置
        if not self.logger.handlers:
            level = logging.DEBUG if self.debug_mode else logging.INFO
            logging.basicConfig(
                level=level,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            
            # 为当前logger设置处理器
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(level)
    
    def debug(self, msg: str, *args):
        """调试日志
        
        Args:
            msg: 日志消息
            *args: 格式化参数
        """
        if self.debug_mode:
            self.logger.debug(msg, *args)
    
    def info(self, msg: str, *args):
        """信息日志
        
        Args:
            msg: 日志消息
            *args: 格式化参数
        """
        self.logger.info(msg, *args)
    
    def warning(self, msg: str, *args):
        """警告日志
        
        Args:
            msg: 日志消息
            *args: 格式化参数
        """
        self.logger.warning(msg, *args)
    
    def error(self, msg: str, *args):
        """错误日志
        
        Args:
            msg: 日志消息
            *args: 格式化参数
        """
        self.logger.error(msg, *args)


class IDGenerator:
    """ID 生成器
    
    提供基于时间戳的唯一 ID 生成功能，以及符合 RFC4122 标准的 UUID 生成。
    """
    
    @staticmethod
    def generate_id(prefix: str = "msg") -> str:
        """生成唯一 ID
        
        Args:
            prefix: ID 前缀
            
        Returns:
            str: 唯一 ID，格式为 prefix-timestamp
        """
        timestamp = int(datetime.now().timestamp() * 1e9)
        return f"{prefix}-{timestamp}"
    
    @staticmethod
    def generate_uuid() -> str:
        """生成符合 RFC4122 标准的 UUID v4
        
        Returns:
            str: 符合 RFC4122 标准的 UUID 字符串
        """
        # 生成随机字节
        bytes_data = bytearray(uuid.uuid4().bytes)
        
        # 设置版本号 (4)
        bytes_data[6] = (bytes_data[6] & 0x0f) | 0x40
        # 设置变体 (10)
        bytes_data[8] = (bytes_data[8] & 0x3f) | 0x80
        
        # 转换为 UUID 格式: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        hex_str = bytes_data.hex()
        return f"{hex_str[0:8]}-{hex_str[8:12]}-{hex_str[12:16]}-{hex_str[16:20]}-{hex_str[20:32]}"
    
    @staticmethod
    def generate_short_id(length: int = 8) -> str:
        """生成短 ID
        
        Args:
            length: ID 长度
            
        Returns:
            str: 生成的短 ID
        """
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


class ModelFormatter:
    """模型名称格式化器
    
    提供模型名称的格式化功能，确保名称的一致性。
    """
    
    @staticmethod
    def format_model_name(name: str) -> str:
        """格式化模型名称
        
        Args:
            name: 原始模型名称
            
        Returns:
            str: 格式化后的模型名称
        """
        if not name:
            return ""
        
        parts = name.split('-')
        if len(parts) == 1:
            return parts[0].upper()
        
        formatted = [parts[0].upper()]
        for p in parts[1:]:
            if not p:
                formatted.append("")
            elif p.isdigit():
                formatted.append(p)
            elif any(c.isalpha() for c in p):
                formatted.append(p.capitalize())
            else:
                formatted.append(p)
        
        return "-".join(formatted)
    
    @staticmethod
    def is_english_letter(ch: str) -> bool:
        """判断是否是英文字符
        
        Args:
            ch: 字符
            
        Returns:
            bool: 是否是英文字符
        """
        return 'A' <= ch <= 'Z' or 'a' <= ch <= 'z'


class ResponseHelper:
    """响应帮助器
    
    提供统一的 HTTP 响应创建功能，包括 CORS 支持。
    """
    
    @staticmethod
    def set_cors_headers(response) -> Any:
        """设置 CORS 头
        
        Args:
            response: Flask 响应对象
            
        Returns:
            Any: 设置了 CORS 头的响应对象
        """
        response.headers.update({
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        })
        return response
    
    @staticmethod
    def create_json_response(data: Dict[str, Any], status_code: int = 200) -> Any:
        """创建 JSON 响应
        
        Args:
            data: 响应数据
            status_code: HTTP 状态码
            
        Returns:
            Any: JSON 响应对象
        """
        from flask import jsonify, make_response
        response = jsonify(data)
        response.status_code = status_code
        return ResponseHelper.set_cors_headers(response)
    
    @staticmethod
    def create_error_response(message: str, error_type: str = "server_error", status_code: int = 500, param: str = None) -> Any:
        """创建错误响应
        
        支持 OpenAI 和 Anthropic API 标准的错误格式
        
        Args:
            message: 错误消息
            error_type: 错误类型
            status_code: HTTP 状态码
            param: 错误参数（可选）
            
        Returns:
            Any: 错误响应对象
        """
        # OpenAI API 格式
        error_data = {
            "error": {
                "message": message,
                "type": error_type,
                "code": error_type,
                "param": param
            }
        }
        
        return ResponseHelper.create_json_response(error_data, status_code)
    
    @staticmethod
    def create_options_response() -> Any:
        """创建 OPTIONS 响应
        
        Returns:
            Any: OPTIONS 响应对象
        """
        from flask import make_response
        return ResponseHelper.set_cors_headers(make_response())