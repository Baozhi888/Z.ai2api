# Z.ai2api 开发指南

## 目录

1. [开发环境搭建](#开发环境搭建)
2. [项目结构](#项目结构)
3. [代码规范](#代码规范)
4. [开发工作流](#开发工作流)
5. [测试指南](#测试指南)
6. [调试技巧](#调试技巧)
7. [性能优化](#性能优化)
8. [贡献指南](#贡献指南)

## 开发环境搭建

### 前置要求

- Python 3.10+
- Git
- Docker (可选，用于容器化开发)

### 1. 克隆项目

```bash
git clone https://github.com/Baozhi888/Z.ai2api.git
cd Z.ai2api
```

### 2. 创建虚拟环境

```bash
# 使用 venv
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 使用 conda
conda create -n zai2api python=3.10
conda activate zai2api
```

### 3. 安装依赖

```bash
# 安装生产依赖
pip install -r requirements.txt

# 安装开发依赖
pip install -r requirements-dev.txt
```

如果 `requirements-dev.txt` 不存在，可以创建：

```txt
# requirements-dev.txt
black==23.7.0
isort==5.12.0
flake8==6.0.0
pytest==7.4.0
pytest-cov==4.1.0
pre-commit==3.3.3
mypy==1.5.1
```

### 4. 配置 pre-commit hooks

```bash
pre-commit install
```

### 5. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，配置开发环境变量
```

开发环境建议的配置：

```bash
ZAI_DEBUG_MODE=true
ZAI_LOG_LEVEL=DEBUG
ZAI_API_KEY_ENABLED=false  # 开发环境可以关闭 API 密钥
```

## 项目结构

```
Z.ai2api/
├── app.py                  # Flask 应用入口
├── config.py              # 配置管理
├── type_definitions.py    # 类型定义
├── http_client.py         # HTTP 客户端
├── content_processor.py   # 内容处理器
├── services.py            # 业务逻辑
├── utils.py               # 工具函数
├── exceptions.py          # 异常定义
├── cache.py               # 缓存实现
├── performance.py         # 性能监控
├── requirements.txt       # 生产依赖
├── requirements-dev.txt   # 开发依赖
├── .env.example           # 环境变量模板
├── .gitignore             # Git 忽略文件
├── Dockerfile             # Docker 配置
├── docker-compose.yml     # Docker 编排
├── tests/                 # 测试目录
│   ├── __init__.py
│   ├── test_app.py
│   ├── test_services.py
│   └── test_cache.py
├── docs/                  # 文档目录
│   ├── API.md
│   └── DEVELOPMENT.md
└── scripts/               # 脚本目录
    └── docker-start.sh
```

### 核心模块说明

#### config.py
- **职责**: 管理所有配置项
- **设计**: 使用 dataclass，支持环境变量加载
- **扩展**: 添加新配置项只需在 AppConfig 中添加属性

#### http_client.py
- **职责**: 封装 HTTP 请求
- **设计**: 使用抽象基类，便于扩展其他 HTTP 客户端
- **缓存**: 集成了缓存机制，提高性能

#### content_processor.py
- **职责**: 处理思考链内容
- **设计**: 策略模式，支持多种处理模式
- **扩展**: 添加新模式只需扩展枚举和处理器

#### services.py
- **职责**: 核心业务逻辑
- **设计**: 依赖注入，便于测试和扩展

## 代码规范

### Python 代码风格

1. **格式化**: 使用 Black 进行代码格式化
   ```bash
   black .
   ```

2. **导入排序**: 使用 isort
   ```bash
   isort .
   ```

3. **代码检查**: 使用 flake8
   ```bash
   flake8 .
   ```

4. **类型注解**: 所有函数和变量都应有类型注解

### 命名规范

- **函数名**: 使用下划线分隔的小写字母 (snake_case)
- **类名**: 使用驼峰命名法 (CamelCase)
- **常量**: 使用全大写字母，下划线分隔 (UPPER_CASE)
- **变量**: 使用下划线分隔的小写字母 (snake_case)

### 注释规范

1. **模块注释**: 每个模块都应有文档字符串
   ```python
   """模块功能描述。
   
   更多详细信息。
   """
   ```

2. **类注释**: 描述类的用途和主要方法
   ```python
   class HttpClient:
       """HTTP 客户端抽象基类。
       
       提供统一的 HTTP 请求接口。
       """
   ```

3. **函数注释**: 描述函数功能、参数和返回值
   ```python
   def send_request(self, url: str, method: str = "GET") -> Response:
       """发送 HTTP 请求。
       
       Args:
           url: 请求的 URL
           method: HTTP 方法，默认 GET
           
       Returns:
           Response: HTTP 响应对象
       """
   ```

## 开发工作流

### Git 工作流

1. **创建功能分支**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **开发并提交**
   ```bash
   git add .
   git commit -m "feat: 添加新功能"
   ```

3. **推送分支**
   ```bash
   git push origin feature/your-feature-name
   ```

4. **创建 Pull Request**
   - 在 GitHub 上创建 PR
   - 填写 PR 描述，包含变更内容
   - 请求代码审查

### 提交信息规范

使用 Conventional Commits 格式：

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

类型说明：
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建或辅助工具变动

示例：
```
feat: 添加新的思考链处理模式

添加了 concise 模式，用于简化思考链显示。
该模式会移除所有思考内容，只保留最终答案。

Closes #123
```

### 代码审查清单

在提交 PR 前，请确保：

- [ ] 代码符合项目规范
- [ ] 所有测试通过
- [ ] 新功能包含测试
- [ ] 文档已更新
- [ ] 提交信息规范
- [ ] 无安全漏洞
- [ ] 性能影响已考虑

## 测试指南

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_services.py

# 运行特定测试函数
pytest tests/test_services.py::test_chat_completion

# 生成覆盖率报告
pytest --cov=. --cov-report=html --cov-report=term
```

### 编写测试

测试文件应放在 `tests/` 目录下，命名格式为 `test_*.py`。

示例测试：

```python
import pytest
from services import ChatService
from content_processor import ContentProcessor, ThinkTagsMode

def test_chat_completion():
    """测试聊天完成功能"""
    # 初始化
    processor = ContentProcessor(ThinkTagsMode.THINK)
    service = ChatService(mock_client, processor, mock_logger)
    
    # 测试数据
    request = {
        "model": "GLM-4.5",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    
    # 执行测试
    result = service.create_chat_completion(request)
    
    # 断言
    assert "id" in result
    assert result["object"] == "chat.completion"
    assert len(result["choices"]) > 0
```

### 测试最佳实践

1. **单元测试**: 测试单个函数或方法
2. **集成测试**: 测试模块间的交互
3. **Mock 对象**: 使用 mock 避免外部依赖
4. **测试覆盖**: 保持高测试覆盖率
5. **测试数据**: 使用 fixtures 管理测试数据

## 调试技巧

### 1. 启用调试模式

```bash
export ZAI_DEBUG_MODE=true
python app.py
```

或在 `.env` 文件中设置：
```bash
ZAI_DEBUG_MODE=true
ZAI_LOG_LEVEL=DEBUG
```

### 2. 使用 Python 调试器

```python
import pdb; pdb.set_trace()  # 设置断点
```

或者使用 ipdb（需要安装）：
```python
import ipdb; ipdb.set_trace()
```

### 3. 日志调试

```python
from utils import Logger

logger = Logger(__name__)
logger.debug("调试信息")
logger.info("一般信息")
logger.error("错误信息")
```

### 4. 性能分析

```python
import cProfile
import pstats

# 性能分析
profiler = cProfile.Profile()
profiler.enable()

# 你的代码
result = some_function()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats()
```

### 5. 内存调试

使用 `memory_profiler`：

```bash
pip install memory_profiler
```

```python
from memory_profiler import profile

@profile
def memory_intensive_function():
    # 你的代码
    pass
```

运行：
```bash
python -m memory_profiler your_script.py
```

## 性能优化

### 1. 缓存优化

监控缓存命中率：
```bash
curl http://localhost:8080/metrics
```

优化策略：
- 调整缓存 TTL
- 增加缓存大小
- 使用更高效的缓存算法

### 2. 并发优化

- 使用连接池
- 调整工作线程数
- 实现请求限流

### 3. 内存优化

- 及时释放资源
- 使用生成器替代列表
- 避免循环引用

### 4. 数据库优化（如果使用）

- 添加适当的索引
- 使用连接池
- 优化查询语句

## 贡献指南

### 报告 Bug

1. 在 GitHub Issues 中创建新 issue
2. 使用 Bug Report 模板
3. 提供复现步骤和环境信息
4. 包含错误日志和堆栈跟踪

### 功能请求

1. 先在 Discussions 中讨论
2. 描述需求的背景和场景
3. 提供可能的实现方案
4. 等待维护者反馈

### 提交代码

1. Fork 项目
2. 创建功能分支
3. 编写代码和测试
4. 确保所有检查通过
5. 提交 PR

### 代码审查

审查者会关注：

- 代码质量和可读性
- 测试覆盖率
- 文档完整性
- 性能影响
- 安全考虑

### 发布流程

1. 更新版本号
2. 更新 CHANGELOG
3. 创建 Git tag
4. 构建 Docker 镜像
5. 发布 Release

## 常见问题

### Q: 如何添加新的 API 端点？

A: 
1. 在 `app.py` 中添加新的路由
2. 在 `services.py` 中实现业务逻辑
3. 添加相应的测试
4. 更新 API 文档

### Q: 如何添加新的配置项？

A:
1. 在 `config.py` 的 `AppConfig` 类中添加新属性
2. 在 `from_env` 方法中添加环境变量读取
3. 更新 `.env.example`
4. 在文档中说明新配置项

### Q: 如何处理新的错误类型？

A:
1. 在 `exceptions.py` 中定义新的异常类
2. 在适当的代码中抛出异常
3. 在 `app.py` 中添加错误处理逻辑
4. 更新错误文档

## 资源链接

- [Python 官方文档](https://docs.python.org/)
- [Flask 文档](https://flask.palletsprojects.com/)
- [OpenAI API 文档](https://platform.openai.com/docs/api-reference)
- [Docker 文档](https://docs.docker.com/)

---

希望这份开发指南能帮助你更好地参与 Z.ai2api 项目的开发！如有任何问题，请随时在 Discussions 中讨论。