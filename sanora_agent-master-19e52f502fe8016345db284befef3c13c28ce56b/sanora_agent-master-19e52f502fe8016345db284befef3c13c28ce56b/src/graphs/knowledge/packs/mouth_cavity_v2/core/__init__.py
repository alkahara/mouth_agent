"""
口腔分诊 V2 - 核心框架层

提供 Manager-Operator 架构的基础组件。
"""

from .base_flow import BaseFlow
from .base_operator import BaseOperator, OperatorResult
from .flow_registry import FlowRegistry
from .invariants import AgentInvariants, EmergencyAction
from .slot_definition import SlotDefinition, SlotValue
from .state import MouthCavityV2State, create_initial_state, merge_slots
from .slot_parsers import normalize_all_slots, normalize_slot_value
from .decision_tree import decide_next_step

__all__ = [
    # 数据类
    "SlotDefinition",
    "SlotValue",
    # 抽象基类
    "BaseFlow",
    "BaseOperator",
    "OperatorResult",
    # 注册表
    "FlowRegistry",
    # Agent 宪法
    "AgentInvariants",
    "EmergencyAction",
    # 状态
    "MouthCavityV2State",
    "create_initial_state",
    "merge_slots",
    # 槽位解析器
    "normalize_all_slots",
    "normalize_slot_value",
]

