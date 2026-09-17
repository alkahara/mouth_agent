"""
Graph registry for dynamic graph type management
"""

from typing import Dict, Type, Optional
from .base import BaseLangGraph
import logging

logger = logging.getLogger(__name__)


class GraphRegistry:
    """Registry for managing different graph types"""
    
    _registry: Dict[str, Type[BaseLangGraph]] = {}
    
    @classmethod
    def register(cls, graph_class: Type[BaseLangGraph]) -> Type[BaseLangGraph]:
        """Register a graph class"""
        if not hasattr(graph_class, 'GRAPH_TYPE') or graph_class.GRAPH_TYPE is None:
            raise ValueError(f"Graph class {graph_class.__name__} must define GRAPH_TYPE")
        
        graph_type = graph_class.GRAPH_TYPE
        if not graph_type or not graph_type.strip():
            raise ValueError(f"Graph class {graph_class.__name__} has empty GRAPH_TYPE")
        
        if graph_type in cls._registry:
            logger.warning(f"Graph type '{graph_type}' already registered, overwriting")
        
        cls._registry[graph_type] = graph_class
        logger.info(f"Registered graph type: {graph_type} -> {graph_class.__name__}")
        return graph_class
    
    @classmethod
    def get_graph_class(cls, graph_type: str) -> Optional[Type[BaseLangGraph]]:
        """Get graph class by type"""
        return cls._registry.get(graph_type)
    
    @classmethod
    def list_available_types(cls) -> Dict[str, str]:
        """List all available graph types"""
        return {
            graph_type: graph_class.__name__ 
            for graph_type, graph_class in cls._registry.items()
        }
    
    @classmethod
    def create_graph(cls, graph_type: str, app_config, llm_provider, **kwargs) -> Optional[BaseLangGraph]:
        """Create graph instance by type

        Args:
            graph_type: Graph 类型标识
            app_config: 应用配置
            llm_provider: LLM 提供者
            **kwargs: 额外参数（如 knowledge_base_path）传递给 Graph 构造函数
        """
        graph_class = cls.get_graph_class(graph_type)
        if graph_class is None:
            logger.error(f"Unknown graph type: {graph_type}")
            return None

        try:
            return graph_class(app_config, llm_provider, **kwargs)
        except Exception as e:
            logger.error(f"Failed to create graph of type {graph_type}: {e}")
            return None


# Decorator for easy registration
def register_graph(graph_class: Type[BaseLangGraph]) -> Type[BaseLangGraph]:
    """Decorator to register a graph class"""
    return GraphRegistry.register(graph_class)
