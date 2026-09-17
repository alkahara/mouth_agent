#!/usr/bin/env python
"""调试 shelad_qa 图构建"""

import traceback
from src.graphs.knowledge.config_loader import build_pack_from_config
from src.llm_service import LLMProvider
from src.config import load_config

# 加载配置
config = load_config()
llm_provider = LLMProvider(config.models)

# 加载 pack
print("加载 pack 配置...")
pack = build_pack_from_config("sheld_qa")
print(f"Pack 加载成功: {pack.metadata.display_name}\n")

try:
    print("构建图...")
    graph, resources = pack.build_graph(llm_provider)
    print("图构建成功!")
    print(f"Retriever tool: {resources.retriever_tool}")
except Exception as e:
    print(f"\n错误: {e}")
    traceback.print_exc()
