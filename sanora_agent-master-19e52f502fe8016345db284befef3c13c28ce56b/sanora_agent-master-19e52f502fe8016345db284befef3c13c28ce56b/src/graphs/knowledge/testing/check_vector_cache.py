#!/usr/bin/env python
"""检查向量缓存中的文档内容"""

import pickle
from pathlib import Path

vector_cache_path = Path("/Users/hogetsu/agent_dev/repos/rooyee_agent/src/graphs/knowledge/packs/sheld_qa/vector_cache/faiss_index.pkl")

with open(vector_cache_path, "rb") as f:
    data = pickle.load(f)

print(f"向量缓存数据类型: {type(data)}")

if isinstance(data, tuple):
    print(f"Tuple 长度: {len(data)}")

    # 第一个元素应该是 InMemoryDocstore
    if len(data) > 0:
        docstore = data[0]
        print(f"\nDocstore 类型: {type(docstore)}")
        if hasattr(docstore, '_dict'):
            docs = docstore._dict
            print(f"文档数量: {len(docs)}")
            print("\n文档来源列表:")
            for doc_id, doc in list(docs.items())[:10]:  # 只显示前10个
                source = doc.metadata.get('source', 'Unknown')
                content_preview = doc.page_content[:100] if hasattr(doc, 'page_content') else 'N/A'
                print(f"  - {source}")
                print(f"    内容预览: {content_preview}...")

            # 检查是否包含 DOCX 文件
            docx_docs = [doc for doc_id, doc in docs.items() if '上海迪士尼乐园酒店会员制度' in doc.metadata.get('source', '')]
            print(f"\n包含 '上海迪士尼乐园酒店会员制度' 的文档数量: {len(docx_docs)}")
            if docx_docs:
                print("\nDOCX 文档详情:")
                for doc in docx_docs[:3]:
                    print(f"  内容: {doc.page_content[:200]}...")
