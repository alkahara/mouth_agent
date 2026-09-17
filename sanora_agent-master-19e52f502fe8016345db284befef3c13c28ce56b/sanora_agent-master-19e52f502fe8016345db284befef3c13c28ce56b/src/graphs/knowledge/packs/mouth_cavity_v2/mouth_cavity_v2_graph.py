"""
口腔术后出血分诊图V2 - Manager-Operator 架构

重构版本：使用 Manager-Operator 模式替代硬编码决策逻辑。
支持异步多并发，使用 MemorySaver 实现多用户槽位隔离。
"""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from ...agentic_knowledge_graph import AgenticKnowledgeGraph
from ....base import ContextSchema, register_graph
from src.models import RiskLevel

# 导入新的核心组件
from .core import (
    AgentInvariants,
    FlowRegistry,
    MouthCavityV2State,
    merge_slots,
)

# 导入节点
from .nodes.manager_node import manager_node, route_decision
from .nodes.intent_router_node import intent_router_node, route_intent

# 导入 Operators
from .operators.ask_slot_operator import ask_slot_operator
from .operators.rag_operator import rag_operator
from .operators.final_operator import final_operator
from .operators.emergency_operator import emergency_operator
from .operators.fallback_operator import fallback_operator
from .operators.general_responder_operator import general_responder_operator

# 导入流程（触发注册）
from .flows import bleeding_flow  # noqa: F401


@register_graph
class MouthCavityV2Knowledge(AgenticKnowledgeGraph):
    """
    口腔术后助手知识库V2 - Manager-Operator 架构

    使用三层架构：
    1. Agent 宪法（框架层拦截紧急情况）
    2. Manager 判断节点（LLM 决策）
    3. Operator 执行层（执行具体任务）
    
    支持异步多并发：
    - 使用进程内 MemorySaver 保存对话状态
    - 每个用户通过 device_id (thread_id) 隔离状态
    - 槽位收集互不干扰
    """

    GRAPH_TYPE = "mouth_cavity_v2_knowledge"

    def __init__(self, app_config, llm_provider):
        super().__init__(app_config, llm_provider)
        self._checkpointer = MemorySaver()

    def get_state_class(self) -> type:
        return MouthCavityV2State

    def _create_workflow(self) -> StateGraph:
        """创建 Manager-Operator 架构的 Workflow（未编译）"""
        # 创建 StateGraph
        workflow = StateGraph(MouthCavityV2State)

        # ================================================================
        # 添加节点
        # ================================================================
        workflow.add_node("intent_router", intent_router_node)
        workflow.add_node("general_responder", general_responder_operator)
        workflow.add_node("manager", manager_node)
        workflow.add_node("ask_slot", ask_slot_operator)
        workflow.add_node("rag", rag_operator)
        workflow.add_node("final", final_operator)
        workflow.add_node("emergency", emergency_operator)
        workflow.add_node("fallback", fallback_operator)

        # ================================================================
        # 添加边
        # ================================================================
        # 入口 -> Intent Router
        workflow.add_edge(START, "intent_router")

        # Intent Router -> 条件路由
        workflow.add_conditional_edges(
            "intent_router",
            route_intent,
            {
                "general_responder": "general_responder",
                "manager": "manager",
            },
        )

        # General Responder -> END
        workflow.add_edge("general_responder", END)

        # Manager -> 条件路由
        workflow.add_conditional_edges(
            "manager",
            route_decision,
            {
                "ask_slot": "ask_slot",
                "rag": "rag",
                "risk_assessment": "final",  # 风险评估直接到 final
                "final": "final",
                "emergency": "emergency",
                "fallback": "fallback",
            },
        )

        # Operators -> END
        workflow.add_edge("ask_slot", END)
        workflow.add_edge("rag", END)
        workflow.add_edge("final", END)
        workflow.add_edge("emergency", END)
        workflow.add_edge("fallback", END)

        return workflow

    def _create_graph(self):
        """创建编译后的 Graph（仅用于初始化日志打印，无 checkpointer）"""
        # 构建 retriever 资源（只在初始化时执行一次）
        from ...pipelines.retriever_setup import build_retriever_resources

        retriever_setup = self.pack.build_resources()
        self.retriever_resources = build_retriever_resources(retriever_setup)

        workflow = self._create_workflow()
        # 不传 checkpointer，仅用于打印图结构
        compiled_graph = workflow.compile()
        self._log_graph_structure(compiled_graph)
        return compiled_graph

    def _log_graph_structure(self, compiled_graph):
        """打印 Graph 结构"""
        raw_graph_getter = getattr(compiled_graph, "get_graph", None)
        if callable(raw_graph_getter):
            try:
                raw_graph = raw_graph_getter()
                mermaid_draw = getattr(raw_graph, "draw_mermaid", None)
                if callable(mermaid_draw):
                    mermaid_text = mermaid_draw()
                    self.logger.info("MouthCavityV2 Manager-Operator Graph:\n%s", mermaid_text)
            except Exception as exc:
                self.logger.warning("Failed to dump workflow graph: %s", exc)

    async def stream_chat(self, request, app_id: str) -> AsyncGenerator[str, None]:
        """
        流式对话 - 异步多并发版本

        使用 MemorySaver 支持多用户槽位隔离，服务重启后状态清空。
        """
        langchain_messages = self._convert_request_messages(request)
        # 优先使用 thread_id，fallback 到 user
        thread_id = getattr(request, "thread_id", None) or request.user or "mouth-cavity-user"
        debug_mode = getattr(request, "debug_mode", False)

        async with nullcontext(self._checkpointer) as checkpointer:
            try:
                async with self._manage_task(thread_id):
                    # 每次请求时动态编译 graph
                    workflow = self._create_workflow()
                    graph = workflow.compile(checkpointer=checkpointer)

                    graph_config = {
                        "configurable": {"thread_id": thread_id},
                        "recursion_limit": 25,
                    }

                    # 尝试加载已有状态
                    existing_slots = {}
                    try:
                        state = await graph.aget_state(graph_config)
                        if state.values:
                            existing_slots = state.values.get("slots", {})
                            if existing_slots:
                                self.logger.debug(f"📦 恢复槽位状态: {list(existing_slots.keys())}")
                    except ValueError as e:
                        if "Message dict must contain" in str(e):
                            self.logger.warning(f"⚠️ 检测到损坏的 checkpoint，清理后重试: {e}")
                        else:
                            raise

                    # 初始化状态
                    initial_state: MouthCavityV2State = {
                        "messages": langchain_messages,
                        "debug_mode": debug_mode,
                    }

                    # 如果有历史槽位，合并到初始状态
                    if existing_slots:
                        initial_state["slots"] = existing_slots

                    # 创建上下文
                    context = ContextSchema(
                        model_name=request.model or self.app_config.model_provider,
                        app_id=app_id,
                        thread_id=thread_id,
                        config_params=self._extract_config_params(request),
                    )

                    # 将 LLM 注入到 context（供 Manager 和 Operators 使用）
                    context.llm = self.llm_provider.get_client(
                        request.model or self.app_config.model_provider
                    )

                    # 将 RAG 资源注入到 context（供 Operators 使用）
                    if hasattr(self, "retriever_resources"):
                        context.retriever = getattr(self.retriever_resources, "retriever", None)

                    # 将 logger 注入到 context
                    context.logger = self.logger

                    # 注入 get_node_llm 方法（供 Operators 调用 LLM）
                    context.get_node_llm = self._get_node_llm

                    # 使用 ainvoke 执行 Graph，获取完整的最终状态
                    # 获取当前活跃的 span (来自 FastAPI Instrumentor)
                    current_span = trace.get_current_span()
                    try:
                        final_state = await graph.ainvoke(
                            initial_state,
                            graph_config,
                            context=context,
                        )
                        # 执行成功，设置根 span 状态为 OK
                        if current_span.is_recording():
                            current_span.set_status(Status(StatusCode.OK))
                    except Exception as e:
                        # 执行失败，设置根 span 状态为 ERROR
                        if current_span.is_recording():
                            current_span.record_exception(e)
                            current_span.set_status(Status(StatusCode.ERROR, str(e)))
                        raise

                    # 从最终状态中提取消息
                    messages = final_state.get("messages", [])
                    slots = final_state.get("slots", {})

                    # Debug 模式：先输出槽位更新
                    if debug_mode and slots:
                        slot_status = {
                            k: v.get("value") for k, v in slots.items() if v.get("value")
                        }
                        if slot_status:
                            self.logger.info(f"[DEBUG] 最终槽位状态: {slot_status}")
                            yield {
                                "text": "",
                                "additional_kwargs": {"slot_update": slot_status},
                            }

                    # 找到最后一条 AIMessage（来自 Operator）
                    final_response = None
                    for msg in reversed(messages):
                        if isinstance(msg, AIMessage):
                            final_response = msg
                            break

                    if final_response:
                        content = getattr(final_response, "content", "")
                        if isinstance(content, list):
                            text = "".join(
                                part.get("text", "")
                                for part in content
                                if isinstance(part, dict) and part.get("type") == "text"
                            )
                        else:
                            text = content or ""

                        payload_dict: Dict[str, Any] = {}
                        if text:
                            payload_dict["text"] = text

                        additional = getattr(final_response, "additional_kwargs", None) or {}
                        if additional:
                            payload_dict["additional_kwargs"] = additional

                        if payload_dict:
                            yield payload_dict
                    else:
                        # 没有找到 AIMessage，返回兜底消息
                        yield {"text": "抱歉，暂时无法处理您的问题，请稍后再试。"}

            except asyncio.CancelledError:
                self.logger.info(f"❌ 任务被取消: {thread_id}")
                return
            except GeneratorExit:
                self.logger.info(f"🛑 生成器被外部关闭: {thread_id}")
                return
            except Exception as exc:
                self.logger.error(
                    "MouthCavityV2Knowledge streaming error: %s", exc, exc_info=True
                )
                yield {"text": "抱歉，口腔助手暂时无法提供服务，请稍后再试。"}

    def _convert_request_messages(self, request) -> List[AnyMessage]:
        """转换请求消息为 LangChain 消息格式"""
        messages = []
        for msg in request.messages:
            if msg.role.value == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role.value == "assistant":
                messages.append(AIMessage(content=msg.content))
        return messages

    def _extract_config_params(self, request) -> Dict[str, Any]:
        """提取配置参数"""
        params = {}
        if hasattr(request, "debug_mode"):
            params["debug_mode"] = request.debug_mode
        return params
