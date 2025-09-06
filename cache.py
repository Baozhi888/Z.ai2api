# -*- coding: utf-8 -*-
"""
缓存模块
提供增强的缓存功能以提高性能
"""

import time
import threading
import atexit
from typing import Any, Dict, Optional, Callable
from functools import wraps


class Cache:
    """增强的内存缓存实现
    
    提供线程安全的内存缓存功能，支持 TTL 过期机制、
    内存使用监控和自动清理。遵循单一职责原则。
    """
    
    def __init__(self, default_ttl: int = 300, max_size: int = 1000):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._lock_timeout = 5  # 锁超时时间（秒）
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'total_sets': 0,
            'lock_timeouts': 0  # 锁超时计数
        }
        self._cleanup_thread = None
        self._cleanup_stop_event = threading.Event()
        
        # 注册清理函数
        atexit.register(self.cleanup_expired)
        
        # 启动后台清理线程
        self._start_cleanup_thread()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            Optional[Any]: 缓存值，如果不存在或已过期则返回 None
        """
        try:
            # 使用超时获取锁
            if not self._lock.acquire(timeout=self._lock_timeout):
                self._stats['lock_timeouts'] += 1
                return None
            
            try:
                item = self._cache.get(key)
                if item is None:
                    self._stats['misses'] += 1
                    return None
                
                if time.time() > item['expires_at']:
                    del self._cache[key]
                    self._stats['misses'] += 1
                    return None
                
                self._stats['hits'] += 1
                return item['value']
            finally:
                self._lock.release()
        except Exception:
            # 如果出现异常，返回 None
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），可选，默认使用实例的默认 TTL
        """
        if ttl is None:
            ttl = self.default_ttl
        
        expires_at = time.time() + ttl
        
        try:
            # 使用超时获取锁
            if not self._lock.acquire(timeout=self._lock_timeout):
                self._stats['lock_timeouts'] += 1
                return
            
            try:
                # 检查缓存大小，如果超过最大大小则清理
                if len(self._cache) >= self.max_size:
                    self._evict_lru()
                
                self._cache[key] = {
                    'value': value,
                    'expires_at': expires_at,
                    'created_at': time.time(),
                    'access_count': 0
                }
                self._stats['total_sets'] += 1
            finally:
                self._lock.release()
        except Exception:
            # 如果出现异常，忽略
            pass
    
    def delete(self, key: str) -> None:
        """删除缓存值
        
        Args:
            key: 要删除的缓存键
        """
        with self._lock:
            self._cache.pop(key, None)
    
    def clear(self) -> None:
        """清空缓存
        
        清空所有缓存项。
        """
        with self._lock:
            self._cache.clear()
    
    def cleanup_expired(self) -> None:
        """清理过期缓存
        
        清理所有已过期的缓存项。
        """
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, item in self._cache.items()
                if current_time > item['expires_at']
            ]
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                self._stats['evictions'] += len(expired_keys)
    
    def _evict_lru(self) -> None:
        """LRU 淘汰策略
        
        淘汰最近最少使用的缓存项。
        """
        if not self._cache:
            return
        
        # 简单的 LRU 策略：删除最早创建的项
        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k]['created_at']
        )
        del self._cache[oldest_key]
        self._stats['evictions'] += 1
    
    def _start_cleanup_thread(self) -> None:
        """启动后台清理线程
        
        定期清理过期缓存项。
        """
        def cleanup_worker():
            while not self._cleanup_stop_event.is_set():
                try:
                    # 等待60秒或直到停止事件
                    if self._cleanup_stop_event.wait(60):
                        break
                    self.cleanup_expired()
                except Exception as e:
                    # 记录错误但不中断线程
                    if hasattr(self, 'logger'):
                        self.logger.error("缓存清理线程错误: %s", e)
        
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
    
    def stop_cleanup_thread(self) -> None:
        """停止后台清理线程"""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_stop_event.set()
            self._cleanup_thread.join(timeout=5)
            if self._cleanup_thread.is_alive():
                # 如果线程仍在运行，强制结束
                import warnings
                warnings.warn("缓存清理线程未能优雅退出")
    
    def __del__(self):
        """析构函数，确保清理线程停止"""
        self.stop_cleanup_thread()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息
        
        Returns:
            Dict[str, Any]: 缓存统计信息
        """
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0
        
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'hit_rate': hit_rate,
            'evictions': self._stats['evictions'],
            'total_sets': self._stats['total_sets']
        }


# 全局缓存实例
_cache = Cache()


def cache_result(ttl: int = 300):
    """缓存装饰器
    
    用于缓存函数的结果，提高性能。
    
    Args:
        ttl: 缓存过期时间（秒），默认 300 秒
        
    Returns:
        Callable: 装饰器函数
        
    Example:
        @cache_result(ttl=60)
        def expensive_function(x, y):
            return x + y
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # 尝试从缓存获取
            result = _cache.get(cache_key)
            if result is not None:
                return result
            
            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            _cache.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator


def get_cache() -> Cache:
    """获取缓存实例
    
    Returns:
        Cache: 全局缓存实例
    """
    return _cache


def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计信息
    
    Returns:
        Dict[str, Any]: 缓存统计信息
    """
    return _cache.get_stats()