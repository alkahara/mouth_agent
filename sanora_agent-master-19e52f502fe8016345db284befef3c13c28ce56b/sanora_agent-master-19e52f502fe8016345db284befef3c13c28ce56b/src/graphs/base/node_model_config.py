"""
节点模型配置管理
"""

from typing import Dict, Optional, Any
from dataclasses import dataclass
import os
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class NodeModelConfig:
    """单个节点的模型配置"""

    model_provider: str  # 使用model_provider而不是model_name，与现有架构一致
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None


class NodeModelManager:
    """节点模型配置管理器"""

    def __init__(self, graph_type: str, graph_dir: Optional[str] = None):
        """
        初始化节点模型管理器

        Args:
            graph_type: 图类型标识
            graph_dir: 图实现类所在目录（用于定位config/nodes.json）
                      如果不提供，会使用旧的全局configs目录（兼容性）
        """
        self.graph_type = graph_type
        self.graph_dir = graph_dir
        self.config_file = self._get_config_file_path()
        self.node_configs = self._load_config()
        self.default_config = None

    def _get_config_file_path(self) -> str:
        """获取配置文件路径

        优先级：
        1. 图内部的 config/nodes.json
        2. 全局 configs/{graph_type}_nodes.json（兼容旧架构）
        """
        # 如果提供了图目录，使用图内部的 config/nodes.json
        if self.graph_dir:
            internal_config = os.path.join(self.graph_dir, "config", "nodes.json")
            if os.path.exists(internal_config):
                logger.debug(f"Using internal config: {internal_config}")
                return internal_config
            else:
                logger.debug(f"Internal config not found: {internal_config}")

        # 回退到全局配置目录（兼容性）
        global_config_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "configs"
        )
        global_config = os.path.join(global_config_dir, f"{self.graph_type}_nodes.json")
        logger.debug(f"Using global config: {global_config}")
        return global_config

    def _load_config(self) -> Dict[str, NodeModelConfig]:
        """从配置文件加载节点模型配置"""
        configs = {}

        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 加载默认配置
                if "default" in data:
                    default_data = data["default"]
                    self.default_config = NodeModelConfig(**default_data)

                # 加载各节点配置
                if "nodes" in data:
                    for node_name, node_data in data["nodes"].items():
                        configs[node_name] = NodeModelConfig(**node_data)

                logger.debug(
                    f"Loaded node model config for {self.graph_type}: {len(configs)} nodes configured"
                )
            else:
                logger.debug(
                    f"No node model config found for {self.graph_type} at {self.config_file}"
                )

        except Exception as e:
            logger.warning(
                f"Failed to load node model config for {self.graph_type}: {e}"
            )

        return configs

    def get_node_config(
        self, node_name: str, fallback_provider: str = None
    ) -> NodeModelConfig:
        """获取指定节点的模型配置"""
        # 优先使用节点专属配置
        if node_name in self.node_configs:
            return self.node_configs[node_name]

        # 其次使用默认配置
        if self.default_config:
            return self.default_config

        # 最后使用fallback
        return NodeModelConfig(
            model_provider=fallback_provider or "qwen3-flash", temperature=0.7
        )

    def get_model_provider(self, node_name: str, fallback_provider: str = None) -> str:
        """获取指定节点的模型提供者名称"""
        config = self.get_node_config(node_name, fallback_provider)
        return config.model_provider

    def get_model_params(self, node_name: str) -> Dict[str, Any]:
        """获取指定节点的模型参数"""
        config = self.get_node_config(node_name)
        params = {}

        if config.temperature is not None:
            params["temperature"] = config.temperature
        if config.max_tokens is not None:
            params["max_tokens"] = config.max_tokens
        if config.top_p is not None:
            params["top_p"] = config.top_p

        return params

    def has_node_config(self, node_name: str) -> bool:
        """检查是否存在指定节点的配置"""
        return node_name in self.node_configs or self.default_config is not None
