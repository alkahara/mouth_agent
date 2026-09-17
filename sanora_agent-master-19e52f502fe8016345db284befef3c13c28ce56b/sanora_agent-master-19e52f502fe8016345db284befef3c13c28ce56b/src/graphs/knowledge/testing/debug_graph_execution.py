#!/usr/bin/env python
"""调试图执行流程"""

from src.config import config
from src.llm_service import LLMProvider
from src.graphs.knowledge.config_loader import build_pack_from_config
from langchain_core.messages import HumanMessage

# 初始化
llm_provider = LLMProvider()
pack = build_pack_from_config("sheld_qa")
graph, resources = pack.build_graph(llm_provider)

print("构建图成功")
print(f"Retriever tool: {resources.retriever_tool.name}")
print(f"Retriever description: {resources.retriever_tool.description}")

# 测试执行
query = "上海迪士尼酒店会员制度"
print(f"\n查询: {query}\n")

initial_state = {"messages": [HumanMessage(content=query)]}
print("开始执行图...")

# 跟踪执行
for event in graph.stream(initial_state, {"recursion_limit": 25}):
    print(f"\n=== Event ===")
    for node_name, node_data in event.items():
        print(f"Node: {node_name}")
        if "messages" in node_data:
            for msg in node_data["messages"]:
                print(f"  Type: {type(msg).__name__}")
                print(f"  Content: {str(msg.content)[:200]}...")
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    print(f"  Tool calls: {msg.tool_calls}")
                if hasattr(msg, "additional_kwargs"):
                    print(f"  Additional kwargs: {msg.additional_kwargs}")
