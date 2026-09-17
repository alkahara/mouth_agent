# 知识库架构说明

## 目录分层
- `ingestion/`：封装 PDF、DOC/DOCX、远程网页等数据源的加载逻辑，并提供统一的文件遍历与标签合并入口。
- `preprocessing/`：负责标签补充与文本切分等轻量预处理，以保证所有知识库复用相同的分块策略。
- `stores/`：构建与缓存混合向量库（FAISS + BM25），集中管理嵌入模型、缓存配置与索引落盘。
- `retrieval/`：封装向量与 BM25 混合检索的组合器，统一暴露 `HybridVectorRetriever` 等检索流组件。
- `pipelines/`：包含 Agentic RAG 的核心拼装逻辑（提示词、检索资源构建、LangGraph 图装配）以及默认提示模板。
- `base.py` 与 `packs/`：`KnowledgePack` 抽象及注册机制，以及每个领域知识库的配置文件与素材目录。
- `packs/<pack_id>/pack.yaml`：声明 pack 元数据、提示词、检索与索引参数，可完全通过 YAML 配置化维护。
- `packs/<pack_id>/prompts/*.md`：领域提示词（包含 `grader_rewrite` 使用的 rewrite/grade 以及回答所需 generate）存放为 Markdown，供策划与校对团队独立维护。
- `configs/`：定义 `KnowledgeBaseConfig` 等更高层的策略参数结构，便于未来在配置中统一调整检索策略。
- `__init__.py`：导出注册表与配置发现工具，供 `AgenticKnowledgeGraph` 直接引用。

## 模块职责
### ingestion
- `pdf_loader.py` / `doc_loader.py` / `web_loader.py`：针对不同来源的文档实现最小加载单元。
- `filesystem.py`：统一遍历知识库目录、调用对应 loader、应用 `labels.json` 标签并返回 LangChain `Document` 列表。


### preprocessing
- `labeling.py`：读取标签映射并实现标签合并策略。
- `text_splitter.py`：提供基于 `RecursiveCharacterTextSplitter` 的通用切分函数（默认 800 tokens、重叠 80 tokens）。
- `pack.yaml` 中的 `preprocess` 段：配置 `remote_urls`，用于在切块前统一文件来源与格式。

### stores
- `vector_store.py`：
  - 创建 DashScope 嵌入（或接收自定义工厂）。
  - 构建/加载向量库并按需启用 BM25，持久化缓存配置与索引。
  - 提供 `HybridVectorRetriever` 包装语义 + 关键词检索。

### retrieval
- `retrieval.py`：定义 `HybridVectorRetriever` 等组合器，统一管理混合检索的 `as_retriever` 行为。

### pipelines
- `prompts.py`：提供 `DEFAULT_SYSTEM_PROMPT` 与 `DEFAULT_USER_PROMPT`，供 `generate_response` 未自定义时复用。
- `retriever_setup.py`：根据 pack 配置构建混合检索器、工具节点与可选重排序器。
- `agentic_graph.py`：组装“改写 → 检索 → 评分 → 回答” LangGraph，并对评分模型的 JSON 输出进行约束。

### base 与 packs
- `base.py`：`KnowledgePack` 抽象统一管理模型 ID、提示词、检索/嵌入参数、BM25 开关与缓存位置；`KnowledgePackRegistry` 提供注册与实例化能力，并在找不到 Python 类时自动读取 `pack.yaml`。
- `packs/<pack_id>/`：各领域知识库的素材目录，包含 `pack.yaml` 配置、`prompts/*.md` 模板、`knowledge_base/` 文档与 `vector_cache/` 索引。

## 运行流程
1. 在 `config.yaml` 中为 LangGraph 应用指定 `graph_type` 为具体的知识库类型（如 `mouth_cavity_knowledge`）。
2. `AgenticKnowledgeGraph` 子类根据 `GRAPH_TYPE` 自动推导 pack_id，利用注册表实例化 pack，调用其 `build_graph`：
   - `build_resources` 通过 ingestion/preprocessing/stores 准备混合向量库与工具；
   - `build_agentic_state_graph` 根据 prompts + 模型拼装 LangGraph；
   - 返回图实例与检索资源，供流式对话使用。
3. 请求流程中若 `grader_rewrite` 开启且评分模型判定上下文不足，则使用 rewrite 提示改写问题再重新检索；关闭时 `retrieve` 会直接流向回答阶段，避免额外模型调用。

## 自定义知识库步骤
1. 在 `packs/<pack_id>/` 下复制并修改一份 `pack.yaml`：
   - 在 `metadata` 段填写 `pack_id`、展示信息、描述等基础字段；
   - 在 `generate_response` 段指定回答模型 `response_model_key`，并分别提供 `system_prompt`（身份/语气设定）与 `user_prompt`（包含 `{question}`、`{context}` 的回答模板，可指向 Markdown 文件）；
   - 在 `embedding` 段声明 `model_key` 与 `path`（`knowledge_base`、`cache`），确保向量缓存与文档目录均集中管理；
   - 通过 `retrieval.tool` 指定检索工具名称/描述，`retrieval.search_kwargs` 控制 `VectorStore.as_retriever` 的查询参数，`retrieval.hybrid` 用于集中开关 BM25 与父页追溯；
   - 在 `preprocess` 段声明 `remote_urls`，在 `chunking` 段配置 `size/overlap`；
   - 可通过 `retrieval.search_kwargs`、`retrieval.hybrid`（如 `enable_bm25`、`enable_parent_pages`）、`embedding`、`rerank` 等键值覆盖默认检索策略。
2. 将领域文档放入 `<pack_id>/knowledge_base/`，可同时提供 `labels.json` 以标注主题。（后续 `chunking` 段的 `size/overlap` 会统一作用于这些文件）。
3. 在 `prompts/` 目录编写或调整 `user.md`、`rewrite.md`、`grade.md` 等 Markdown 文件；`generate_response.user_prompt` 与 `grader_rewrite` 中的 `rewrite_prompt` / `grade_prompt` 支持引用这些文件，方便策划/法务协作维护。如需单独维护 system prompt，也可以提供独立 Markdown 并在 `generate_response.system_prompt` 中引用。
4. 如需自定义图流程，仍可在 `agentic_knowledge_graph.py` 中创建继承自 `AgenticKnowledgeGraph` 的子类（`GRAPH_TYPE`=`<pack_id>_knowledge`）；否则直接复用默认实现即可。
5. 在 `config.yaml` 中为 LangGraph 应用配置 `graph_type` 为 `<pack_id>_knowledge`，即可启用该知识库。

## 现有知识库概览
- `mouth_cavity_knowledge`（对应 pack: `mouth_cavity`）：术后护理知识，默认调用 `qwen3-flash` 进行改写/评分/回答；基础检索 `k=30`，可按需通过配置调整。
- `sheld_qa_knowledge`（对应 pack: `sheld_qa`）：Sheld QA 常见问题库，复制口腔知识库的配置（`qwen3-flash` + `k=30`），方便快速维护新版资料。
- `disney_tickets_knowledge`（对应 pack: `disney_tickets`）：迪士尼门票规则，默认调用 `qwen3-max`；检索 Top 10 且默认不启用 rerank；配套文档与索引缓存位于 pack 目录下。

## 默认提示与覆写
- 可通过 `retrieval.hybrid.enable_bm25 = False` 关闭关键词检索，仅保留向量检索。
- 全局默认提示在 `pipelines/prompts.py` 中提供，适合无特殊需求的知识库。
- Pack 可通过 `pack.yaml` 中的 `generate_response.system_prompt` / `user_prompt` 自定义回答语调与格式；若需调整 rewrite/grade，可在 `grader_rewrite` 段指定 `rewrite_prompt`、`grade_prompt` 覆盖，确保领域语调与输出格式满足业务要求。

## 历史兼容性
- 旧的 `vectorstore.py` 与 `performance.py` 已移除，请直接引用 `stores/vector_store.py`。`KnowledgePack`、`AgenticKnowledgeGraph` 已完成对新目录结构的适配。

## 更新记录
- 2025-03-18：引入父页检索方案 —— ingestion 阶段为文档补充 `parent_document_id` / `parent_page_content` 元数据，新增 `ParentPageRetriever`，默认保持 `enable_parent_pages=False`，按需在 `KnowledgePack` 或 `KnowledgeBaseConfig` 中打开。


## grader_rewrite 配置

- 在 `pack.yaml` 通过 `grader_rewrite` 段控制评分 + 重写流程，例如：

  ```yaml
  grader_rewrite:
    enabled: true
    grader_model: "qwen3-flash"          # 评分节点使用的模型
    rewrite_model: "qwen3-lite"          # 重写节点使用的模型
    grade_prompt: "prompts/grade.md"     # 可选：覆盖默认模板
    rewrite_prompt: "prompts/rewrite.md"
  ```
- `enabled: false` 时，Agentic RAG 图将移除 `grade_documents`/`rewrite_question`，`retrieve` 执行后直接进入 `generate_answer`，适合对实时性要求更高的场景。
- 通过定制 `grade_prompt`、`rewrite_prompt` 或模型可缩短提示、降低延迟，且无需改 Python 代码。

### grader_rewrite 流程

1. `generate_query_or_respond` 先判断是否需要调用检索工具。
2. 一旦进入 `retrieve`：
   - 若 `grader_rewrite.enabled = true`，`grade_documents` 会根据 `prompts/grade` 判定上下文是否相关，`yes → generate_answer`，`no → rewrite_question`；
   - `rewrite_question` 依据 `prompts/rewrite` 改写问题，再跳回 `generate_query_or_respond` 重新检索。
3. 当 `grader_rewrite` 关闭时，`retrieve` 会直接流向 `generate_answer`，不再触发额外的判分/改写。

因此，`grader_rewrite` 模块承担“检索结果判分 + 必要时重写”的职责，可通过配置灵活启用或禁用，从而在准确率与性能之间取得平衡。
