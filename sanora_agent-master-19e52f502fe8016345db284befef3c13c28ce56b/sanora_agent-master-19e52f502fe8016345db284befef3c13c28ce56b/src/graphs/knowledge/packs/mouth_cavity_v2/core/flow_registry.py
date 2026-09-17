"""
FlowRegistry - 流程注册表

使用工厂模式管理所有决策流程的注册和查找。
"""

from typing import Dict, List, Optional, Type

from .base_flow import BaseFlow


class FlowRegistry:
    """
    流程注册表

    管理所有决策流程的注册、查找和实例化。
    使用装饰器模式进行流程注册。
    """

    _flows: Dict[str, Type[BaseFlow]] = {}
    _instances: Dict[str, BaseFlow] = {}  # 缓存流程实例

    @classmethod
    def register(cls, flow_id: str):
        """
        装饰器：注册流程

        使用方式:
            @FlowRegistry.register("bleeding")
            class BleedingFlow(BaseFlow):
                ...

        Args:
            flow_id: 流程唯一标识
        """
        def decorator(flow_class: Type[BaseFlow]):
            if not issubclass(flow_class, BaseFlow):
                raise TypeError(f"{flow_class.__name__} must inherit from BaseFlow")
            cls._flows[flow_id] = flow_class
            return flow_class
        return decorator

    @classmethod
    def get(cls, flow_id: str) -> BaseFlow:
        """
        获取流程实例

        Args:
            flow_id: 流程 ID

        Returns:
            BaseFlow: 流程实例

        Raises:
            ValueError: 未知的流程 ID
        """
        if flow_id not in cls._flows:
            available = ", ".join(cls._flows.keys()) or "无"
            raise ValueError(f"Unknown flow: {flow_id}. Available flows: {available}")

        # 使用缓存的实例
        if flow_id not in cls._instances:
            cls._instances[flow_id] = cls._flows[flow_id]()

        return cls._instances[flow_id]

    @classmethod
    def get_or_none(cls, flow_id: str) -> Optional[BaseFlow]:
        """
        获取流程实例，不存在返回 None

        Args:
            flow_id: 流程 ID

        Returns:
            Optional[BaseFlow]: 流程实例或 None
        """
        try:
            return cls.get(flow_id)
        except ValueError:
            return None

    @classmethod
    def list_flows(cls) -> List[str]:
        """
        列出所有已注册的流程 ID

        Returns:
            List[str]: 流程 ID 列表
        """
        return list(cls._flows.keys())

    @classmethod
    def list_flow_info(cls) -> List[Dict[str, str]]:
        """
        列出所有已注册流程的信息

        Returns:
            List[Dict]: 流程信息列表
        """
        result = []
        for flow_id in cls._flows:
            flow = cls.get(flow_id)
            result.append({
                "flow_id": flow_id,
                "flow_name": flow.flow_name,
                "trigger_keywords": flow.trigger_keywords,
            })
        return result

    @classmethod
    def identify_flow(cls, user_message: str) -> Optional[str]:
        """
        根据用户消息识别匹配的流程

        使用关键词匹配进行初步识别。
        如果多个流程匹配，返回第一个匹配的（后续可改为 LLM 决策）。

        Args:
            user_message: 用户消息

        Returns:
            Optional[str]: 匹配的流程 ID，或 None
        """
        for flow_id in cls._flows:
            flow = cls.get(flow_id)
            for keyword in flow.trigger_keywords:
                if keyword in user_message:
                    return flow_id
        return None

    @classmethod
    def clear(cls):
        """
        清空注册表（主要用于测试）
        """
        cls._flows.clear()
        cls._instances.clear()

    @classmethod
    def is_registered(cls, flow_id: str) -> bool:
        """
        检查流程是否已注册

        Args:
            flow_id: 流程 ID

        Returns:
            bool: 是否已注册
        """
        return flow_id in cls._flows
