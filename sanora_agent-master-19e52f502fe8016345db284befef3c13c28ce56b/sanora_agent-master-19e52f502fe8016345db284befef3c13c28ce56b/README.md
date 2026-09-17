# OpenAI Compatible API Server

基于 FastAPI + LangGraph 实现的 OpenAI Chat Completions 接口流式兼容的 Web 服务框架，支持多个 LangGraph 应用和 API Key 认证。

## 特性

- ✅ **OpenAI 兼容接口**: 完全兼容 OpenAI Chat Completions API
- ✅ **流式响应**: 支持 Server-Sent Events (SSE) 流式输出
- ✅ **多 LangGraph 支持**: 支持多个独立的 LangGraph 应用，每个应用有独立的 API Key
- ✅ **API Key 认证**: 类似 Dify 的认证方式，通过 `Authorization: Bearer <API_KEY>` 头部认证
- ✅ **多模型支持**: 支持 OpenAI、Qwen、Anthropic、Moonshot 等多种 LLM 服务
- ✅ **配置驱动**: 通过 YAML 配置文件管理模型参数和 LangGraph 应用
- ✅ **环境变量**: 通过 .env 文件安全管理 API 密钥
- ✅ **高性能**: 基于 FastAPI 的异步架构
- ✅ **生产就绪**: 包含错误处理、日志记录、CORS 支持等

## 架构说明

### 多 LangGraph 架构

每个 LangGraph 应用都是独立的：

- **独立的 API Key**: 每个应用有自己的认证密钥
- **独立的模型配置**: 可以使用不同的 LLM 提供商
- **独立的图类型**: 支持不同类型的处理逻辑
- **独立的启用状态**: 可以单独启用/禁用应用

### 认证方式

```bash
# 使用 Authorization 头部进行认证
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Authorization: Bearer lg-test-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填入你的 API 密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# LLM API Keys
OPENAI_API_KEY=your_openai_api_key_here
QWEN_API_KEY=your_qwen_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
MOONSHOT_API_KEY=your_moonshot_api_key_here

# Server Configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
DEBUG=true
```

### 3. 配置 LangGraph 应用

编辑 `config.yaml` 文件来配置你的 LangGraph 应用：

```yaml
# LangGraph Applications Configuration
langgraph_apps:
  # 测试图 - 简单聊天功能
  test_graph:
    name: "Test Chat Graph"
    description: "A simple test chat graph for demonstration"
    api_key: "lg-test-key-12345"  # 自定义 API 密钥
    model_provider: "openai"
    graph_type: "simple_chat"
    enabled: true
    
  # 推理图 - 多步推理分析 (禁用状态)
  reasoning_graph:
    name: "Advanced Reasoning Graph"
    description: "Multi-step reasoning and analysis graph"
    api_key: "lg-reasoning-67890"
    model_provider: "qwen"
    graph_type: "reasoning_chain"
    enabled: false
```

### 4. 启动服务器

```bash
python run_server.py
```

服务器将在 `http://localhost:8000` 启动。

### 5. 测试接口

运行测试客户端：

```bash
python test_client.py
```

或者运行多图演示：

```bash
python demo_multi_graph.py
```

### 6. 使用 curl 测试

```bash
# 使用测试图的 API Key
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Authorization: Bearer lg-test-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'

# 流式请求
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Authorization: Bearer lg-test-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

## API 端点

### 1. 健康检查

```http
GET /health
```

### 2. 获取模型列表

```http
GET /v1/models
```

### 3. 获取 LangGraph 应用列表

```http
GET /v1/langgraph/apps
```

返回示例：

```json
{
  "langgraph_apps": [
    {
      "id": "test_graph",
      "name": "Test Chat Graph",
      "description": "A simple test chat graph for demonstration",
      "graph_type": "simple_chat",
      "model_provider": "openai",
      "enabled": true
    }
  ]
}
```

### 4. 聊天完成 (需要认证)

```http
POST /v1/chat/completions
Authorization: Bearer <API_KEY>
```

请求体：

```json
{
  "messages": [
    {"role": "user", "content": "Hello, how are you?"}
  ],
  "stream": false,
  "max_tokens": 100,
  "temperature": 0.7
}
```

### 5. 兼容端点 (无版本前缀)

```http
POST /chat/completions
Authorization: Bearer <API_KEY>
```

## 项目结构

```
rooyee_agent/
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用主文件
│   ├── config.py            # 配置管理
│   ├── models.py            # Pydantic 数据模型
│   ├── llm_service.py       # LLM 服务和 LangGraph 集成
│   └── chat_service.py      # 聊天服务逻辑
├── config.yaml              # 模型配置文件
├── .env.example             # 环境变量示例
├── requirements.txt         # Python 依赖
├── run_server.py           # 服务器启动脚本
├── test_client.py          # 测试客户端
└── README.md               # 项目文档
```

## 配置说明

### 模型配置 (config.yaml)

```yaml
models:
  model_name:
    name: "actual-model-name"      # 实际的模型名称
    base_url: "https://api.xxx"    # API 基础地址
    max_tokens: 4096               # 最大 token 数
    temperature: 0.7               # 温度参数
    top_p: 1.0                    # top_p 参数
    frequency_penalty: 0.0         # 频率惩罚
    presence_penalty: 0.0          # 存在惩罚

server:
  default_model: "openai"          # 默认模型
  stream_timeout: 30               # 流式超时时间
  max_concurrent_requests: 100     # 最大并发请求数

api:
  rate_limit: 100                  # 速率限制 (每分钟请求数)
  enable_cors: true                # 启用 CORS
  cors_origins: ["*"]             # CORS 允许的源
```

### 环境变量 (.env)

```env
# 模型 API 密钥
OPENAI_API_KEY=your_key
QWEN_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
MOONSHOT_API_KEY=your_key

# 服务器配置
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
DEBUG=true

# 应用配置
APP_NAME=OpenAI Compatible API Server
VERSION=1.0.0
```

## 支持的模型服务

### 1. OpenAI

```yaml
openai:
  name: "gpt-3.5-turbo"
  base_url: "https://api.openai.com/v1"
```

### 2. 阿里云通义千问 (Qwen)

```yaml
qwen:
  name: "qwen-turbo"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
```

### 3. Anthropic Claude

```yaml
anthropic:
  name: "claude-3-sonnet-20240229"
  base_url: "https://api.anthropic.com/v1"
```

### 4. 月之暗面 Moonshot

```yaml
moonshot:
  name: "moonshot-v1-8k"
  base_url: "https://api.moonshot.cn/v1"
```

## 流式响应格式

服务器返回标准的 Server-Sent Events (SSE) 格式：

```
data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1699999999,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1699999999,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1699999999,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":20,"total_tokens":30}}

data: [DONE]
```
### 工具配置 
在相应的tools文件夹中添加工具文件，例如：src/tools/call_search_poi.py
直接在相应的graphs中进行引用，例如：src/graphs/poi_search.py
todo 使用config yaml文件进行工具配置
## 开发

### 运行开发服务器

```bash
python run_server.py
```

### 运行测试

```bash
python test_client.py
```

### 添加新的模型服务

1. 在 `config.yaml` 中添加模型配置
2. 在 `.env` 中添加对应的 API 密钥环境变量
3. 在 `src/config.py` 中的 `key_mapping` 添加密钥映射
4. 重启服务器

## 生产部署

### 使用 Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker src.main:app --bind 0.0.0.0:8000
```

### 使用 Docker

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["python", "run_server.py"]
```
