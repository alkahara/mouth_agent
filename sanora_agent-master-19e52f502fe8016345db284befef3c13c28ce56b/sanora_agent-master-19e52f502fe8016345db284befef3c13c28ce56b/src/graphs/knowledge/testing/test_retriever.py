#!/usr/bin/env python
"""测试 shelad_qa 检索器"""

from pathlib import Path
from langchain_community.vectorstores import FAISS
from src.graphs.knowledge.stores.vector_store import create_embeddings

# 加载向量存储
cache_dir = Path("/Users/hogetsu/agent_dev/repos/rooyee_agent/src/graphs/knowledge/packs/sheld_qa/vector_cache")
embedding_model = create_embeddings("text-embedding-v4")

print("正在加载向量存储...")
vectorstore = FAISS.load_local(
    str(cache_dir),
    embedding_model,
    allow_dangerous_deserialization=True,
    index_name="faiss_index"
)

print(f"向量存储加载成功，包含 {vectorstore.index.ntotal} 个向量\n")

# 测试查询
query = "上海迪士尼酒店会员制度"
print(f"查询: {query}\n")

# 使用相似度搜索
results = vectorstore.similarity_search_with_score(query, k=5)

print(f"找到 {len(results)} 个相关文档:\n")
for i, (doc, score) in enumerate(results, 1):
    source = doc.metadata.get('source', 'Unknown')
    print(f"文档 {i} (相似度分数: {score:.4f}):")
    print(f"  来源: {source}")
    print(f"  内容: {doc.page_content[:200]}...")
    print()
