"""Agentic knowledge graph powered by domain knowledge packs."""

from __future__ import annotations

from pathlib import Path
from typing import AsyncGenerator, Optional

from langgraph.graph import MessagesState

from ..base.base import BaseLangGraph, ContextSchema
from ..base.registry import register_graph
from . import KnowledgePackRegistry


class AgenticKnowledgeGraph(BaseLangGraph):
    """Graph wrapper that routes RAG flows through configured knowledge packs."""

    GRAPH_TYPE = ""

    def __init__(self, app_config, llm_provider, knowledge_base_path: Optional[str] = None):
        if self.GRAPH_TYPE.endswith("_knowledge"):
            self.pack_id = self.GRAPH_TYPE[:-10]
        else:
            raise ValueError(
                f"Graph type '{self.GRAPH_TYPE}' must end with '_knowledge' suffix"
            )
        self.pack = KnowledgePackRegistry.create(self.pack_id)

        # 方案A: 支持动态覆盖文档路径
        if knowledge_base_path:
            input_path = Path(knowledge_base_path)
            storage_root = self.pack.embedding.storage_root  # 🔄 使用新字段名

            # 如果是相对路径且配置了 storage_root，则拼接
            if not input_path.is_absolute() and storage_root:
                new_path = (storage_root / input_path).resolve()
            else:
                new_path = input_path.resolve()

            # 方案B: 自动创建目录（支持空知识库启动）
            if not new_path.exists():
                new_path.mkdir(parents=True, exist_ok=True)
            object.__setattr__(self.pack.embedding, 'dataset_root', new_path)  # 🔄 使用新字段名

        self.retriever_resources = None
        super().__init__(app_config, llm_provider)

    def get_state_class(self) -> type:
        return MessagesState

    def _create_graph(self):
        graph, resources = self.pack.build_graph(self.llm_provider)
        self.retriever_resources = resources
        return graph

    async def stream_chat(
        self, request, app_id: str
    ) -> AsyncGenerator[str, None]:
        langchain_messages = self._convert_request_messages(request)
        device_id = request.user if request.user else "knowledge-user"
        config = {"configurable": {"thread_id": device_id}, "recursion_limit": 25}

        initial_state = {"messages": langchain_messages}

        chunks = self.graph.stream(
            initial_state,
            config,
            stream_mode=["messages"],
            context=ContextSchema(
                model_name=request.model or self.pack.response_model_key,
                app_id=app_id,
                thread_id=device_id,
                config_params=self._extract_config_params(request),
            ),
        )

        try:
            for event, payload in chunks:
                if event != "messages":
                    continue
                message, metadata = payload
                if getattr(message, "type", "") != "AIMessageChunk":
                    continue

                content = message.content
                if isinstance(content, list):
                    text = "".join(
                        part.get("text", "")
                        for part in content
                        if isinstance(part, dict) and part.get("type") == "text"
                    )
                else:
                    text = content or ""

                if text:
                    yield text

                usage = getattr(message, "usage_metadata", None)
                if usage:
                    yield f"__USAGE__{usage}__USAGE__"
        except Exception as exc:  # noqa: BLE001
            self.logger.error(f"Knowledge graph streaming error: {exc}", exc_info=True)
            yield "抱歉，知识库查询失败，请稍后再试。"


@register_graph
class SheldQaKnowledge(AgenticKnowledgeGraph):
    """Sheld QA 知识库."""

    GRAPH_TYPE = "sheld_qa_knowledge"
