# -*- coding: utf-8 -*-
"""
Z.ai 2 API
将 Z.ai 代理为 OpenAI Compatible 格式，支持免 Cookie、智能处理思考链等功能
基于 https://github.com/kbykb/OpenAI-Compatible-API-Proxy-for-Z 使用 AI 辅助重构。

主要特性：
- OpenAI API 兼容格式
- 智能思考链处理
- 流式响应支持
- 完整的错误处理
- 线程安全的缓存机制
- 灵活的配置管理
"""

from flask import Flask, request, Response, jsonify
from config import config
from http_client import RequestsHttpClient, ZAIClient
from content_processor import ContentProcessor, ThinkTagsMode
from services import ChatService
from utils import Logger, ResponseHelper
from performance import get_monitor
from cache import get_cache_stats
from anthropic_api import AnthropicAPIHandler

# --- 初始化 ---
app = Flask(__name__)
logger = Logger(__name__)

# 全局错误处理中间件
@app.errorhandler(404)
def handle_not_found(error):
    """处理 404 错误"""
    logger.warning("404 错误: %s", error)
    return ResponseHelper.create_error_response("接口不存在", "not_found", 404)

@app.errorhandler(405)
def handle_method_not_allowed(error):
    """处理 405 错误"""
    logger.warning("405 错误: %s", error)
    return ResponseHelper.create_error_response("方法不被允许", "method_not_allowed", 405)

@app.errorhandler(500)
def handle_internal_error(error):
    """处理 500 错误"""
    logger.error("500 内部服务器错误: %s", error)
    return ResponseHelper.create_error_response("内部服务器错误", "server_error", 500)

@app.errorhandler(Exception)
def handle_all_exceptions(error):
    """处理所有未捕获的异常"""
    logger.error("未捕获的异常: %s", error)
    
    # 导入异常类
    from http_client import HttpClientError
    from exceptions import ZAIException, handle_http_client_error
    
    # 根据异常类型返回不同的错误响应
    if isinstance(error, ZAIException):
        # 已经是 ZAI 异常，直接使用
        return ResponseHelper.create_error_response(
            error.message,
            error.error_code.value,
            error.status_code,
            error.details.get("param")
        )
    elif isinstance(error, HttpClientError):
        # 转换为 ZAI 异常
        zai_error = handle_http_client_error(error)
        return ResponseHelper.create_error_response(
            zai_error.message,
            zai_error.error_code.value,
            zai_error.status_code
        )
    elif isinstance(error, ValueError):
        return ResponseHelper.create_error_response(
            f"参数错误: {error}", 
            "invalid_request_error", 
            400
        )
    elif isinstance(error, RuntimeError):
        return ResponseHelper.create_error_response(
            f"运行时错误: {error}", 
            "runtime_error", 
            500
        )
    else:
        # 其他未知错误
        return ResponseHelper.create_error_response(
            "内部服务器错误", 
            "server_error", 
            500
        )

# --- 依赖注入 ---
# 遵循依赖倒置原则，通过接口注入依赖
http_client = RequestsHttpClient(config.browser_headers)
zai_client = ZAIClient(http_client)
content_processor = ContentProcessor(ThinkTagsMode(config.think_tags_mode))
chat_service = ChatService(zai_client, content_processor, logger)
anthropic_handler = AnthropicAPIHandler(chat_service, content_processor)

# --- API 密钥验证中间件 ---
def require_api_key(f):
    """API 密钥验证装饰器
    
    如果启用了 API 密钥验证，则检查请求头中的 Authorization。
    """
    def decorated_function(*args, **kwargs):
        if config.api_key_enabled:
            # 从请求头获取 API 密钥
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({
                    "error": {
                        "message": "Missing or invalid API key. Please provide a valid API key in the Authorization header using the Bearer scheme.",
                        "type": "invalid_request_error",
                        "code": "invalid_api_key"
                    }
                }), 401
            
            api_key = auth_header.split(' ')[1]
            if not api_key or api_key != config.api_key:
                return jsonify({
                    "error": {
                        "message": "Invalid API key.",
                        "type": "invalid_request_error",
                        "code": "invalid_api_key"
                    }
                }), 401
        
        return f(*args, **kwargs)
    
    decorated_function.__name__ = f.__name__
    return decorated_function

# --- 路由 ---
@app.route("/", methods=["GET"])
def index():
    """根路径
    
    返回服务基本信息。
    """
    return jsonify({
        "service": "Z.ai2api",
        "version": "1.0.0",
        "description": "Z.ai API 代理服务，兼容 OpenAI 和 Anthropic API 格式",
        "endpoints": {
            "health": "/health",
            "openai_chat": "/v1/chat/completions",
            "openai_models": "/v1/models",
            "anthropic_messages": "/v1/messages",
            "metrics": "/metrics"
        },
        "repository": "https://github.com/Baozhi888/Z.ai2api"
    })

@app.route("/health", methods=["GET"])
def health():
    """健康检查端点
    
    用于检查服务是否正常运行。
    健康检查端点不需要 API 密钥验证。
    """
    return jsonify({"status": "ok", "service": "Z.ai2api"})

@app.route("/v1/models", methods=["GET", "OPTIONS"])
def models():
    """获取模型列表
    
    符合 OpenAI API 格式的模型列表端点。
    """
    if request.method == "OPTIONS":
        return ResponseHelper.create_options_response()
    
    try:
        models_data = chat_service.get_models_list()
        return ResponseHelper.create_json_response(models_data)
    except Exception as e:
        logger.error("模型列表失败: %s", e)
        return ResponseHelper.create_error_response("fetch models failed")

@app.route("/v1/chat/completions", methods=["POST", "OPTIONS"])
@require_api_key
def chat():
    """创建聊天完成
    
    符合 OpenAI API 格式的聊天完成端点，支持流式和普通响应。
    """
    if request.method == "OPTIONS":
        return ResponseHelper.create_options_response()
    
    req = request.get_json(force=True, silent=True) or {}
    
    try:
        result = chat_service.create_chat_completion(req)
        
        if result.get("type") == "stream":
            return Response(
                result["generator"],
                mimetype="text/event-stream"
            )
        else:
            return ResponseHelper.create_json_response(result)
    except Exception as e:
        logger.error("聊天完成失败: %s", e)
        return ResponseHelper.create_error_response(f"请求处理失败: {e}", 502)

@app.route("/metrics", methods=["GET"])
@require_api_key
def metrics():
    """获取性能指标
    
    返回应用的性能统计数据，包括请求计数、缓存命中率等。
    """
    monitor = get_monitor()
    metrics_data = monitor.get_metrics()
    return jsonify(metrics_data)

@app.route("/metrics/reset", methods=["POST"])
def reset_metrics():
    """重置性能指标
    
    重置所有性能统计数据。
    """
    monitor = get_monitor()
    monitor.reset_metrics()
    return jsonify({"status": "metrics reset"})

@app.route("/cache/stats", methods=["GET"])
def cache_stats():
    """获取缓存统计信息
    
    返回缓存的使用统计信息。
    """
    stats = get_cache_stats()
    return jsonify(stats)

@app.route("/cache/clear", methods=["POST"])
def cache_clear():
    """清空缓存
    
    清空所有缓存项。
    """
    from cache import get_cache
    cache = get_cache()
    cache.clear()
    return jsonify({"status": "cache cleared"})

# --- Anthropic API 路由 ---
@app.route("/v1/messages", methods=["POST", "OPTIONS"])
def anthropic_messages():
    """Anthropic Messages API 端点
    
    完全兼容 Anthropic Messages API 格式。
    """
    if request.method == "OPTIONS":
        return ResponseHelper.create_options_response()
    
    return anthropic_handler.handle_messages()

# --- 主入口 ---
if __name__ == "__main__":
    """主入口点
    
    启动 Flask 应用服务器。
    """
    # 设置控制台输出编码
    import sys
    if sys.platform.startswith('win'):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    # 免责声明
    print("\n" + "="*60)
    print("⚠️  免责声明：本项目仅供个人学习和研究使用")
    print("🚫 禁止用于任何商业目的或商业环境")
    print("📚 使用者需自行承担使用风险并遵守相关法律法规")
    print("="*60 + "\n")
    
    logger.info(
        "代理启动: 端口=%s, 备选模型=%s，思考处理=%s, Debug=%s",
        config.port, config.model_name, config.think_tags_mode, config.debug_mode
    )
    app.run(host="0.0.0.0", port=config.port, threaded=True)