#!/usr/bin/env python
"""完整模拟服务器初始化"""

import traceback
from src.config import config
from src.llm_service import LLMProvider
from src.graphs import GraphRegistry

# 初始化 LLM Provider
print("初始化 LLMProvider...")
llm_provider = LLMProvider()

# 获取 shelad_qa 的配置
enabled_apps = config.list_enabled_langgraph_apps()
sheld_qa_config = enabled_apps.get("sheld_qa_graph")

if sheld_qa_config is None:
    print("shelad_qa_graph 未启用或未找到")
else:
    print(f"\nApp config:")
    print(f"  Name: {sheld_qa_config.name}")
    print(f"  Graph type: {sheld_qa_config.graph_type}")
    print(f"  Model provider: {sheld_qa_config.model_provider}")

    try:
        print("\n直接实例化图类...")
        from src.graphs.agentic_knowledge_graph import SheldQaKnowledge
        graph = SheldQaKnowledge(sheld_qa_config, llm_provider)
        print(f"图创建成功: {type(graph)}")
    except Exception as e:
        print(f"\n错误: {e}")
        traceback.print_exc()
