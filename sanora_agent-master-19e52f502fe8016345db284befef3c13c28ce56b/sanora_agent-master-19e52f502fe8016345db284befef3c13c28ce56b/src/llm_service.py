import asyncio
import httpx
import json
import uuid
from typing import AsyncGenerator, Dict, Any, Optional, Tuple
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import logging
import ssl

from .config import config, LangGraphAppConfig
from .models import ChatRequest, Message, MessageRole
from .graphs import GraphRegistry, BaseLangGraph

logger = logging.getLogger(__name__)

# 模型别名映射表：将前端友好名称映射到 config.yaml 中的 key
# Sheld 前端可以传入左边的值，后端会自动映射到右边的 config key
MODEL_ALIAS_MAP = {
    # Qwen 系列 - 商业计划书默认使用 qwen3-max
    "qwen": "qwen3-max",
    "qwen-plus": "qwen3-max",
    "qwen3": "qwen3",
    "qwen-flash": "qwen3-flash",
    "qwen3-flash": "qwen3-flash",
    "qwen-max": "qwen3-max",
    "qwen3-max": "qwen3-max",
    # Deepseek 系列
    "deepseek": "deepseek-v4-flash",
    "deepseek-flash": "deepseek-v4-flash",
    "deepseek-v4": "deepseek-v4-flash",
    "deepseek-v4-flash": "deepseek-v4-flash",
    "deepseek-v3": "ali-deepseek",
    "deepseek-v3.2": "ali-deepseek",
    "deepseek-v3.2-exp": "ali-deepseek",
    "ali-deepseek": "ali-deepseek",
    # 直接映射（保持兼容）
    "openai": "openai",
    "moonshot": "moonshot",
    "anthropic": "anthropic",
    # Openrouter 系列 - gpt 别名指向 gpt5.2-pro
    "gpt": "openrouter-gpt5.2-pro",
    "gpt5": "openrouter-gpt5.2-pro",
    "gpt5.2": "openrouter-gpt5.2-pro",
    "gpt-5.2": "openrouter-gpt5.2-pro",
    "gpt5.2-pro": "openrouter-gpt5.2-pro",
    "gpt-5.2-pro": "openrouter-gpt5.2-pro",
    "openrouter-gpt5.2-pro": "openrouter-gpt5.2-pro",
    "gpt5.5": "openrouter-gpt5.5",
    "gpt-5.5": "openrouter-gpt5.5",
    "openrouter-gpt5.5": "openrouter-gpt5.5",
    "opus": "openrouter-claude-opus-4.8",
    "opus-4.8": "openrouter-claude-opus-4.8",
    "claude-opus-4.8": "openrouter-claude-opus-4.8",
    "openrouter-claude-opus-4.8": "openrouter-claude-opus-4.8",
    "gemini-3-pro": "openrouter-gemini-3-pro",
    "gemini3-pro": "openrouter-gemini-3-pro",
    "gemini-3": "openrouter-gemini-3-pro",
    "openrouter-gemini-3-pro": "openrouter-gemini-3-pro",
}


def resolve_model_alias(model_name: str) -> str:
    """
    解析模型别名，返回 config.yaml 中对应的 key
    如果没有匹配的别名，返回原始名称
    """
    resolved = MODEL_ALIAS_MAP.get(model_name, model_name)
    if resolved != model_name:
        logger.debug(f"模型别名映射: {model_name} -> {resolved}")
    return resolved


class LLMProvider:
    """LLM provider for different model services"""

    def __init__(self):
        self.clients = {}
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize LLM clients for different providers"""
        for model_name in config.list_available_models():
            if config.is_model_available(model_name):
                model_config = config.get_model_config(model_name)
                api_key = config.get_api_key(model_name)

                try:
                    # OpenRouter 模型需要更长的超时时间
                    is_openrouter = model_name.startswith('openrouter-')
                    timeout_seconds = 300 if is_openrouter else 120
                    
                    #  默认使用 OpenAI 兼容的接口
                    client = ChatOpenAI(
                        model=model_config.name,
                        openai_api_key=api_key,
                        openai_api_base=model_config.base_url,
                        max_tokens=model_config.max_tokens,
                        temperature=model_config.temperature,
                        top_p=model_config.top_p,
                        stream_usage=True,
                        seed=42,
                        max_retries=(
                            model_config.max_retries
                            if hasattr(model_config, 'max_retries')
                            else 3
                        ),
                        frequency_penalty=model_config.frequency_penalty,
                        presence_penalty=model_config.presence_penalty,
                        timeout=timeout_seconds,  # 设置超时时间
                    )
                    self.clients[model_name] = client
                    if is_openrouter:
                        logger.info(f"🌐 Initialized {model_name} client with {timeout_seconds}s timeout")
                    else:
                        logger.info(f"Initialized {model_name} client successfully")

                except Exception as e:
                    logger.error(f"Failed to initialize {model_name} client: {e}")

    def get_client(self, model_name: str):
        """Get LLM client for a specific model
        
        支持模型别名映射，前端可以传入友好名称（如 qwen、deepseek），
        会自动映射到 config.yaml 中的 key
        """
        # 应用别名映射
        resolved_name = resolve_model_alias(model_name)
        client = self.clients.get(resolved_name)
        
        if client and resolved_name != model_name:
            logger.info(f"🔄 模型别名映射: '{model_name}' -> '{resolved_name}'")
        
        return client

    def is_available(self, model_name: str) -> bool:
        """Check if model is available (支持别名)"""
        resolved_name = resolve_model_alias(model_name)
        return resolved_name in self.clients


class LangGraphManager:
    """Manager for multiple LangGraph applications with registry-based graph creation"""

    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider
        self.graphs: Dict[str, BaseLangGraph] = {}
        self._initialize_graphs()

    def _initialize_graphs(self):
        """Initialize all enabled LangGraph applications using registry"""
        enabled_apps = config.list_enabled_langgraph_apps()

        logger.info(f"Available graph types: {GraphRegistry.list_available_types()}")

        for app_id, app_config in enabled_apps.items():
            try:
                # Create graph using registry
                graph = GraphRegistry.create_graph(
                    app_config.graph_type, app_config, self.llm_provider
                )

                if graph is None:
                    logger.error(
                        f"Failed to create graph for app {app_id}: Unknown graph type '{app_config.graph_type}'"
                    )
                    continue

                self.graphs[app_id] = graph
                logger.info(
                    f"Successfully initialized LangGraph app: {app_id} ({app_config.name}) with type '{app_config.graph_type}'"
                )

            except Exception as e:
                logger.error(f"Failed to initialize LangGraph app {app_id}: {e}")

        graph_names = [
            f"{app_id}({graph.app_config.name})"
            for app_id, graph in self.graphs.items()
        ]
        logger.info(
            f"Initialized {len(self.graphs)} LangGraph applications: {', '.join(graph_names)}"
        )

    def get_graph_by_api_key(self, api_key: str) -> Optional[Tuple[str, BaseLangGraph]]:
        """Get graph by API key"""
        result = config.get_langgraph_app_by_api_key(api_key)
        if result:
            app_id, app_config = result
            graph = self.graphs.get(app_id)
            if graph:
                return app_id, graph
        return None

    def get_graph(self, app_id: str) -> Optional[BaseLangGraph]:
        """Get graph by app ID"""
        return self.graphs.get(app_id)

    def list_available_graphs(self) -> Dict[str, str]:
        """List available graphs with their names"""
        return {app_id: graph.app_config.name for app_id, graph in self.graphs.items()}

    def authenticate_request(
        self, api_key: str
    ) -> Optional[Tuple[str, LangGraphAppConfig]]:
        """Authenticate API key and return app info"""
        return config.get_langgraph_app_by_api_key(api_key)

    def reload_graphs(self):
        """Reload all graphs (useful for configuration changes)"""
        logger.info("Reloading all LangGraph applications...")
        self.graphs.clear()
        self._initialize_graphs()

    def reload_graph(self, app_id: str, knowledge_base_path: str = None) -> bool:
        """
        重新加载指定的 Graph（支持热更新）

        Args:
            app_id: 应用 ID
            knowledge_base_path: 动态指定文档路径（可选）

        Returns:
            是否成功重新加载
        """
        try:
            enabled_apps = config.list_enabled_langgraph_apps()
            app_config = enabled_apps.get(app_id)

            if not app_config:
                logger.error(f"App {app_id} not found in configuration")
                return False

            logger.info(f"🔄 Reloading graph for app: {app_id}")

            # 重新创建 Graph（支持动态路径覆盖）
            graph = GraphRegistry.create_graph(
                app_config.graph_type,
                app_config,
                self.llm_provider,
                knowledge_base_path=knowledge_base_path,
            )

            if graph is None:
                logger.error(f"Failed to create graph for app {app_id}")
                return False

            # 替换旧的 Graph 实例
            self.graphs[app_id] = graph

            logger.info(f"✅ Successfully reloaded graph for app: {app_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to reload graph {app_id}: {e}", exc_info=True)
            return False

    def get_graph_info(self) -> Dict[str, Dict[str, Any]]:
        """Get detailed information about all loaded graphs"""
        info = {}
        for app_id, graph in self.graphs.items():
            info[app_id] = {
                "name": graph.app_config.name,
                "description": graph.app_config.description,
                "graph_type": graph.app_config.graph_type,
                "model_provider": graph.app_config.model_provider,
                "enabled": graph.app_config.enabled,
                "state_class": graph.get_state_class().__name__,
            }
        return info


# Global instances
llm_provider = LLMProvider()
langgraph_manager = LangGraphManager(llm_provider)
