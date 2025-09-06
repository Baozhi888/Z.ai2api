# -*- coding: utf-8 -*-
"""
性能监控模块
提供性能统计和监控功能
"""

import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from threading import Thread
from collections import defaultdict
import json


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    request_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_response_time: float = 0.0
    average_response_time: float = 0.0
    error_count: int = 0
    tool_call_count: int = 0
    tool_call_success_count: int = 0
    tool_call_total_tokens: int = 0
    tool_call_average_tokens: float = 0.0
    
    def update_response_time(self, response_time: float) -> None:
        """更新响应时间统计"""
        self.request_count += 1
        self.total_response_time += response_time
        self.average_response_time = self.total_response_time / self.request_count
    
    def increment_cache_hits(self) -> None:
        """增加缓存命中次数"""
        self.cache_hits += 1
    
    def increment_cache_misses(self) -> None:
        """增加缓存未命中次数"""
        self.cache_misses += 1
    
    def increment_errors(self) -> None:
        """增加错误次数"""
        self.error_count += 1
    
    def increment_tool_calls(self, tokens: int = 0) -> None:
        """增加工具调用次数"""
        self.tool_call_count += 1
        if tokens > 0:
            self.tool_call_success_count += 1
            self.tool_call_total_tokens += tokens
            self.tool_call_average_tokens = self.tool_call_total_tokens / self.tool_call_success_count
    
    @property
    def cache_hit_rate(self) -> float:
        """缓存命中率"""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0
    
    @property
    def tool_call_success_rate(self) -> float:
        """工具调用成功率"""
        return self.tool_call_success_count / self.tool_call_count if self.tool_call_count > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "request_count": self.request_count,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": self.cache_hit_rate,
            "average_response_time": self.average_response_time,
            "error_count": self.error_count,
            "tool_call_count": self.tool_call_count,
            "tool_call_success_rate": self.tool_call_success_rate,
            "tool_call_average_tokens": self.tool_call_average_tokens
        }


class PerformanceMonitor:
    """性能监控器
    
    提供性能统计和监控功能，包括请求计数、缓存命中率、响应时间等。
    """
    
    def __init__(self):
        self.metrics = PerformanceMetrics()
        self.request_times: Dict[str, float] = {}
        self.endpoint_stats: Dict[str, PerformanceMetrics] = defaultdict(PerformanceMetrics)
        self._lock = None
        try:
            import threading
            self._lock = threading.RLock()
        except ImportError:
            pass
    
    def start_request(self, request_id: str, endpoint: str) -> None:
        """开始记录请求"""
        self.request_times[request_id] = time.time()
    
    def end_request(self, request_id: str, endpoint: str, success: bool = True, cached: bool = False) -> None:
        """结束记录请求"""
        if request_id not in self.request_times:
            return
        
        response_time = time.time() - self.request_times[request_id]
        del self.request_times[request_id]
        
        if self._lock:
            with self._lock:
                self._update_metrics(response_time, endpoint, success, cached)
        else:
            self._update_metrics(response_time, endpoint, success, cached)
    
    def _update_metrics(self, response_time: float, endpoint: str, success: bool, cached: bool) -> None:
        """更新性能指标"""
        # 更新全局指标
        self.metrics.update_response_time(response_time)
        if cached:
            self.metrics.increment_cache_hits()
        else:
            self.metrics.increment_cache_misses()
        if not success:
            self.metrics.increment_errors()
        
        # 更新端点指标
        endpoint_metrics = self.endpoint_stats[endpoint]
        endpoint_metrics.update_response_time(response_time)
        if cached:
            endpoint_metrics.increment_cache_hits()
        else:
            endpoint_metrics.increment_cache_misses()
        if not success:
            endpoint_metrics.increment_errors()
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return {
            "global": self.metrics.to_dict(),
            "endpoints": {endpoint: metrics.to_dict() for endpoint, metrics in self.endpoint_stats.items()}
        }
    
    def reset_metrics(self) -> None:
        """重置性能指标"""
        if self._lock:
            with self._lock:
                self.metrics = PerformanceMetrics()
                self.endpoint_stats.clear()
                self.request_times.clear()
        else:
            self.metrics = PerformanceMetrics()
            self.endpoint_stats.clear()
            self.request_times.clear()


# 全局性能监控实例
_monitor = PerformanceMonitor()


def get_monitor() -> PerformanceMonitor:
    """获取性能监控实例"""
    return _monitor


class RequestTimer:
    """请求计时器上下文管理器"""
    
    def __init__(self, endpoint: str, request_id: Optional[str] = None):
        self.endpoint = endpoint
        self.request_id = request_id or f"req_{int(time.time() * 1000000)}"
        self.start_time: Optional[float] = None
        self.success = True
        self.cached = False
        self.monitor = get_monitor()
    
    def __enter__(self):
        self.start_time = time.time()
        self.monitor.start_request(self.request_id, self.endpoint)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.success = False
        
        self.monitor.end_request(self.request_id, self.endpoint, self.success, self.cached)
    
    def mark_cached(self) -> None:
        """标记为缓存命中"""
        self.cached = True