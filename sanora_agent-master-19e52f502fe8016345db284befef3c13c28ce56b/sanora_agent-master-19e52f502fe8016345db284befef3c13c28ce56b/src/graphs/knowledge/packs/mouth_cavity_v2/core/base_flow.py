"""
BaseFlow - 决策流程抽象基类

所有决策流程（如出血、感染、疼痛）都应继承此基类。
使用策略模式，每个 Flow 定义自己的槽位、风险评估和护理方案。
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .slot_definition import SlotDefinition
from src.models import RiskLevel


class BaseFlow(ABC):
    """
    决策流程抽象基类

    所有具体流程（BleedingFlow, InfectionFlow 等）必须实现此接口。
    """

    @property
    @abstractmethod
    def flow_id(self) -> str:
        """
        流程唯一标识

        Returns:
            str: 流程 ID，如 "bleeding", "infection"
        """
        pass

    @property
    @abstractmethod
    def flow_name(self) -> str:
        """
        流程显示名称

        Returns:
            str: 流程名称，如 "术后出血", "术后感染"
        """
        pass

    @property
    @abstractmethod
    def trigger_keywords(self) -> List[str]:
        """
        触发该流程的关键词列表

        用于 Manager 判断是否激活该流程。

        Returns:
            List[str]: 关键词列表
        """
        pass

    @property
    @abstractmethod
    def slots(self) -> List[SlotDefinition]:
        """
        该流程需要收集的槽位定义列表

        Returns:
            List[SlotDefinition]: 槽位定义列表
        """
        pass

    @abstractmethod
    def assess_risk(self, slots: Dict[str, Any]) -> Tuple[RiskLevel, str]:
        """
        风险评估

        根据已收集的槽位进行风险评估。

        Args:
            slots: 已收集的槽位值，格式 {slot_name: SlotValue.to_dict()}

        Returns:
            Tuple[RiskLevel, str]: (风险等级, 护理方案 ID)
        """
        pass

    @abstractmethod
    def get_care_plan(self, care_plan_id: str, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取护理方案

        Args:
            care_plan_id: 护理方案 ID
            slots: 已收集的槽位值

        Returns:
            Dict: 护理方案内容
        """
        pass

    def get_next_slot(self, current_slots: Dict[str, Any]) -> Optional[SlotDefinition]:
        """
        获取下一个需要收集的槽位

        Args:
            current_slots: 当前已收集的槽位值

        Returns:
            Optional[SlotDefinition]: 下一个槽位，或 None 表示收集完成
        """
        # 按 order 排序
        sorted_slots = sorted(self.slots, key=lambda s: s.order)

        for slot in sorted_slots:
            if slot.should_ask(current_slots):
                return slot

        return None

    def get_ask_slot_prompt_path(self) -> Optional[Path]:
        """
        返回该 Flow 专用的 ask_slot prompt 路径

        默认返回 None，使用通用的 prompts/ask_slot.md。
        子类可覆盖此方法提供定制化 prompt。

        Returns:
            Optional[Path]: prompt 文件路径，或 None 使用默认
        """
        return None

    def get_rag_query_prompt_path(self) -> Optional[Path]:
        """
        返回该 Flow 专用的 RAG 查询 prompt 路径

        Returns:
            Optional[Path]: prompt 文件路径，或 None 使用默认
        """
        return None

    def get_care_plan_prompt_path(self) -> Optional[Path]:
        """
        返回该 Flow 专用的护理方案 prompt 路径

        Returns:
            Optional[Path]: prompt 文件路径，或 None 使用默认
        """
        return None

    def get_knowledge_base_path(self) -> Path:
        """
        获取该流程的知识库路径

        默认实现返回当前模块的 knowledge_base 目录。
        子类可覆盖此方法。

        Returns:
            Path: 知识库目录路径
        """
        return Path(__file__).parent.parent / "knowledge_base"

    def is_all_slots_collected(self, current_slots: Dict[str, Any]) -> bool:
        """
        判断是否所有必需槽位都已收集

        Args:
            current_slots: 当前已收集的槽位值

        Returns:
            bool: 是否收集完成
        """
        for slot in self.slots:
            if slot.required and slot.should_ask(current_slots):
                return False
        return True

    def get_slots_summary(self, current_slots: Dict[str, Any]) -> str:
        """
        生成已收集槽位的摘要（用于 Prompt）

        Args:
            current_slots: 当前已收集的槽位值

        Returns:
            str: 槽位摘要文本
        """
        lines = []
        for slot in self.slots:
            slot_data = current_slots.get(slot.name, {})
            value = slot_data.get("value", "未收集")
            raw = slot_data.get("raw", "")
            if value != "未收集":
                lines.append(f"- {slot.description}: {value}" + (f" (原始: {raw})" if raw else ""))
            else:
                lines.append(f"- {slot.description}: 未收集")
        return "\n".join(lines)
