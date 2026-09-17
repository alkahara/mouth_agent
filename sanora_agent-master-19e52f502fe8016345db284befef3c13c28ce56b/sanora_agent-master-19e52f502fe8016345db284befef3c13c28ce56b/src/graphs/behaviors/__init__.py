from __future__ import annotations

from typing import Dict

from .base import GraphBehavior, DefaultGraphBehavior
from .mouth_cavity_v2_behavior import MouthCavityV2Behavior


class GraphBehaviorRegistry:
    """Registry mapping graph_type to behavior implementations."""

    _registry: Dict[str, GraphBehavior] = {
        "mouth_cavity_v2_knowledge": MouthCavityV2Behavior(),
    }
    _default_behavior: GraphBehavior = DefaultGraphBehavior()

    @classmethod
    def get_behavior(cls, graph_type: str) -> GraphBehavior:
        return cls._registry.get(graph_type, cls._default_behavior)


__all__ = ["GraphBehaviorRegistry", "GraphBehavior"]
