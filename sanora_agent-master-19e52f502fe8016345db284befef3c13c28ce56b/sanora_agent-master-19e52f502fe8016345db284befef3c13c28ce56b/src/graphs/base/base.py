"""
Base classes for LangGraph implementations
"""

from dataclasses import dataclass, field
import uuid
import os
import json
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, Optional, List, Union
from typing_extensions import TypedDict, Annotated
from datetime import datetime
import asyncio
from contextlib import asynccontextmanager

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from src.config import LangGraphAppConfig
from src.models import ChatRequest, Message, MessageRole

from src.logging_config import LoggingConfig
import logging

from pathlib import Path


class BaseState(TypedDict):
    """Base state for all LangGraph implementations"""

    messages: Annotated[List[AnyMessage], add_messages]
    # Memory相关字段
    device_id: Optional[str]
    user_id: Optional[str]


@dataclass
class ContextSchema:
    model_name: str
    app_id: str
    thread_id: Optional[str]
    config_params: Dict[str, Any]


class BaseLangGraph(ABC):
    """Base class for LangGraph implementations"""

    GRAPH_TYPE: str = None

    def __init__(self, app_config: LangGraphAppConfig, llm_provider):
        if self.GRAPH_TYPE is None:
            raise ValueError(f"{self.__class__.__name__} must define GRAPH_TYPE")

        self.app_config = app_config
        self.llm_provider = llm_provider
        self.skills = []
        # 获取图实现类所在目录
        import inspect

        graph_module = inspect.getfile(self.__class__)
        graph_dir = os.path.dirname(graph_module)

        # 初始化节点模型管理器，传入图目录
        from .node_model_config import NodeModelManager

        self.node_model_manager = NodeModelManager(self.GRAPH_TYPE, graph_dir)

        # 配置图专用日志记录器
        self.logger = self._setup_logger()

        # 加载该图目录下的 skills
        self._load_graph_skills(graph_dir)

        self.graph = self._create_graph()

        self.logger.info(
            f"Initialized {self.__class__.__name__} for app {app_config.name}"
        )

        # 添加任务管理字典：thread_id -> asyncio.Task
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._task_lock = asyncio.Lock()

    async def cancel_task(self, thread_id: str) -> bool:
        """
        取消指定线程ID的任务

        Args:
            thread_id: 线程/会话ID

        Returns:
            bool: 如果成功取消返回True，否则返回False
        """
        task = self._active_tasks.get(thread_id)
        if task and not task.done():
            self.logger.info(f"正在取消会话任务: {thread_id}")
            task.cancel()

            # ✅ 关键修改: 不等待任务完成，让它在后台自行清理
            # 这样可以避免与 LangGraph 的 cancel scope 冲突
            self._active_tasks.pop(thread_id, None)

            # 给一个短暂的延迟，让取消信号传播
            await asyncio.sleep(0.05)

            self.logger.info(f"会话任务取消信号已发送: {thread_id}")
            return True
        return False

    @asynccontextmanager
    async def _manage_task(self, thread_id: str):
        """管理任务生命周期的上下文管理器 - 改进版本"""
        # 如果存在相同thread_id的旧任务，先取消
        await self.cancel_task(thread_id)

        # 注册当前任务
        current_task = asyncio.current_task()
        self._active_tasks[thread_id] = current_task

        try:
            yield current_task
        except asyncio.CancelledError:
            self.logger.info(f"任务被取消: {thread_id}")
            # 不重新抛出，让生成器正常退出
        except GeneratorExit:
            self.logger.info(f"生成器被关闭: {thread_id}")
        except Exception as e:
            # 捕获其他异常，包括 LangGraph 的嵌套 CancelledError
            error_str = str(e)
            if (
                "CancelledError" in str(type(e).__name__)
                or "Cancelled by cancel scope" in error_str
            ):
                self.logger.info(f"检测到 LangGraph cancel scope 异常: {thread_id}")
            else:
                raise
        finally:
            # 清理任务引用
            self._active_tasks.pop(thread_id, None)

    async def cleanup_finished_tasks(self):
        """清理已完成的任务（可选的定期清理）"""
        finished = [tid for tid, task in self._active_tasks.items() if task.done()]
        for tid in finished:
            self._active_tasks.pop(tid, None)
        if finished:
            self.logger.debug(f"清理了 {len(finished)} 个已完成的任务")

    def _setup_logger(self) -> logging.Logger:
        """设置图专用的日志记录器"""
        return LoggingConfig.get_graph_logger(self.GRAPH_TYPE, self.__class__.__name__)

    def _load_graph_skills(self, graph_dir: str) -> None:
        """加载该图目录下的 skills

        Args:
            graph_dir: 图实现类所在目录的绝对路径

        目录结构：
        graph_dir/
        ├── skills/
        │   ├── search/
        │   │   └── SKILL.md
        │   ├── order/
        │   │   └── SKILL.md
        │   └── ...
        """
        from .skill.skill_loader import SkillLoader

        skills_dir = Path(graph_dir) / "skills"

        if not skills_dir.exists():
            self.logger.info(f"图 {self.GRAPH_TYPE} 没有 skills 目录: {skills_dir}")
            return

        # 设置该图专属的 skills 目录并初始化
        SkillLoader.set_skills_dir(skills_dir)
        SkillLoader.initialize(skills_dir)

        # 加载所有 skill 元数据
        skill_metas = SkillLoader.list_skills()
        self.skills = skill_metas

        if skill_metas:
            skill_names = [meta.name for meta in skill_metas]
            self.logger.info(
                f"✅ 图 {self.GRAPH_TYPE} 加载了 {len(skill_metas)} 个 SKILL: {', '.join(skill_names)}"
            )
        else:
            self.logger.info(f"图 {self.GRAPH_TYPE} 的 skills 目录为空")

    def _load_prompts(
        self, prompt_files: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """从图内部的 prompts 目录加载 prompt 模板

        Args:
            prompt_files: 可选的prompt文件名映射字典，格式为 {key: filename}
                         如果不提供，子类需要传入或覆盖此方法

        Returns:
            Dict[str, str]: 加载的prompt模板字典

        约定：每个图的提示词文件存放在图目录下的 prompts 子目录中
        例如：src/graphs/router_graph/prompts/intent.md
        """
        # 获取当前图类文件所在目录
        import inspect

        graph_module = inspect.getfile(self.__class__)
        graph_dir = os.path.dirname(graph_module)

        # prompts 目录在图目录下
        prompts_dir = os.path.join(graph_dir, "prompts")

        prompts = {}

        if prompt_files is None:
            self.logger.info(
                f"No prompt files specified for {self.GRAPH_TYPE}, returning empty dict"
            )
            return prompts

        for key, filename in prompt_files.items():
            file_path = os.path.join(prompts_dir, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    prompts[key] = f.read().strip()
                self.logger.debug(f"Loaded prompt '{key}' from {file_path}")
            except FileNotFoundError:
                self.logger.warning(f"Prompt file not found: {file_path}")
                prompts[key] = ""
            except Exception as e:
                self.logger.error(f"Error loading prompt {key}: {e}")
                prompts[key] = ""

        self.logger.info(
            f"Loaded {len([p for p in prompts.values() if p])} prompts for {self.GRAPH_TYPE}"
        )
        return prompts

    def _convert_request_messages(self, request: ChatRequest) -> List[Any]:
        """将 ChatRequest 的消息转换为 LangChain 格式"""
        langchain_messages = []
        for msg in request.messages:
            if msg.role == MessageRole.SYSTEM:
                langchain_messages.append(SystemMessage(content=msg.content))
            elif msg.role == MessageRole.USER:
                langchain_messages.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.ASSISTANT:
                langchain_messages.append(AIMessage(content=msg.content))
            else:
                # 保持字典格式用于其他类型
                langchain_messages.append({"role": msg.role, "content": msg.content})
        return langchain_messages

    def _get_node_llm(self, node_name: str, runtime, fallback_provider: str = None):
        """为指定节点获取LLM客户端"""
        # 获取节点专属的模型提供者，如果没有则使用运行时模型或fallback
        node_provider = self.node_model_manager.get_model_provider(
            node_name, fallback_provider or runtime.context.model_name
        )

        # 获取LLM客户端
        llm = self.llm_provider.get_client(node_provider)
        if not llm:
            # 如果节点专属模型不可用，回退到默认模型
            self.logger.warning(
                f"Model {node_provider} not available for node {node_name}, falling back to {runtime.context.model_name}"
            )
            llm = self.llm_provider.get_client(runtime.context.model_name)
            if not llm:
                raise ValueError(f"No available model for node {node_name}")

        # 应用请求级别的配置参数
        self._apply_llm_params(llm, runtime.context.config_params)

        # 应用节点级别的模型参数
        node_params = self.node_model_manager.get_model_params(node_name)
        if node_params:
            self._apply_llm_params(llm, node_params)

        # 结合上下文进行微调（不会覆盖显式节点配置，除非未设置）
        tuned = self._tune_params_by_state(node_name, runtime)
        for k, v in tuned.items():
            if hasattr(llm, k) and getattr(llm, k, None) is None and v is not None:
                setattr(llm, k, v)

        if self.node_model_manager.has_node_config(node_name):
            self.logger.debug(
                f"Node '{node_name}' using model: {node_provider} with params: {node_params}"
            )
        else:
            self.logger.debug(
                f"Node '{node_name}' using default model: {node_provider}"
            )

        return llm

    @abstractmethod
    def _create_graph(self) -> StateGraph:
        """Create the graph - must be implemented by subclasses"""
        pass

    @abstractmethod
    async def stream_chat(
        self, request: ChatRequest, app_id: str
    ) -> AsyncGenerator[str, None]:
        """Stream chat response - must be implemented by subclasses"""
        pass

    @abstractmethod
    def get_state_class(self) -> type:
        """Return the state class used by this graph"""
        pass

    def _extract_config_params(self, request: ChatRequest) -> Dict[str, Any]:
        """Extract configuration parameters from request"""
        params = {}
        if request.max_tokens is not None:
            params["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            params["temperature"] = request.temperature
        if request.top_p is not None:
            params["top_p"] = request.top_p
        if request.frequency_penalty is not None:
            params["frequency_penalty"] = request.frequency_penalty
        if request.presence_penalty is not None:
            params["presence_penalty"] = request.presence_penalty

        # 提取 debug_mode（使用 getattr 更安全）
        debug_mode = getattr(request, 'debug_mode', False)
        params["debug_mode"] = debug_mode
        self.logger.info(
            f"[EXTRACT_CONFIG] debug_mode extracted: {debug_mode} (type: {type(debug_mode)})"
        )
        self.logger.info(
            f"[EXTRACT_CONFIG] request.debug_mode raw value: {repr(request.debug_mode)}"
        )
        self.logger.info(f"[EXTRACT_CONFIG] request dict: {request.dict()}")

        return params

    def _apply_llm_params(self, llm, config_params: Dict[str, Any]):
        """Apply configuration parameters to LLM instance"""
        if config_params:
            for param, value in config_params.items():
                if hasattr(llm, param) and value is not None:
                    setattr(llm, param, value)

    def _tune_params_by_state(self, node_name: str, runtime) -> Dict[str, Any]:
        """根据上下文状态对模型参数做小幅动态调节，降低不稳定性"""
        params: Dict[str, Any] = {}
        try:
            if node_name in {
                "intent",
                "search_node",
                "order_node",
                "queue_node",
                "nav_node",
                "plan_node",
                "manager_node",
            }:
                params["temperature"] = 0.1
                params["top_p"] = 0.4
            elif node_name in {"search_human", "order_human", "nav_human", "chitchat"}:
                params["temperature"] = 0.6 if node_name != "chitchat" else 0.8
                params["top_p"] = 0.8 if node_name != "chitchat" else 0.9
            elif node_name == "output":
                params["temperature"] = 0.3
                params["top_p"] = 0.7
        except Exception:
            pass
        return params

    def get_system_message(self) -> str:
        """Get system message for this graph

        Try to load from prompts/{graph_type}.md file first,
        fallback to default message if file doesn't exist.
        """
        try:
            # Get the project root directory (assuming it's 2 levels up from this file)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))

            # Construct the prompt file path
            prompt_file = os.path.join(project_root, "prompts", f"{self.GRAPH_TYPE}.md")

            # Try to read the prompt file
            if os.path.exists(prompt_file):
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                if content:
                    self.logger.debug(f"Loaded system message from {prompt_file}")
                    return content
                else:
                    self.logger.warning(f"Prompt file {prompt_file} is empty")
            else:
                self.logger.debug(
                    f"Prompt file {prompt_file} not found, using default message"
                )

        except Exception as e:
            self.logger.warning(
                f"Failed to load prompt file for {self.GRAPH_TYPE}: {e}"
            )

        # Fallback to default message
        return f"You are {self.app_config.name}: {self.app_config.description}"

    def draw_graph(self):
        """Draw the graph to a file (e.g., PNG or SVG)"""
        try:
            png_bytes = self.graph.get_graph().draw_mermaid_png()
            with open(f"{self.GRAPH_TYPE}.png", "wb") as f:
                f.write(png_bytes)
        except Exception:
            # This requires some extra dependencies and is optional
            pass

    @classmethod
    def get_graph_type(cls) -> str:
        """Get the graph type identifier"""
        return cls.GRAPH_TYPE
