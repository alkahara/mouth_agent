"""Compilation helpers for the agentic RAG state graph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import logging
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.retrievers import BaseRetriever
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class GradeDocuments(BaseModel):
    """Structured output schema used by the grader model."""

    binary_score: str = Field(
        description="Relevance decision using 'yes' for relevant and 'no' for irrelevant documents."
    )


def build_agentic_state_graph(
    *,
    response_model: BaseChatModel,
    grader_model: BaseChatModel | None,
    system_prompt: str,
    user_prompt: str,
    retriever_tool,
    grader_rewrite: GraderRewriteRuntimeConfig,
    use_llm_intent_query_retrieval: bool = True,
    base_retriever: Optional[BaseRetriever] = None,
) -> any:
    """Compile the agentic RAG graph using the supplied models and prompts."""

    def generate_query_or_respond(state: MessagesState):
        response = response_model.bind_tools([retriever_tool]).invoke(state["messages"])
        return {"messages": [response]}

    rewrite_llm = grader_rewrite.rewrite_model or response_model

    if grader_rewrite.enabled and grader_model is None:
        raise ValueError("grader_model must be provided when grader_rewrite is enabled")
    if grader_rewrite.enabled and (
        not grader_rewrite.rewrite_prompt or not grader_rewrite.grade_prompt
    ):
        raise ValueError("rewrite_prompt and grade_prompt are required when grader_rewrite is enabled")

    if grader_rewrite.enabled:

        def grade_documents(
            state: MessagesState,
        ) -> Literal["generate_answer", "rewrite_question"]:
            question = state["messages"][0].content
            context = state["messages"][-1].content
            prompt = (
                grader_rewrite.grade_prompt.format(question=question, context=context)  # type: ignore[union-attr]
                + '\n请以 JSON 格式回复，例如 {"binary_score": "yes"}。'
            )
            score = (
                grader_model.with_structured_output(GradeDocuments)  # type: ignore[union-attr]
                .invoke([{"role": "user", "content": prompt}])
                .binary_score
            )
            return "generate_answer" if score.lower() == "yes" else "rewrite_question"

        def rewrite_question(state: MessagesState):
            question = state["messages"][0].content
            prompt = grader_rewrite.rewrite_prompt.format(question=question)  # type: ignore[union-attr]
            response = rewrite_llm.invoke([{"role": "user", "content": prompt}])
            return {"messages": [HumanMessage(content=response.content)]}

    def generate_answer(state: MessagesState):
        from langchain_core.messages import SystemMessage

        messages_list = state["messages"]

        # 🔄 检查是否有外部传入的 SystemMessage（支持 Sheld 后端传入）
        external_system = None
        user_messages = []

        for msg in messages_list:
            if isinstance(msg, SystemMessage):
                external_system = msg.content
            elif hasattr(msg, 'type') and msg.type in ('human', 'user'):
                user_messages.append(msg.content)

        # 使用外部 system prompt（如果有），否则使用配置的 system_prompt
        system_content = external_system if external_system else system_prompt
        if external_system:
            # 记录外部传入的 system prompt 以便排查
            logger.info(
                "Using external system prompt from request (truncated to 300 chars): %s",
                external_system[:300],
            )

        # 提取问题和上下文
        # 第一条 user message 是问题，最后一条是检索到的上下文
        if len(user_messages) >= 2:
            question = user_messages[0]
            context = user_messages[-1]
        elif len(user_messages) == 1:
            # 如果只有一条消息，可能是直接回答模式
            question = user_messages[0]
            context = messages_list[-1].content if messages_list else ""
        else:
            # 兼容旧逻辑
            question = messages_list[0].content if messages_list else ""
            context = messages_list[-1].content if len(messages_list) > 1 else ""

        # 格式化 user prompt
        prompt_text = user_prompt.format(question=question, context=context)

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt_text},
        ]
        response = response_model.invoke(messages)
        return {"messages": [response]}

    workflow = StateGraph(MessagesState)
    workflow.add_node("generate_answer", generate_answer)

    if use_llm_intent_query_retrieval:
        workflow.add_node("generate_query_or_respond", generate_query_or_respond)
        workflow.add_node("retrieve", ToolNode([retriever_tool]))

        workflow.add_edge(START, "generate_query_or_respond")
        workflow.add_conditional_edges(
            "generate_query_or_respond",
            tools_condition,
            {"tools": "retrieve", END: END},
        )
        if grader_rewrite.enabled:
            workflow.add_node("rewrite_question", rewrite_question)
            workflow.add_conditional_edges("retrieve", grade_documents)
            workflow.add_edge("rewrite_question", "generate_query_or_respond")
        else:
            workflow.add_edge("retrieve", "generate_answer")
    else:
        if base_retriever is None:
            raise ValueError(
                "base_retriever is required when use_llm_intent_query_retrieval is False"
            )

        def direct_retrieve(state: MessagesState):
            question = state["messages"][0].content
            try:
                docs = None
                # 优先使用 invoke，兼容只实现 Runnable 接口的检索器
                if hasattr(base_retriever, "invoke"):
                    try:
                        docs = base_retriever.invoke(question)  # type: ignore[arg-type]
                    except TypeError:
                        docs = base_retriever.invoke({"query": question})  # type: ignore[arg-type]
                elif hasattr(base_retriever, "get_relevant_documents"):
                    docs = base_retriever.get_relevant_documents(question)  # type: ignore[arg-type]
                else:
                    docs = base_retriever(question)  # type: ignore[call-arg]
            except Exception as exc:  # pragma: no cover - retriever runtime failure
                context_text = f"检索失败：{exc}"
            else:
                if not docs:
                    context_text = "未检索到相关内容。"
                else:
                    if isinstance(docs, dict):
                        docs = docs.get("documents") or docs.get("docs") or []
                    context_text = "\n\n".join(
                        doc.page_content for doc in docs if getattr(doc, "page_content", "")
                    )
            return {"messages": [HumanMessage(content=context_text)]}

        workflow.add_node("direct_retrieve", direct_retrieve)
        workflow.add_edge(START, "direct_retrieve")
        workflow.add_edge("direct_retrieve", "generate_answer")

    workflow.add_edge("generate_answer", END)

    return workflow.compile()


@dataclass(slots=True)
class GraderRewriteRuntimeConfig:
    enabled: bool = False
    rewrite_model: BaseChatModel | None = None
    rewrite_prompt: str | None = None
    grade_prompt: str | None = None


__all__ = ["GradeDocuments", "GraderRewriteRuntimeConfig", "build_agentic_state_graph"]
