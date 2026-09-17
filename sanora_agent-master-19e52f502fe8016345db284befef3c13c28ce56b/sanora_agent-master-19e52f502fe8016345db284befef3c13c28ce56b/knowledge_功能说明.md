# 知识库（Knowledge）功能说明文档

## 概述

知识库系统是基于 LangGraph 的声明式 RAG (Retrieval-Augmented Generation) 框架，支持通过 YAML 配置快速创建和管理多个知识库，提供智能问答服务。

---

## 目录结构

```
src/graphs/knowledge/
├── __init__.py                     # 导出注册表和配置发现工具
├── base.py                         # KnowledgePack 抽象和 KnowledgePackRegistry
├── config_loader.py                # YAML 配置加载器
├── agentic_knowledge_graph.py      # 知识库图的核心入口
├── agentic_pipeline.py             # 管道包装器
│
├── api/                            # API 服务层
│   └── service.py                  # 知识库文档 API 服务
│
├── models/                         # 数据模型
│   └── qa_pair.py                  # QA 对数据模型
│
├── ingestion/                      # 文档加载层
│   ├── filesystem.py               # 文件系统遍历和加载
│   ├── pdf_loader.py               # PDF 文档加载
│   ├── doc_loader.py               # Word 文档加载（DOC/DOCX）
│   └── web_loader.py               # 网页文档加载
│
├── preprocessing/                  # 文本预处理层
│   ├── text_splitter.py            # 文本切分
│   ├── enhanced_splitter.py        # 增强的切分器（记录位置信息）
│   └── labeling.py                 # 标签管理
│
├── stores/                         # 向量库和元数据存储
│   ├── vector_store.py             # FAISS 向量库构建和缓存
│   ├── qa_vector_store.py          # QA 对向量库
│   ├── qa_store.py                 # QA 对文件存储
│   └── metadata_store.py           # 切片元数据存储
│
├── retrieval/                      # 检索层
│   ├── retrieval.py                # 混合检索器（FAISS + BM25）
│   ├── parent_pages.py             # 父页面检索包装器
│   └── hybrid_doc_qa_retriever.py  # 文档和 QA 混合检索
│
├── pipelines/                      # LangGraph 管道构建
│   ├── prompts.py                  # 默认提示模板
│   ├── agentic_graph.py            # Agentic RAG 图构建
│   └── retriever_setup.py          # 检索资源配置
│
├── rerank/                         # 重排序层
│   ├── config.py                   # 重排序配置
│   ├── providers.py                # Jina、BGE 等提供者实现
│   └── retriever.py                # 重排序检索器包装
│
└── packs/                          # 知识包实现
    ├── mouth_cavity/               # 口腔术后知识包
    ├── mouth_cavity_v2/            # 口腔术后知识包 V2（Manager-Operator 架构）
    ├── sheld_qa/                   # Sheld 签证问答知识包
    └── disney_tickets/             # 迪士尼门票知识包
```

---

## 核心功能

### 1. 声明式知识包配置

通过 YAML 配置文件定义知识库，无需修改代码即可定制：

```python
# src/graphs/knowledge/base.py
@dataclass
class KnowledgePack:
    metadata: PackMetadataConfig        # 包的基本信息
    generate_response: GenerateResponseConfig  # 回答生成配置
    retrieval: RetrievalConfig         # 检索工具和参数
    embedding: EmbeddingConfig         # 嵌入和缓存配置
    preprocess: PreprocessConfig       # 预处理配置
    chunking: ChunkingConfig           # 切分参数
    rerank_config: RerankConfig | None # 可选重排序配置
    grader_rewrite: GraderRewriteConfig # 评分和重写配置
```

### 2. 知识包注册机制

支持两种知识包注册方式：

```python
# src/graphs/knowledge/base.py
class KnowledgePackRegistry:
    # 方式1: Python 类注册
    @classmethod
    def register(cls, pack_id: str):
        """装饰器注册 Python 类"""

    # 方式2: YAML 配置自动发现
    @classmethod
    def create(cls, pack_id: str) -> KnowledgePack:
        """优先使用注册的 Python 类，否则从 YAML 配置加载"""
```

### 3. 多格式文档加载

支持多种文档格式的自动加载：

- **PDF 文档**: `ingestion/pdf_loader.py` - 使用 PyPDFLoader
- **Word 文档**: `ingestion/doc_loader.py` - 支持 .doc 和 .docx
- **网页内容**: `ingestion/web_loader.py` - 远程 URL 加载
- **Markdown**: 通用文本加载器

### 4. 智能文本切分

两种切分模式：

```python
# 基础切分 (preprocessing/text_splitter.py)
def split_documents(
    docs: Sequence[Document],
    chunk_size: int,
    chunk_overlap: int
) -> list[Document]

# 增强切分 (preprocessing/enhanced_splitter.py)
def split_documents_with_positions(
    docs: Sequence[Document],
    chunk_size: int,
    chunk_overlap: int
) -> List[DocumentChunks]  # 包含位置信息
```

### 5. 向量存储与缓存

FAISS 向量库的构建和持久化：

```python
# stores/vector_store.py
def prepare_combined_vectorstore(
    pack_id: str,
    embeddings: Embeddings,
    docs: Sequence[Document],
    cache_dir: Path,
    chunk_size: int,
    chunk_overlap: int,
    labels: Optional[Dict[str, str]] = None,
    save_metadata: bool = True
) -> FAISS
```

**缓存机制特性**:
- 自动检测文档变更（基于文件哈希）
- 支持增量更新
- 持久化为 `.faiss` 和 `.pkl` 文件

### 6. 混合检索策略

支持多种检索模式的组合：

```python
# retrieval/retrieval.py
class HybridVectorRetriever:
    """FAISS 向量检索 + BM25 关键词检索"""

    def __init__(
        self,
        vectorstore: VectorStore,
        enable_bm25: bool = False,  # BM25 开关
        search_kwargs: Optional[dict] = None
    )
```

```python
# retrieval/parent_pages.py
class ParentPageRetriever:
    """从切片自动提升到原页面检索"""
```

### 7. 重排序（Rerank）支持

集成第三方重排序服务提升检索质量：

```python
# rerank/config.py
@dataclass
class RerankConfig:
    provider: RerankProvider | str  # "jina" 或 "bge"
    model: str                       # 模型名称
    api_key: str | None              # API 密钥
    endpoint: str | None             # 自定义端点
    top_k: int | None                # 返回的文档数
    candidate_k: int | None          # 候选文档数
```

**支持的提供者**:
- **Jina AI Reranker** (`rerank/providers.py:JinaReranker`)
- **BGE Reranker** (`rerank/providers.py:BGEReranker`)

### 8. 问答对（QA Pair）管理

独立的问答对向量库和存储机制：

```python
# models/qa_pair.py
@dataclass
class QAPair:
    qa_id: str
    pack_id: str
    question: str
    answer: str
    session_id: str
    created_at: str
    updated_at: str
    quality_score: float = 0.0
    usage_count: int = 0
    status: str = "active"
    editor_id: int | None = None    # 编辑人 ID（追责）
    editor_name: str | None = None  # 编辑人用户名
    edited_at: str | None = None    # 编辑时间
```

**核心 API**:

```python
# stores/qa_store.py
def add_qa_pair(
    pack_id: str,
    question: str,
    answer: str,
    session_id: str,
    qa_pairs_path: Path,
    metadata: Optional[Dict[str, Any]] = None,
    editor_id: Optional[int] = None,
    editor_name: Optional[str] = None,
    edited_at: Optional[str] = None
) -> QAPair

def load_qa_pairs(qa_pairs_path: Path) -> Optional[QAPairsCollection]
def save_qa_pairs(collection: QAPairsCollection, qa_pairs_path: Path) -> None
```

### 9. 智能评分与重写

可选的文档相关性评分和问题改写流程：

```python
# pipelines/agentic_graph.py
class GradeDocuments(BaseModel):
    """文档相关性评分"""
    binary_score: str  # "yes" 或 "no"

# 配置示例
grader_rewrite:
  enabled: true
  grader_model_key: "qwen3-flash"
  rewrite_model_key: "qwen3-flash"
  grade_prompt: "prompts/grade.md"
  rewrite_prompt: "prompts/rewrite.md"
```

### 10. 元数据管理

完整的文档切片元数据追踪：

```python
# stores/metadata_store.py
def save_chunks_metadata(
    pack_id: str,
    document_chunks_list: List[DocumentChunks],
    chunk_size: int,
    chunk_overlap: int,
    output_path: Path
) -> None
```

**元数据内容**:
```json
{
  "pack_id": "sheld_qa",
  "generated_at": "2025-11-13T10:30:00",
  "chunking_config": {
    "chunk_size": 800,
    "chunk_overlap": 80
  },
  "documents": [
    {
      "file_name": "policy.pdf",
      "file_path": "/path/to/policy.pdf",
      "total_chars": 12450,
      "chunks": [
        {
          "chunk_id": "uuid-...",
          "sequence": 1,
          "content": "...",
          "char_count": 800,
          "start_pos": 0,
          "end_pos": 800,
          "metadata": {...},
          "page_mapping": [1, 2]
        }
      ]
    }
  ]
}
```

---

## 工作流程

```
请求输入
    ↓
AgenticKnowledgeGraph.stream_chat()
    ↓
1. 消息转换
    ↓
2. 图执行 (LangGraph)
    ├─ generate_query_or_respond
    │   └─ 判断是否需要检索
    │
    ├─ (可选) retrieve
    │   ├─ 加载/构建向量库
    │   ├─ 执行混合检索（FAISS + BM25）
    │   ├─ (可选) 评分过滤
    │   └─ (可选) 重写问题
    │
    ├─ (可选) rerank
    │   └─ 使用重排序服务优化结果
    │
    └─ generate_answer
        └─ 基于检索到的上下文生成答案
    ↓
3. 流式输出
    ↓
响应输出
```

---

## 标准知识包结构

每个知识包（pack）遵循以下目录结构：

```
packs/<pack_id>/
├── pack.yaml                    # 配置文件（必需）
├── prompts/                     # 提示模板目录
│   ├── system.md               # 系统提示
│   ├── user.md                 # 用户提示（含 {question}, {context}）
│   ├── rewrite.md              # 重写问题的提示（可选）
│   ├── grade.md                # 评分的提示（可选）
│   └── qa_pair.md              # QA 对生成提示（可选）
├── knowledge_base/             # 源文档目录
│   ├── *.pdf
│   ├── *.docx
│   ├── *.doc
│   └── labels.json             # 可选的标签映射
└── vector_cache/               # 向量索引缓存目录
    ├── faiss_index.faiss
    ├── faiss_index.pkl
    ├── config.json
    ├── chunks_metadata.json    # 切片元数据
    └── qa_pairs.json           # 问答对集合
```

---

## pack.yaml 配置说明

### 基础配置示例

```yaml
metadata:
  pack_id: mouth_cavity
  display_name: "口腔术后问答"
  description: "针对口腔手术术后出血、护理的常见问题提供结构化指导。"

preprocess:
  remote_urls: []  # 可选的远程 URL 列表

generate_response:
  response_model_key: "qwen3-flash"
  system_prompt: "prompts/system.md"
  user_prompt: "prompts/user.md"

grader_rewrite:
  enabled: false
  grader_model_key: "qwen3-flash"
  rewrite_model_key: "qwen3-flash"
  rewrite_prompt: "prompts/rewrite.md"
  grade_prompt: "prompts/grade.md"

embedding:
  model_key: "text-embedding-v4"
  path:
    knowledge_base: "knowledge_base"
    cache: "vector_cache"

retrieval:
  llm_intent_query_retrieval: false  # 是否使用 LLM 生成查询
  tool:
    name: "mouth_cavity_retriever"
    description: "检索口腔术后护理建议与注意事项。"
  search_kwargs:
    k: 5  # 返回的文档数
  hybrid:
    enable_bm25: false
    enable_parent_pages: false

chunking:
  size: 500
  overlap: 70

rerank: null  # 不使用重排序
```

### 高级配置（重排序 + 父页检索）

```yaml
# disney_tickets 示例
retrieval:
  search_kwargs:
    k: 30  # 检索更多候选文档
  hybrid:
    enable_bm25: false
    enable_parent_pages: true  # 启用父页检索

rerank:
  provider: "bge"
  model: "bge-reranker-v2-m3"
  endpoint: "http://47.93.78.21:28800/v1/rerank"
  top_k: 10        # 重排后返回 10 个
  candidate_k: 20  # 从 30 个候选中选 20 个进行重排
```

### 动态知识库配置（环境变量）

```yaml
# sheld_qa 示例
embedding:
  model_key: "text-embedding-v4"
  path:
    storage_root: "${SHELD_EMBEDDING_STORAGE_ROOT}"  # 环境变量
    dataset_path: null                                # 动态指定
    cache: "vector_cache"

retrieval:
  tool:
    name: "sheld_qa_retriever"
    description: "检索签证相关问答"
  search_kwargs:
    k: 10
  hybrid:
    enable_bm25: false
    enable_parent_pages: true
  qa_pairs:
    enabled: true  # 启用 QA 对检索
    prompt: "prompts/qa_pair.md"
```

**环境变量使用**:
```bash
export SHELD_EMBEDDING_STORAGE_ROOT=/app/storage
```

---

## API 接口

### 1. 文档切片 API

```python
# api/service.py
from src.graphs.knowledge.api.service import knowledge_doc_service

# 获取文档切片信息
doc_chunks = knowledge_doc_service.get_document_chunks(
    pack_id="sheld_qa",
    file_name="policy.pdf"
)
```

**返回格式**:
```python
{
    "pack_id": "sheld_qa",
    "file_name": "policy.pdf",
    "document_info": {
        "total_chars": 12450,
        "total_chunks": 15,
        "processed_at": "2025-11-13T10:30:00"
    },
    "chunking_config": {
        "chunk_size": 800,
        "chunk_overlap": 80
    },
    "chunks": [
        {
            "chunk_id": "uuid-...",
            "sequence": 1,
            "content": "文档内容...",
            "char_count": 800,
            "start_pos": 0,
            "end_pos": 800,
            "metadata": {...},
            "page_mapping": [1]
        }
    ]
}
```

### 2. 问答对管理 API

```python
from src.graphs.knowledge.stores.qa_store import (
    load_qa_pairs,
    save_qa_pairs,
    add_qa_pair
)
from pathlib import Path

qa_pairs_path = Path("packs/sheld_qa/vector_cache/qa_pairs.json")

# 加载现有问答对
collection = load_qa_pairs(qa_pairs_path)

# 添加新问答对（自动去重）
new_qa = add_qa_pair(
    pack_id="sheld_qa",
    question="签证需要多少天?",
    answer="通常需要 10-15 个工作日",
    session_id="session_123",
    qa_pairs_path=qa_pairs_path,
    metadata={"source": "manual"},
    editor_id=1,
    editor_name="admin"
)

# 保存
save_qa_pairs(collection, qa_pairs_path)
```

### 3. 知识包注册 API

```python
from src.graphs.knowledge import KnowledgePackRegistry

# 列出所有可用的知识包
pack_ids = KnowledgePackRegistry.list_packs()

# 创建知识包实例
pack = KnowledgePackRegistry.create("mouth_cavity")

# 构建 LangGraph
graph, resources = pack.build_graph(
    llm_provider=llm_provider,
    config=app_config
)
```

### 4. 知识图 API

```python
from src.graphs.knowledge.agentic_knowledge_graph import AgenticKnowledgeGraph

# 创建图实例
graph = AgenticKnowledgeGraph(
    app_config=config,
    llm_provider=llm_provider,
    knowledge_base_path="/path/to/kb"  # 可选覆盖
)

# 流式对话
async for chunk in graph.stream_chat(request, app_id):
    print(chunk)
```

---

## 现有知识库概览

| 知识包 | 位置 | 功能 | 模型 | 检索参数 | 特性 |
|--------|------|------|------|---------|------|
| `mouth_cavity` | `packs/mouth_cavity/` | 口腔术后护理 | qwen3-flash | k=5 | 基础 RAG |
| `mouth_cavity_v2` | `packs/mouth_cavity_v2/` | 口腔术后护理 v2 | qwen3-flash | k=5 | Manager-Operator 架构 |
| `sheld_qa` | `packs/sheld_qa/` | 签证问答 | qwen3-flash | k=10 | 动态知识库、QA 对、父页检索 |
| `disney_tickets` | `packs/disney_tickets/` | 迪士尼门票 | qwen3-flash | k=30 | 重排序（BGE）、父页检索 |

---

## 核心特性

### 架构设计

- ✅ **声明性配置**: 完全基于 YAML，无需修改代码
- ✅ **模块化设计**: ingestion → preprocessing → stores → retrieval → pipelines 清晰的数据流
- ✅ **可扩展性**: 支持自定义嵌入模型、重排序提供者、检索策略
- ✅ **向后兼容**: 支持旧命名字段的兼容属性

### 核心能力

- 📄 **多种文档格式**: PDF、DOC/DOCX、网页、Markdown
- 🔍 **混合检索**: FAISS 向量检索 + BM25 关键词检索
- 🎯 **智能评分重写**: 评分模块判定检索结果相关性，重写模块优化问题
- ⚡ **重排序支持**: 集成 Jina、BGE 等重排序服务
- 💬 **问答对管理**: 独立的 QA 对向量库和存储机制
- 📑 **父页检索**: 从切片自动提升到原页面
- 🆕 **空知识库启动**: 支持无初始文档的知识库动态创建

### 生产就绪

- 💾 **向量缓存**: FAISS 索引持久化，支持增量更新检测
- 📋 **元数据管理**: 完整的切片元数据和来源追踪
- 🔐 **可审计性**: QA 对包含编辑人、编辑时间等追责字段
- 🌍 **环境变量支持**: 支持动态路径配置
- ⚙️ **并发安全**: 基于 LangGraph 的可靠状态管理

---

## 快速开始

### 1. 创建新知识包

```bash
# 创建目录结构
mkdir -p packs/my_pack/{prompts,knowledge_base,vector_cache}
```

### 2. 编写 pack.yaml

```yaml
metadata:
  pack_id: my_pack
  display_name: "我的知识包"
  description: "描述你的知识包用途"

generate_response:
  response_model_key: "qwen3-flash"
  system_prompt: "prompts/system.md"
  user_prompt: "prompts/user.md"

embedding:
  model_key: "text-embedding-v4"
  path:
    knowledge_base: "knowledge_base"
    cache: "vector_cache"

retrieval:
  tool:
    name: "my_pack_retriever"
    description: "描述检索工具的作用"
  search_kwargs:
    k: 5
  hybrid:
    enable_bm25: false
    enable_parent_pages: false

chunking:
  size: 800
  overlap: 80

grader_rewrite:
  enabled: false

rerank: null
```

### 3. 准备提示模板

**prompts/system.md**:
```markdown
你是一个专业的客服助手，负责回答用户关于 XXX 的问题。
```

**prompts/user.md**:
```markdown
基于以下上下文回答问题：

{context}

用户问题：{question}
```

### 4. 添加文档

将 PDF、DOCX 等文档放入 `knowledge_base/` 目录。

### 5. 使用知识包

```python
from src.graphs.knowledge import KnowledgePackRegistry

# 创建知识包
pack = KnowledgePackRegistry.create("my_pack")

# 构建图
graph, resources = pack.build_graph(
    llm_provider=llm_provider,
    config=app_config
)

# 流式对话
async for chunk in graph.stream_chat(request, app_id):
    print(chunk)
```

---

## 关键文件路径参考

| 功能模块 | 文件路径 | 主要类/函数 |
|---------|---------|-----------|
| 基础框架 | `src/graphs/knowledge/base.py` | KnowledgePack, KnowledgePackRegistry |
| 配置加载 | `src/graphs/knowledge/config_loader.py` | build_pack_from_config, discover_configured_pack_ids |
| 图入口 | `src/graphs/knowledge/agentic_knowledge_graph.py` | AgenticKnowledgeGraph, SheldQaKnowledge |
| API 服务 | `src/graphs/knowledge/api/service.py` | KnowledgeDocumentService |
| QA 对模型 | `src/graphs/knowledge/models/qa_pair.py` | QAPair, QAPairsCollection |
| 文件加载 | `src/graphs/knowledge/ingestion/filesystem.py` | load_documents_from_directory |
| PDF 加载 | `src/graphs/knowledge/ingestion/pdf_loader.py` | load_pdf_documents |
| Word 加载 | `src/graphs/knowledge/ingestion/doc_loader.py` | load_doc_documents |
| 网页加载 | `src/graphs/knowledge/ingestion/web_loader.py` | load_remote_documents |
| 文本切分 | `src/graphs/knowledge/preprocessing/enhanced_splitter.py` | split_documents_with_positions |
| 向量库 | `src/graphs/knowledge/stores/vector_store.py` | prepare_combined_vectorstore |
| QA 向量库 | `src/graphs/knowledge/stores/qa_vector_store.py` | build_qa_vectorstore |
| QA 存储 | `src/graphs/knowledge/stores/qa_store.py` | load_qa_pairs, add_qa_pair |
| 元数据存储 | `src/graphs/knowledge/stores/metadata_store.py` | save_chunks_metadata |
| 混合检索 | `src/graphs/knowledge/retrieval/retrieval.py` | HybridVectorRetriever |
| 父页检索 | `src/graphs/knowledge/retrieval/parent_pages.py` | ParentPageRetriever |
| Agentic 图 | `src/graphs/knowledge/pipelines/agentic_graph.py` | build_agentic_state_graph |
| 重排序配置 | `src/graphs/knowledge/rerank/config.py` | RerankConfig, RerankProvider |
| 重排序实现 | `src/graphs/knowledge/rerank/providers.py` | JinaReranker, BGEReranker |

---

## 技术栈

- **LangGraph**: 状态管理和工作流编排
- **LangChain**: 文档加载和文本切分
- **FAISS**: 向量相似度检索
- **BM25**: 关键词检索
- **PyPDF**: PDF 文档解析
- **python-docx**: Word 文档解析
- **Jina AI / BGE**: 重排序服务

---

## 常见问题

### Q: 如何更新知识库文档？

A: 将新文档添加到 `knowledge_base/` 目录后，删除 `vector_cache/` 目录，系统会自动重新构建向量索引。

### Q: 如何启用重排序？

A: 在 `pack.yaml` 中配置 `rerank` 字段：

```yaml
rerank:
  provider: "bge"
  model: "bge-reranker-v2-m3"
  endpoint: "http://your-endpoint/v1/rerank"
  top_k: 10
  candidate_k: 20
```

### Q: 如何使用环境变量？

A: 在 YAML 中使用 `${ENV_VAR}` 语法：

```yaml
embedding:
  path:
    storage_root: "${KNOWLEDGE_STORAGE_ROOT}"
```

然后在启动前设置环境变量：
```bash
export KNOWLEDGE_STORAGE_ROOT=/app/storage
```

### Q: 如何添加 QA 对？

A: 使用 `add_qa_pair` API：

```python
from src.graphs.knowledge.stores.qa_store import add_qa_pair
from pathlib import Path

add_qa_pair(
    pack_id="my_pack",
    question="示例问题",
    answer="示例答案",
    session_id="session_id",
    qa_pairs_path=Path("packs/my_pack/vector_cache/qa_pairs.json"),
    editor_id=1,
    editor_name="admin"
)
```

---

## 版本历史

- **v1**: 基础 RAG 流程（mouth_cavity）
- **v2**: Manager-Operator 架构（mouth_cavity_v2）
- **当前**: 声明式配置 + 多知识包支持（sheld_qa, disney_tickets）

---

## 联系与支持

如有问题或建议，请联系开发团队或查看代码库中的测试文件：
- `src/graphs/knowledge/testing/test_cavity.py`
- `src/graphs/knowledge/testing/test_disney.py`
- `src/graphs/knowledge/testing/test_sheld_qa.py`
